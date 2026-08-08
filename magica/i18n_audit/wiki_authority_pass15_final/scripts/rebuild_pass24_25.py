#!/usr/bin/env python3
"""Rebuild the missing pass24/pass25 non-card equivalence layers.

This script deliberately starts from the independently reconstructed pass14
residual ledger (stable business keys), not from the vanished cloud worktree or
its array-index candidate file.  Runtime JSON is read-only.

Authority order is respected as follows:
* a same-record official-CN value is inspected first and any conflict aborts;
* otherwise the pre-LLM baseline can prove that the pass14 value is only a
  closed orthographic/mechanical normalization, not a new LLM translation.

Pass24 is the narrow Japanese-shinjitai/Traditional-to-Simplified bridge plus a
small closed mechanics notation normalizer.  Pass25 adds a reviewed extended
glyph bridge and the repeated Japanese compound `可能性の因子 -> 可能性因子`.
No fuzzy matching is used.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
BASELINE_LIB = ROOT / "work/archive_audit/baseline/magica/js/libs"
PASS14_LIB = ROOT / "work/pass15_agent_dump/repro_pass14/magica/js/libs"
CURRENT_LIB = ROOT / "work/pass15_agent_rebuild/product/magica/js/libs"
PASS14_RESIDUAL = ROOT / "work/pass15_agent_structure/pass14_residual_reconstructed.tsv"
OFFICIAL = ROOT / "work/pass15_agent_rebuild/inputs/official/authority.json"
COMBINED_LEDGER = ROOT / "work/pass17_max_integrated/release/authority_layer_ledger_571.tsv"
CONVERSATION = ROOT / "work/shared_conversation_extracted.jsonl"
ICU_JAR = OUT / "tools/icu4j-77.1.jar"
ICU_CLASS_DIR = OUT / "tools"

EXPECTED_PASS14_RESIDUAL = 9643

PK = {
    "arenaClassList.json": "arenaBattleFreeRankClass",
    "cardList.json": "cardId",
    "charaList.json": "id",
    "chapterList.json": "chapterId",
    "doppelList.json": "id",
    "enemyList.json": "enemyId",
    "eventList.json": "eventId",
    "eventStoryList.json": "storyIds",
    "formationSheetList.json": "id",
    "giftList.json": "id",
    "itemList.json": "itemCode",
    "patrolAreaList.json": "patrolAreaId",
    "pieceList.json": "pieceId",
    "sectionList.json": "sectionId",
    "shopItemList.json": "id",
}

EXCLUDED_FAMILIES = {
    "cardMagiaMap.json",
    "doppelCardMagiaMap.json",
    "doppelList.json",
}

# This is the exact bridge visible in shared-conversation command 405.
NARROW_BRIDGE = str.maketrans({
    "黒": "黑", "浜": "滨", "織": "织", "鶴": "鹤", "竜": "龙",
    "愛": "爱", "機": "机", "覚": "觉", "結": "结", "願": "愿",
    "燦": "灿", "並": "并", "満": "满", "錦": "锦", "倉": "仓",
    "國": "国", "學": "学", "園": "园", "澤": "泽", "﨑": "崎",
})

# Reviewed extended bridge recoverable from the later full visible-orthography
# script.  NARROW_BRIDGE is applied as well, but a pass25 row must contain at
# least one EXTENDED_ONLY source character so pass24/pass25 remain disjoint.
EXTENDED_ONLY_MAP = {
    "殲": "歼", "戦": "战", "栄": "荣", "穂": "穗", "観": "观",
    "亜": "亚", "紗": "纱", "仮": "假", "薬": "药", "復": "复",
    "撃": "击", "時": "时", "無": "无", "養": "养", "徳": "德",
    "監": "监", "獄": "狱", "電": "电", "車": "车", "団": "团",
    "湯": "汤", "館": "馆", "廃": "废", "広": "广", "樹": "树",
    "塁": "垒", "伝": "传",
}
EXTENDED_BRIDGE = str.maketrans({
    **{chr(k): v for k, v in NARROW_BRIDGE.items()},
    **EXTENDED_ONLY_MAP,
})
EXTENDED_ONLY = set(EXTENDED_ONLY_MAP)

NUMERIC_ROMAN = re.compile(r"\d+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+")
WS = re.compile(r"\s+")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_tsv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=fields, delimiter="\t", lineterminator="\n",
            extrasaction="ignore",
        )
        w.writeheader()
        w.writerows(rows)


def parse_text(value: str) -> str:
    """Pass9/pass14 TSV stores baseline/pass8 strings as JSON literals."""
    try:
        parsed = json.loads(value)
    except Exception:
        return value
    return parsed if isinstance(parsed, str) else value


def load_json_tree(root: Path) -> dict[str, Any]:
    return {
        p.name: json.loads(p.read_text(encoding="utf-8-sig"))
        for p in sorted(root.glob("*.json"))
    }


def stable_map(filename: str, obj: Any) -> dict[str, dict[str, Any]]:
    if isinstance(obj, dict):
        return {str(k): v for k, v in obj.items() if isinstance(v, dict)}
    if not isinstance(obj, list):
        return {}
    if filename == "charaMessageList.json":
        return {
            f"{r.get('charaNo')}|{r.get('messageId')}": r
            for r in obj if isinstance(r, dict)
        }
    if filename == "live2dList.json":
        return {
            f"{r.get('charaId')}|{r.get('live2dId')}": r
            for r in obj if isinstance(r, dict)
        }
    key = PK.get(filename)
    if key is None:
        return {}
    return {
        str(r.get(key)): r
        for r in obj if isinstance(r, dict) and r.get(key) is not None
    }


def icu_simplify(values: list[str], bridge: dict[int, str]) -> list[str]:
    """Batch ICU transform without losing row alignment on embedded newlines."""
    sentinel_lf, sentinel_cr = "\ue000", "\ue001"
    prepared = [
        value.translate(bridge)
        .replace("\r", sentinel_cr)
        .replace("\n", sentinel_lf)
        for value in values
    ]
    cp = f"{ICU_JAR}{';' if sys.platform.startswith('win') else ':'}{ICU_CLASS_DIR}"
    proc = subprocess.run(
        ["java", "-cp", cp, "IcuTransliterate", "Traditional-Simplified"],
        input="\n".join(prepared) + "\n",
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    lines = proc.stdout.splitlines()
    if len(lines) != len(values):
        raise AssertionError(f"ICU row alignment drifted: {len(lines)} != {len(values)}")
    return [x.replace(sentinel_lf, "\n").replace(sentinel_cr, "\r") for x in lines]


def piece_mechanics(value: str) -> str:
    """Closed notation aliases used only for pieceSkill short descriptions."""
    value = value.translate(str.maketrans({"獲": "获", "撃": "击"}))
    aliases = (
        ("Accele MP提升", "Accele MPUP"),
        ("MP获得量提升", "MP获得量UP"),
        ("防御力提升", "防御力UP"),
        ("攻击力提升", "攻击力UP"),
        ("自身", "自"),
    )
    for before, after in aliases:
        value = value.replace(before, after)
    return WS.sub("", value)


def key_field(filename: str) -> str:
    if filename == "charaMessageList.json":
        return "charaNo_messageId"
    if filename == "live2dList.json":
        return "charaId_live2dId"
    return PK.get(filename, "dict_key")


def main() -> int:
    inputs = [
        PASS14_RESIDUAL, OFFICIAL, COMBINED_LEDGER, CONVERSATION, ICU_JAR,
        BASELINE_LIB / "itemList.json", PASS14_LIB / "itemList.json",
        CURRENT_LIB / "itemList.json",
    ]
    for path in inputs:
        if not path.exists():
            raise FileNotFoundError(path)

    residual = read_tsv(PASS14_RESIDUAL)
    if len(residual) != EXPECTED_PASS14_RESIDUAL:
        raise AssertionError(f"pass14 residual drifted: {len(residual)}")

    baseline_obj = load_json_tree(BASELINE_LIB)
    pass14_obj = load_json_tree(PASS14_LIB)
    current_obj = load_json_tree(CURRENT_LIB)
    baseline_idx = {fn: stable_map(fn, obj) for fn, obj in baseline_obj.items()}
    pass14_idx = {fn: stable_map(fn, obj) for fn, obj in pass14_obj.items()}
    current_idx = {fn: stable_map(fn, obj) for fn, obj in current_obj.items()}
    official_all = json.loads(OFFICIAL.read_text(encoding="utf-8"))
    official_idx = {
        fn: stable_map(fn, obj) for fn, obj in official_all.items()
        if fn.endswith(".json")
    }

    universe: list[dict[str, Any]] = []
    verification_failures: list[str] = []
    for source in residual:
        fn, stable_key, field = source["file"], source["key"], source["field"]
        if fn in EXCLUDED_FAMILIES:
            continue
        baseline = parse_text(source["baseline"])
        pass14_value = source["release"]
        if not isinstance(baseline, str) or not isinstance(pass14_value, str):
            continue
        b_rec = baseline_idx.get(fn, {}).get(stable_key)
        p_rec = pass14_idx.get(fn, {}).get(stable_key)
        c_rec = current_idx.get(fn, {}).get(stable_key)
        baseline_verified = isinstance(b_rec, dict) and b_rec.get(field) == baseline
        pass14_verified = isinstance(p_rec, dict) and p_rec.get(field) == pass14_value
        # Some unrelated residual rows represent records absent from the old
        # baseline, and some composite-key lists contain duplicate revisions.
        # Fail closed only if a row selected by pass24/pass25 is not verified.
        if not baseline_verified:
            verification_failures.append(f"baseline:{fn}/{stable_key}/{field}")
        if not pass14_verified:
            verification_failures.append(f"pass14:{fn}/{stable_key}/{field}")
        current_value = c_rec.get(field) if isinstance(c_rec, dict) else None
        official_rec = official_idx.get(fn, {}).get(stable_key)
        official_value = official_rec.get(field) if isinstance(official_rec, dict) else None
        universe.append({
            "file": fn,
            "stable_key": stable_key,
            "field": field,
            "baseline": baseline,
            "pass14_value": pass14_value,
            "current_product_value": current_value if isinstance(current_value, str) else "",
            "official_value": official_value if isinstance(official_value, str) else "",
            "baseline_record_verified": baseline_verified,
            "pass14_record_verified": pass14_verified,
        })

    narrow_values = icu_simplify([r["baseline"] for r in universe], NARROW_BRIDGE)
    for row, simplified in zip(universe, narrow_values):
        row["narrow_simplified"] = simplified

    pass24: list[dict[str, Any]] = []
    pass24_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in universe:
        fn, field = row["file"], row["field"]
        # The 21 areaDetailName narrow rows are later pass28/pass29 sequence
        # transitions; keeping them out prevents the known double deduction.
        if field == "areaDetailName":
            continue
        simplified = row["narrow_simplified"]
        current = row["pass14_value"]
        kind = ""
        norm_b = simplified
        norm_c = current
        if simplified == current:
            kind = "narrow_glyph_exact"
        elif fn == "cardList.json" and field == "cardName":
            norm_b, norm_c = WS.sub("", simplified), WS.sub("", current)
            if norm_b == norm_c:
                kind = "narrow_glyph_plus_whitespace"
        elif fn == "pieceSkillMap.json" and field == "shortDescription":
            norm_b, norm_c = piece_mechanics(simplified), piece_mechanics(current)
            if norm_b == norm_c:
                kind = "narrow_glyph_plus_closed_mechanics_notation"
        if not kind:
            continue
        if NUMERIC_ROMAN.findall(row["baseline"]) != NUMERIC_ROMAN.findall(current):
            raise AssertionError(f"pass24 signature drift: {fn}/{row['stable_key']}/{field}")
        out = dict(row)
        out.update({
            "equivalence_kind": kind,
            "normalized_baseline": norm_b,
            "normalized_pass14": norm_c,
            "numeric_roman_signature": json.dumps(NUMERIC_ROMAN.findall(current), ensure_ascii=False),
            "runtime_byte_change": "false",
            "counts_toward_pass14_residual": "true",
            "reason": (
                "closed Japanese-shinjitai/Traditional-to-Simplified bridge"
                if kind == "narrow_glyph_exact" else
                "closed glyph bridge plus field-typed notation normalization; no fuzzy matching"
            ),
        })
        triple = (fn, row["stable_key"], field)
        pass24_by_key[triple] = out
        pass24.append(out)

    extended_values = icu_simplify([r["baseline"] for r in universe], EXTENDED_BRIDGE)
    pass25: list[dict[str, Any]] = []
    for row, simplified in zip(universe, extended_values):
        triple = (row["file"], row["stable_key"], row["field"])
        if triple in pass24_by_key:
            continue
        # areaDetailName narrow rows were intentionally deferred to the later
        # location sequence layer; do not let pass25 re-admit them merely
        # because their source also contains an extended trigger character.
        if row["field"] == "areaDetailName" and row["narrow_simplified"] == row["pass14_value"]:
            continue
        current = row["pass14_value"]
        kind = ""
        norm_b, norm_c = simplified, current
        if set(row["baseline"]) & EXTENDED_ONLY and simplified == current:
            kind = "extended_jp_glyph_exact"
        elif row["baseline"] == "可能性の因子" and current == "可能性因子":
            norm_b = row["baseline"].replace("の", "")
            if norm_b == current:
                kind = "closed_japanese_compound_particle_normalization"
        if not kind:
            continue
        if NUMERIC_ROMAN.findall(row["baseline"]) != NUMERIC_ROMAN.findall(current):
            raise AssertionError(
                f"pass25 signature drift: {row['file']}/{row['stable_key']}/{row['field']}"
            )
        out = dict(row)
        out.update({
            "equivalence_kind": kind,
            "normalized_baseline": norm_b,
            "normalized_pass14": norm_c,
            "numeric_roman_signature": json.dumps(NUMERIC_ROMAN.findall(current), ensure_ascii=False),
            "runtime_byte_change": "false",
            "counts_toward_pass14_residual": "true",
            "reason": (
                "reviewed extended Japanese-shinjitai glyph bridge plus ICU Traditional-Simplified"
                if kind == "extended_jp_glyph_exact" else
                "closed repeated Japanese compound particle normalization; exact pair only"
            ),
        })
        pass25.append(out)

    pass24.sort(key=lambda r: (r["file"], r["stable_key"], r["field"]))
    pass25.sort(key=lambda r: (r["file"], r["stable_key"], r["field"]))
    selected_source_failures = [
        f"{r['file']}/{r['stable_key']}/{r['field']}"
        for r in pass24 + pass25
        if not r["baseline_record_verified"] or not r["pass14_record_verified"]
    ]
    if selected_source_failures:
        raise AssertionError(
            "selected stable-key source verification failed: "
            + repr(selected_source_failures[:10])
        )
    for rows in (pass24, pass25):
        for i, row in enumerate(rows, 1):
            row["sequence"] = i
            row["key_field"] = key_field(row["file"])
            ov = row["official_value"]
            if ov == row["pass14_value"] and ov:
                relation = "official_same_record_current_exact"
            elif ov == row["baseline"] and ov:
                relation = "official_same_record_baseline_conflict"
            elif ov:
                relation = "official_same_record_other_conflict"
            else:
                relation = "official_same_record_absent"
            row["official_relation"] = relation

    official_conflicts = [
        r for r in pass24 + pass25
        if r["official_relation"] in {
            "official_same_record_baseline_conflict", "official_same_record_other_conflict"
        }
    ]
    if official_conflicts:
        raise AssertionError("official-CN conflict in equivalence layer: " + repr(official_conflicts[:3]))

    p24_set = {(r["file"], r["stable_key"], r["field"]) for r in pass24}
    p25_set = {(r["file"], r["stable_key"], r["field"]) for r in pass25}
    if p24_set & p25_set:
        raise AssertionError("pass24/pass25 must be disjoint")

    combined = read_tsv(COMBINED_LEDGER)
    ledger_by_triple: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in combined:
        t = (row["file"], row["stable_key"], row["field"])
        ledger_by_triple.setdefault(t, []).append(row)

    overlap_rows: list[dict[str, Any]] = []
    for layer, rows in (("pass24", pass24), ("pass25", pass25)):
        for row in rows:
            t = (row["file"], row["stable_key"], row["field"])
            hits = ledger_by_triple.get(t, [])
            counting = [x for x in hits if x.get("counts_toward_residual") == "true"]
            current_value = row["current_product_value"]
            if current_value == row["pass14_value"]:
                current_relation = "unchanged_since_pass14"
            elif hits and current_value == hits[-1].get("after"):
                current_relation = "verified_later_sequential_transition"
            else:
                current_relation = "unexplained_current_drift"
            row["current_product_relation"] = current_relation
            row["current_net_new_residual_delta"] = "false" if counting else "true"
            if current_relation == "unexplained_current_drift":
                raise AssertionError(
                    f"current product drift: {row['file']}/{row['stable_key']}/{row['field']}"
                )
            if hits:
                overlap_rows.append({
                    "candidate_layer": layer,
                    "file": row["file"],
                    "stable_key": row["stable_key"],
                    "field": row["field"],
                    "candidate_value": row["pass14_value"],
                    "current_product_value": current_value,
                    "existing_layers": ",".join(x["layer"] for x in hits),
                    "existing_counting_layers": ",".join(x["layer"] for x in counting),
                    "current_product_relation": current_relation,
                    "counts_as_new_now": "false" if counting else "true",
                })

    # The old pass24 summary's item count 47 is exactly 34 proper pass24 item
    # rows plus these 13 pass25 item rows.  Record this as a reproducible
    # double-count signature rather than silently forcing pass24 to 86.
    p25_item = [r for r in pass25 if r["file"] == "itemList.json"]
    old_signature = []
    for row in p25_item:
        old_signature.append({
            "file": row["file"], "stable_key": row["stable_key"],
            "field": row["field"], "baseline": row["baseline"],
            "pass14_value": row["pass14_value"],
            "proper_layer": "pass25", "exclude_from_pass24": "true",
            "reason": "this is an extended-glyph/compound row, not a narrow pass24 row",
        })

    fields = [
        "sequence", "file", "key_field", "stable_key", "field", "baseline",
        "pass14_value", "current_product_value", "equivalence_kind",
        "normalized_baseline", "normalized_pass14", "numeric_roman_signature",
        "official_relation", "official_value", "current_product_relation",
        "runtime_byte_change", "counts_toward_pass14_residual",
        "current_net_new_residual_delta", "reason",
    ]
    p24_path = OUT / "pass24_strict_narrow_mechanical_73.tsv"
    p25_path = OUT / "pass25_extended_glyph_equivalence_52.tsv"
    write_tsv(p24_path, pass24, fields)
    write_tsv(p25_path, pass25, fields)
    write_tsv(
        OUT / "prior_and_later_layer_overlaps.tsv", overlap_rows,
        [
            "candidate_layer", "file", "stable_key", "field", "candidate_value",
            "current_product_value", "existing_layers", "existing_counting_layers",
            "current_product_relation", "counts_as_new_now",
        ],
    )
    write_tsv(
        OUT / "old_pass24_pass25_double_count_signature_13.tsv", old_signature,
        [
            "file", "stable_key", "field", "baseline", "pass14_value",
            "proper_layer", "exclude_from_pass24", "reason",
        ],
    )

    # Preserve compact, exact transcript evidence without copying the full chat.
    conversation_rows = [json.loads(x) for x in CONVERSATION.read_text(encoding="utf-8").splitlines()]
    evidence_indices = [405, 408, 409, 412, 480]
    conversation_evidence = []
    for index in evidence_indices:
        row = conversation_rows[index]
        text = "\n".join(str(x) for x in row.get("parts", []))
        conversation_evidence.append({
            "index": index,
            "role": row.get("role"),
            "recipient": row.get("recipient"),
            "content_type": row.get("content_type"),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text": text,
        })
    (OUT / "conversation_evidence.json").write_text(
        json.dumps(conversation_evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    p24_dist = dict(sorted(Counter(r["file"] for r in pass24).items()))
    p25_dist = dict(sorted(Counter(r["file"] for r in pass25).items()))
    overlap_dist = dict(sorted(Counter(r["existing_counting_layers"] for r in overlap_rows).items()))
    p24_net = sum(r["current_net_new_residual_delta"] == "true" for r in pass24)
    p25_net = sum(r["current_net_new_residual_delta"] == "true" for r in pass25)
    verification = {
        "schema": "magireco-cn-pass24-pass25-independent-rebuild/v1",
        "status": "PASS",
        "inputs": {
            str(path.relative_to(ROOT)).replace("\\", "/"): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in inputs
        },
        "conversation_evidence_indices": evidence_indices,
        "conversation_hidden_pass24_or_pass25_script_recovered": False,
        "pass14_residual_input": len(residual),
        "stable_key_source_verification_failures": 0,
        "fuzzy_matching_used": False,
        "runtime_product_files_written": 0,
        "pass24": {
            "strict_disjoint_rows": len(pass24),
            "by_file": p24_dist,
            "numeric_roman_signature_failures": 0,
            "official_same_record_conflicts": 0,
            "net_new_against_current_combined_ledger": p24_net,
        },
        "pass25": {
            "strict_disjoint_rows": len(pass25),
            "by_file": p25_dist,
            "extended_glyph_rows": sum(r["equivalence_kind"] == "extended_jp_glyph_exact" for r in pass25),
            "closed_particle_rows": sum(r["equivalence_kind"] == "closed_japanese_compound_particle_normalization" for r in pass25),
            "numeric_roman_signature_failures": 0,
            "official_same_record_conflicts": 0,
            "net_new_against_current_combined_ledger": p25_net,
        },
        "pass24_pass25_intersection": len(p24_set & p25_set),
        "existing_layer_overlap_rows": len(overlap_rows),
        "existing_layer_overlap_profile": overlap_dist,
        "old_reported_pass24_86_reproducible_correction": {
            "proper_pass24": len(pass24),
            "pass25_item_rows_improperly_added_to_pass24": len(old_signature),
            "reproduces_old_86": len(pass24) + len(old_signature),
            "old_item_47_decomposition": {
                "proper_pass24_item": p24_dist.get("itemList.json", 0),
                "pass25_item_overlap": len(old_signature),
            },
            "decision": "keep layers disjoint; do not deduct the 13 item rows twice",
        },
        "net_new_residual_delta_against_current_combined_ledger": p24_net + p25_net,
        "notes": [
            "The hidden cloud apply scripts were not present in the recovered conversation; command 480 only records an attempted sed read whose output was redacted.",
            "Pass24 areaDetailName rows already represented by later pass28/pass29 sequence work are excluded from pass24 reconstruction.",
            "One pass25 section areaDetailName row is a verified later pass29 sequential punctuation transition and is not a new current-ledger deduction.",
        ],
    }

    # General rules must independently produce the historically indicated
    # profiles; assertions guard source drift, they do not select rows.
    expected_p24 = {
        "cardList.json": 2,
        "charaMessageList.json": 2,
        "emotionSkillMap.json": 1,
        "itemList.json": 34,
        "live2dList.json": 1,
        "pieceSkillMap.json": 7,
        "sectionList.json": 11,
        "shopItemList.json": 15,
    }
    expected_p25 = {
        "itemList.json": 13,
        "sectionList.json": 31,
        "shopItemList.json": 8,
    }
    if p24_dist != expected_p24:
        raise AssertionError(f"pass24 independently generated profile drifted: {p24_dist}")
    if p25_dist != expected_p25:
        raise AssertionError(f"pass25 independently generated profile drifted: {p25_dist}")
    if len(pass24) != 73 or len(pass25) != 52 or len(old_signature) != 13:
        raise AssertionError((len(pass24), len(pass25), len(old_signature)))

    (OUT / "verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    readme = f"""# Pass24 / Pass25 independent reconstruction

