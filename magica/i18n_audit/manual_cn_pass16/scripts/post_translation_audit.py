#!/usr/bin/env python3
"""Verify that Pass16 has no unresolved player-visible untranslated candidate."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


AUDIT = Path(__file__).resolve().parents[1]
REPO = AUDIT.parents[2]
LIBS = REPO / "magica" / "js" / "libs"
MAP = AUDIT / "runtime_translation_map.tsv"
SOURCE = AUDIT / "source_evidence"
REPORT = AUDIT / "post_translation_audit.json"
PRESERVED = AUDIT / "authority_preserved_exceptions.tsv"
REMAINING = AUDIT / "untranslated_remaining.tsv"


def string_leaves(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from string_leaves(child)
    elif isinstance(value, list):
        for child in value:
            yield from string_leaves(child)
    elif isinstance(value, str):
        yield value


def main() -> None:
    map_rows = list(csv.DictReader(MAP.open("r", encoding="utf-8", newline=""), delimiter="\t"))
    originals = {row["original_text"]: row for row in map_rows}
    counts = Counter()
    for path in sorted(LIBS.glob("*.json")):
        for value in string_leaves(json.loads(path.read_text(encoding="utf-8"))):
            if value in originals:
                counts[value] += 1
    preserved_rows = [row for row in map_rows if row["original_text"] == row["final_cn"]]
    unexpected_runtime = []
    for row in map_rows:
        old = row["original_text"]
        expected = int(row["expected_occurrences"]) if old == row["final_cn"] else 0
        if counts[old] != expected:
            unexpected_runtime.append({"text": old, "expected": expected, "actual": counts[old]})

    static_remaining = []
    excluded = {"不指定", "・"}
    for kind, source_name in (
        ("js", "js_untranslated_candidates_before.tsv"),
        ("html", "html_untranslated_candidates_before.tsv"),
    ):
        with (SOURCE / source_name).open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                old = row["exact_text"]
                if old in excluded:
                    continue
                path = REPO / row["file"]
                if old in path.read_text(encoding="utf-8"):
                    static_remaining.append({"kind": kind, "file": row["file"], "text": old})

    raw = json.loads((SOURCE / "post_runtime_raw_summary.json").read_text(encoding="utf-8"))
    authority = json.loads((SOURCE / "runtime_authority_lookup_148_summary.json").read_text(encoding="utf-8"))
    status = "PASS" if not unexpected_runtime and not static_remaining and raw["actual_kana_outside_credit_fields"] == 0 else "FAIL"
    report = {
        "schema": "magireco-cn-pass16-post-translation-audit/v1",
        "status": status,
        "runtime_unique_candidates_reviewed": len(map_rows),
        "runtime_occurrences_reviewed": sum(int(row["expected_occurrences"]) for row in map_rows),
        "authority_matches": authority["authoritative_matches"],
        "authority_tier_counts": authority["tier_counts"],
        "manual_unique_translations": sum(row["source_tier"].startswith("3_") for row in map_rows),
        "authority_preserved_unique": len(preserved_rows),
        "unresolved_runtime_unique": len(unexpected_runtime),
        "unresolved_static_candidates": len(static_remaining),
        "actual_kana_outside_credit_fields": raw["actual_kana_outside_credit_fields"],
        "unexpected_runtime": unexpected_runtime,
        "static_remaining": static_remaining,
        "conclusion": "无尚待中文化的玩家可见候选；两条指定Wiki中文字段按权威原文保留。" if status == "PASS" else "仍有待处理项。",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    with PRESERVED.open("w", encoding="utf-8", newline="") as f:
        fields = ["original_text", "final_cn", "expected_occurrences", "source_tier", "source_path", "translation_note"]
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(preserved_rows)
    with REMAINING.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["kind", "file", "text"], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(static_remaining)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
