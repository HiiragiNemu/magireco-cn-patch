#!/usr/bin/env python3
"""Shared schema and provenance rules for the Pass20 final-value receipt.

hash=allow consumer=Pass20 final-value binding; replaces unbound workbook rows;
decision=fail-closed release eligibility.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


HUMAN_REVIEW_MODE = "human-review"
ROUGH_PRODUCTION_MODE = "rough-production"
PROVENANCE_MODES = {HUMAN_REVIEW_MODE, ROUGH_PRODUCTION_MODE}


FINAL_VALUE_FIELDS = (
    "item_id",
    "stable_business_key",
    "source_path",
    "source_key",
    "source_field",
    "japanese_or_source_original",
    "seed_cn",
    "seed_origin",
    "current_cn",
    "suggested_cn",
    "final_value",
    "source_record_sha256",
    "target_contract_sha256",
    "review_status",
    "final_origin",
    "machine_translated",
)

SOURCE_BINDING_FIELDS = (
    "item_id",
    "stable_business_key",
    "source_path",
    "source_key",
    "source_field",
    "japanese_or_source_original",
    "current_cn",
    "suggested_cn",
    "parent_verdict",
    "highest_authority_tier",
    "authority_status",
)


def canonical_json_sha256(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def source_record_sha256(source: dict[str, Any]) -> str:
    return canonical_json_sha256({field: str(source.get(field, "")) for field in SOURCE_BINDING_FIELDS})


def target_contract_sha256(target: dict[str, Any]) -> str:
    return canonical_json_sha256(target)


def seed_for_source(
    source: dict[str, str], adopted_suggestion: str = "",
) -> tuple[str, str]:
    if adopted_suggestion:
        return adopted_suggestion, "adopted_suggestion"
    suggested = source.get("suggested_cn", "")
    if suggested:
        return suggested, "suggested"
    return source.get("current_cn", ""), "current"


def classify_final_value(
    source: dict[str, str], final_value: str, adopted_suggestion: str = "",
    provenance_mode: str = HUMAN_REVIEW_MODE,
) -> dict[str, str]:
    """Derive the only provenance status accepted by the product pipeline."""
    if provenance_mode not in PROVENANCE_MODES:
        raise ValueError(f"unknown final-value provenance mode: {provenance_mode}")
    current = source.get("current_cn", "")
    suggested = adopted_suggestion or source.get("suggested_cn", "")
    seed, _ = seed_for_source(source, adopted_suggestion)
    if provenance_mode == ROUGH_PRODUCTION_MODE:
        if final_value != seed:
            raise ValueError(
                "rough-production final values must equal the bound prefilled value"
            )
        if suggested and final_value == suggested:
            return {
                "review_status": "rough-production-machine-suggestion-adopted",
                "final_origin": "machine-suggestion",
                "machine_translated": "true",
            }
        return {
            "review_status": "rough-production-machine-current-retained",
            "final_origin": "machine-current",
            "machine_translated": "unknown",
        }
    if (
        adopted_suggestion and final_value == adopted_suggestion
    ) or (
        not adopted_suggestion and suggested and suggested != current and final_value == suggested
    ):
        return {
            "review_status": "human-confirmed-machine-suggestion-adopted",
            "final_origin": "machine-suggestion",
            "machine_translated": "true",
        }
    if final_value == current:
        return {
            "review_status": "human-confirmed-machine-origin-retained",
            "final_origin": "machine-current",
            "machine_translated": "unknown",
        }
    return {
        "review_status": "human-revised",
        "final_origin": "human-revision",
        "machine_translated": "false",
    }


def expected_final_value_row(
    source: dict[str, str], target: dict[str, Any], final_value: str,
    adopted_suggestion: str = "",
    provenance_mode: str = HUMAN_REVIEW_MODE,
) -> dict[str, str]:
    seed_cn, seed_origin = seed_for_source(source, adopted_suggestion)
    result = {
        "item_id": source.get("item_id", ""),
        "stable_business_key": source.get("stable_business_key", ""),
        "source_path": source.get("source_path", ""),
        "source_key": source.get("source_key", ""),
        "source_field": source.get("source_field", ""),
        "japanese_or_source_original": source.get("japanese_or_source_original", ""),
        "seed_cn": seed_cn,
        "seed_origin": seed_origin,
        "current_cn": source.get("current_cn", ""),
        "suggested_cn": source.get("suggested_cn", ""),
        "final_value": final_value,
        "source_record_sha256": source_record_sha256(source),
        "target_contract_sha256": target_contract_sha256(target),
    }
    result.update(classify_final_value(
        source, final_value, adopted_suggestion, provenance_mode,
    ))
    return result


def provenance_mode_for_receipt(row: dict[str, str]) -> str:
    status = row.get("review_status", "")
    if status.startswith("rough-production-"):
        return ROUGH_PRODUCTION_MODE
    if status.startswith("human-"):
        return HUMAN_REVIEW_MODE
    raise ValueError(f"unknown final-value review_status: {status!r}")
