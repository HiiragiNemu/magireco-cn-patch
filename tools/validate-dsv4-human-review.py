#!/usr/bin/env python3
"""Validate a reviewer-edited copy of the complete 1,912-row DSV4 handoff."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


TOTAL = 1912
REQUIRED_DECISIONS = 522
ISO_8601 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SOURCE_FIELDS = (
    "source_index", "batch_number", "item_id", "stable_business_key",
    "source_path", "source_key", "source_field", "review_kind", "allowed_action",
    "japanese_or_source_original", "old_cn", "current_cn", "parent_verdict",
    "suggested_cn", "parent_rationale", "role_verdicts", "role_details",
    "protected_authority_text", "product_write_allowed", "highest_authority_tier",
    "authority_status", "authority_evidence", "official_cn", "wiki_cn",
    "confirmed_human_cn",
)
DECISION_FIELDS = (
    "allowed_human_decisions", "review_status", "human_decision", "reviewer",
    "timestamp", "final_value", "human_revision", "human_notes",
)


class HumanReviewError(RuntimeError):
    """A full human-review contract failed."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file() or path.is_symlink():
        raise HumanReviewError(f"TSV missing or unsafe: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise HumanReviewError(f"TSV must be UTF-8-no-BOM with LF endings: {path}")
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            header = list(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise HumanReviewError(f"invalid TSV {path}: {exc}") from exc
    if any(None in row for row in rows):
        raise HumanReviewError(f"malformed TSV row in {path}")
    return header, rows


def _allowed(source: dict[str, str]) -> list[str]:
    if source["review_kind"] == "historical-pass8-llm-comparison-only":
        return ["keep-authority", "unresolved"]
    if source["review_kind"] == "current-low-tier-translation-review":
        return ["approve-current", "revise", "unresolved"]
    raise HumanReviewError(f"unknown review_kind: {source['review_kind']}")


def validate(source: Path, decisions: Path) -> dict[str, Any]:
    source_header, source_rows = load_tsv(source)
    decision_header, decision_rows = load_tsv(decisions)
    if len(source_rows) != TOTAL or len(decision_rows) != TOTAL:
        raise HumanReviewError(f"source and decision tables must each contain {TOTAL} rows")
    if not set(SOURCE_FIELDS).issubset(source_header):
        raise HumanReviewError("full_review source lacks immutable comparison fields")
    if not set(SOURCE_FIELDS + DECISION_FIELDS).issubset(decision_header):
        raise HumanReviewError("decision table lacks comparison or decision fields")
    source_ids = [row["item_id"] for row in source_rows]
    decision_ids = [row["item_id"] for row in decision_rows]
    if len(set(source_ids)) != TOTAL or decision_ids != source_ids:
        raise HumanReviewError("decision row order/IDs differ from the frozen source")

    states = {
        "not_required": 0,
        "pending": 0,
        "approved_current": 0,
        "revised": 0,
        "kept_authority": 0,
        "unresolved": 0,
    }
    required_by_kind = {
        "current-low-tier-translation-review": 0,
        "historical-pass8-llm-comparison-only": 0,
    }
    for source_row, decision_row in zip(source_rows, decision_rows):
        item_id = source_row["item_id"]
        for field in SOURCE_FIELDS:
            if decision_row[field] != source_row[field]:
                raise HumanReviewError(f"immutable field drift {field}: {item_id}")
        if source_row["product_write_allowed"] != "false":
            raise HumanReviewError(f"source unexpectedly permits product write: {item_id}")
        allowed = _allowed(source_row)
        expected_allowed = json.dumps(allowed, ensure_ascii=False, separators=(",", ":"))
        if decision_row["allowed_human_decisions"] != expected_allowed:
            raise HumanReviewError(f"decision enum drift: {item_id}")
        verdict = source_row["parent_verdict"]
        requires = verdict in {"manual-required", "correction", "unresolved"}
        decision = decision_row["human_decision"].strip()
        reviewer = decision_row["reviewer"].strip()
        timestamp = decision_row["timestamp"].strip()
        final_value = decision_row["final_value"]
        human_revision = decision_row["human_revision"]
        notes = decision_row["human_notes"].strip()
        if not requires:
            if verdict != "approved":
                raise HumanReviewError(f"unexpected parent verdict: {item_id}")
            if any((decision, reviewer, timestamp, final_value, human_revision, notes)):
                raise HumanReviewError(f"DS-approved row must remain decision-empty: {item_id}")
            states["not_required"] += 1
            continue
        required_by_kind[source_row["review_kind"]] += 1
        if not decision:
            if any((reviewer, timestamp, final_value, human_revision, notes)):
                raise HumanReviewError(f"pending row carries review output: {item_id}")
            states["pending"] += 1
            continue
        if decision not in allowed:
            raise HumanReviewError(f"decision {decision!r} is forbidden for {item_id}")
        if not reviewer or not ISO_8601.fullmatch(timestamp):
            raise HumanReviewError(f"decided row lacks reviewer/ISO timestamp: {item_id}")
        if decision == "unresolved":
            if final_value or human_revision:
                raise HumanReviewError(f"unresolved row carries applicable text: {item_id}")
            states["unresolved"] += 1
        elif decision == "keep-authority":
            values = {v for v in (source_row["wiki_cn"], source_row["current_cn"]) if v}
            if final_value not in values or human_revision:
                raise HumanReviewError(f"keep-authority value drift: {item_id}")
            states["kept_authority"] += 1
        elif decision == "approve-current":
            if final_value != source_row["current_cn"] or human_revision:
                raise HumanReviewError(f"approve-current must retain current_cn: {item_id}")
            states["approved_current"] += 1
        elif decision == "revise":
            if not final_value or final_value == source_row["current_cn"]:
                raise HumanReviewError(f"revise requires changed final_value: {item_id}")
            if human_revision and human_revision != final_value:
                raise HumanReviewError(f"human_revision/final_value disagree: {item_id}")
            states["revised"] += 1

    if states["not_required"] != 1390 or sum(required_by_kind.values()) != REQUIRED_DECISIONS:
        raise HumanReviewError("required/not-required partition drifted")
    if required_by_kind != {
        "current-low-tier-translation-review": 258,
        "historical-pass8-llm-comparison-only": 264,
    }:
        raise HumanReviewError("current/history decision partition drifted")
    decided = REQUIRED_DECISIONS - states["pending"]
    return {
        "schema": "magireco-cn-dsv4-v3-full-human-decision-validation/1",
        "status": "PASS",
        "rows": TOTAL,
        "decision_required": REQUIRED_DECISIONS,
        "required_by_kind": required_by_kind,
        "states": states,
        "decided": decided,
        "all_decided": states["pending"] == 0,
        "release_gate_open": states["pending"] == 0 and states["unresolved"] == 0,
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "source_sha256": sha256(source),
        "decisions_sha256": sha256(decisions),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate(args.source, args.decisions)
        payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.report:
            args.report.write_text(payload, encoding="utf-8", newline="\n")
        print(payload, end="")
        return 0
    except (HumanReviewError, OSError, UnicodeDecodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
