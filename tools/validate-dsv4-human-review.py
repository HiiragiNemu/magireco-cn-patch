#!/usr/bin/env python3
"""Validate the complete DSV4 handoff under the 1,565-item human gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from pass20_review_contract import (
    AUTHORITY_RESOLUTIONS, CONTRACT_JSON, EFFECTIVE, HUMAN_REVIEW_ITEMS,
    OFFICIAL_REVIEW, PROVENANCE, SHADOWED_ITEMS, SHADOW_JSON, TOTAL_ROWS,
    is_shadowed, load_tsv as load_contract_tsv, read_contract,
    validate_authority_resolutions,
)


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


def load_authority_shadows(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    if not path.is_file() or path.is_symlink():
        raise HumanReviewError(f"authority shadow manifest missing or unsafe: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS" or not str(payload.get("schema", "")).startswith(
        "magireco-cn-pass20-authority-shadowed-machine-items/"
    ):
        raise HumanReviewError("authority shadow manifest is invalid")
    rows = payload.get("items")
    if not isinstance(rows, list) or len(rows) != SHADOWED_ITEMS:
        raise HumanReviewError(f"authority shadow manifest must contain {SHADOWED_ITEMS} items")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise HumanReviewError("authority shadow manifest contains a non-object item")
        item_id = str(row.get("item_id", ""))
        if not item_id or item_id in result:
            raise HumanReviewError("authority shadow manifest has empty/duplicate item_id")
        if row.get("product_write_forbidden") is not True or row.get("product_write_allowed") is True:
            raise HumanReviewError(f"authority shadow permits product write: {item_id}")
        if not row.get("effective_cn") or not row.get("effective_tier"):
            raise HumanReviewError(f"authority shadow lacks effective authority: {item_id}")
        result[item_id] = row
    return result


def validate(
    source: Path,
    decisions: Path,
    authority_resolutions: Path | None = None,
    authority_shadows: Path | None = SHADOW_JSON,
    provenance_path: Path = PROVENANCE,
    effective_path: Path = EFFECTIVE,
    official_review_path: Path = OFFICIAL_REVIEW,
    contract_path: Path = CONTRACT_JSON,
) -> dict[str, Any]:
    source_header, source_rows = load_tsv(source)
    decision_header, decision_rows = load_tsv(decisions)
    if len(source_rows) != TOTAL_ROWS or len(decision_rows) != TOTAL_ROWS:
        raise HumanReviewError(f"source and decision tables must each contain {TOTAL_ROWS} rows")
    if not set(SOURCE_FIELDS).issubset(source_header):
        raise HumanReviewError("full_review source lacks immutable comparison fields")
    if not set(SOURCE_FIELDS + DECISION_FIELDS).issubset(decision_header):
        raise HumanReviewError("decision table lacks comparison or decision fields")
    source_ids = [row["item_id"] for row in source_rows]
    decision_ids = [row["item_id"] for row in decision_rows]
    if len(set(source_ids)) != TOTAL_ROWS or len(set(decision_ids)) != TOTAL_ROWS:
        raise HumanReviewError("source/decision item IDs are empty or duplicated")
    if set(decision_ids) != set(source_ids):
        raise HumanReviewError("decision IDs differ from the frozen source")
    decisions_by_id = {row["item_id"]: row for row in decision_rows}
    resolutions = load_authority_resolutions(authority_resolutions)
    shadows = load_authority_shadows(authority_shadows)
    _, provenance_rows = load_contract_tsv(provenance_path)
    _, effective_rows = load_contract_tsv(effective_path)
    _, official_review_rows = load_contract_tsv(official_review_path)
    validate_authority_resolutions(source_rows, list(resolutions.values()), official_review_rows)
    contract = read_contract(contract_path)
    unknown_resolutions = set(resolutions).difference(source_ids)
    if unknown_resolutions:
        raise HumanReviewError("authority resolution item is absent from frozen source")

    unknown_shadows = set(shadows).difference(source_ids)
    if unknown_shadows:
        raise HumanReviewError("authority shadow item is absent from frozen source")
    if set(resolutions) & set(shadows):
        raise HumanReviewError("authority resolution and shadow sets overlap")
    contract_sources = contract.get("source_sha256")
    if not isinstance(contract_sources, dict) or contract_sources != {
        "full_review": sha256(source),
        "authority_resolutions": sha256(authority_resolutions) if authority_resolutions else "",
        "input_provenance": sha256(provenance_path),
        "effective": sha256(effective_path),
    }:
        raise HumanReviewError("Pass20 contract source hash binding drifted")
    contract_ids = contract.get("item_ids")
    if not isinstance(contract_ids, dict):
        raise HumanReviewError("Pass20 contract stable-ID binding is missing")
    if set(contract_ids.get("higher_authority_shadowed", [])) != set(shadows):
        raise HumanReviewError("Pass20 contract shadow stable-ID set drifted")
    provenance = {row["candidate_id"]: row for row in provenance_rows}
    effective = {row["key"]: row for row in effective_rows}
    if len(provenance) != len(provenance_rows) or len(effective) != len(effective_rows):
        raise HumanReviewError("provenance/effective semantic keys are not unique")
    expected_shadow_ids: set[str] = set()
    for row in source_rows:
        if row["review_kind"] != "current-low-tier-translation-review" or row["item_id"] in resolutions:
            continue
        candidate = provenance.get(row["source_key"])
        if candidate is None or candidate["source_file"] != row["source_path"]:
            raise HumanReviewError(f"source provenance binding drifted: {row['item_id']}")
        winner = effective.get(candidate["key"])
        if winner is None:
            raise HumanReviewError(f"effective semantic key is missing: {row['item_id']}")
        if is_shadowed(candidate, winner):
            expected_shadow_ids.add(row["item_id"])
            shadow = shadows.get(row["item_id"])
            if shadow is None:
                continue
            if (
                shadow.get("source_key") != row["source_key"]
                or shadow.get("machine_current_cn") != row["current_cn"]
                or shadow.get("effective_cn") != winner["selected_cn"]
                or shadow.get("effective_tier") != winner["authority"]
                or shadow.get("effective_source_file") != winner["source_file"]
                or str(shadow.get("effective_source_line")) != winner["source_line"]
                or candidate.get("selected") != "false"
            ):
                raise HumanReviewError(f"authority shadow provenance/effective binding drifted: {row['item_id']}")
    if expected_shadow_ids != set(shadows) or len(expected_shadow_ids) != SHADOWED_ITEMS:
        raise HumanReviewError("computed higher-authority shadow stable-ID set drifted")
    states = {
        "pending": 0,
        "approved_current": 0,
        "revised": 0,
        "kept_authority": 0,
        "authority_resolved": 0,
        "higher_authority_shadowed": 0,
        "unresolved": 0,
    }
    source_by_kind = {
        "current-low-tier-translation-review": 0,
        "historical-pass8-llm-comparison-only": 0,
    }
    for source_row in source_rows:
        item_id = source_row["item_id"]
        decision_row = decisions_by_id[item_id]
        if source_row["review_kind"] not in source_by_kind:
            raise HumanReviewError(f"unknown review_kind: {source_row['review_kind']}")
        source_by_kind[source_row["review_kind"]] += 1
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
        if verdict not in {"approved", "manual-required", "correction", "unresolved"}:
            raise HumanReviewError(f"unexpected parent verdict: {item_id}")
        decision = decision_row["human_decision"].strip()
        reviewer = decision_row["reviewer"].strip()
        timestamp = decision_row["timestamp"].strip()
        final_value = decision_row["final_value"]
        human_revision = decision_row["human_revision"]
        notes = decision_row["human_notes"].strip()
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
        shadow = shadows.get(item_id)
        if shadow:
            if source_row["review_kind"] != "current-low-tier-translation-review":
                raise HumanReviewError(f"historical row cannot be a current authority shadow: {item_id}")
            if any((decision, reviewer, timestamp, final_value, human_revision, notes)):
                raise HumanReviewError(f"authority-shadowed row must remain decision-empty: {item_id}")
            if (
                shadow.get("machine_current_cn") != source_row["current_cn"]
                or shadow.get("product_write_forbidden") is not True
            ):
                raise HumanReviewError(f"authority shadow source/effective contract drifted: {item_id}")
            states["higher_authority_shadowed"] += 1
            continue
        if source_row["review_kind"] != "current-low-tier-translation-review":
            raise HumanReviewError(f"unresolved historical row lacks authority resolution: {item_id}")
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
            expected_status = "human-reviewed-unresolved"
        elif decision == "keep-authority":
            values = {v for v in (source_row["wiki_cn"], source_row["current_cn"]) if v}
            if final_value not in values or human_revision:
                raise HumanReviewError(f"keep-authority value drift: {item_id}")
            states["kept_authority"] += 1
        elif decision == "approve-current":
            if final_value != source_row["current_cn"] or human_revision:
                raise HumanReviewError(f"approve-current must retain current_cn: {item_id}")
            states["approved_current"] += 1
            expected_status = "human-reviewed-approved-current"
        elif decision == "revise":
            if not final_value or final_value == source_row["current_cn"]:
                raise HumanReviewError(f"revise requires changed final_value: {item_id}")
            if human_revision and human_revision != final_value:
                raise HumanReviewError(f"human_revision/final_value disagree: {item_id}")
            states["revised"] += 1
            expected_status = "human-reviewed-revised"
        else:
            expected_status = "human-reviewed-kept-authority"
        if decision_row["review_status"] != expected_status:
            raise HumanReviewError(f"human review status drift: {item_id}")

    if source_by_kind != {
        "current-low-tier-translation-review": 1648,
        "historical-pass8-llm-comparison-only": 264,
    }:
        raise HumanReviewError("current/history source partition drifted")
    if states["authority_resolved"] != AUTHORITY_RESOLUTIONS:
        raise HumanReviewError("existing authority resolution count drifted")
    if states["higher_authority_shadowed"] != SHADOWED_ITEMS:
        raise HumanReviewError("higher-authority shadow count drifted")
    effective_required = HUMAN_REVIEW_ITEMS
    if sum(states[key] for key in ("pending", "approved_current", "revised", "unresolved")) != effective_required:
        raise HumanReviewError("human review partition drifted")
    decided = effective_required - states["pending"]
    return {
        "schema": "magireco-cn-dsv4-v3-full-human-decision-validation/2",
        "status": "PASS",
        "rows": TOTAL_ROWS,
        "machine_source_inventory": HUMAN_REVIEW_ITEMS + SHADOWED_ITEMS,
        "base_decision_required": HUMAN_REVIEW_ITEMS,
        "authority_resolved": states["authority_resolved"],
        "higher_authority_shadowed": states["higher_authority_shadowed"],
        "authority_excluded_total": states["authority_resolved"] + states["higher_authority_shadowed"],
        "decision_required": effective_required,
        "required_by_kind": {"current-low-tier-translation-review": HUMAN_REVIEW_ITEMS},
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
        "authority_shadows_sha256": sha256(authority_shadows) if authority_shadows else "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--authority-resolutions", type=Path)
    parser.add_argument("--authority-shadows", type=Path, default=SHADOW_JSON)
    parser.add_argument("--provenance", type=Path, default=PROVENANCE)
    parser.add_argument("--effective", type=Path, default=EFFECTIVE)
    parser.add_argument("--official-review", type=Path, default=OFFICIAL_REVIEW)
    parser.add_argument("--contract", type=Path, default=CONTRACT_JSON)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--require-release-open",
        action="store_true",
        help="exit nonzero unless every required decision is complete and unresolved is zero",
    )
    args = parser.parse_args(argv)
    try:
        result = validate(
            args.source, args.decisions, args.authority_resolutions, args.authority_shadows,
            args.provenance, args.effective, args.official_review, args.contract,
        )
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
