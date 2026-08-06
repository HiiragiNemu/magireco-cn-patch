from __future__ import annotations

import json
import subprocess
from pathlib import Path

from analyze_css import parse_rules


HERE = Path(__file__).resolve().parent
ROOT = HERE / "extracted" / "totentanz-frontend" / "totentanz-frontend"


def main() -> int:
    failures = []
    js_files = sorted(ROOT.rglob("*.js"))
    for p in js_files:
        cp = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True)
        if cp.returncode:
            failures.append({"check": "node_syntax", "path": p.relative_to(ROOT).as_posix(), "stderr": cp.stderr})
    css_files = sorted(ROOT.rglob("*.css"))
    css_rule_count = 0
    for p in css_files:
        try:
            css_rule_count += len(parse_rules(p.read_text(encoding="utf-8-sig", errors="strict")))
        except Exception as exc:
            failures.append({"check": "css_parse", "path": p.relative_to(ROOT).as_posix(), "error": str(exc)})
    expected_core_missing = {
        "css/_common/sanitize.css", "css/_common/common.css", "css/_common/base.css",
        "css/_common/fonts.css", "js/system/replacement.js", "js/libs/jquery-3.7.1.min.js",
        "js/libs/require.js", "js/_common/base.js",
    }
    dependency = json.loads((HERE / "dependency_audit.json").read_text(encoding="utf-8"))
    index_missing = {
        r["resolved_path"] for r in dependency["references"]
        if r["source_file"] == "index.html" and r["availability"] in {"old_only", "absent_both"}
    }
    if index_missing != expected_core_missing:
        failures.append({
            "check": "layer_boundary",
            "expected_core_missing": sorted(expected_core_missing),
            "actual_core_missing": sorted(index_missing),
        })
    verify = subprocess.run(
        ["python", str(HERE / "verify_safe_copy.py")], capture_output=True, text=True
    )
    if verify.returncode:
        failures.append({"check": "safe_copy_map", "output": verify.stdout, "stderr": verify.stderr})
    staged_verify = subprocess.run(
        [
            "python", str(HERE / "verify_safe_copy.py"),
            "--staged-root", str(HERE / "verification_stage"),
        ],
        capture_output=True,
        text=True,
    )
    if staged_verify.returncode:
        failures.append({"check": "staged_safe_copy_map", "output": staged_verify.stdout, "stderr": staged_verify.stderr})
    record = {
        "current_root": str(ROOT),
        "node_js_files_checked": len(js_files),
        "css_files_checked": len(css_files),
        "css_selector_rules_parsed": css_rule_count,
        "expected_apk_layer_dependencies": sorted(expected_core_missing),
        "safe_copy_map_verification": json.loads(verify.stdout) if verify.stdout else None,
        "staged_safe_copy_verification": json.loads(staged_verify.stdout) if staged_verify.stdout else None,
        "failures": failures,
        "exit_status": 1 if failures else 0,
    }
    (HERE / "verification_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return record["exit_status"]


if __name__ == "__main__":
    raise SystemExit(main())
