#!/usr/bin/env python3
"""Apply or verify scoped high-authority static text corrections."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "magica/i18n_audit/release_v26_authority/pass19_official_static_corrections.tsv"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    required = {
        "change_id", "file", "locator", "before", "after", "source_tier",
        "source_locator", "source_sha256", "match_method", "machine_translated",
        "confidence", "review_status", "evidence",
        "expected_count", "expected_after_count",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError("invalid official static correction manifest")
    if len({row["change_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate change_id")
    return rows


def run(root: Path, manifest: Path, apply: bool) -> dict[str, object]:
    rows = load_rows(manifest)
    changed = 0
    states: dict[str, int] = {"before": 0, "already_after": 0}
    files: list[dict[str, object]] = []
    for row in rows:
        evidence_contracts = {
            "official_cn_dump": {
                "match_methods": {"exact-path-dom-match", "exact-path-term-match"},
                "review_status": "official-source-verified",
            },
            "wiki": {
                "match_methods": {"exact-wiki-term-with-official-same-path-absence"},
                "review_status": "wiki-source-verified",
            },
        }
        contract = evidence_contracts.get(row["source_tier"])
        if (
            contract is None
            or row["machine_translated"] != "false"
            or row["match_method"] not in contract["match_methods"]
            or row["review_status"] != contract["review_status"]
            or len(row["source_sha256"]) != 64
        ):
            raise ValueError(f"{row['change_id']}: authority evidence contract failed")
        path = root / row["file"]
        raw_before = path.read_bytes()
        if raw_before.startswith(b"\xef\xbb\xbf") or b"\r\n" in raw_before:
            raise ValueError(f"{row['change_id']}: product file is not UTF-8/LF without BOM")
        text = raw_before.decode("utf-8")
        before_count = text.count(row["before"])
        after_count = text.count(row["after"])
        expected_count_text = row.get("expected_count", "1")
        try:
            expected_count = int(expected_count_text)
            expected_after_count = int(row["expected_after_count"])
        except ValueError as exc:
            raise ValueError(f"{row['change_id']}: invalid expected count") from exc
        if expected_count < 1 or expected_after_count < expected_count:
            raise ValueError(f"{row['change_id']}: invalid expected count")
        if before_count == expected_count and after_count == expected_after_count - expected_count:
            states["before"] += 1
            if apply:
                text = text.replace(row["before"], row["after"])
                path.write_text(text, encoding="utf-8", newline="\n")
                changed += expected_count
        elif before_count == 0 and after_count == expected_after_count:
            states["already_after"] += 1
        else:
            raise ValueError(
                f"{row['change_id']}: literal preimage drift "
                f"before={before_count} after={after_count}"
            )
        files.append({
            "change_id": row["change_id"], "file": row["file"],
            "before_sha256": hashlib.sha256(raw_before).hexdigest(),
            "after_sha256": sha256_file(path),
        })
    if not apply and states["before"]:
        raise ValueError(f"verification found {states['before']} unapplied rows")
    return {
        "schema": "magireco-cn-v26-authority-static-corrections/v2",
        "mode": "apply" if apply else "verify", "status": "PASS",
        "manifest_sha256": sha256_file(manifest), "rows": len(rows),
        "changed": changed, "states": states, "files": files,
        "product_fields_changed": changed, "protected_lower_tier_overwrites": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        report = run(args.root.resolve(), args.manifest.resolve(), args.apply)
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
