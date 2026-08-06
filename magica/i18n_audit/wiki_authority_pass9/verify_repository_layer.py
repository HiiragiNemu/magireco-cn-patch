#!/usr/bin/env python3
"""Verify the committed Wiki authority dictionary layer in this repository."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
LIBS = ROOT / "magica" / "js" / "libs"
LIST_KEYS = {
    "arenaClassList": ("arenaBattleFreeRankClass",),
    "cardList": ("cardId",),
    "chapterList": ("chapterId",),
    "charaList": ("id",),
    "charaMessageList": ("charaNo", "messageId"),
    "doppelList": ("id",),
    "enemyList": ("enemyId",),
    "eventList": ("eventId",),
    "eventStoryList": ("storyIds",),
    "formationSheetList": ("id",),
    "giftList": ("id",),
    "itemList": ("itemCode",),
    "live2dList": ("charaId", "live2dId"),
    "patrolAreaList": ("patrolAreaId",),
    "pieceList": ("pieceId",),
    "sectionList": ("sectionId",),
    "shopItemList": ("id",),
}
EXPECTED = {
    "arenaClassList", "cardList", "cardMagiaMap", "cardSkillMap", "chapterList",
    "charaList", "charaMessageList", "doppelCardMagiaMap", "doppelList",
    "emotionSkillMap", "enemyList", "eventList", "eventStoryList",
    "formationSheetList", "giftList", "itemList", "live2dList", "patrolAreaList",
    "pieceList", "pieceSkillMap", "placeSkillMap", "sectionList", "shopItemList",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def as_map(name: str, value):
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    keys = LIST_KEYS[name]
    result = {}
    for row in value:
        key = "_".join(str(row[field]) for field in keys)
        if key in result:
            raise AssertionError(f"duplicate {name} key {key}")
        result[key] = row
    return result


def embedded_cn(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    marker = re.search(r"\bvar\s+cn\s*=\s*", text)
    if not marker:
        raise AssertionError("jquery embedded cn marker missing")
    value, _ = json.JSONDecoder().raw_decode(text[marker.end():])
    return value


def main() -> int:
    files = {path.stem: path for path in LIBS.glob("*.json")}
    assert set(files) == EXPECTED, (sorted(EXPECTED - set(files)), sorted(set(files) - EXPECTED))
    standalone = {name: as_map(name, load(path)) for name, path in files.items()}
    embedded = embedded_cn(LIBS / "jquery-3.7.1.min.js")
    assert set(embedded) == EXPECTED
    for name in sorted(EXPECTED):
        assert embedded[name] == standalone[name], f"embedded mismatch: {name}"

    doppel = standalone["doppelList"]
    card = standalone["cardMagiaMap"]
    doppel_card = standalone["doppelCardMagiaMap"]
    groups = 0
    for doppel_id, row in doppel.items():
        magia_id = str(int(doppel_id) // 100) + "8"
        assert magia_id in card and magia_id in doppel_card, (doppel_id, magia_id)
        assert row["name"] == card[magia_id]["name"] == doppel_card[magia_id]["name"], doppel_id
        groups += 1
    assert groups == 217

    failures = []
    js_files = sorted((ROOT / "magica").rglob("*.js"))
    for path in js_files:
        proc = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        if proc.returncode:
            failures.append({"file": path.relative_to(ROOT).as_posix(), "stderr": proc.stderr})
    assert not failures, failures

    result = {
        "status": "PASS",
        "dictionaries": len(standalone),
        "records": sum(len(value) for value in standalone.values()),
        "embedded_mismatches": 0,
        "doppel_groups": groups,
        "javascript_checked": len(js_files),
        "javascript_syntax_failures": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
