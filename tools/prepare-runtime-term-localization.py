#!/usr/bin/env python3
"""Build stable-field changes for authoritative visible combat terminology."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LIBS = ROOT / "magica" / "js" / "libs"
OUT_DEFAULT = (
    ROOT / "magica" / "research" / "totentanz-full-localization-20260817"
    / "runtime-dictionary" / "combat_term_changes.json"
)

FILES = (
    "cardMagiaMap.json",
    "cardSkillMap.json",
    "doppelCardMagiaMap.json",
    "emotionSkillMap.json",
    "itemList.json",
    "pieceSkillMap.json",
)

LIST_KEYS = {"itemList.json": ("itemCode",)}

# Long phrases must run before their component tokens.  The Chinese word order
# follows the old official CN client (解除增益 / 解除减益 / 幸存).  Later IDs can
# reuse these same mechanics terms, but they are not mislabeled as exact-ID hits.
REPLACEMENTS = (
    ("Buff解除", "解除增益", "official-cn-game-term"),
    ("解除Buff", "解除增益", "official-cn-game-term"),
    ("Debuff解除", "解除减益", "official-cn-game-term"),
    ("解除Debuff", "解除减益", "official-cn-game-term"),
    ("Debuff效果", "减益效果", "official-cn-game-term"),
    ("Buff", "增益", "official-cn-game-term"),
    ("Debuff", "减益", "official-cn-game-term"),
    ("Survive", "幸存", "official-cn-game-term"),
)

EVIDENCE = {
    "official-cn-game-term": (
        "D:/magia/MyProducts/MAGIA RECORD CN/Full_Raw_Dump_V2/magica/api/"
        "page/MyPage_001.json; SHA256 a82601d7cad737bf00a9a2f714d401c81389b825b27d45b492ae6f3bcc8a10db; "
        "stable mechanics examples: cardMagia art 200300700=解除增益, "
        "cardMagia/cardSkill art 200200800=解除减益, "
        "doppelCardMagia id 30208=幸存"
    ),
}

VISIBLE_FIELDS = {"name", "shortDescription", "description"}

# These uppercase forms are literal display strings, not API enum fields.  The
# exact stable-key allowlist prevents a broad DEBUFF replacement from touching
# native/API mechanics structures.
EXACT_FIELD_REPLACEMENTS = {
    ("cardMagiaMap.json", "90360", "shortDescription"): (
        "对单个敌人造成伤害[Ⅴ] & 必定眩晕(单个敌人/1T) & 攻击力UP(自己/3T) & 解除DEBUFF(自己) ",
        "对单个敌人造成伤害[Ⅴ] & 必定眩晕(单个敌人/1T) & 攻击力UP(自己/3T) & 解除减益(自己) ",
    ),
    **{
        ("emotionSkillMap.json", key, "name"): ("反抗DEBUFF", "减益反抗")
        for key in (
            "1035109", "1042109", "1042111", "1046109", "2202106",
            "2203106", "3048110", "3052105", "3052109", "4036108", "4061107",
        )
    },
    ("emotionSkillMap.json", "2009113", "name"): (
        "忽视DEBUFF圆环[Ⅱ]", "减益无效光环[Ⅱ]"
    ),
}


def stable_key(file_name: str, path: list[str], root_data: object) -> tuple[str, str]:
    """Return record key and field from a walked string path."""
    if isinstance(root_data, dict):
        if len(path) < 2:
            raise ValueError(f"unsupported shallow field {file_name}:{path}")
        return path[0], "/".join(path[1:])
    if file_name not in LIST_KEYS or len(path) < 2:
        raise ValueError(f"unsupported list field {file_name}:{path}")
    row = root_data[int(path[0])]
    key = "/".join(str(row[field]) for field in LIST_KEYS[file_name])
    return key, "/".join(path[1:])


def translate(value: str) -> tuple[str, list[str]]:
    after = value
    tiers: list[str] = []
    for before, replacement, tier in REPLACEMENTS:
        # Phrase rules preserve official Chinese word order.  Component-token
        # rules are ASCII-boundary exact so BUFF/DEBUFF enums and identifiers
        # are never touched.
        pattern = (
            re.escape(before)
            if before not in {"Buff", "Debuff", "Survive"}
            else rf"(?<![A-Za-z]){re.escape(before)}(?![A-Za-z])"
        )
        if re.search(pattern, after):
            after = re.sub(pattern, replacement, after)
            tiers.append(tier)
    return after, sorted(set(tiers))


def walk_strings(value: object, path: list[str]):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_strings(child, path + [str(key)])
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_strings(child, path + [str(index)])
    elif isinstance(value, str):
        yield path, value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    changes: list[dict[str, object]] = []
    token_counts = {"Buff": 0, "Debuff": 0, "Survive": 0}
    for file_name in FILES:
        data = json.loads((LIBS / file_name).read_text(encoding="utf-8"))
        for path, before in walk_strings(data, []):
            if not path or path[-1] not in VISIBLE_FIELDS:
                continue
            hits = {token: before.count(token) for token in token_counts}
            if not any(hits.values()):
                continue
            after, tiers = translate(before)
            if after == before:
                raise RuntimeError(f"unhandled visible term {file_name}:{path}: {before!r}")
            key, field = stable_key(file_name, path, data)
            for token, count in hits.items():
                token_counts[token] += count
            source_tier = "official-cn-game-term"
            evidence = "; ".join(EVIDENCE[tier] for tier in tiers)
            changes.append({
                "file": f"magica/js/libs/{file_name}",
                "key": key,
                "field": field,
                "before": before,
                "after": after,
                "source_tier": source_tier,
                "review_status": "authority-term-verified",
                "evidence": evidence,
                "verdict": "exact-visible-token-normalization",
                "matched_tokens": hits,
            })

        for (target_file, key, field), (before, after) in EXACT_FIELD_REPLACEMENTS.items():
            if target_file != file_name:
                continue
            record = data.get(key) if isinstance(data, dict) else None
            if not isinstance(record, dict) or record.get(field) != before:
                actual = None if not isinstance(record, dict) else record.get(field)
                raise RuntimeError(
                    f"uppercase display field drift {file_name}:{key}:{field}: "
                    f"expected={before!r} actual={actual!r}"
                )
            changes.append({
                "file": f"magica/js/libs/{file_name}",
                "key": key,
                "field": field,
                "before": before,
                "after": after,
                "source_tier": "official-cn-game-term",
                "review_status": "authority-term-verified",
                "evidence": EVIDENCE["official-cn-game-term"],
                "verdict": "exact-visible-uppercase-field-normalization",
                "matched_tokens": {"DEBUFF": before.count("DEBUFF")},
            })

    identity = [(c["file"], c["key"], c["field"]) for c in changes]
    if len(identity) != len(set(identity)):
        raise RuntimeError("duplicate stable field identity")
    changes.sort(key=lambda c: (c["file"], str(c["key"]), str(c["field"])))
    payload = {
        "schema": "magireco-cn-runtime-dictionary-localization/v1",
        "authority_order": [
            "official-cn", "wiki", "existing-confirmed-human", "new-human-proposal"
        ],
        "scope": "visible combat dictionary string values only; keys and code excluded",
        "changes": changes,
        "change_count": len(changes),
        "file_count": len({c["file"] for c in changes}),
        "token_counts": token_counts,
        "exact_uppercase_field_count": len(EXACT_FIELD_REPLACEMENTS),
        "product_write_allowed": True,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "status": "PASS",
        "changes": len(changes),
        "files": payload["file_count"],
        "token_counts": token_counts,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
