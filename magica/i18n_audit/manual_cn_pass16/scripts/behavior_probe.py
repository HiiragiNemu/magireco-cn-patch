#!/usr/bin/env python3
"""Literal baseline/final behavior probe used by the release verification record."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def leaves(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from leaves(child)
    elif isinstance(value, str):
        yield value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--expected", choices=("baseline", "final"), required=True)
    parser.add_argument("--audit", type=Path, help="evidence folder; defaults to TREE/magica/i18n_audit/manual_cn_pass16")
    args = parser.parse_args()
    tree = args.tree.resolve()
    audit = args.audit.resolve() if args.audit else tree / "magica" / "i18n_audit" / "manual_cn_pass16"
    mapping = list(csv.DictReader((audit / "runtime_translation_map.tsv").open("r", encoding="utf-8", newline=""), delimiter="\t"))
    value_counts: dict[str, int] = {}
    for path in sorted((tree / "magica" / "js" / "libs").glob("*.json")):
        for value in leaves(json.loads(path.read_text(encoding="utf-8"))):
            value_counts[value] = value_counts.get(value, 0) + 1
    preserved = {row["original_text"] for row in mapping if row["original_text"] == row["final_cn"]}
    runtime_changed_originals = sum(value_counts.get(row["original_text"], 0) for row in mapping if row["original_text"] != row["final_cn"])
    runtime_preserved = sum(value_counts.get(value, 0) for value in preserved)

    excluded = {"不指定", "・"}
    static_matches = []
    for kind, name in (("js", "js_untranslated_candidates_before.tsv"), ("html", "html_untranslated_candidates_before.tsv")):
        for row in csv.DictReader((audit / "source_evidence" / name).open("r", encoding="utf-8", newline=""), delimiter="\t"):
            if row["exact_text"] in excluded:
                continue
            text = (tree / row["file"]).read_text(encoding="utf-8")
            if row["exact_text"] in text:
                static_matches.append({"kind": kind, "file": row["file"], "text": row["exact_text"]})

    items = json.loads((tree / "magica" / "js" / "libs" / "itemList.json").read_text(encoding="utf-8"))
    coins = [record for record in items if isinstance(record, dict) and str(record.get("itemCode", "")).startswith("GACHA_FREEBIE") and "MEDAL" in str(record.get("itemCode", ""))]
    authoritative_coin_triples = sum(
        record.get("name") == "调整专家币"
        and record.get("shortDescription") == "调整专家币"
        and record.get("description") == "在「调整专家币」中用于兑换的道具"
        for record in coins
    )
    shop_items = json.loads((tree / "magica" / "js" / "libs" / "shopItemList.json").read_text(encoding="utf-8"))
    gold_ascii = sum(isinstance(record, dict) and record.get("name") == "3周年DX福袋(金)" for record in shop_items)
    gold_fullwidth = sum(isinstance(record, dict) and record.get("name") == "3周年DX福袋（金）" for record in shop_items)
    ready_count = value_counts.get("准备完毕", 0)
    cemetery_count = value_counts.get("神滨市营陵园", 0)
    message_by_key = {
        f"{record.get('charaNo')}_{record.get('messageId')}": record.get("message", "")
        for record in json.loads((tree / "magica" / "js" / "libs" / "charaMessageList.json").read_text(encoding="utf-8"))
        if isinstance(record, dict)
    }
    multiline_layout_ok = (
        message_by_key.get("1040_1", "").count("\n") == 6
        and message_by_key.get("1040_2", "").count("\n") == 3
        and "\\n" not in message_by_key.get("1040_1", "")
        and "\\n" not in message_by_key.get("1040_2", "")
    )
    errors = []
    if args.expected == "baseline":
        if runtime_changed_originals + runtime_preserved != 654:
            errors.append("baseline runtime candidate count is not 654")
        if not static_matches:
            errors.append("baseline static candidates unexpectedly absent")
        if authoritative_coin_triples == 225:
            errors.append("baseline already has final adjustment-expert coin triples")
        if gold_ascii != 1 or gold_fullwidth != 0:
            errors.append("baseline DX gold lucky-bag punctuation is not the expected ASCII form")
    else:
        if runtime_changed_originals != 0:
            errors.append("final tree still contains replaced runtime originals")
        if runtime_preserved != 2:
            errors.append("final authority-preserved count is not 2")
        if static_matches:
            errors.append("final tree still contains static untranslated candidates")
        if authoritative_coin_triples != 225:
            errors.append("final adjustment-expert coin triples are not 225/225")
        if gold_ascii != 0 or gold_fullwidth != 1:
            errors.append("final DX gold lucky-bag punctuation is not harmonized")
        if ready_count != 1 or cemetery_count != 2:
            errors.append("final personally translated precision terms are missing")
        if not multiline_layout_ok:
            errors.append("final multiline character-message layout drifted")
    result = {
        "schema": "magireco-cn-pass16-behavior-probe/v1",
        "expected": args.expected,
        "status": "PASS" if not errors else "FAIL",
        "runtime_replaced_original_instances": runtime_changed_originals,
        "runtime_authority_preserved_instances": runtime_preserved,
        "static_untranslated_candidate_matches": len(static_matches),
        "adjustment_expert_coin_records": len(coins),
        "authoritative_adjustment_expert_coin_triples": authoritative_coin_triples,
        "dx_gold_ascii_records": gold_ascii,
        "dx_gold_fullwidth_records": gold_fullwidth,
        "personally_translated_ready_count": ready_count,
        "personally_translated_cemetery_count": cemetery_count,
        "multiline_character_message_layout_ok": multiline_layout_ok,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
