#!/usr/bin/env python3
"""Build the occurrence-level human review checklist from verified change logs."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


AUDIT = Path(__file__).resolve().parents[1]
RUNTIME_LOG = AUDIT / "runtime_change_log.tsv"
UI_LOG = AUDIT / "ui_change_log.tsv"
OUTPUT = AUDIT / "manual_translation_review_checklist.tsv"
SUMMARY = AUDIT / "manual_translation_review_checklist.summary.json"
UNIQUE_OUTPUT = AUDIT / "manual_unique_review_checklist.tsv"
COLUMNS = [
    "status", "risk", "file", "key_or_line", "field", "original_text",
    "final_cn", "category", "source_tier", "source_path", "reviewer_check", "notes",
]


def nonempty(value: str, fallback: str) -> str:
    return value if value else fallback


def main() -> None:
    out: list[dict[str, str]] = []
    with RUNTIME_LOG.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            action = row["action"]
            preserved = action == "authority_preserved"
            pointer = row["pointer"]
            out.append({
                "status": "权威原文保留待确认" if preserved else "待人工校对",
                "risk": nonempty(row["risk"], "medium"),
                "file": "magica/js/libs/" + row["dictionary"],
                "key_or_line": pointer,
                "field": pointer.rsplit("/", 1)[-1] or "root",
                "original_text": row["original_text"],
                "final_cn": row["final_cn"],
                "category": action,
                "source_tier": row["source_tier"],
                "source_path": nonempty(row["source_path"], "Pass16人工审校记录"),
                "reviewer_check": "□核对专名、数值、范围、回合与同族字段",
                "notes": "指定Wiki中文字段原样保留，不以人工改写覆盖" if preserved else "逐字段变更；结构键与非字符串值不得改变",
            })
    with UI_LOG.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            source = nonempty(row["source"], "Pass16人工审校记录")
            tier = "2_designated_wiki" if "Wiki" in source else "3_manual_static_review"
            out.append({
                "status": "待人工校对",
                "risk": nonempty(row["risk"], "medium"),
                "file": row["file"],
                "key_or_line": "line:" + row["line"],
                "field": "visible_text_or_string",
                "original_text": row["original_text"],
                "final_cn": row["final_cn"],
                "category": row["category"],
                "source_tier": tier,
                "source_path": source,
                "reviewer_check": "□核对页面语义、术语、占位符与标签结构",
                "notes": "静态界面逐槽位审校；不得改变ID、class、链接或模板表达式",
            })
    for row in out:
        for key in COLUMNS:
            if not row[key]:
                raise RuntimeError(f"empty checklist cell: {key}: {row}")
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(out)
    # Compact reviewer entry point: the 15 personally translated runtime texts
    # plus the two designated-Wiki strings intentionally preserved verbatim.
    source_context = {
        row["text"]: row
        for row in csv.DictReader(
            (AUDIT / "source_evidence" / "runtime_candidates_classified.tsv").open("r", encoding="utf-8", newline=""),
            delimiter="\t",
        )
    }
    map_rows = list(csv.DictReader((AUDIT / "runtime_translation_map.tsv").open("r", encoding="utf-8", newline=""), delimiter="\t"))
    unique_fields = [
        "status", "risk", "original_text", "final_cn", "occurrences", "dictionaries", "fields",
        "source_tier", "source_path", "review_focus", "notes",
    ]
    with UNIQUE_OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=unique_fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in map_rows:
            if not (row["source_tier"].startswith("3_") or row["source_tier"].endswith("_preserved")):
                continue
            ctx = source_context[row["original_text"]]
            preserved = row["original_text"] == row["final_cn"]
            writer.writerow({
                "status": "权威原文保留待确认" if preserved else "待人工校对",
                "risk": row["risk"], "original_text": row["original_text"], "final_cn": row["final_cn"],
                "occurrences": row["expected_occurrences"], "dictionaries": ctx["dictionaries"], "fields": ctx["fields"],
                "source_tier": row["source_tier"], "source_path": row["source_path"],
                "review_focus": "确认是否继续服从指定Wiki原文" if preserved else "核对人工定译及国服标点风格",
                "notes": row["translation_note"],
            })
    data = OUTPUT.read_bytes()
    summary = {
        "schema": "magireco-cn-pass16-manual-review/v1",
        "checklist_path": "magica/i18n_audit/manual_cn_pass16/manual_translation_review_checklist.tsv",
        "checklist_sha256": hashlib.sha256(data).hexdigest(),
        "row_count": len(out),
        "rows": len(out),
        "sha256": hashlib.sha256(data).hexdigest(),
        "status_counts": dict(Counter(row["status"] for row in out)),
        "risk_counts": dict(Counter(row["risk"] for row in out)),
        "category_counts": dict(Counter(row["category"] for row in out)),
        "source_tier_counts": dict(Counter(row["source_tier"] for row in out)),
        "changed_file_count": len({row["file"] for row in out}),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
