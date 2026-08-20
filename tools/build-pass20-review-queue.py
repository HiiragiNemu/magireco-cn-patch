#!/usr/bin/env python3
"""Build the Pass20 machine inventory, human queue, and authority shadows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pass20_review_contract import (
    ADOPTIONS, CLASSIFICATION_FIELDS, CONTRACT_JSON, DECISION_FIELDS, DECISIONS, EFFECTIVE,
    FULL_REVIEW, HUMAN_DECISIONS, HUMAN_QUEUE, MACHINE_INVENTORY, OFFICIAL_REVIEW, PRIORITY_QUEUE,
    PRIORITY_VERDICTS, PROVENANCE, RESOLUTIONS, SHADOW_TSV,
    ContractError, contract_payload, human_review_status, is_shadowed, load_tsv,
    validate_authority_resolutions, validate_contract_counts, write_tsv,
)


class QueueError(ContractError):
    pass


def build(
    full_review_path: Path,
    decisions_schema_path: Path,
    resolutions_path: Path,
    official_review_path: Path,
    provenance_path: Path,
    effective_path: Path,
    adoptions_path: Path = ADOPTIONS,
) -> tuple[
    list[str], list[dict[str, str]], list[dict[str, str]],
    list[dict[str, str]], list[dict[str, str]],
]:
    source_header, source_rows = load_tsv(full_review_path)
    decision_header, _ = load_tsv(decisions_schema_path)
    _, resolutions = load_tsv(resolutions_path)
    _, official_review = load_tsv(official_review_path)
    _, provenance_rows = load_tsv(provenance_path)
    _, effective_rows = load_tsv(effective_path)
    adoption_header, adoption_rows = load_tsv(adoptions_path)
    if not {"item_id", "adopted_cn", "machine_origin"}.issubset(adoption_header):
        raise QueueError("suggestion adoption table lacks required columns")
    adoptions = {row["item_id"]: row["adopted_cn"] for row in adoption_rows}
    if (
        len(adoptions) != len(adoption_rows)
        or len(adoptions) != 29
        or any(not value for value in adoptions.values())
        or any(row["machine_origin"] != "true" for row in adoption_rows)
    ):
        raise QueueError("suggestion adoption table has an invalid row or count")
    immutable_schema = [field for field in decision_header if field not in DECISION_FIELDS]
    if not set(immutable_schema).issubset(source_header):
        missing = sorted(set(immutable_schema).difference(source_header))
        raise QueueError(f"decision schema fields are absent from frozen full_review: {missing}")

    resolution_ids: set[str] = set()
    for row in resolutions:
        item_id = row["item_id"]
        if not item_id or item_id in resolution_ids:
            raise QueueError(f"authority resolutions contain missing/duplicate item_id: {item_id!r}")
        resolution_ids.add(item_id)
    validate_authority_resolutions(source_rows, resolutions, official_review)
    provenance = {row["candidate_id"]: row for row in provenance_rows}
    effective = {row["key"]: row for row in effective_rows}
    if len(provenance) != len(provenance_rows) or len(effective) != len(effective_rows):
        raise QueueError("provenance/effective semantic keys are not unique")

    source_ids: set[str] = set()
    inventory: list[dict[str, str]] = []
    allowed = json.dumps(HUMAN_DECISIONS, ensure_ascii=False, separators=(",", ":"))
    read_only = json.dumps([], ensure_ascii=False, separators=(",", ":"))
    for source_row in source_rows:
        item_id = source_row.get("item_id", "")
        if not item_id or item_id in source_ids:
            raise QueueError(f"frozen source contains missing/duplicate item_id: {item_id!r}")
        source_ids.add(item_id)
        if (
            source_row["review_kind"] != "current-low-tier-translation-review"
            or item_id in resolution_ids
        ):
            continue
        row = {field: source_row.get(field, "") for field in decision_header}
        if item_id in adoptions:
            candidates = [
                entry for entry in provenance_rows
                if entry.get("source_file") == row["source_path"]
                and entry.get("source_text") == row["japanese_or_source_original"]
                and entry.get("candidate_cn") == adoptions[item_id]
                and entry.get("authority") == "legacy_unverified_ai_assisted"
                and entry.get("selected") == "true"
            ]
            if len(candidates) != 1:
                raise QueueError(f"adopted candidate provenance drifted: {item_id}")
            source = candidates[0]
        else:
            source = provenance.get(row["source_key"])
            if source is None or source["source_file"] != row["source_path"]:
                raise QueueError(f"candidate provenance is missing or drifted: {item_id}")
        winner = effective.get(source["key"])
        if winner is None:
            raise QueueError(f"effective semantic key is missing: {item_id}")
        shadowed = is_shadowed(source, winner)
        status = human_review_status(row["parent_verdict"])
        if not status:
            raise QueueError(f"unsupported DSV4 verdict: {item_id}={row['parent_verdict']!r}")
        row.update({
            "allowed_human_decisions": read_only if shadowed else allowed,
            "review_status": "higher-authority-shadowed-read-only" if shadowed else status,
            "human_decision": "", "reviewer": "", "timestamp": "",
            "final_value": "", "human_revision": "", "human_notes": "",
            "review_scope_status": (
                "higher-authority-shadowed" if shadowed else "current-effective-low-authority"
            ),
            "application_policy": (
                "product-write-forbidden" if shadowed else "human-reviewed-materialization"
            ),
            "effective_cn": winner["selected_cn"],
            "effective_tier": winner["authority"],
            "effective_source_file": winner["source_file"],
            "effective_source_line": winner["source_line"],
            "shadowed_by_higher_authority": str(shadowed).lower(),
            "product_write_forbidden": str(shadowed).lower(),
            "canonical_write_allowed_after_human_gate": str(not shadowed).lower(),
        })
        inventory.append(row)

    shadowed = [row for row in inventory if row["shadowed_by_higher_authority"] == "true"]
    human = [row for row in inventory if row["shadowed_by_higher_authority"] == "false"]
    priority = [row for row in human if row["parent_verdict"] in PRIORITY_VERDICTS]
    approved = [row for row in human if row["parent_verdict"] == "approved"]
    if len(priority) + len(approved) != len(human):
        raise QueueError("human queue contains an unsupported DSV4 verdict")
    priority.sort(key=lambda row: int(row["source_index"]))
    approved.sort(key=lambda row: int(row["source_index"]))
    shadowed.sort(key=lambda row: int(row["source_index"]))
    human = priority + approved
    inventory = human + shadowed
    validate_contract_counts(machine=inventory, human=human, priority=priority, shadowed=shadowed)
    if "LOW-MT-01485" in {row["item_id"] for row in human}:
        raise QueueError("LOW-MT-01485 must remain closed by existing official authority")
    header = decision_header + [field for field in CLASSIFICATION_FIELDS if field not in decision_header]
    return header, inventory, human, priority, shadowed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=FULL_REVIEW)
    parser.add_argument("--decisions-schema", type=Path, default=DECISIONS)
    parser.add_argument("--resolutions", type=Path, default=RESOLUTIONS)
    parser.add_argument("--official-review", type=Path, default=OFFICIAL_REVIEW)
    parser.add_argument("--provenance", type=Path, default=PROVENANCE)
    parser.add_argument("--effective", type=Path, default=EFFECTIVE)
    parser.add_argument("--adoptions", type=Path, default=ADOPTIONS)
    parser.add_argument("--out", type=Path, default=HUMAN_QUEUE)
    parser.add_argument("--priority-out", type=Path, default=PRIORITY_QUEUE)
    parser.add_argument("--inventory-out", type=Path, default=MACHINE_INVENTORY)
    parser.add_argument("--shadow-tsv", type=Path, default=SHADOW_TSV)
    parser.add_argument("--contract", type=Path, default=CONTRACT_JSON)
    args = parser.parse_args(argv)
    try:
        header, inventory, human, priority, shadowed = build(
            args.source, args.decisions_schema, args.resolutions, args.official_review,
            args.provenance, args.effective, args.adoptions,
        )
        write_tsv(args.inventory_out, header, inventory)
        write_tsv(args.out, header, human)
        write_tsv(args.priority_out, header, priority)
        write_tsv(args.shadow_tsv, header, shadowed)
        contract = contract_payload(
            full_review=args.source, resolutions=args.resolutions,
            provenance=args.provenance, effective=args.effective,
            machine=inventory, human=human, priority=priority, shadowed=shadowed,
        )
        args.contract.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(json.dumps(contract["counts"], ensure_ascii=False, sort_keys=True))
        return 0
    except (ContractError, OSError, UnicodeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
