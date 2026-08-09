#!/usr/bin/env python3
"""End-to-end verification for the v26 JS/WebView + engine TSV release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "magica" / "i18n_audit" / "release_v26_authority"
EXCLUDED = ("magica/research/", "magica/i18n_audit/")
ENGINE = "madomagi/engine_i18n.tsv"


def product_files(suffix: str):
    return sorted(
        path for path in (ROOT / "magica").rglob(f"*{suffix}")
        if not path.relative_to(ROOT).as_posix().startswith(EXCLUDED)
    )


def run_json(command):
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(map(str, command))}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return json.loads(result.stdout)


def verify_engine(path: Path):
    raw = path.read_bytes()
    assert raw and not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw, "engine_i18n.tsv must use LF"
    text = raw.decode("utf-8")
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        assert "\t" in line, f"engine_i18n.tsv:{number}: missing TAB"
        source, target = line.split("\t", 1)
        assert source, f"engine_i18n.tsv:{number}: empty source"
        rows.append((source, target))
    assert len(rows) == 298, len(rows)
    assert len({source for source, _ in rows}) == len(rows), "duplicate engine source"
    return {"rows": len(rows), "empty_targets": sum(not target for _, target in rows),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def verify_zip(path: Path):
    expected = {}
    for file in (ROOT / "magica").rglob("*"):
        if not file.is_file():
            continue
        name = file.relative_to(ROOT).as_posix()
        if name.startswith(EXCLUDED):
            continue
        expected[name] = file.read_bytes()
    expected[ENGINE] = (ROOT / ENGINE).read_bytes()

    with zipfile.ZipFile(path) as archive:
        infos = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in infos]
        assert len(names) == len(set(names)), "duplicate ZIP paths"
        assert set(names) == set(expected), (
            sorted(set(expected) - set(names))[:10],
            sorted(set(names) - set(expected))[:10],
        )
        assert archive.testzip() is None, "ZIP CRC failure"
        mismatches = [name for name in names if archive.read(name) != expected[name]]
        assert not mismatches, f"ZIP bytes differ from product tree: {mismatches[:10]}"
    raw = path.read_bytes()
    return {
        "path": str(path.resolve()), "file_entries": len(names),
        "duplicate_paths": 0, "crc_errors": 0, "byte_mismatches": 0,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "engine_entries": names.count(ENGINE),
        "scenario_entries": sum(name.startswith("madomagi/resource/scenario/") for name in names),
        "audit_entries": sum(name.startswith(EXCLUDED) for name in names),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    runtime = run_json([sys.executable, str(ROOT / "tools/verify-runtime-layer.py")])
    authority = run_json([
        sys.executable, str(ROOT / "tools/i18n-authority-guard.py"), "--json"
    ])
    assert runtime["status"] == "PASS" and authority["ok"] is True

    js_files = product_files(".js")
    js_failures = []
    for path in js_files:
        result = subprocess.run(
            ["node", "--check", str(path)], capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )
        if result.returncode:
            js_failures.append({"path": path.relative_to(ROOT).as_posix(),
                                "stderr": result.stderr})
    assert not js_failures, js_failures[:3]

    html_files = product_files(".html")
    css_files = product_files(".css")
    json_files = sorted((ROOT / "magica/js/libs").glob("*.json"))
    assert (len(js_files), len(html_files), len(css_files), len(json_files)) == (198, 182, 19, 23)

    ui = json.loads((AUDIT / "ui_union_validation.json").read_text(encoding="utf-8"))
    assert ui["status"] == "PASS"
    assert ui["checks"]["main_only_12"]["matched"] == 12
    assert ui["checks"]["pass_only_14"]["matched"] == 14
    assert ui["checks"]["specified_gacha_3"]["matched"] == 3
    assert ui["checks"]["node_syntax"]["failures"] == []
    assert ui["checks"]["html_sensitive_attributes"]["status"] == "PASS"

    remaining = ROOT / "magica/i18n_audit/manual_cn_pass16/untranslated_remaining.tsv"
    with remaining.open(encoding="utf-8-sig", newline="") as handle:
        remaining_rows = list(csv.DictReader(handle, delimiter="\t"))
    assert not remaining_rows, "visible untranslated backlog is not empty"

    checklist_summary = json.loads(
        (AUDIT / "manual_review_checklist.summary.json").read_text(encoding="utf-8")
    )
    assert checklist_summary["total_rows"] == 1183
    engine = verify_engine(ROOT / ENGINE)

    report = {
        "schema": "magireco-cn-v26-product-verification/v1",
        "status": "PASS",
        "counts": {
            "product_js": len(js_files), "js_syntax_failures": len(js_failures),
            "product_html": len(html_files), "product_css": len(css_files),
            "runtime_json_dictionaries": len(json_files),
            "visible_untranslated_backlog": len(remaining_rows),
            "manual_review_rows": checklist_summary["total_rows"],
        },
        "runtime_layer": runtime,
        "authority_guard": authority,
        "ui_union": {
            "status": ui["status"], "main_only": "12/12", "pass_only": "14/14",
            "specified_gacha": "3/3", "sensitive_attribute_drift": 0,
        },
        "engine_i18n": engine,
    }
    if args.zip:
        report["zip"] = verify_zip(args.zip)

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
