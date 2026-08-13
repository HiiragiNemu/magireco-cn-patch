#!/usr/bin/env python3
"""Verify the final v26 runtime dictionaries, manifest and generated jQuery."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import Build_JS_Injector as builder  # noqa: E402


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def embedded_dictionaries(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    start = text.rfind("(function(){")
    if start < 0:
        raise AssertionError("injector IIFE marker missing")
    marker = "var cn = "
    payload_start = text.find(marker, start)
    if payload_start < 0:
        raise AssertionError("runtime dictionary marker missing")
    value, _ = json.JSONDecoder().raw_decode(text[payload_start + len(marker):])
    return value, text


def main() -> int:
    actual_names = sorted(path.stem for path in builder.LIBS.glob("*.json"))
    assert actual_names == sorted(builder.DICT_NAMES), "23-dictionary set drift"

    standalone = {}
    for name in builder.DICT_NAMES:
        path = builder.LIBS / f"{name}.json"
        raw = path.read_bytes()
        assert b"\r" not in raw, f"CR byte present: {path}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM present: {path}"
        value = json.loads(raw.decode("utf-8"))
        standalone[name] = builder.map_dictionary(name, value)

    jquery_raw = builder.TARGET.read_bytes()
    assert b"\r" not in jquery_raw, "CR byte present in jQuery"
    embedded, jquery_text = embedded_dictionaries(builder.TARGET)
    assert list(embedded) == list(builder.DICT_NAMES), "embedded dictionary order drift"
    assert embedded == standalone, "embedded dictionaries differ from standalone JSON"
    expected_authority = (
        'authority:"OFFICIAL-CN-DUMP>WIKI>EXISTING-VERIFIED-HUMAN>'
        'NEW-HUMAN-OR-LLM"'
    )
    assert expected_authority in jquery_text, "runtime authority metadata drift"
    assert 'packageId:"cn-js-v26-authority-pass17"' in jquery_text

    paths = [builder.LIBS / f"{name}.json" for name in builder.DICT_NAMES]
    paths.append(builder.TARGET)
    rows = []
    for path in paths:
        data = path.read_bytes()
        rows.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(data),
            "sha256": sha256(data),
        })

    manifest_raw = builder.RUNTIME_MANIFEST.read_bytes()
    sums_raw = builder.RUNTIME_SUMS.read_bytes()
    assert b"\r" not in manifest_raw and b"\r" not in sums_raw
    manifest = json.loads(manifest_raw.decode("utf-8"))
    assert manifest["schema"] == "magireco-cn-runtime-layer/v26"
    assert manifest["package_id"] == "cn-js-v26-authority-pass17"
    assert manifest["line_endings"] == "LF"
    assert manifest["dictionary_order"] == list(builder.DICT_NAMES)
    assert manifest["files"] == rows, "runtime manifest hash/size drift"
    expected_sums = "".join(
        f"{row['sha256']}  {row['path']}\n" for row in rows
    ).encode("ascii")
    assert sums_raw == expected_sums, "runtime SHA256SUMS drift"

    node = subprocess.run(
        ["node", "--check", str(builder.TARGET)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        check=False,
    )
    assert node.returncode == 0, node.stderr

    result = {
        "status": "PASS",
        "dictionary_count": len(standalone),
        "record_count": sum(len(value) for value in standalone.values()),
        "embedded_equals_standalone": True,
        "jquery": {"bytes": len(jquery_raw), "sha256": sha256(jquery_raw)},
        "manifest": {
            "entries": len(rows),
            "sha256": sha256(manifest_raw),
            "sums_sha256": sha256(sums_raw),
        },
        "line_endings": "LF",
        "node_check_exit_status": node.returncode,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
