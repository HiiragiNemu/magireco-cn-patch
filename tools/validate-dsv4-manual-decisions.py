#!/usr/bin/env python3
"""Validate human decisions for the frozen DSV4 manual-handoff inventory.

This tool is read-only.  It neither edits the product tree nor applies a
translation.  The JSONL is the immutable source/evidence inventory; reviewers
edit only a copy of the TSV and run this validator before any later, separately
approved application step.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


HEX64 = re.compile(r"^[0-9a-f]{64}$")
ISO_8601 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
TOTAL = 440


class DecisionError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_source(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise DecisionError("manual-required source JSONL must be a regular file")
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf") or b"\r\n" in data:
        raise DecisionError("manual-required source must be UTF-8/LF without BOM")
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line]
    if len(rows) != TOTAL:
        raise DecisionError(f"manual-required source must contain exactly {TOTAL} rows")
    for row in rows:
        item = row.get("source_item")
        if not isinstance(item, dict) or hashlib.sha256(canonical_json_bytes(item)).hexdigest() != row.get("source_item_sha256"):
            raise DecisionError(f"source item hash mismatch: {row.get('item_id')}")
    ids = [row.get("item_id") for row in rows]
    if any(not isinstance(item_id, str) or not item_id for item_id in ids) or len(set(ids)) != TOTAL:
        raise DecisionError("manual-required source IDs are not unique")
    return rows


def _blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def validate(source: Path, decisions: Path) -> dict[str, Any]:
    source_rows = load_source(source)
    if decisions.is_symlink() or not decisions.is_file():
        raise DecisionError("decision TSV must be a regular file")
    data = decisions.read_bytes()
    if data.startswith(b"\xef\xbb\xbf") or b"\r\n" in data:
        raise DecisionError("decision TSV must be UTF-8/LF without BOM")
    reader = csv.DictReader(data.decode("utf-8").splitlines(), delimiter="\t")
    rows = list(reader)
    required = {
        "source_index", "batch_number", "item_id", "stable_business_key", "source_text_sha256",
        "old_cn_sha256", "source_item_sha256", "protected_authority_text", "current_cn", "wiki_cn",
        "human_decision", "reviewer", "reviewed_at", "final_value", "human_notes",
    }
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise DecisionError(f"decision TSV missing fields: {sorted(required-set(reader.fieldnames or []))}")
    if len(rows) != TOTAL:
        raise DecisionError(f"decision TSV must contain exactly {TOTAL} rows")
    states = {"pending": 0, "approved_current": 0, "revised": 0, "kept_authority": 0, "unresolved": 0}
    for source_row, row in zip(source_rows, rows):
        item = source_row["source_item"]
        identity = (
            str(source_row["source_index"]), str(source_row["batch_number"]), source_row["item_id"],
            source_row["stable_business_key"], source_row["source_item_sha256"],
            item.get("source_text_sha256", ""), item.get("old_cn_sha256", ""),
        )
        actual = (
            row["source_index"], row["batch_number"], row["item_id"], row["stable_business_key"],
            row["source_item_sha256"], row["source_text_sha256"], row["old_cn_sha256"],
        )
        if actual != identity:
            raise DecisionError(f"stable identity/hash drift: {source_row['item_id']}")
        protected = bool(source_row["protected_authority_text"])
        if row["protected_authority_text"] != str(protected).lower() or row["current_cn"] != source_row["current_cn"] or row["wiki_cn"] != source_row["wiki_cn"]:
            raise DecisionError(f"protected/source snapshot drift: {source_row['item_id']}")
        decision = row["human_decision"].strip()
        reviewer = row["reviewer"].strip()
        reviewed_at = row["reviewed_at"].strip()
        final = row["final_value"]
        if not decision:
            if reviewer or reviewed_at or final or row["human_notes"].strip():
                raise DecisionError(f"pending decision has review output: {source_row['item_id']}")
            states["pending"] += 1
            continue
        allowed = {"keep-authority", "unresolved"} if protected else {"approve-current", "revise", "unresolved"}
        if decision not in allowed:
            raise DecisionError(f"human decision is not allowed for item type: {source_row['item_id']}")
        if not reviewer or not ISO_8601.fullmatch(reviewed_at):
            raise DecisionError(f"nonempty decision requires reviewer and ISO-8601 timestamp: {source_row['item_id']}")
        if decision == "unresolved":
            if final:
                raise DecisionError(f"unresolved decision cannot carry an applicable value: {source_row['item_id']}")
            states["unresolved"] += 1
        elif decision == "keep-authority":
            allowed_values = {value for value in (source_row["wiki_cn"], source_row["current_cn"]) if value}
            if not final or final not in allowed_values:
                raise DecisionError(f"protected final value must equal wiki_cn or current_cn: {source_row['item_id']}")
            states["kept_authority"] += 1
        elif decision == "approve-current":
            if final != source_row["current_cn"]:
                raise DecisionError(f"approve-current must retain current_cn: {source_row['item_id']}")
            states["approved_current"] += 1
        elif decision == "revise":
            if not final or final == source_row["current_cn"]:
                raise DecisionError(f"revise requires a nonempty changed final value: {source_row['item_id']}")
            states["revised"] += 1
    return {
        "schema": "magireco-cn-dsv4-v3-manual-decision-validation/1",
        "status": "PASS",
        "rows": TOTAL,
        "states": states,
        "all_decided": states["pending"] == 0,
        "applicable_rows": states["approved_current"] + states["revised"] + states["kept_authority"],
        "unresolved_rows": states["unresolved"],
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "decisions_sha256": hashlib.sha256(decisions.read_bytes()).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate(args.source, args.decisions)
        payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.report:
            args.report.write_text(payload, encoding="utf-8", newline="\n")
        print(payload, end="")
        return 0
    except (DecisionError, csv.Error, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
