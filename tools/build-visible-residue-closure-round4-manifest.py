#!/usr/bin/env python3
"""Classify the final visible runtime-dictionary residue by exact authority."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESIDUE = (
    ROOT.parent
    / "next_round_execution_20260819"
    / "post_manual_visible_residue_audit"
    / "actionable_visible_residue.tsv"
)
DEFAULT_OUT = (
    ROOT
    / "magica/research/totentanz-full-localization-20260817"
    / "visible-residue-closure-round4"
)
DEFAULT_OFFICIAL_STORY = Path(r"A:\magicaOLD\api\page\StoryCollection_001.json")
DEFAULT_OFFICIAL_MAIN = Path(r"A:\magicaOLD\api\page\MainQuest_001.json")
DEFAULT_WIKI_CHARACTERS = Path(r"D:\magia\MyProducts\wiki-data\data\characters.json")
DEFAULT_WIKI_MEMORIA = Path(r"D:\magia\MyProducts\wiki-data\data\memoria.json")


class BuildError(RuntimeError):
    pass


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def unique(rows, predicate, label: str):
    found = [row for row in rows if predicate(row)]
    if len(found) != 1:
        raise BuildError(f"{label}: expected one row, got {len(found)}")
    return found[0]


def flatten_official_story(data: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for event in data["eventStoryList"]:
        for row in event.get("storyList", []):
            key = str(row["storyIds"])
            if key in result:
                raise BuildError(f"duplicate official storyIds: {key}")
            result[key] = row
    return result


def official_section(data: object, section_id: int) -> dict:
    found: list[dict] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if value.get("sectionId") == section_id and "title" in value:
                found.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    titles = {str(row["title"]) for row in found}
    if len(titles) != 1:
        raise BuildError(f"official section {section_id}: title count={len(titles)}")
    return {"sectionId": section_id, "title": next(iter(titles))}


def wiki_character(data: dict, chara_id: str) -> dict:
    rows = [row for row in data.values() if isinstance(row, dict) and str(row.get("charaId")) == chara_id]
    return unique(rows, lambda _: True, f"Wiki charaId={chara_id}")


def wiki_memoria(data: object, piece_id: int) -> dict:
    rows = list(data.values()) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise BuildError("Wiki memoria root must be an object or list")
    return unique(rows, lambda row: isinstance(row, dict) and row.get("number") == piece_id, f"Wiki memoria={piece_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--residue-tsv", type=Path, default=DEFAULT_RESIDUE)
    parser.add_argument("--official-story", type=Path, default=DEFAULT_OFFICIAL_STORY)
    parser.add_argument("--official-main", type=Path, default=DEFAULT_OFFICIAL_MAIN)
    parser.add_argument("--wiki-characters", type=Path, default=DEFAULT_WIKI_CHARACTERS)
    parser.add_argument("--wiki-memoria", type=Path, default=DEFAULT_WIKI_MEMORIA)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    residue = list(csv.DictReader(args.residue_tsv.open(encoding="utf-8-sig", newline=""), delimiter="\t"))
    if len(residue) != 36:
        raise BuildError(f"post-manual residue count drift: {len(residue)}")
    official_story = flatten_official_story(read_json(args.official_story))
    official_encounter = official_section(read_json(args.official_main), 330491)
    wiki_chara = wiki_character(read_json(args.wiki_characters), "1042")
    wiki_piece = wiki_memoria(read_json(args.wiki_memoria), 1608)
    if wiki_chara.get("nameZh") != "小丘比":
        raise BuildError("Wiki charaId=1042 nameZh drift")
    if wiki_piece.get("name_zh") != "Disguise":
        raise BuildError("Wiki memoria 1608 name_zh drift")

    retained: list[dict] = []
    changes: list[dict] = []
    narrative_cn = {
        "INTERMISSION": "幕间", "Intermission": "幕间",
        "EPILOGUE": "尾声", "Epilogue": "尾声",
        "Prologue": "序章", "Story": "故事",
    }
    for row in residue:
        path, key, field, current = row["path"], row["stable_key"], row["field"], row["current_text"]
        if path.endswith("eventStoryList.json"):
            story_ids = key.split("/", 1)[0].split("=", 1)[1]
            official = official_story.get(story_ids)
            if not official or official.get(field) != current:
                raise BuildError(f"official story mismatch: {key}")
            after = narrative_cn.get(current)
            if not after:
                raise BuildError(f"no reviewed narrative translation: {current!r}")
            changes.append({
                "item_id": row["audit_id"], "file": path, "key": story_ids,
                "field": field, "before": current, "after": after,
                "source_tier": "new-root-translation", "review_status": "not-yet-human-reviewed",
                "evidence": f"{args.official_story}/eventStoryList/storyIds={story_ids}/{field} retains English; careful Chinese completion",
            })
        elif path.endswith("pieceList.json"):
            if key != "pieceId=1608/pieceName" or current != wiki_piece["name_zh"]:
                raise BuildError("Wiki memoria 1608 residue mismatch")
            changes.append({
                "item_id": row["audit_id"], "file": path, "key": "1608",
                "field": field, "before": current, "after": "伪装",
                "source_tier": "new-root-translation", "review_status": "not-yet-human-reviewed",
                "evidence": f"{args.wiki_memoria}/number=1608/name_ja=ディスガイズ; name_zh retains English; careful Chinese completion",
            })
        elif path.endswith("sectionList.json") and key == "sectionId=330491/title":
            if current != official_encounter["title"]:
                raise BuildError("official Encounter residue mismatch")
            changes.append({
                "item_id": row["audit_id"], "file": path, "key": "330491",
                "field": field, "before": current, "after": "邂逅",
                "source_tier": "new-root-translation", "review_status": "not-yet-human-reviewed",
                "evidence": f"{args.official_main}/sectionId=330491/title retains English; careful Chinese completion",
            })
        elif current == "Kyubert":
            stable = key.split("/", 1)[0].split("=", 1)[1]
            changes.append({
                "item_id": row["audit_id"], "file": path, "key": stable,
                "field": field, "before": current, "after": "小丘比",
                "source_tier": "wiki", "review_status": "authority-exact-stable-character",
                "evidence": f"{args.wiki_characters}/charaId=1042/nameZh + magica/js/libs/charaList.json#id=1042",
            })
        else:
            raise BuildError(f"unclassified residue row: {row['audit_id']}")

    # One mixed-language sibling title was not part of the pure English residue set.
    changes.append({
        "item_id": "POST-MANUAL-037", "file": "magica/js/libs/sectionList.json",
        "key": "310424", "field": "title", "before": "Kyubert 的试炼", "after": "小丘比的试炼",
        "source_tier": "wiki", "review_status": "authority-exact-stable-character",
        "evidence": f"{args.wiki_characters}/charaId=1042/nameZh + same sectionId=310424 context",
    })
    for index, path in enumerate((
        "magica/css/regularEvent/groupBattle/RegularEventGroupBattleRanking.css",
        "magica/css/regularEvent/groupBattle/RegularEventGroupBattleUser.css",
    ), 1):
        changes.append({
            "item_id": f"POST-MANUAL-CSS-{index:02d}", "file": path,
            "key": "css-content/必要GP", "field": "content", "before": "必要GP", "after": "所需GP",
            "source_tier": "new-root-translation", "review_status": "not-yet-human-reviewed",
            "evidence": "visible CSS pseudo-element; path-scoped careful translation",
        })

    if len(changes) != 39 or retained:
        raise BuildError(f"partition drift: changes={len(changes)} retained={len(retained)}")
    identities = [(row["file"], row["key"], row["field"]) for row in changes]
    if len(identities) != len(set(identities)):
        raise BuildError("duplicate change identity")
    payload = {
        "schema": "magireco-visible-residue-closure-round4/v1",
        "authority_order": ["official-cn", "wiki", "confirmed-human", "new-root-translation"],
        "counts": {
            "screened_residue_fields": 36,
            "protected_authority_retained": len(retained),
            "authority_changes": 7,
            "new_root_translation_changes": 32,
            "product_changes": len(changes),
            "target_files": len({row["file"] for row in changes}),
        },
        "changes": sorted(changes, key=lambda row: (row["file"], str(row["key"]), row["field"])),
        "protected_retained": sorted(retained, key=lambda row: (row["file"], str(row["key"]), row["field"])),
        "product_write_allowed": True,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "closure_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    fields = ["item_id", "file", "key", "field", "before", "after", "source_tier", "review_status", "evidence"]
    with (args.out_dir / "applied_candidates.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(payload["changes"])
    retained_fields = ["item_id", "file", "key", "field", "value", "disposition", "source_tier", "review_status", "evidence"]
    with (args.out_dir / "authority_retained.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=retained_fields, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(payload["protected_retained"])
    print(json.dumps({"status": "PASS", **payload["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
