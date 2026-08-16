#!/usr/bin/env python3
"""Shared, fail-closed contract for the Pass20 human translation review."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from v26_authority_protection import sha256_file


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
FULL_REVIEW = AUDIT / "dsv4_terminal_handoff/full_review.tsv"
DECISIONS = AUDIT / "dsv4_human_decisions.tsv"
RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
OFFICIAL_REVIEW = AUDIT / "pass20_official_static_review.tsv"
PROVENANCE = ROOT / "i18n/generated/input-provenance.tsv"
EFFECTIVE = ROOT / "i18n/generated/effective.tsv"
MACHINE_INVENTORY = AUDIT / "pass20_machine_source_inventory.tsv"
HUMAN_QUEUE = AUDIT / "pass20_remaining_manual_review.tsv"
PRIORITY_QUEUE = AUDIT / "pass20_priority_manual_review.tsv"
SHADOW_TSV = AUDIT / "pass20_authority_shadowed_machine_items.tsv"
SHADOW_JSON = AUDIT / "pass20_authority_shadowed_machine_items.json"
CONTRACT_JSON = AUDIT / "pass20_review_contract.json"

TOTAL_ROWS = 1912
AUTHORITY_RESOLUTIONS = 323
MACHINE_SOURCE_ITEMS = 1589
HUMAN_REVIEW_ITEMS = 1565
PRIORITY_ITEMS = 199
DS_APPROVED_ITEMS = 1366
SHADOWED_ITEMS = 24
AUTHORITY_EXCLUDED_ITEMS = AUTHORITY_RESOLUTIONS + SHADOWED_ITEMS
EXACT_RUNTIME_ITEMS = 1443
MAINTENANCE_ONLY_ITEMS = 122
RUNTIME_OCCURRENCES = 2439

PRIORITY_VERDICTS = {"manual-required", "correction", "unresolved"}
HUMAN_DECISIONS = ["approve-current", "revise", "unresolved"]
DECISION_FIELDS = (
    "allowed_human_decisions", "review_status", "human_decision", "reviewer",
    "timestamp", "final_value", "human_revision", "human_notes",
)
CLASSIFICATION_FIELDS = (
    "review_scope_status", "application_policy", "effective_cn", "effective_tier",
    "effective_source_file", "effective_source_line", "shadowed_by_higher_authority",
    "product_write_forbidden", "canonical_write_allowed_after_human_gate",
)


class ContractError(RuntimeError):
    pass


def load_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"TSV missing or unsafe: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise ContractError(f"TSV must be UTF-8-no-BOM with LF endings: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if not header or any(None in row for row in rows):
        raise ContractError(f"invalid TSV structure: {path}")
    return header, rows


def write_tsv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in header} for row in rows)


def assert_unique_ids(rows: list[dict[str, str]], expected: int, label: str) -> None:
    ids = [row.get("item_id", "") for row in rows]
    if len(ids) != expected or any(not item_id for item_id in ids) or len(set(ids)) != expected:
        raise ContractError(f"{label} must contain {expected} unique item IDs, found {len(ids)}")


def human_review_status(parent_verdict: str) -> str:
    return {
        "approved": "ds-approved-human-unreviewed",
        "correction": "staged-correction-needs-human-decision",
        "manual-required": "manual-required",
        "unresolved": "needs-human-review",
    }.get(parent_verdict, "")


def validate_authority_resolutions(
    source_rows: list[dict[str, str]],
    resolution_rows: list[dict[str, str]],
    official_review_rows: list[dict[str, str]],
) -> None:
    history_ids = {
        row["item_id"] for row in source_rows
        if row["review_kind"] == "historical-pass8-llm-comparison-only"
    }
    accepted_official = {
        row["item_id"]: row for row in official_review_rows
        if row["decision"] == "accept-official-cn"
    }
    if len(history_ids) != 264 or len(accepted_official) != 58:
        raise ContractError("authority source evidence partition drifted")
    resolutions = {row["item_id"]: row for row in resolution_rows}
    if len(resolutions) != len(resolution_rows):
        raise ContractError("authority resolutions contain duplicate item IDs")
    actual_history = {
        item_id for item_id, row in resolutions.items()
        if row["resolution_kind"] == "protected-history-retained"
    }
    actual_current = {
        item_id for item_id, row in resolutions.items()
        if row["resolution_kind"] == "official-cn-applied"
    }
    expected_current = set(accepted_official) | {"LOW-MT-01485"}
    if actual_history != history_ids or actual_current != expected_current:
        raise ContractError("authority resolution stable-ID set drifted")
    for item_id, evidence in accepted_official.items():
        resolution = resolutions[item_id]
        candidates = json.loads(evidence["official_candidates"])
        if (
            resolution["authority_tier"] != "official_cn_dump"
            or resolution["final_value"] not in candidates
            or resolution["product_write_status"]
            not in {"applied-and-verified", "equivalent-already-present"}
        ):
            raise ContractError(f"official resolution evidence drifted: {item_id}")
    existing = resolutions["LOW-MT-01485"]
    if (
        existing["authority_tier"] != "official_cn_dump"
        or existing["final_value"] != "心魔战"
        or existing["product_write_status"] != "equivalent-already-present"
    ):
        raise ContractError("LOW-MT-01485 existing official authority drifted")
    if "LOW-MT-00674" not in actual_current:
        raise ContractError("LOW-MT-00674 official path override is missing")


def is_shadowed(source: dict[str, str], effective: dict[str, str]) -> bool:
    return any((
        effective["selected_cn"] != source["candidate_cn"],
        effective["authority"] != source["authority"],
        effective["source_file"] != source["source_file"],
        effective["source_line"] != source["source_line"],
    ))


def validate_contract_counts(
    *, machine: list[dict[str, str]], human: list[dict[str, str]],
    priority: list[dict[str, str]], shadowed: list[dict[str, str]],
) -> None:
    assert_unique_ids(machine, MACHINE_SOURCE_ITEMS, "machine inventory")
    assert_unique_ids(human, HUMAN_REVIEW_ITEMS, "human queue")
    assert_unique_ids(priority, PRIORITY_ITEMS, "priority queue")
    assert_unique_ids(shadowed, SHADOWED_ITEMS, "authority-shadow inventory")
    machine_ids = {row["item_id"] for row in machine}
    human_ids = {row["item_id"] for row in human}
    priority_ids = {row["item_id"] for row in priority}
    shadow_ids = {row["item_id"] for row in shadowed}
    if human_ids & shadow_ids or machine_ids != human_ids | shadow_ids:
        raise ContractError("1589 machine inventory does not partition into 1565 human + 24 shadow")
    if not priority_ids.issubset(human_ids):
        raise ContractError("199 priority items are not a subset of the human queue")
    approved = sum(row["parent_verdict"] == "approved" for row in human)
    if approved != DS_APPROVED_ITEMS:
        raise ContractError(f"expected {DS_APPROVED_ITEMS} DS-approved human rows, found {approved}")
    scopes: dict[str, int] = {}
    for row in human:
        scopes[row["source_path"]] = scopes.get(row["source_path"], 0) + 1
    expected_scopes = {
        "i18n/frontend-strings.tsv": 1549,
        "i18n/overrides.tsv": 9,
        "i18n/fragments.tsv": 7,
    }
    if scopes != expected_scopes:
        raise ContractError(f"human maintenance-layer partition drifted: {scopes}")


def contract_payload(
    *, full_review: Path, resolutions: Path, provenance: Path, effective: Path,
    machine: list[dict[str, str]], human: list[dict[str, str]],
    priority: list[dict[str, str]], shadowed: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "schema": "magireco-cn-pass20-review-contract/2",
        "status": "PASS",
        "counts": {
            "frozen_rows": TOTAL_ROWS,
            "existing_authority_resolutions": AUTHORITY_RESOLUTIONS,
            "machine_source_inventory": MACHINE_SOURCE_ITEMS,
            "human_review_required": HUMAN_REVIEW_ITEMS,
            "priority_human_review": PRIORITY_ITEMS,
            "ds_approved_but_human_required": DS_APPROVED_ITEMS,
            "higher_authority_shadowed": SHADOWED_ITEMS,
            "authority_excluded_total": AUTHORITY_EXCLUDED_ITEMS,
            "exact_runtime_items": EXACT_RUNTIME_ITEMS,
            "maintenance_only_items": MAINTENANCE_ONLY_ITEMS,
            "runtime_occurrences": RUNTIME_OCCURRENCES,
        },
        "item_ids": {
            "machine_source_inventory": [row["item_id"] for row in machine],
            "human_review_required": [row["item_id"] for row in human],
            "priority_human_review": [row["item_id"] for row in priority],
            "higher_authority_shadowed": [row["item_id"] for row in shadowed],
        },
        "source_sha256": {
            "full_review": sha256_file(full_review),
            "authority_resolutions": sha256_file(resolutions),
            "input_provenance": sha256_file(provenance),
            "effective": sha256_file(effective),
        },
        "policy": {
            "human_queue_excludes_higher_authority_shadowed": True,
            "shadowed_product_write_forbidden": True,
            "approved_machine_text_still_requires_human_review": True,
            "stable_id_driven": True,
            "source_product_write_allowed_is_preserved_provenance": True,
            "canonical_write_requires_completed_human_gate": True,
        },
    }


def read_contract(path: Path = CONTRACT_JSON) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS" or payload.get("schema") != "magireco-cn-pass20-review-contract/2":
        raise ContractError("Pass20 review contract is invalid")
    return payload
