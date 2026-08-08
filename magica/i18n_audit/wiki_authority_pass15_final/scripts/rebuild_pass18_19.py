#!/usr/bin/env python3
"""Rebuild the provenance-only pass18 and pass19 authority layers.

This script deliberately writes only under ``work/pass18_19_rebuilt``.  It
does not read from, or modify, the final integration product tree.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]

REMAINING = ROOT / "work/pass15_agent_pass17/transcript_replay_remaining_cardMagia_highrisk_208.tsv"
AUTHORITY = ROOT / "work/pass15_agent_rebuild/inputs/official/authority.json"
TRANSCRIPT = ROOT / "work/shared_conversation_extracted.jsonl"
LEDGER = ROOT / "work/pass17_max_integrated/release/authority_layer_ledger_571.tsv"
PASS9 = ROOT / "work/pass15_agent_rebuild/product/magica/i18n_audit/wiki_authority_pass9/residual_llm_or_other_candidates.tsv"
PASS14_RESIDUAL = ROOT / "work/pass15_agent_structure/pass14_residual_reconstructed.tsv"

ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
NUMBER_ROMAN_RE = re.compile(r"\d+|[" + ROMAN + r"]+|∞")

GLYPHS = str.maketrans(
    {
        "個": "个",
        "浜": "滨",
        "園": "园",
        "開": "开",
        "発": "发",
        "実": "实",
        "験": "验",
        "絶": "绝",
        "級": "级",
        "現": "现",
        "編": "编",
        "時": "时",
        "撃": "击",
        "傷": "伤",
        "態": "态",
        "異": "异",
        "獲": "获",
        "敵": "敌",
        "単": "单",
        "動": "动",
        "復": "复",
        "減": "减",
        "強": "强",
    }
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_record_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def numeric_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def sigtext(values: tuple[str, ...]) -> str:
    return "|".join(values)


def numeric_roman_signature(text: str) -> tuple[str, ...]:
    # Extraction is deliberately before NFKC so Roman-rank glyphs remain typed.
    return tuple(NUMBER_ROMAN_RE.findall(text or ""))


def turn_signature(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text or "").upper()
    return tuple(re.findall(r"(?:/|\b)(\d+|∞)T\b", normalized))


def target_signature(text: str) -> tuple[str, ...]:
    """Extract ordered typed targets without relying on free-form equivalence."""
    value = unicodedata.normalize("NFKC", text or "")

    # Geometry in a leading damage phrase is an implicit enemy target.
    value = re.sub(r"横向(?:造成)?伤害", " <ENEMY_HORIZONTAL> ", value)
    value = re.sub(r"纵向(?:造成)?伤害", " <ENEMY_VERTICAL> ", value)

    for pattern, token in (
        (r"敌方全体|全体敌人|敌全体|全部敌人", "ENEMY_ALL"),
        (r"敌方单体|单个敌人|单体敌人", "ENEMY_SINGLE"),
        (r"敌方纵向|纵向敌人", "ENEMY_VERTICAL"),
        (r"我方全体|己方全体", "ALLY_ALL"),
        (r"自身|自己", "SELF"),
    ):
        value = re.sub(pattern, f" <{token}> ", value)

    # The official UI's bare parenthetical 全体 is ally-side shorthand.  Bare
    # 单体/单个 is the enemy target used in these effect descriptions.
    value = re.sub(r"\(\s*全体(?=[/)])", "( <ALLY_ALL> ", value)
    value = re.sub(r"\(\s*(?:单体|单个)(?=[/)])", "( <ENEMY_SINGLE> ", value)

    return tuple(
        re.findall(
            r"<(ENEMY_ALL|ENEMY_SINGLE|ENEMY_VERTICAL|ENEMY_HORIZONTAL|ALLY_ALL|SELF)>",
            value,
        )
    )


def direction_signature(text: str) -> tuple[str, ...]:
    """Protect every explicit increase/decrease direction in source order."""
    value = unicodedata.normalize("NFKC", text or "").upper()
    # The current prose form is the same directional mechanic as baseline UP.
    value = value.replace("伤害越高", "伤害UP")
    value = value.replace("提升", "UP").replace("上升", "UP")
    value = value.replace("降低", "DOWN").replace("下降", "DOWN")
    return tuple(re.findall(r"UP|DOWN", value))


def normalize_mechanic(text: str) -> str:
    """Closed, typed lexical normalizer reconstructed for pass19.

    The normalizer only collapses known official-CN UI word-order, target and
    status aliases.  Acceptance additionally requires independent equality of
    numeric/Roman, target, turn and direction signatures.
    """
    value = unicodedata.normalize("NFKC", text or "").translate(GLYPHS)
    value = value.replace("効果", "效果")

    # Canonicalize damage syntax before generic target replacement.
    value = re.sub(
        r"(?:对)?(?:敌方全体|全体敌人|敌全体|全部敌人)(?:造成|给予)?(属性强化伤害|伤害)",
        r"敌全\1",
        value,
    )
    value = re.sub(
        r"(?:对)?(?:敌方单体|单个敌人|单体敌人)(?:造成|给予)?(属性强化伤害|伤害)",
        r"敌单\1",
        value,
    )
    value = value.replace("全体敌人体伤害", "敌全体伤害")
    value = value.replace("敌方全体体伤害", "敌全体伤害")
    value = value.replace("横向造成伤害", "横向伤害")
    value = value.replace("纵向造成伤害", "纵向伤害")

    for source, target in (
        ("全体敌人", "敌全"),
        ("敌方全体", "敌全"),
        ("敌全体", "敌全"),
        ("全部敌人", "敌全"),
        ("单个敌人", "敌单"),
        ("敌方单体", "敌单"),
        ("单体敌人", "敌单"),
        ("纵向敌人", "敌纵"),
        ("敌方纵向", "敌纵"),
        ("我方全体", "味全"),
        ("己方全体", "味全"),
        ("己全", "味全"),
        ("自己", "自"),
        ("自身", "自"),
    ):
        value = value.replace(source, target)

    value = re.sub(r"([（(])全体(?=[/）)])", r"\1味全", value)
    value = re.sub(r"([（(])(?:单体|单个)(?=[/）)])", r"\1敌单", value)

    # Closed status/word-order aliases observed in this 165-row source set.
    for source, target in (
        ("敌人的异常状态种类越多,伤害越高", "状态异常种类伤害UP"),
        ("敌人的异常状态种类越多，伤害越高", "状态异常种类伤害UP"),
        ("根据敌方异常状态种类提升伤害", "状态异常种类伤害UP"),
        ("根据敌人状态异常的种类伤害UP", "状态异常种类伤害UP"),
        ("敌方处于异常状态时伤害提升", "状态异常时伤害UP"),
        ("敌方状态异常时伤害UP", "状态异常时伤害UP"),
        ("诱惑", "魅惑"),
        ("迷惑", "幻惑"),
        ("拘束", "束缚"),
        ("技能封印", "禁用技能"),
        ("Magia封印", "禁用Magia"),
        ("magia封印", "禁用magia"),
        ("异常状态", "状态异常"),
        ("强化中毒", "强化毒"),
        ("強化毒", "强化毒"),
        ("解除异常状态", "解除状态异常"),
        ("复活", "苏生"),
        ("禁用HP回复", "HP回复禁止"),
        ("防御增益", "防御BUFF"),
        ("给予屏障", "屏障"),
        ("赋予屏障", "屏障"),
        ("全行动盘效果", "所有行动盘效果"),
        ("全行动盘効果", "所有行动盘效果"),
        ("HP越低威力越大", "HP越低威力越高"),
        ("解除Debuff", "解除DEBUFF"),
        ("解除debuff", "解除DEBUFF"),
        ("解除Buff", "解除BUFF"),
        ("解除buff", "解除BUFF"),
    ):
        value = value.replace(source, target)

    value = value.replace("概率赋予", "概率")
    value = value.replace("一定几率", "概率")
    value = value.replace("必定赋予", "必定")
    value = value.replace("赋予", "").replace("附带", "")

    value = value.replace("提升", "UP").replace("上升", "UP")
    value = value.replace("降低", "DOWN").replace("下降", "DOWN")

    for source, target in (
        ("造成伤害DOWN", "伤害DOWN"),
        ("攻击UP", "攻击力UP"),
        ("Charge行动盘伤害UP", "Charge盘伤害UP"),
        ("受到的Blast伤害UP", "Blast受到伤害UP"),
        ("Blast受到的伤害UP", "Blast受到伤害UP"),
        ("Charge后所受伤害UP", "Charge后受到伤害UP"),
        ("Charge后受到的伤害UP", "Charge后受到伤害UP"),
        ("状态异常种类越多,伤害越高", "状态异常种类伤害UP"),
        ("全行动盘效果UP", "所有行动盘效果UP"),
        ("全行动盘效果DOWN", "所有行动盘效果DOWN"),
        ("状态异常无效", "异常状态无效"),
        ("对自诅咒", "诅咒自"),
    ):
        value = value.replace(source, target)

    value = re.sub(r"攻击力(?:与|和)防御力DOWN", "攻击力防御力DOWN", value)
    value = re.sub(r"随机(\d+)次\s*造成?伤害", r"随机\1次伤害", value)
    value = value.lower()
    value = re.sub(r'''[\s&＆,，。·・、:：;；“”"'`]''', "", value)
    value = value.replace("（", "(").replace("）", ")")
    return value


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    for path in (REMAINING, AUTHORITY, TRANSCRIPT, LEDGER, PASS9, PASS14_RESIDUAL):
        assert path.is_file(), path

    remaining = read_tsv(REMAINING)
    assert len(remaining) == 208
    assert Counter(row["field"] for row in remaining) == Counter({"shortDescription": 165, "name": 43})
    assert len({(r["file"], r["key"], r["field"]) for r in remaining}) == 208

    authority_all = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    official = authority_all["cardMagiaMap.json"]
    official_by_name: dict[str, list[tuple[str, dict[str, object]]]] = defaultdict(list)
    for key, record in official.items():
        if isinstance(record, dict) and isinstance(record.get("name"), str):
            official_by_name[record["name"]].append((str(key), record))
    for records in official_by_name.values():
        records.sort(key=lambda item: numeric_key(item[0]))

    ledger_rows = read_tsv(LEDGER)
    assert len(ledger_rows) == 571
    ledger_counted = {
        (row["file"], row["stable_key"], row["field"])
        for row in ledger_rows
        if row.get("counts_toward_residual") == "true"
    }

    pass9_rows = read_tsv(PASS9)
    pass9_set = {(r["file"], str(r["key"]), r["field"]) for r in pass9_rows}
    pass14_residual_rows = read_tsv(PASS14_RESIDUAL)
    assert len(pass14_residual_rows) == 9643
    pass14_residual_set = {
        (r["file"], str(r["key"]), r["field"]) for r in pass14_residual_rows
    }

    # Recover the exact transcript claims and source algorithm messages.
    transcript_messages = []
    with TRANSCRIPT.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            message = json.loads(line)
            parts = message.get("parts") or []
            content = "\n".join(str(part) for part in parts)
            if any(
                marker in content
                for marker in (
                    "35 个 current 值能在 2022 国服 dump",
                    "pass18 也已通过",
                    "analyze_pass19_equiv.py",
                    "pass19 的严格等价边界已经闭合",
                    "pass19 已通过全部 gate",
                )
            ):
                transcript_messages.append(
                    {
                        "line": line_number,
                        "id": message.get("id", ""),
                        "role": message.get("role", ""),
                        "recipient": message.get("recipient", ""),
                        "content_sha256": sha256_text(content),
                        "matched_markers": [
                            marker
                            for marker in (
                                "35 个 current 值能在 2022 国服 dump",
                                "pass18 也已通过",
                                "analyze_pass19_equiv.py",
                                "pass19 的严格等价边界已经闭合",
                                "pass19 已通过全部 gate",
                            )
                            if marker in content
                        ],
                    }
                )
    found_markers = {
        marker
        for message in transcript_messages
        for marker in message["matched_markers"]
    }
    assert found_markers == {
        "35 个 current 值能在 2022 国服 dump",
        "pass18 也已通过",
        "analyze_pass19_equiv.py",
        "pass19 的严格等价边界已经闭合",
        "pass19 已通过全部 gate",
    }

    # Pass18: exact current-name matches against official CN cardMagiaMap.
    raw_hits = [
        row
        for row in remaining
        if row["field"] == "name" and row["current"] in official_by_name
    ]
    raw_hits.sort(key=lambda row: numeric_key(row["key"]))
    assert len(raw_hits) == 35

    raw_hit_pairs = {(r["file"], r["key"], r["field"]) for r in raw_hits}
    hit_ledger_overlap = raw_hit_pairs & ledger_counted
    assert hit_ledger_overlap == {("cardMagiaMap.json", "90181", "name")}

    pass18_hit_rows: list[dict[str, object]] = []
    pass18_accepted: list[dict[str, object]] = []
    for row in raw_hits:
        records = official_by_name[row["current"]]
        ids = [key for key, _ in records]
        record_bundle = {key: record for key, record in records}
        pair = (row["file"], row["key"], row["field"])
        overlap = pair in ledger_counted
        original_pass9 = pair in pass9_set
        in_pass14_residual = pair in pass14_residual_set
        source_locator = "authority.json/cardMagiaMap.json/{" + ",".join(ids) + "}/name"
        official_desc_signatures = {
            key: {
                "numeric_roman": list(numeric_roman_signature(str(record.get("shortDescription", "")))),
                "targets": list(target_signature(str(record.get("shortDescription", "")))),
                "turns": list(turn_signature(str(record.get("shortDescription", "")))),
                "directions": list(direction_signature(str(record.get("shortDescription", "")))),
            }
            for key, record in records
        }
        hit = {
            "file": row["file"],
            "key": row["key"],
            "field": row["field"],
            "baseline": row["baseline"],
            "pass8": row["pass8"],
            "current": row["current"],
            "official_name": row["current"],
            "official_family_ids": ",".join(ids),
            "authority_locator": source_locator,
            "source_record_sha256": canonical_record_sha256(record_bundle),
            "official_family_typed_signatures_json": compact_json(official_desc_signatures),
            "name_match": "exact",
            "existing_ledger_overlap": str(overlap).lower(),
            "original_pass9_residual": str(original_pass9).lower(),
            "pass14_residual": str(in_pass14_residual).lower(),
            "accepted_as_new_layer": str(not overlap).lower(),
            "runtime_byte_change": "false",
            "reason": (
                "current name is a byte-exact official CN cardMagiaMap family name; "
                "official family descriptions are retained as typed numeric/Roman/target/turn/direction evidence"
            ),
        }
        pass18_hit_rows.append(hit)
        if not overlap:
            assert original_pass9
            pass18_accepted.append(hit)

    assert len(pass18_accepted) == 34
    assert all(row["original_pass9_residual"] == "true" for row in pass18_accepted)
    assert all(row["existing_ledger_overlap"] == "false" for row in pass18_accepted)

    pass18_pairs = {(r["file"], r["key"], r["field"]) for r in pass18_accepted}
    pass18_remaining_source = [
        {**row, "existing_ledger_covered": str((row["file"], row["key"], row["field"]) in ledger_counted).lower()}
        for row in remaining
        if (row["file"], row["key"], row["field"]) not in pass18_pairs
    ]
    assert len(pass18_remaining_source) == 174
    assert Counter(row["field"] for row in pass18_remaining_source) == Counter(
        {"shortDescription": 165, "name": 9}
    )

    # Pass19: closed mechanical equivalence plus independent typed guards.
    description_rows = [row for row in remaining if row["field"] == "shortDescription"]
    pass19_accepted: list[dict[str, object]] = []
    pass19_rejected: list[dict[str, object]] = []

    for row in sorted(description_rows, key=lambda r: numeric_key(r["key"])):
        baseline = row["baseline"]
        current = row["current"]
        nb = normalize_mechanic(baseline)
        nc = normalize_mechanic(current)
        num_b, num_c = numeric_roman_signature(baseline), numeric_roman_signature(current)
        target_b, target_c = target_signature(baseline), target_signature(current)
        turn_b, turn_c = turn_signature(baseline), turn_signature(current)
        direction_b, direction_c = direction_signature(baseline), direction_signature(current)
        gates = {
            "closed_normalization_equal": nb == nc,
            "numeric_roman_equal": num_b == num_c,
            "target_equal": target_b == target_c,
            "turn_equal": turn_b == turn_c,
            "direction_equal": direction_b == direction_c,
        }
        accepted = all(gates.values())
        pair = (row["file"], row["key"], row["field"])
        failure_reasons = [name for name, value in gates.items() if not value]
        evidence = {
            "file": row["file"],
            "key": row["key"],
            "field": row["field"],
            "baseline": baseline,
            "pass8": row["pass8"],
            "current": current,
            "normalized_baseline": nb,
            "normalized_current": nc,
            "numeric_roman_signature_baseline": sigtext(num_b),
            "numeric_roman_signature_current": sigtext(num_c),
            "target_signature_baseline": sigtext(target_b),
            "target_signature_current": sigtext(target_c),
            "turn_signature_baseline": sigtext(turn_b),
            "turn_signature_current": sigtext(turn_c),
            "direction_signature_baseline": sigtext(direction_b),
            "direction_signature_current": sigtext(direction_c),
            "closed_normalization_equal": str(gates["closed_normalization_equal"]).lower(),
            "numeric_roman_equal": str(gates["numeric_roman_equal"]).lower(),
            "target_equal": str(gates["target_equal"]).lower(),
            "turn_equal": str(gates["turn_equal"]).lower(),
            "direction_equal": str(gates["direction_equal"]).lower(),
            "failure_reasons": ",".join(failure_reasons),
            "authority_type": "pre_llm_baseline_strict_mechanical_equivalence",
            "source_locator": (
                "transcript_replay_remaining_cardMagia_highrisk_208.tsv/"
                + row["key"]
                + "/shortDescription/baseline"
            ),
            "source_record_sha256": canonical_record_sha256(
                {"file": row["file"], "key": row["key"], "field": row["field"], "baseline": baseline}
            ),
            "original_pass9_residual": str(pair in pass9_set).lower(),
            "pass14_residual": str(pair in pass14_residual_set).lower(),
            "existing_ledger_overlap": str(pair in ledger_counted).lower(),
            "runtime_byte_change": "false",
            "reason": (
                "current wording and pre-LLM baseline normalize to the same closed mechanic while all independent "
                "numeric/Roman, target, turn and direction signatures are identical"
                if accepted
                else "fail-closed: " + ",".join(failure_reasons)
            ),
        }
        (pass19_accepted if accepted else pass19_rejected).append(evidence)

    assert len(pass19_accepted) == 162
    assert len(pass19_rejected) == 3
    assert {row["key"] for row in pass19_rejected} == {"90320", "90338", "90347"}
    assert {
        row["key"] for row in pass19_rejected if row["numeric_roman_equal"] == "false"
    } == {"90320"}
    assert {
        row["key"] for row in pass19_rejected if row["direction_equal"] == "false"
    } == {"90338", "90347"}
    assert all(row["target_equal"] == "true" for row in pass19_rejected)
    assert all(row["turn_equal"] == "true" for row in pass19_rejected)
    assert all(row["original_pass9_residual"] == "true" for row in pass19_accepted)
    assert all(row["existing_ledger_overlap"] == "false" for row in pass19_accepted)

    pass19_pairs = {(r["file"], r["key"], r["field"]) for r in pass19_accepted}
    pass19_remaining = [
        row
        for row in pass18_remaining_source
        if (row["file"], row["key"], row["field"]) not in pass19_pairs
    ]
    assert len(pass19_remaining) == 12
    assert Counter(row["field"] for row in pass19_remaining) == Counter(
        {"name": 9, "shortDescription": 3}
    )

    new_pairs = pass18_pairs | pass19_pairs
    assert len(new_pairs) == 196
    assert not (new_pairs & ledger_counted)
    assert all(pair in pass9_set for pair in new_pairs)
    assert all(pair in pass14_residual_set for pair in new_pairs)

    p18_fields = [
        "file",
        "key",
        "field",
        "baseline",
        "pass8",
        "current",
        "official_name",
        "official_family_ids",
        "authority_locator",
        "source_record_sha256",
        "official_family_typed_signatures_json",
        "name_match",
        "existing_ledger_overlap",
        "original_pass9_residual",
        "pass14_residual",
        "accepted_as_new_layer",
        "runtime_byte_change",
        "reason",
    ]
    p19_fields = [
        "file",
        "key",
        "field",
        "baseline",
        "pass8",
        "current",
        "normalized_baseline",
        "normalized_current",
        "numeric_roman_signature_baseline",
        "numeric_roman_signature_current",
        "target_signature_baseline",
        "target_signature_current",
        "turn_signature_baseline",
        "turn_signature_current",
        "direction_signature_baseline",
        "direction_signature_current",
        "closed_normalization_equal",
        "numeric_roman_equal",
        "target_equal",
        "turn_equal",
        "direction_equal",
        "failure_reasons",
        "authority_type",
        "source_locator",
        "source_record_sha256",
        "original_pass9_residual",
        "pass14_residual",
        "existing_ledger_overlap",
        "runtime_byte_change",
        "reason",
    ]

    write_tsv(OUT / "pass18_official_same_name_hits_35.tsv", pass18_hit_rows, p18_fields)
    write_tsv(OUT / "pass18_accepted_official_family_names_34.tsv", pass18_accepted, p18_fields)
    write_tsv(
        OUT / "pass18_remaining_transcript_pool_174.tsv",
        pass18_remaining_source,
        ["file", "key", "field", "baseline", "pass8", "current", "existing_ledger_covered"],
    )
    write_tsv(OUT / "pass19_accepted_strict_equivalence_162.tsv", pass19_accepted, p19_fields)
    write_tsv(OUT / "pass19_rejected_semantic_drift_3.tsv", pass19_rejected, p19_fields)
    write_tsv(
        OUT / "pass19_remaining_transcript_pool_12.tsv",
        pass19_remaining,
        ["file", "key", "field", "baseline", "pass8", "current", "existing_ledger_covered"],
    )

    # Produce a directly appendable ledger overlay.  Sequence values continue
    # the supplied 571-row ledger and may be renumbered by a later merger.
    overlay: list[dict[str, object]] = []
    next_sequence = max(int(row["sequence"]) for row in ledger_rows) + 1
    for row in pass18_accepted:
        overlay.append(
            {
                "sequence": next_sequence,
                "layer": "pass18",
                "file": row["file"],
                "key_field": "dict_key",
                "stable_key": row["key"],
                "field": row["field"],
                "expected_before": row["current"],
                "after": row["current"],
                "runtime_byte_change": "false",
                "counts_toward_residual": "true",
                "original_pass9_residual": "true",
                "authority_tier": "1-linked",
                "authority_type": "official_cn_dump_exact_cardmagia_family_name",
                "source_locator": row["authority_locator"],
                "source_record_sha256": row["source_record_sha256"],
                "wiki_locator": "",
                "wiki_record_sha256": "",
                "note": "byte-exact official CN family name; provenance-only; existing ledger collisions excluded",
            }
        )
        next_sequence += 1
    for row in pass19_accepted:
        overlay.append(
            {
                "sequence": next_sequence,
                "layer": "pass19",
                "file": row["file"],
                "key_field": "dict_key",
                "stable_key": row["key"],
                "field": row["field"],
                "expected_before": row["current"],
                "after": row["current"],
                "runtime_byte_change": "false",
                "counts_toward_residual": "true",
                "original_pass9_residual": "true",
                "authority_tier": "pre_llm_baseline",
                "authority_type": "pre_llm_baseline_strict_mechanical_equivalence",
                "source_locator": row["source_locator"],
                "source_record_sha256": row["source_record_sha256"],
                "wiki_locator": "",
                "wiki_record_sha256": "",
                "note": "closed equivalence plus exact numeric/Roman, target, turn and direction signatures; provenance-only",
            }
        )
        next_sequence += 1
    assert len(overlay) == 196
    assert Counter(row["layer"] for row in overlay) == Counter({"pass19": 162, "pass18": 34})
    write_tsv(OUT / "pass18_19_authority_ledger_overlay_196.tsv", overlay, list(ledger_rows[0].keys()))

    transcript_evidence = {
        "schema": "magireco-pass18-19-transcript-evidence/v1",
        "source_sha256": sha256_file(TRANSCRIPT),
        "messages": transcript_messages,
    }
    (OUT / "transcript_evidence.json").write_text(
        json.dumps(transcript_evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    tsv_names = [
        "pass18_official_same_name_hits_35.tsv",
        "pass18_accepted_official_family_names_34.tsv",
        "pass18_remaining_transcript_pool_174.tsv",
        "pass19_accepted_strict_equivalence_162.tsv",
        "pass19_rejected_semantic_drift_3.tsv",
        "pass19_remaining_transcript_pool_12.tsv",
        "pass18_19_authority_ledger_overlay_196.tsv",
    ]
    verification = {
        "schema": "magireco-pass18-19-rebuild/v1",
        "status": "PASS",
        "scope": "provenance-only; no product files read or changed",
        "inputs": {
            str(REMAINING.relative_to(ROOT)).replace("\\", "/"): sha256_file(REMAINING),
            str(AUTHORITY.relative_to(ROOT)).replace("\\", "/"): sha256_file(AUTHORITY),
            str(TRANSCRIPT.relative_to(ROOT)).replace("\\", "/"): sha256_file(TRANSCRIPT),
            str(LEDGER.relative_to(ROOT)).replace("\\", "/"): sha256_file(LEDGER),
            str(PASS9.relative_to(ROOT)).replace("\\", "/"): sha256_file(PASS9),
            str(PASS14_RESIDUAL.relative_to(ROOT)).replace("\\", "/"): sha256_file(PASS14_RESIDUAL),
        },
        "source_pool": {
            "fields": 208,
            "name_fields": 43,
            "shortDescription_fields": 165,
        },
        "pass18": {
            "official_same_name_hits": 35,
            "existing_ledger_overlap_count": 1,
            "existing_ledger_overlap": ["cardMagiaMap.json/90181/name"],
            "newly_accepted": 34,
            "runtime_changes": 0,
            "transcript_pool_remaining": 174,
        },
        "pass19": {
            "description_candidates": 165,
            "accepted_strict_equivalence": 162,
            "rejected": 3,
            "rejected_keys": ["90320", "90338", "90347"],
            "numeric_roman_mismatch_keys": ["90320"],
            "target_mismatch_keys": [],
            "turn_mismatch_keys": [],
            "direction_mismatch_keys": ["90338", "90347"],
            "runtime_changes": 0,
            "transcript_pool_remaining": 12,
        },
        "guards": {
            "accepted_numeric_roman_mismatches": 0,
            "accepted_target_mismatches": 0,
            "accepted_turn_mismatches": 0,
            "accepted_direction_mismatches": 0,
            "new_layer_fields_outside_original_pass9_residual": 0,
            "new_layer_fields_outside_pass14_residual": 0,
            "new_layer_existing_ledger_duplicates": 0,
            "fuzzy_matching": False,
        },
        "set_intersections": {
            "pass14_residual_size": len(pass14_residual_set),
            "pass18_raw_hits_with_pass14_residual": len(raw_hit_pairs & pass14_residual_set),
            "pass18_new_rows_with_pass14_residual": len(pass18_pairs & pass14_residual_set),
            "pass19_new_rows_with_pass14_residual": len(pass19_pairs & pass14_residual_set),
            "combined_new_rows_with_pass14_residual": len(new_pairs & pass14_residual_set),
            "pass18_raw_hits_with_existing_ledger": len(raw_hit_pairs & ledger_counted),
            "combined_new_rows_with_existing_ledger": len(new_pairs & ledger_counted),
        },
        "combined_new_layer": {
            "fields": 196,
            "runtime_changes": 0,
            "provenance_only": 196,
            "true_residual_delta": 196,
            "input_ledger_remaining_residual": 9274,
            "projected_remaining_residual_after_overlay": 9078,
        },
        "outputs": {name: sha256_file(OUT / name) for name in tsv_names},
        "transcript_evidence_sha256": sha256_file(OUT / "transcript_evidence.json"),
    }
    (OUT / "verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    (OUT / "README.md").write_text(
        "# Pass18 / Pass19 independent rebuild\n\n"
        "This directory independently reconstructs the two provenance-only layers from the frozen 208-field cardMagia pool.\n\n"
        "- Pass18: 35 exact official-CN `cardMagiaMap` family-name hits were reproduced. `90181/name` is already counted in the supplied 571-row ledger, so the new layer contains 34 rows.\n"
        "- Pass19: 165 descriptions were evaluated by a closed lexical normalizer and independent numeric/Roman, target, turn and direction guards. 162 pass; `90320` fails the Roman-rank guard, while `90338` and `90347` fail the direction guard.\n"
        "- All 196 new rows are members of the frozen pass9 residual and have zero overlap with the supplied ledger. Runtime byte changes are zero.\n"
        "- No final integration product file is read or modified.\n\n"
        "Run `python rebuild_pass18_19.py` from any directory to reproduce every report.\n",
        encoding="utf-8",
        newline="\n",
    )

    checksum_files = [
        OUT / "rebuild_pass18_19.py",
        OUT / "README.md",
        *(OUT / name for name in tsv_names),
        OUT / "transcript_evidence.json",
        OUT / "verification.json",
    ]
    checksum_lines = [f"{sha256_file(path)}  {path.name}" for path in sorted(checksum_files, key=lambda p: p.name)]
    (OUT / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="ascii", newline="\n")

    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