This directory reconstructs the missing cloud-only provenance layers from stable
business keys and verifies every row against the baseline, pass14 product, official
CN authority map, and current combined product. No runtime JSON is modified.

## Correct disjoint result

* pass24: **{len(pass24)}** strict narrow-glyph/mechanics rows ({p24_dist})
* pass25: **{len(pass25)}** extended-glyph/closed-compound rows ({p25_dist})
* pass24/pass25 intersection: **0**
* net new residual deductions against the current combined ledger: **{p24_net + p25_net}**

The old `pass24 = 86` summary is reproducibly explained by adding pass25's 13
`itemList` rows to the proper pass24 set: `73 + 13 = 86`, and its stated item
profile becomes `34 + 13 = 47`. Those same 13 rows also occur in the independently
generated pass25 set, so counting 86 and 52 as disjoint deductions would deduct
them twice. `old_pass24_pass25_double_count_signature_13.tsv` records the exact rows.

One pass25 row (`sectionList/208102/areaDetailName`) already has a later pass29
punctuation transition in the current ledger, so it is retained as pass25 evidence
but does not create a second current-ledger residual deduction.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    # Hash final roles except the checksum file itself.
    artifact_names = [
        "README.md",
        "conversation_evidence.json",
        "old_pass24_pass25_double_count_signature_13.tsv",
        "pass24_strict_narrow_mechanical_73.tsv",
        "pass25_extended_glyph_equivalence_52.tsv",
        "prior_and_later_layer_overlaps.tsv",
        "rebuild_pass24_25.py",
        "tools/IcuTransliterate.class",
        "tools/IcuTransliterate.java",
        "tools/icu4j-77.1.jar",
        "verification.json",
    ]
    sums = []
    for name in artifact_names:
        path = OUT / name
        sums.append(f"{sha256(path)}  {name}")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps(verification, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
