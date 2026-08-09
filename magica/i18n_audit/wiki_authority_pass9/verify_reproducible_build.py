#!/usr/bin/env python3
"""Fail-closed verification for the committed Wiki-authority runtime layer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
AUDIT = Path(__file__).resolve().parent
MANIFEST = AUDIT / "layer_manifest.json"
BUILDER = ROOT / "Build_JS_Injector.py"
ORIGINAL = ROOT / "original_source" / "jquery-3.7.1.min.js"
LIBS = ROOT / "magica" / "js" / "libs"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_builder(dest: Path) -> dict:
    (dest / "original_source").mkdir(parents=True)
    (dest / "magica/js/libs").mkdir(parents=True)
    shutil.copy2(BUILDER, dest / "Build_JS_Injector.py")
    shutil.copy2(ORIGINAL, dest / "original_source/jquery-3.7.1.min.js")
    for path in sorted(LIBS.glob("*.json")):
        shutil.copy2(path, dest / "magica/js/libs" / path.name)
    shutil.copy2(LIBS / "jquery-3.7.1.min.js", dest / "magica/js/libs/jquery-3.7.1.min.js")
    proc = subprocess.run(
        [sys.executable, str(dest / "Build_JS_Injector.py")],
        cwd=dest, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    out = dest / "magica/js/libs/jquery-3.7.1.min.js"
    return {
        "exit_status": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "bytes": out.stat().st_size if out.exists() else None,
        "sha256": digest(out) if out.exists() else None,
    }


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = manifest["files"]
    if len(files) != 24:
        raise AssertionError(f"manifest file count != 24: {len(files)}")
    declared = {row["path"]: row for row in files}
    expected_paths = {f"magica/js/libs/{p.name}" for p in LIBS.glob("*.json")}
    expected_paths.add("magica/js/libs/jquery-3.7.1.min.js")
    if set(declared) != expected_paths:
        raise AssertionError("manifest path set differs from 23 JSON + jQuery")

    hash_errors = []
    for rel, row in sorted(declared.items()):
        path = ROOT / rel
        actual = {"bytes": path.stat().st_size, "sha256": digest(path)}
        if actual["bytes"] != row["bytes"] or actual["sha256"] != row["sha256"]:
            hash_errors.append({"path": rel, "expected": row, "actual": actual})
    if hash_errors:
        raise AssertionError(f"manifest hash mismatch: {hash_errors[:2]}")

    with tempfile.TemporaryDirectory(prefix="magia-cn-repro-a-") as a, tempfile.TemporaryDirectory(prefix="magia-cn-repro-b-") as b:
        build_a = run_builder(Path(a))
        build_b = run_builder(Path(b))
    target = declared["magica/js/libs/jquery-3.7.1.min.js"]
    if build_a["exit_status"] or build_b["exit_status"]:
        raise AssertionError({"build_a": build_a, "build_b": build_b})
    if build_a["sha256"] != build_b["sha256"] or build_a["sha256"] != target["sha256"]:
        raise AssertionError({"target": target, "build_a": build_a, "build_b": build_b})
    if build_a["bytes"] != target["bytes"] or build_b["bytes"] != target["bytes"]:
        raise AssertionError({"target": target, "build_a": build_a, "build_b": build_b})

    node = subprocess.run(
        ["node", "--check", str(LIBS / "jquery-3.7.1.min.js")],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if node.returncode:
        raise AssertionError(node.stderr)

    result = {
        "status": "PASS",
        "manifest_schema": manifest.get("schema"),
        "manifest_matches": 24,
        "manifest_total": 24,
        "dictionary_count": 23,
        "line_endings": manifest.get("line_endings"),
        "dictionary_order": manifest.get("dictionary_order"),
        "build_a": build_a,
        "build_b": build_b,
        "double_build_byte_identity": True,
        "matches_committed_jquery": True,
        "node_check_exit_status": node.returncode,
        "builder_sha256": digest(BUILDER),
        "original_jquery_sha256": digest(ORIGINAL),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
