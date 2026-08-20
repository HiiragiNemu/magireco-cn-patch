#!/usr/bin/env python3
"""Turn the reviewed runtime mapper into a stable-key product change manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "magica" / "js" / "libs"

LIST_KEYS = {
    "chapterList.json": ("chapterId",),
    "charaMessageList.json": ("charaNo", "messageId"),
    "doppelList.json": ("id",),
    "itemList.json": ("itemCode",),
    "pieceList.json": ("pieceId",),
    "sectionList.json": ("sectionId",),
    "shopItemList.json": ("id",),
}

# Changes found during independent semantic review.  Values not listed here use
# the mapper's proposed Chinese verbatim.
REVIEWED_CORRECTIONS = {
    ("cardMagiaMap.json", "35048", "name"): "欢乐蛋糕庆典",
    ("doppelCardMagiaMap.json", "35048", "name"): "欢乐蛋糕庆典",
    ("doppelList.json", "350400", "name"): "欢乐蛋糕庆典",
    ("cardMagiaMap.json", "40618", "name"): "心之使命",
    ("doppelCardMagiaMap.json", "40618", "name"): "心之使命",
    ("doppelList.json", "406100", "name"): "心之使命",
    ("cardMagiaMap.json", "40624", "name"): "泷奈乱射",
    ("cardMagiaMap.json", "40625", "name"): "泷奈乱射",
    ("charaMessageList.json", "1012/55", "message"): "恶作剧与糖果！",
    ("charaMessageList.json", "1023/42", "message"): "简单模式……轻松游戏……\n！",
    ("charaMessageList.json", "3039/42", "message"): "摄像机就位，开拍\n！",
    ("itemList.json", "HOME_EV_1125_20661", "shortDescription"): "苦乐参半的AI回忆",
    ("itemList.json", "HOME_EV_1205_21189", "shortDescription"): "回忆水滴",
    ("pieceList.json", "1609", "pieceName"): "夜间热聊时光",
    ("pieceList.json", "1808", "pieceName"): "镜中的命",
    ("pieceSkillMap.json", "22011", "name"): "全力爆发精通[Ⅰ]",
    ("pieceSkillMap.json", "22012", "name"): "全力爆发精通[Ⅱ]",
    ("sectionList.json", "340622", "title"): "心怀善意，坦诚待人。",
    ("sectionList.json", "340623", "title"): "乐在其中。",
}


class ManifestError(RuntimeError):
    pass


def load_product() -> dict[str, object]:
    return {
        name: json.loads((LIBS / name).read_text(encoding="utf-8"))
        for name in {
            "cardMagiaMap.json", "chapterList.json", "charaMessageList.json",
            "doppelCardMagiaMap.json", "doppelList.json", "itemList.json",
            "pieceList.json", "pieceSkillMap.json", "placeSkillMap.json",
            "sectionList.json", "shopItemList.json",
        }
    }


def record_for(file_name: str, key: str, data: object) -> dict[str, object]:
    if isinstance(data, dict):
        record = data.get(str(key))
        if not isinstance(record, dict):
            raise ManifestError(f"missing dictionary key {file_name}:{key}")
        return record
    fields = LIST_KEYS[file_name]
    parts = key.split("/")
    if len(parts) != len(fields):
        raise ManifestError(f"bad composite key {file_name}:{key}")
    found = []
    for row in data:
        if all(str(row.get(field)) == part for field, part in zip(fields, parts)):
            found.append(row)
    if len(found) != 1:
        raise ManifestError(f"stable key is not unique {file_name}:{key} count={len(found)}")
    return found[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapper", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = list(csv.DictReader(
        args.mapper.open(encoding="utf-8-sig", newline=""), delimiter="\t"
    ))
    product = load_product()
    changes: list[dict[str, object]] = []
    home_titles: dict[str, str] = {}
    for source in rows:
        if source["current"] == source["proposed_cn"]:
            continue
        file_name = source["file"]
        key = source["key/id"]
        field = source["field"]
        record = record_for(file_name, key, product[file_name])
        before = record.get(field)
        mapper_before = source["current"]
        if before != mapper_before and not (
            isinstance(before, str) and before == mapper_before.replace("\\n", "\n")
        ):
            raise ManifestError(
                f"mapper/product drift {file_name}:{key}:{field}: "
                f"mapper={mapper_before!r} product={before!r}"
            )
        after = REVIEWED_CORRECTIONS.get(
            (file_name, key, field), source["proposed_cn"]
        )
        if before == after:
            continue
        change = {
            "file": f"magica/js/libs/{file_name}",
            "key": key,
            "field": field,
            "before": before,
            "after": after,
            "source_tier": source["source_tier"],
            "review_status": source["review_status"],
            "evidence": source["evidence"],
            "verdict": source["verdict"],
        }
        changes.append(change)
        if file_name == "itemList.json" and key.startswith("HOME_EV_"):
            home_titles[key] = str(after)

    # A home-background title is exposed by all three sibling fields.  The
    # mapper found shortDescription; this closes the same-record English leak.
    item_data = product["itemList.json"]
    for key, title in sorted(home_titles.items()):
        record = record_for("itemList.json", key, item_data)
        if key == "HOME_EV_1205_21189":
            continue  # name/description already use the selected Chinese title.
        for field, after in (
            ("name", f"背景「{title}」"),
            ("description", f"主页背景「{title}」。"),
        ):
            before = record[field]
            if before == after:
                continue
            changes.append({
                "file": "magica/js/libs/itemList.json",
                "key": key,
                "field": field,
                "before": before,
                "after": after,
                "source_tier": "new-human-proposal",
                "review_status": "needs-human-review",
                "evidence": f"same-record sibling of itemList.json#{key}.shortDescription",
                "verdict": "same-record-visible-field-completion",
            })

    identity = [(c["file"], c["key"], c["field"]) for c in changes]
    if len(identity) != len(set(identity)):
        raise ManifestError("duplicate change identity")
    changes.sort(key=lambda c: (c["file"], str(c["key"]), c["field"]))
    payload = {
        "schema": "magireco-cn-runtime-dictionary-localization/v1",
        "authority_order": [
            "official-cn", "wiki", "existing-confirmed-human", "new-human-proposal"
        ],
        "changes": changes,
        "change_count": len(changes),
        "file_count": len({c["file"] for c in changes}),
        "product_write_allowed": True,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": "PASS", "changes": len(changes),
                      "files": payload["file_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
