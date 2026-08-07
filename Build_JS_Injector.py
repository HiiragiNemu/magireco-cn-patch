#!/usr/bin/env python3
"""Deterministically rebuild the 23-dictionary MagiaCN jQuery payload.

The committed jQuery is the audited runtime-code template.  This script extracts only its
code outside ``var cn = {...}``, verifies that code against pass8/pass9 audit hashes, and
replaces the dictionary payload in a fixed order.  It therefore cannot silently fall back
to an older injector implementation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "original_source" / "jquery-3.7.1.min.js"
LIBS = ROOT / "magica" / "js" / "libs"
TARGET = LIBS / "jquery-3.7.1.min.js"

ORIGINAL_SHA256 = "fc9a93dd241f6b045cbff0481cf4e1901becd0e12fb45166a8f17f95823f0b1a"
AUDITED_PREFIX_SHA256 = "0243774265dc954e6f9d129d63776c0446097030bebeffaa81798477de3892a1"
AUDITED_SUFFIX_SHA256 = "c4c18438082918f8a2b25612230ff46277a4f31aef1cd0333a0b028ebce0f7e3"
DICT_NAMES = (
    "arenaClassList", "cardList", "cardMagiaMap", "cardSkillMap", "chapterList",
    "charaList", "charaMessageList", "doppelCardMagiaMap", "doppelList",
    "emotionSkillMap", "enemyList", "eventList", "eventStoryList",
    "formationSheetList", "giftList", "itemList", "live2dList", "patrolAreaList",
    "pieceList", "pieceSkillMap", "placeSkillMap", "sectionList", "shopItemList",
)
LIST_KEYS = {
    "arenaClassList": ("arenaBattleFreeRankClass",),
    "cardList": ("cardId", "id"),
    "chapterList": ("chapterId", "id"),
    "charaList": ("id", "charaNo"),
    "charaMessageList": ("charaNo_messageId",),
    "doppelList": ("id",),
    "enemyList": ("enemyId", "id"),
    "eventList": ("eventId", "id"),
    "eventStoryList": ("storyIds",),
    "formationSheetList": ("formationSheetId", "id"),
    "giftList": ("id", "giftId"),
    "itemList": ("itemCode", "id", "itemId"),
    "live2dList": ("charaId_live2dId",),
    "patrolAreaList": ("patrolAreaId", "id"),
    "pieceList": ("pieceId", "id"),
    "sectionList": ("sectionId", "id"),
    "shopItemList": ("shopItemId", "id"),
}


def lf_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_audited_runtime() -> tuple[bytes, bytes]:
    text = lf_bytes(TARGET).decode("utf-8-sig")
    start = text.rfind("(function(){")
    if start < 0:
        raise RuntimeError("audited injector start marker missing")
    marker = "var cn = "
    payload_start = text.find(marker, start)
    if payload_start < 0:
        raise RuntimeError("audited var cn marker missing")
    payload_start += len(marker)
    _, consumed = json.JSONDecoder().raw_decode(text[payload_start:])
    payload_end = payload_start + consumed
    prefix = text[:payload_start].encode("utf-8")
    suffix = text[payload_end:].encode("utf-8")
    if sha(prefix) != AUDITED_PREFIX_SHA256 or sha(suffix) != AUDITED_SUFFIX_SHA256:
        raise RuntimeError(
            "runtime code outside the dictionary payload differs from the audited pass8/pass9 template"
        )
    original = lf_bytes(ORIGINAL)
    if sha(original) != ORIGINAL_SHA256:
        raise RuntimeError(f"original jQuery hash mismatch: {sha(original)}")
    if not prefix.startswith(original):
        raise RuntimeError("audited jQuery prefix is not based on the pinned original jQuery")
    return prefix, suffix


def map_dictionary(name: str, data):
    if name not in LIST_KEYS:
        if not isinstance(data, dict):
            raise TypeError(f"{name} must be a JSON object")
        return data
    if not isinstance(data, list):
        raise TypeError(f"{name} must be a JSON array")
    mapped = {}
    for item in data:
        if not isinstance(item, dict):
            raise TypeError(f"{name} contains a non-object row")
        if name == "charaMessageList":
            key = f"{item.get('charaNo', '')}_{item.get('messageId', '')}"
        elif name == "live2dList":
            key = f"{item.get('charaId', '')}_{item.get('live2dId', '')}"
        else:
            key = ""
            for field in LIST_KEYS[name]:
                if field in item:
                    key = str(item[field])
                    break
        if not key or key == "_":
            continue
        if key in mapped:
            raise ValueError(f"duplicate {name} key: {key}")
        mapped[key] = item
    return mapped


def main() -> int:
    actual = {p.stem for p in LIBS.glob("*.json")}
    expected = set(DICT_NAMES)
    if actual != expected:
        raise RuntimeError(
            f"dictionary set mismatch; missing={sorted(expected-actual)} extra={sorted(actual-expected)}"
        )
    prefix, suffix = split_audited_runtime()
    dictionaries = {}
    for name in DICT_NAMES:
        with (LIBS / f"{name}.json").open("r", encoding="utf-8-sig", newline="") as fh:
            dictionaries[name] = map_dictionary(name, json.load(fh))
    payload = json.dumps(dictionaries, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    output = prefix + payload.encode("utf-8") + suffix
    TARGET.write_bytes(output)  # byte write: never use platform newline conversion
    print(
        f"MagiaCN injector rebuilt: dictionaries={len(DICT_NAMES)} "
        f"bytes={len(output)} sha256={sha(output)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
