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
RESOLUTION_FIELDS = (
    "item_id", "resolution_kind", "authority_tier", "final_value",
    "evidence", "product_write_status",
)
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


def load_authority_resolutions(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    header, rows = load_tsv(path)
    if tuple(header) != RESOLUTION_FIELDS:
        raise HumanReviewError("authority resolution table has unexpected columns")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        item_id = row["item_id"]
        if not item_id or item_id in result:
            raise HumanReviewError("authority resolution table has empty/duplicate item_id")
        if not row["authority_tier"] or not row["final_value"] or not row["evidence"]:
            raise HumanReviewError(f"incomplete authority resolution: {item_id}")
        result[item_id] = row
    return result


def validate(
    source: Path,
    decisions: Path,
    authority_resolutions: Path | None = None,
) -> dict[str, Any]:
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
    resolutions = load_authority_resolutions(authority_resolutions)
    unknown_resolutions = set(resolutions).difference(source_ids)
    if unknown_resolutions:
        raise HumanReviewError("authority resolution item is absent from frozen source")

    states = {
        "not_required": 0,
        "pending": 0,
        "approved_current": 0,
        "revised": 0,
        "kept_authority": 0,
        "authority_resolved": 0,
        "unresolved": 0,
    }
    base_required_by_kind = {
        "current-low-tier-translation-review": 0,
        "historical-pass8-llm-comparison-only": 0,
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
        base_required_by_kind[source_row["review_kind"]] += 1
        resolution = resolutions.get(item_id)
        if resolution:
            if any((decision, reviewer, timestamp, final_value, human_revision, notes)):
                raise HumanReviewError(
                    f"authority-resolved row must remain human-decision-empty: {item_id}"
                )
            if source_row["review_kind"] == "historical-pass8-llm-comparison-only":
                if resolution["resolution_kind"] != "protected-history-retained":
                    raise HumanReviewError(f"invalid historical resolution kind: {item_id}")
                allowed_values = {
                    value for value in (source_row["wiki_cn"], source_row["current_cn"]) if value
                }
                if (
                    source_row["protected_authority_text"] != "true"
                    or resolution["final_value"] not in allowed_values
                    or resolution["product_write_status"] != "no-product-write-protected"
                ):
                    raise HumanReviewError(f"historical authority resolution drift: {item_id}")
            else:
                if (
                    resolution["resolution_kind"] != "official-cn-applied"
                    or resolution["authority_tier"] != "official_cn_dump"
                    or resolution["product_write_status"]
                    not in {"applied-and-verified", "equivalent-already-present"}
                ):
                    raise HumanReviewError(f"current authority resolution drift: {item_id}")
            states["authority_resolved"] += 1
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

    if states["not_required"] != 1390 or sum(base_required_by_kind.values()) != REQUIRED_DECISIONS:
        raise HumanReviewError("required/not-required partition drifted")
    if base_required_by_kind != {
        "current-low-tier-translation-review": 258,
        "historical-pass8-llm-comparison-only": 264,
    }:
        raise HumanReviewError("current/history decision partition drifted")
    effective_required = REQUIRED_DECISIONS - states["authority_resolved"]
    if sum(required_by_kind.values()) != effective_required:
        raise HumanReviewError("effective authority/manual partition drifted")
    decided = effective_required - states["pending"]
    return {
        "schema": "magireco-cn-dsv4-v3-full-human-decision-validation/1",
        "status": "PASS",
        "rows": TOTAL,
        "base_decision_required": REQUIRED_DECISIONS,
        "authority_resolved": states["authority_resolved"],
        "decision_required": effective_required,
        "required_by_kind": required_by_kind,
        "states": states,
        "decided": decided,
        "all_decided": states["pending"] == 0,
        "release_gate_open": states["pending"] == 0 and states["unresolved"] == 0,
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "source_sha256": sha256(source),
        "decisions_sha256": sha256(decisions),
        "authority_resolutions_sha256": (
            sha256(authority_resolutions) if authority_resolutions else ""
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--authority-resolutions", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--require-release-open",
        action="store_true",
        help="exit nonzero unless every required decision is complete and unresolved is zero",
    )
    args = parser.parse_args(argv)
    try:
        result = validate(args.source, args.decisions, args.authority_resolutions)
        payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.report:
            args.report.write_text(payload, encoding="utf-8", newline="\n")
        print(payload, end="")
        if args.require_release_open and not result["release_gate_open"]:
            print(
                f"release gate closed: all {result['decision_required']} remaining "
                "decisions must be complete and unresolved must be zero",
                file=sys.stderr,
            )
            return 3
        return 0
    except (HumanReviewError, OSError, UnicodeDecodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
