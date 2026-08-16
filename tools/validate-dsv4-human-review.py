#!/usr/bin/env python3
"""Validate the 1,565-item Pass20 final-value return contract.

hash=allow consumer=Pass20 final-value binding; replaces unbound workbook rows;
decision=fail-closed release eligibility.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from pass20_final_values_contract import (
    FINAL_VALUE_FIELDS, HUMAN_REVIEW_MODE, ROUGH_PRODUCTION_MODE,
    expected_final_value_row, provenance_mode_for_receipt,
)
from pass20_review_contract import (
    AUTHORITY_RESOLUTIONS, CONTRACT_JSON, EFFECTIVE, HUMAN_REVIEW_ITEMS,
    OFFICIAL_REVIEW, PROVENANCE, SHADOWED_ITEMS, SHADOW_JSON, TOTAL_ROWS,
    is_shadowed, load_tsv as load_contract_tsv, read_contract,
    validate_authority_resolutions,
)

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
FINAL_VALUES = AUDIT / "pass20_human_final_values.tsv"
TARGETS = AUDIT / "pass20_product_targets.json"
ADOPTIONS = AUDIT / "pass21_user_directed_suggested_adoptions.tsv"
RESOLUTION_FIELDS = (
    "item_id", "resolution_kind", "authority_tier", "final_value",
    "evidence", "product_write_status",
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

class HumanReviewError(RuntimeError):
    """The final-value review contract failed."""

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
    if not header or any(None in row for row in rows):
        raise HumanReviewError(f"malformed TSV: {path}")
    return header, rows

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

def load_targets(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise HumanReviewError(f"product target manifest missing or unsafe: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1"
        or payload.get("status") != "PASS"
        or not isinstance(payload.get("items"), list)
    ):
        raise HumanReviewError("product target manifest is invalid")
    result: dict[str, dict[str, Any]] = {}
    for row in payload["items"]:
        if not isinstance(row, dict):
            raise HumanReviewError("product target manifest contains a non-object item")
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in result:
            raise HumanReviewError("product target manifest has empty/duplicate item_id")
        result[item_id] = row
    return result

def load_adoptions(path: Path) -> dict[str, str]:
    header, rows = load_tsv(path)
    required = {"item_id", "current_cn", "ds_suggested_cn", "adopted_cn", "machine_origin"}
    if not required.issubset(header):
        raise HumanReviewError("suggestion adoption table lacks required columns")
    result: dict[str, str] = {}
    for row in rows:
        item_id = row["item_id"]
        adopted = row["adopted_cn"]
        if not item_id or item_id in result or not adopted or row["machine_origin"] != "true":
            raise HumanReviewError("suggestion adoption table has an invalid row")
        result[item_id] = adopted
    return result

def _validate_authority_partition(
    source_rows: list[dict[str, str]],
    resolutions: dict[str, dict[str, str]],
    shadows: dict[str, dict[str, Any]],
    provenance_path: Path,
    effective_path: Path,
    targets: dict[str, dict[str, Any]],
    adoptions: dict[str, str],
) -> None:
    _, provenance_rows = load_contract_tsv(provenance_path)
    _, effective_rows = load_contract_tsv(effective_path)
    provenance = {row["candidate_id"]: row for row in provenance_rows}
    effective = {row["key"]: row for row in effective_rows}
    if len(provenance) != len(provenance_rows) or len(effective) != len(effective_rows):
        raise HumanReviewError("provenance/effective semantic keys are not unique")
    expected_shadow_ids: set[str] = set()
    for row in source_rows:
        item_id = row["item_id"]
        if row["review_kind"] != "current-low-tier-translation-review" or item_id in resolutions:
            continue
        if item_id in adoptions:
            target = targets.get(item_id)
            semantic_key = str((target or {}).get("semantic_key", ""))
            candidates = [
                entry for entry in provenance_rows
                if entry.get("key") == semantic_key
                and entry.get("source_file") == row["source_path"]
                and entry.get("source_text") == row["japanese_or_source_original"]
            ]
            if (
                len(candidates) != 1
                or candidates[0].get("candidate_cn") != adoptions[item_id]
                or candidates[0].get("authority") != "legacy_unverified_ai_assisted"
                or candidates[0].get("selected") != "true"
            ):
                raise HumanReviewError(f"Pass21 adopted provenance binding drifted: {item_id}")
            candidate = candidates[0]
        else:
            candidate = provenance.get(row["source_key"])
            if candidate is None or candidate["source_file"] != row["source_path"]:
                raise HumanReviewError(f"source provenance binding drifted: {item_id}")
        winner = effective.get(candidate["key"])
        if winner is None:
            raise HumanReviewError(f"effective semantic key is missing: {item_id}")
        if item_id in adoptions and (
            winner.get("selected_cn") != adoptions[item_id]
            or winner.get("authority") != "legacy_unverified_ai_assisted"
            or winner.get("source_file") != row["source_path"]
        ):
            raise HumanReviewError(f"Pass21 adopted effective binding drifted: {item_id}")
        if is_shadowed(candidate, winner):
            expected_shadow_ids.add(item_id)
            shadow = shadows.get(item_id)
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
                raise HumanReviewError(f"authority shadow provenance/effective binding drifted: {item_id}")
    if expected_shadow_ids != set(shadows) or len(expected_shadow_ids) != SHADOWED_ITEMS:
        raise HumanReviewError("computed higher-authority shadow stable-ID set drifted")

def validate(
    source: Path,
    final_values: Path | None,
    authority_resolutions: Path | None = None,
    authority_shadows: Path | None = SHADOW_JSON,
    provenance_path: Path = PROVENANCE,
    effective_path: Path = EFFECTIVE,
    official_review_path: Path = OFFICIAL_REVIEW,
    contract_path: Path = CONTRACT_JSON,
    targets_path: Path = TARGETS,
    adoptions_path: Path = ADOPTIONS,
) -> dict[str, Any]:
    source_header, source_rows = load_tsv(source)
    if len(source_rows) != TOTAL_ROWS or not set(SOURCE_FIELDS).issubset(source_header):
        raise HumanReviewError(f"full_review source must contain {TOTAL_ROWS} bound rows")
    source_by_id = {row["item_id"]: row for row in source_rows}
    if len(source_by_id) != TOTAL_ROWS or "" in source_by_id:
        raise HumanReviewError("full_review source item IDs are empty or duplicated")
    resolutions = load_authority_resolutions(authority_resolutions)
    shadows = load_authority_shadows(authority_shadows)
    _, official_review_rows = load_contract_tsv(official_review_path)
    validate_authority_resolutions(source_rows, list(resolutions.values()), official_review_rows)
    if set(resolutions) & set(shadows) or not set(resolutions).issubset(source_by_id) or not set(shadows).issubset(source_by_id):
        raise HumanReviewError("authority resolution/shadow partition is invalid")
    targets = load_targets(targets_path)
    adoptions = load_adoptions(adoptions_path)
    _validate_authority_partition(
        source_rows, resolutions, shadows, provenance_path, effective_path,
        targets, adoptions,
    )
    contract = read_contract(contract_path)
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
    required_ids = set(source_by_id).difference(resolutions, shadows)
    if len(required_ids) != HUMAN_REVIEW_ITEMS or set(contract_ids.get("human_review_required", [])) != required_ids:
        raise HumanReviewError("Pass20 human final-value stable-ID set drifted")
    if any(source_by_id[item]["review_kind"] != "current-low-tier-translation-review" for item in required_ids):
        raise HumanReviewError("historical or protected row leaked into final-value gate")
    if set(targets) != required_ids:
        raise HumanReviewError("product target manifest differs from the final-value queue")
    if not set(adoptions).issubset(required_ids):
        raise HumanReviewError("suggestion adoption table contains an excluded stable ID")
    for item_id in adoptions:
        if not source_by_id[item_id]["suggested_cn"]:
            raise HumanReviewError(f"adopted suggestion lacks raw suggestion evidence: {item_id}")
    states = {
        "pending": HUMAN_REVIEW_ITEMS,
        "machine_current_retained": 0,
        "machine_suggestion_adopted": 0,
        "human_revised": 0,
        "human_review_mode_rows": 0,
        "rough_production_rows": 0,
        "unresolved": 0,
        "authority_resolved": len(resolutions),
        "higher_authority_shadowed": len(shadows),
    }
    final_sha = ""
    receipt_modes: set[str] = set()
    if final_values is not None and final_values.is_file():
        header, final_rows = load_tsv(final_values)
        if tuple(header) != FINAL_VALUE_FIELDS:
            raise HumanReviewError("final-value table has unexpected columns")
        if not final_rows:
            final_rows = []
            final_sha = sha256(final_values)
        else:
            ids = [row["item_id"] for row in final_rows]
            if len(ids) != HUMAN_REVIEW_ITEMS or len(set(ids)) != HUMAN_REVIEW_ITEMS or set(ids) != required_ids:
                raise HumanReviewError(f"final-value table must contain exactly {HUMAN_REVIEW_ITEMS} stable IDs")
            for row in final_rows:
                item_id = row["item_id"]
                final_value = row["final_value"]
                if not final_value:
                    raise HumanReviewError(f"final value is empty: {item_id}")
                source_row = source_by_id[item_id]
                try:
                    provenance_mode = provenance_mode_for_receipt(row)
                except ValueError as exc:
                    raise HumanReviewError(str(exc)) from exc
                receipt_modes.add(provenance_mode)
                try:
                    expected = expected_final_value_row(
                        source_row, targets[item_id], final_value, adoptions.get(item_id, ""),
                        provenance_mode,
                    )
                except ValueError as exc:
                    raise HumanReviewError(str(exc)) from exc
                for field in FINAL_VALUE_FIELDS:
                    if row.get(field, "") != expected[field]:
                        raise HumanReviewError(f"final-value binding drift {field}: {item_id}")
                if final_value == "<DELETE>" and source_row["current_cn"] != "<DELETE>":
                    raise HumanReviewError(f"reserved deletion token is forbidden: {item_id}")
                states[{
                    "machine-current": "machine_current_retained",
                    "machine-suggestion": "machine_suggestion_adopted",
                    "human-revision": "human_revised",
                }[row["final_origin"]]] += 1
                states[
                    "rough_production_rows"
                    if provenance_mode == ROUGH_PRODUCTION_MODE
                    else "human_review_mode_rows"
                ] += 1
            if len(receipt_modes) != 1:
                raise HumanReviewError("final-value table mixes provenance modes")
            states["pending"] = 0
            final_sha = sha256(final_values)
    elif final_values is not None and final_values.exists():
        raise HumanReviewError(f"final-value return is unsafe: {final_values}")
    completed = sum(states[key] for key in (
        "machine_current_retained", "machine_suggestion_adopted", "human_revised",
    ))
    if completed + states["pending"] != HUMAN_REVIEW_ITEMS:
        raise HumanReviewError("final-value completion partition drifted")
    provenance_mode = next(iter(receipt_modes), "pending")
    return {
        "schema": "magireco-cn-pass20-final-values-validation/2",
        "status": "PASS",
        "rows": TOTAL_ROWS,
        "machine_source_inventory": HUMAN_REVIEW_ITEMS + SHADOWED_ITEMS,
        "authority_resolved": len(resolutions),
        "higher_authority_shadowed": len(shadows),
        "authority_excluded_total": len(resolutions) + len(shadows),
        "final_values_required": HUMAN_REVIEW_ITEMS,
        "states": states,
        "final_values_received": completed,
        "all_final_values_received": states["pending"] == 0,
        "release_gate_open": states["pending"] == 0,
        "provenance_mode": provenance_mode,
        "machine_provenance_retained": (
            provenance_mode == ROUGH_PRODUCTION_MODE
            and states["rough_production_rows"] == HUMAN_REVIEW_ITEMS
        ),
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "source_sha256": sha256(source),
        "final_values_sha256": final_sha,
        "targets_sha256": sha256(targets_path),
        "adoptions_sha256": sha256(adoptions_path),
        "authority_resolutions_sha256": sha256(authority_resolutions) if authority_resolutions else "",
        "authority_shadows_sha256": sha256(authority_shadows) if authority_shadows else "",
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--final-values", type=Path, default=FINAL_VALUES)
    parser.add_argument("--authority-resolutions", type=Path)
    parser.add_argument("--authority-shadows", type=Path, default=SHADOW_JSON)
    parser.add_argument("--targets", type=Path, default=TARGETS)
    parser.add_argument("--adoptions", type=Path, default=ADOPTIONS)
    parser.add_argument("--provenance", type=Path, default=PROVENANCE)
    parser.add_argument("--effective", type=Path, default=EFFECTIVE)
    parser.add_argument("--official-review", type=Path, default=OFFICIAL_REVIEW)
    parser.add_argument("--contract", type=Path, default=CONTRACT_JSON)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--require-release-open", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate(
            args.source, args.final_values, args.authority_resolutions, args.authority_shadows,
            args.provenance, args.effective, args.official_review, args.contract, args.targets,
            args.adoptions,
        )
        payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(payload, encoding="utf-8", newline="\n")
        print(payload, end="")
        if args.require_release_open and not result["release_gate_open"]:
            print(
                f"release gate closed: all {result['final_values_required']} final values must be returned",
                file=sys.stderr,
            )
            return 3
        return 0
    except (HumanReviewError, OSError, UnicodeDecodeError, csv.Error, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
