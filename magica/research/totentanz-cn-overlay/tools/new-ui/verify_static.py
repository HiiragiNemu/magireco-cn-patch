from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from localization_lib import (
    apply_replacements,
    count_slots,
    encode_utf8_exact,
    protected_tokens,
    read_utf8_exact,
    slot_values,
)


HERE = Path(__file__).resolve().parent


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_rows() -> list[dict[str, str]]:
    with (HERE / "translations.tsv").open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("baseline", "modified", "syntax"), required=True)
    args = parser.parse_args()

    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    rows = load_rows()
    source_root = Path(manifest["source_root"])
    baseline_root = HERE / "baseline"
    overlay_root = HERE / "overlay"
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["path"], row["kind"])].append(row)

    if args.phase == "syntax":
        kana = re.compile(r"[\u3040-\u30ff]")
        residuals: list[tuple[str, str]] = []
        js_files: list[Path] = []
        for file_info in manifest["files"]:
            rel = file_info["path"]
            kind = file_info["kind"]
            overlay_path = overlay_root / rel
            text, _ = read_utf8_exact(overlay_path)
            residuals.extend((rel, value) for value in slot_values(text, kind) if kana.search(value))
            if overlay_path.suffix.lower() == ".js":
                js_files.append(overlay_path)
        if residuals:
            raise AssertionError(f"kana remains in localized UI slots: {residuals[:5]!r}")
        node = shutil.which("node")
        if not node:
            raise RuntimeError("node was not found for JavaScript syntax checks")
        for path in js_files:
            run = subprocess.run([node, "--check", str(path)], text=True, capture_output=True)
            if run.returncode != 0:
                raise AssertionError(f"JavaScript syntax check failed: {path}: {run.stderr}")
        print(
            "SYNTAX_UI_OK "
            f"js={len(js_files)}/{len(js_files)} kana_ui_slot_residuals=0 "
            f"checked_files={len(manifest['files'])}"
        )
        return 0

    if args.phase == "baseline":
        occurrence_total = 0
        for file_info in manifest["files"]:
            rel = file_info["path"]
            live = (source_root / rel).read_bytes()
            snapshot = (baseline_root / rel).read_bytes()
            expected_hash = file_info["baseline_sha256"]
            if sha256_bytes(live) != expected_hash or sha256_bytes(snapshot) != expected_hash:
                raise AssertionError(f"baseline hash drift: {rel}")
            kind = file_info["kind"]
            text, _ = read_utf8_exact(source_root / rel)
            counts = count_slots(text, kind)
            for row in grouped[(rel, kind)]:
                actual = counts[row["source_text"]]
                expected = int(row["source_occurrences"])
                if actual != expected or actual <= 0:
                    raise AssertionError(
                        f"baseline occurrence mismatch: {rel}: {row['source_text']!r}: {actual} != {expected}"
                    )
                occurrence_total += actual
        print(
            "BASELINE_OK "
            f"files={len(manifest['files'])} records={len(rows)} "
            f"production={manifest['counts']['production_records']} "
            f"test={manifest['counts']['test_records']} "
            f"occurrences={occurrence_total} sha256_match={len(manifest['files'])}/{len(manifest['files'])}"
        )
        return 0

    guard_total = 0
    removed_total = 0
    removable_total = 0
    reconstructed_total = 0
    overlay_occurrences = 0
    for file_info in manifest["files"]:
        rel = file_info["path"]
        kind = file_info["kind"]
        overlay_bytes = (overlay_root / rel).read_bytes()
        if sha256_bytes(overlay_bytes) != file_info["overlay_sha256"]:
            raise AssertionError(f"overlay hash drift: {rel}")

        source_text, has_bom = read_utf8_exact(source_root / rel)
        mapping = {row["source_text"]: row["cn_text"] for row in grouped[(rel, kind)]}
        reconstructed, hits = apply_replacements(source_text, kind, mapping)
        expected_bytes = encode_utf8_exact(reconstructed, has_bom)
        if expected_bytes != overlay_bytes:
            raise AssertionError(f"overlay is not an exact slot-only reconstruction: {rel}")
        reconstructed_total += 1

        overlay_text, _ = read_utf8_exact(overlay_root / rel)
        after_counts = count_slots(overlay_text, kind)
        for row in grouped[(rel, kind)]:
            source = row["source_text"]
            target = row["cn_text"]
            expected_hits = int(row["source_occurrences"])
            if hits[source] != expected_hits:
                raise AssertionError(f"reconstruction hit mismatch: {rel}: {source!r}")
            if protected_tokens(source) != protected_tokens(target):
                raise AssertionError(f"numeric/markup/identifier guard mismatch: {rel}: {source!r}")
            guard_total += 1
            if source != target:
                removable_total += expected_hits
                if after_counts[source] != 0:
                    raise AssertionError(f"source UI slot remains: {rel}: {source!r}")
                removed_total += expected_hits
            if after_counts[target] <= 0:
                raise AssertionError(f"translated UI slot missing: {rel}: {target!r}")
            overlay_occurrences += expected_hits

    print(
        "MODIFIED_OK "
        f"files={len(manifest['files'])} records={len(rows)} occurrences={overlay_occurrences} "
        f"removed_source_slots={removed_total}/{removable_total} "
        f"structural_exact={reconstructed_total}/{len(manifest['files'])} "
        f"numeric_markup_guards={guard_total}/{len(rows)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VERIFY_ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
