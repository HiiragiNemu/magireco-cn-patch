#!/usr/bin/env python3
"""Deterministically rebuild the embedded MagiaCN dictionaries.

The existing jQuery file is the canonical runtime wrapper.  This program only
replaces its ``var cn = <JSON>`` value, so rerunning the dictionary build cannot
silently replace the reviewed runtime logic with an older injector template.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent
LIBS = ROOT / "magica" / "js" / "libs"
JQUERY = LIBS / "jquery-3.7.1.min.js"
AUDIT = ROOT / "magica" / "i18n_audit" / "wiki_authority_pass9"
MANIFEST = AUDIT / "layer_manifest.json"
SUMS = AUDIT / "LAYER_SHA256SUMS.txt"

# This tuple is deliberately ordered.  It is both the allow-list and the
# serialized outer-object order; never derive it from os.listdir/glob order.
DICTIONARIES: tuple[tuple[str, tuple[str, ...] | None], ...] = (
    ("arenaClassList.json", ("arenaBattleFreeRankClass",)),
    ("cardList.json", ("cardId",)),
    ("cardMagiaMap.json", None),
    ("cardSkillMap.json", None),
    ("chapterList.json", ("chapterId",)),
    ("charaList.json", ("id",)),
    ("charaMessageList.json", ("charaNo", "messageId")),
    ("doppelCardMagiaMap.json", None),
    ("doppelList.json", ("id",)),
    ("emotionSkillMap.json", None),
    ("enemyList.json", ("enemyId",)),
    ("eventList.json", ("eventId",)),
    ("eventStoryList.json", ("storyIds",)),
    ("formationSheetList.json", ("id",)),
    ("giftList.json", ("id",)),
    ("itemList.json", ("itemCode",)),
    ("live2dList.json", ("charaId", "live2dId")),
    ("patrolAreaList.json", ("patrolAreaId",)),
    ("pieceList.json", ("pieceId",)),
    ("pieceSkillMap.json", None),
    ("placeSkillMap.json", None),
    ("sectionList.json", ("sectionId",)),
    ("shopItemList.json", ("id",)),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_id(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def lf_text(data: bytes, *, label: str) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AssertionError(f"{label}: not UTF-8: {exc}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def record_map(name: str, value: Any, keys: tuple[str, ...] | None) -> dict[str, Any]:
    if keys is None:
        if not isinstance(value, dict):
            raise AssertionError(f"{name}: expected object/map root")
        return {str(key): row for key, row in value.items()}
    if not isinstance(value, list):
        raise AssertionError(f"{name}: expected list root")
    result: dict[str, Any] = {}
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise AssertionError(f"{name}[{index}]: expected object")
        missing = [key for key in keys if key not in row]
        if missing:
            raise AssertionError(f"{name}[{index}]: missing identity fields {missing}")
        key = "_".join(str(row[field]) for field in keys)
        if key in result:
            raise AssertionError(f"{name}: duplicate identity {key!r}")
        result[key] = row
    return result


def standalone_payload() -> dict[str, dict[str, Any]]:
    expected = [name for name, _ in DICTIONARIES]
    actual = sorted(path.name for path in LIBS.glob("*.json"))
    if actual != sorted(expected):
        raise AssertionError(
            f"dictionary set drift: missing={sorted(set(expected)-set(actual))}, "
            f"extra={sorted(set(actual)-set(expected))}"
        )
    # A Windows checkout may have materialized CRLF even when the Git blobs are
    # LF.  Normalize the authoritative standalone inputs before hashing them so
    # the worktree build and ``git archive`` build have identical byte ledgers.
    for filename in expected:
        path = LIBS / filename
        normalized = lf_text(path.read_bytes(), label=str(path)).encode("utf-8")
        if path.read_bytes() != normalized:
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_bytes(normalized)
            temporary.replace(path)
    result: dict[str, dict[str, Any]] = {}
    for filename, keys in DICTIONARIES:
        result[Path(filename).stem] = record_map(filename, load_json(LIBS / filename), keys)
    return result


def embedded_span(text: str) -> tuple[dict[str, Any], int, int]:
    matches = list(re.finditer(r"\bvar\s+cn\s*=\s*", text))
    if len(matches) != 1:
        raise AssertionError(f"expected one embedded cn marker, found {len(matches)}")
    start = matches[0].end()
    value, consumed = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise AssertionError("embedded cn value is not an object")
    return value, start, start + consumed


def canonical_json(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def write_lf(path: Path, text: str) -> None:
    data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def rebuild_jquery(payload: dict[str, dict[str, Any]]) -> tuple[bytes, str, str]:
    original = lf_text(JQUERY.read_bytes(), label=str(JQUERY))
    _, start, end = embedded_span(original)
    prefix = original[:start]
    suffix = original[end:]
    rebuilt = prefix + canonical_json(payload) + suffix
    write_lf(JQUERY, rebuilt)
    data = JQUERY.read_bytes()
    if b"\r" in data or data.startswith(b"\xef\xbb\xbf"):
        raise AssertionError("generated jQuery is not BOM-free LF UTF-8")
    reparsed, new_start, new_end = embedded_span(data.decode("utf-8"))
    if reparsed != payload:
        raise AssertionError("generated jQuery payload differs from standalone JSON")
    if prefix != rebuilt[:new_start] or suffix != rebuilt[new_end:]:
        raise AssertionError("runtime wrapper changed outside the embedded dictionary span")
    return data, sha256_bytes(prefix.encode("utf-8")), sha256_bytes(suffix.encode("utf-8"))


def update_layer_metadata() -> tuple[bytes, bytes]:
    manifest = load_json(MANIFEST)
    file_paths = [LIBS / filename for filename, _ in DICTIONARIES] + [JQUERY]
    entries = []
    for path in file_paths:
        data = path.read_bytes()
        entries.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        })
    manifest["files"] = entries
    write_lf(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n")
    sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in entries)
    write_lf(SUMS, sums)
    return MANIFEST.read_bytes(), SUMS.read_bytes()


def main() -> int:
    payload = standalone_payload()
    jquery, prefix_sha, suffix_sha = rebuild_jquery(payload)
    manifest, sums = update_layer_metadata()
    proc = subprocess.run(["node", "--check", str(JQUERY)], capture_output=True, text=True)
    if proc.returncode:
        raise AssertionError(f"node --check failed: {proc.stderr.strip()}")
    result = {
        "status": "PASS",
        "dictionary_order": [Path(name).stem for name, _ in DICTIONARIES],
        "dictionary_count": len(payload),
        "record_count": sum(len(rows) for rows in payload.values()),
        "jquery": {
            "bytes": len(jquery),
            "sha256": sha256_bytes(jquery),
            "git_blob": git_blob_id(jquery),
            "cr_bytes": jquery.count(b"\r"),
            "prefix_sha256": prefix_sha,
            "suffix_sha256": suffix_sha,
        },
        "layer_manifest_sha256": sha256_bytes(manifest),
        "layer_sha256s_sha256": sha256_bytes(sums),
        "embedded_equals_standalone": True,
        "node_check_exit_status": proc.returncode,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"BUILD_FAILED: {exc}", file=sys.stderr)
        raise
