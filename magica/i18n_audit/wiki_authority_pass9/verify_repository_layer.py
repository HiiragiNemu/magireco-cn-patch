#!/usr/bin/env python3
"""Verify the 23-dictionary layer, deterministic jQuery, and hash ledgers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[3]
LIBS = ROOT / "magica" / "js" / "libs"
AUDIT = ROOT / "magica" / "i18n_audit" / "wiki_authority_pass9"
JQUERY = LIBS / "jquery-3.7.1.min.js"
MANIFEST = AUDIT / "layer_manifest.json"
SUMS = AUDIT / "LAYER_SHA256SUMS.txt"

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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def as_map(name: str, value, keys: tuple[str, ...] | None):
    if keys is None:
        assert isinstance(value, dict), name
        return {str(key): row for key, row in value.items()}
    assert isinstance(value, list), name
    result = {}
    for index, row in enumerate(value):
        assert isinstance(row, dict), (name, index)
        assert all(field in row for field in keys), (name, index, keys)
        key = "_".join(str(row[field]) for field in keys)
        assert key not in result, (name, key)
        result[key] = row
    return result


def embedded_cn(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    matches = list(re.finditer(r"\bvar\s+cn\s*=\s*", text))
    assert len(matches) == 1, len(matches)
    value, _ = json.JSONDecoder().raw_decode(text[matches[0].end():])
    return value


def main() -> int:
    names = [name for name, _ in DICTIONARIES]
    actual = sorted(path.name for path in LIBS.glob("*.json"))
    assert actual == sorted(names), (sorted(set(names)-set(actual)), sorted(set(actual)-set(names)))
    standalone = {
        Path(name).stem: as_map(name, load(LIBS / name), keys)
        for name, keys in DICTIONARIES
    }
    embedded = embedded_cn(JQUERY)
    assert list(embedded) == list(standalone), "embedded dictionary order drift"
    assert embedded == standalone, "embedded dictionaries differ from standalone JSON"

    jquery = JQUERY.read_bytes()
    manifest_bytes = MANIFEST.read_bytes()
    sums_bytes = SUMS.read_bytes()
    normalized_paths = [LIBS / name for name in names] + [JQUERY, MANIFEST, SUMS]
    for path in normalized_paths:
        data = path.read_bytes()
        assert b"\r" not in data, f"CR byte present: {path}"
        assert not data.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM present: {path}"

    paths = [LIBS / name for name in names] + [JQUERY]
    expected_entries = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(path.read_bytes()),
            "sha256": sha256(path.read_bytes()),
        }
        for path in paths
    ]
    manifest = load(MANIFEST)
    assert manifest["files"] == expected_entries, "layer_manifest files/order/hash drift"
    expected_sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in expected_entries).encode("ascii")
    assert sums_bytes == expected_sums, "LAYER_SHA256SUMS content/order/hash drift"

    doppel = standalone["doppelList"]
    card = standalone["cardMagiaMap"]
    doppel_card = standalone["doppelCardMagiaMap"]
    for doppel_id, row in doppel.items():
        magia_id = str(int(doppel_id) // 100) + "8"
        assert row["name"] == card[magia_id]["name"] == doppel_card[magia_id]["name"], doppel_id

    proc = subprocess.run(["node", "--check", str(JQUERY)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    result = {
        "status": "PASS",
        "dictionary_count": len(standalone),
        "dictionary_order": list(standalone),
        "record_count": sum(len(value) for value in standalone.values()),
        "embedded_equals_standalone": True,
        "jquery": {
            "bytes": len(jquery),
            "sha256": sha256(jquery),
            "git_blob": git_blob(jquery),
            "cr_bytes": jquery.count(b"\r"),
        },
        "layer_manifest_sha256": sha256(manifest_bytes),
        "layer_sha256s_sha256": sha256(sums_bytes),
        "manifest_entries_match": True,
        "checksums_match": True,
        "node_check_exit_status": proc.returncode,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
