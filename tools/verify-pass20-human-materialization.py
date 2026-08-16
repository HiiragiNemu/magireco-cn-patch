#!/usr/bin/env python3
"""Verify that a closed Pass20 review is materialized into i18n and magica."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_REL = Path("magica/i18n_audit/release_v26_authority")
SOURCE_REL = AUDIT_REL / "dsv4_terminal_handoff/full_review.tsv"
DECISIONS_REL = AUDIT_REL / "dsv4_human_decisions.tsv"
RESOLUTIONS_REL = AUDIT_REL / "pass20_authority_resolutions.tsv"
QUEUE_REL = AUDIT_REL / "pass20_remaining_manual_review.tsv"
WORKBOOK_REL = AUDIT_REL / "magireco_v26_translation_review_1565.xlsx"
TARGETS_REL = AUDIT_REL / "pass20_product_targets.json"
SHADOWED_REL = AUDIT_REL / "pass20_authority_shadowed_machine_items.json"
PROTECTED_REL = AUDIT_REL / "protected_authority/protected_translation_fields.tsv"
REVIEWED_REL = Path("i18n/reviewed-candidates.tsv")
EFFECTIVE_REL = Path("i18n/generated/effective.tsv")
PROVENANCE_REL = Path("i18n/generated/input-provenance.tsv")

LOCATOR_PREFIX = (
    "magica/i18n_audit/release_v26_authority/"
    "dsv4_human_decisions.tsv#"
)


class MaterializationError(RuntimeError):
    pass


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise MaterializationError(f"could not load tool module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file() or path.is_symlink():
        raise MaterializationError(f"TSV missing or unsafe: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise MaterializationError(f"TSV must be UTF-8-no-BOM with LF endings: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if not header or any(None in row for row in rows):
        raise MaterializationError(f"invalid TSV: {path}")
    return header, rows


def load_reviewed_candidates(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.is_symlink():
        raise MaterializationError(f"reviewed candidate input missing or unsafe: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise MaterializationError("reviewed-candidates.tsv must be UTF-8-no-BOM with LF endings")
    lines = raw.decode("utf-8").splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if line.startswith("# scope\t")),
        None,
    )
    if header_index is None:
        raise MaterializationError("reviewed-candidates.tsv header is missing")
    payload = [lines[header_index][2:]]
    payload.extend(
        line for line in lines[header_index + 1 :]
        if line and not line.startswith("#")
    )
    reader = csv.DictReader(io.StringIO("\n".join(payload) + "\n"), delimiter="\t")
    rows = list(reader)
    if not reader.fieldnames or any(None in row for row in rows):
        raise MaterializationError("reviewed-candidates.tsv structure is invalid")
    return rows


def index_unique(rows: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str) or not value or value in result:
            raise MaterializationError(f"{label} has an empty or duplicate {field}: {value!r}")
        result[value] = row
    return result


def decode_cell(value: str) -> str:
    return value.replace("\\t", "\t").replace("\\n", "\n").replace("\\\\", "\\")


def validate_workbook_receipt(
    result: dict[str, Any], imported: bytes, committed: bytes,
    expected_items: int,
) -> None:
    counts = result.get("decision_counts")
    if not isinstance(counts, dict):
        raise MaterializationError("completed workbook decision counts are missing")
    if (
        result.get("status") != "PASS"
        or result.get("decisions_imported") != expected_items
        or result.get("pending_in_workbook") != 0
        or sum(counts.values()) != expected_items
        or counts.get("unresolved") != 0
    ):
        raise MaterializationError(
            f"completed workbook must contain {expected_items} closed decisions and zero unresolved rows"
        )
    if imported != committed:
        raise MaterializationError("completed workbook does not reproduce the committed decision TSV")


def verify_materialized_bindings(
    repo_root: Path,
    queue_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    target_rows: list[dict[str, Any]],
    reviewed_rows: list[dict[str, str]],
    effective_rows: list[dict[str, str]],
    *,
    expected_items: int | None = None,
    expected_runtime_items: int | None = None,
    expected_maintenance_items: int | None = None,
    expected_occurrences: int | None = None,
    structure_check: Any | None = None,
) -> dict[str, int]:
    queue = index_unique(queue_rows, "item_id", "Pass20 queue")
    decisions = index_unique(decision_rows, "item_id", "decision table")
    targets = index_unique(target_rows, "item_id", "product target manifest")
    effective = index_unique(effective_rows, "key", "effective i18n table")
    expected_items = len(queue) if expected_items is None else expected_items
    if len(queue) != expected_items or set(queue) != set(targets):
        raise MaterializationError("Pass20 queue and product target IDs/count differ")

    pass20_reviewed = [
        row for row in reviewed_rows
        if row.get("source_locator", "").startswith(LOCATOR_PREFIX)
    ]
    reviewed_by_id: dict[str, dict[str, str]] = {}
    for row in pass20_reviewed:
        item_id = row["source_locator"][len(LOCATOR_PREFIX):]
        if not item_id or item_id in reviewed_by_id:
            raise MaterializationError(f"duplicate or invalid Pass20 reviewed candidate: {item_id!r}")
        reviewed_by_id[item_id] = row
    if set(reviewed_by_id) != set(queue):
        raise MaterializationError("human-reviewed canonical rows do not exactly cover the Pass20 queue")

    operations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    runtime_items = 0
    maintenance_items = 0
    occurrence_count = 0
    for item_id, source in queue.items():
        decision = decisions.get(item_id)
        target = targets[item_id]
        reviewed = reviewed_by_id[item_id]
        if decision is None:
            raise MaterializationError(f"decision row missing: {item_id}")
        if decision.get("human_decision") not in {"approve-current", "revise"}:
            raise MaterializationError(f"decision is not publishable: {item_id}")
        final_value = decision.get("final_value", "")
        if not final_value:
            raise MaterializationError(f"decision final value is empty: {item_id}")
        if structure_check is not None:
            try:
                structure_check(item_id, source.get("current_cn", ""), final_value)
            except Exception as exc:
                raise MaterializationError(f"translation structure gate failed: {item_id}: {exc}") from exc
        expected_reviewed = {
            "scope": target.get("maintenance_scope", ""),
            "path_prefix": target.get("path_prefix", ""),
            "source_text": source.get("japanese_or_source_original", ""),
            "candidate_cn": final_value,
            "status": "present",
            "authority": "existing_human_reviewed",
            "source_batch": "pass20-human-review-v1",
            "source_locator": LOCATOR_PREFIX + item_id,
            "match_method": "exact-semantic-key-human-review",
        }
        for field, expected in expected_reviewed.items():
            if reviewed.get(field) != expected:
                raise MaterializationError(f"canonical reviewed candidate drift {field}: {item_id}")
        if not reviewed.get("review_status", "").startswith("human-reviewed"):
            raise MaterializationError(f"canonical review status drift: {item_id}")
        expected_machine = "false" if decision.get("human_decision") == "revise" else "unknown"
        if reviewed.get("machine_translated") != expected_machine:
            raise MaterializationError(f"canonical machine-origin status drift: {item_id}")

        semantic_key = target.get("semantic_key")
        winner = effective.get(semantic_key)
        if winner is None:
            raise MaterializationError(f"effective i18n winner missing: {item_id}")
        if (
            winner.get("selected_cn") != final_value
            or winner.get("authority") != "existing_human_reviewed"
            or winner.get("source_file") != "i18n/reviewed-candidates.tsv"
            or winner.get("source_batch") != "pass20-human-review-v1"
        ):
            raise MaterializationError(f"effective human-reviewed winner drift: {item_id}")

        application_allowed = target.get("application_allowed") is True
        occurrences = target.get("occurrences")
        if not isinstance(occurrences, list):
            raise MaterializationError(f"target occurrences are invalid: {item_id}")
        if not application_allowed:
            maintenance_items += 1
            # Some maintenance-only rows retain declared or drifted paths as
            # audit evidence.  They remain non-applicable precisely because
            # the manifest contains no verified occurrence to write.
            if occurrences:
                raise MaterializationError(f"maintenance-only item claims a runtime occurrence: {item_id}")
            if not str(target.get("match_status", "")).startswith("maintenance-only-"):
                raise MaterializationError(f"maintenance-only target status drift: {item_id}")
            continue
        runtime_items += 1
        if not occurrences:
            raise MaterializationError(f"runtime item has no occurrence: {item_id}")
        before = decode_cell(str(target.get("current_cn", "")))
        after = decode_cell(final_value)
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                raise MaterializationError(f"runtime occurrence is invalid: {item_id}")
            path = occurrence.get("path")
            start = occurrence.get("start")
            end = occurrence.get("end")
            if (
                not isinstance(path, str) or not path
                or not isinstance(start, int) or not isinstance(end, int)
                or start < 0 or end < start or end - start != len(before)
                or path not in target.get("product_target_paths", [])
            ):
                raise MaterializationError(f"runtime occurrence contract drift: {item_id}")
            operations[path].append({
                "item_id": item_id,
                "start": start,
                "end": end,
                "before": before,
                "after": after,
            })
            occurrence_count += 1

    expected_runtime_items = runtime_items if expected_runtime_items is None else expected_runtime_items
    expected_maintenance_items = (
        maintenance_items if expected_maintenance_items is None else expected_maintenance_items
    )
    expected_occurrences = occurrence_count if expected_occurrences is None else expected_occurrences
    if runtime_items != expected_runtime_items:
        raise MaterializationError(f"expected {expected_runtime_items} runtime items, got {runtime_items}")
    if maintenance_items != expected_maintenance_items:
        raise MaterializationError(
            f"expected {expected_maintenance_items} maintenance-only items, got {maintenance_items}"
        )
    if occurrence_count != expected_occurrences:
        raise MaterializationError(
            f"expected {expected_occurrences} runtime occurrences, got {occurrence_count}"
        )

    for rel, file_operations in operations.items():
        product = repo_root / "magica" / rel
        if not product.is_file() or product.is_symlink():
            raise MaterializationError(f"runtime target missing or unsafe: {rel}")
        text = product.read_text(encoding="utf-8")
        shift = 0
        previous_end = -1
        for operation in sorted(file_operations, key=lambda row: (row["start"], row["end"])):
            if operation["start"] < previous_end:
                raise MaterializationError(f"runtime target occurrences overlap: {rel}")
            start = operation["start"] + shift
            after = operation["after"]
            if text[start:start + len(after)] != after:
                raise MaterializationError(
                    f"human-reviewed runtime value is not materialized: {operation['item_id']} {rel}"
                )
            shift += len(after) - len(operation["before"])
            previous_end = operation["end"]

    return {
        "canonical_human_reviewed": len(reviewed_by_id),
        "effective_human_reviewed": expected_items,
        "exact_runtime_items": runtime_items,
        "maintenance_only_items": maintenance_items,
        "runtime_occurrences": occurrence_count,
    }


def verify_higher_authority_shadows(
    shadow_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, str]],
    reviewed_rows: list[dict[str, str]],
    provenance_rows: list[dict[str, str]],
    effective_rows: list[dict[str, str]],
) -> dict[str, int]:
    shadows = index_unique(shadow_rows, "item_id", "higher-authority shadow manifest")
    decisions = index_unique(decision_rows, "item_id", "decision table")
    provenance = index_unique(provenance_rows, "candidate_id", "input provenance table")
    effective = index_unique(effective_rows, "key", "effective i18n table")
    reviewed_ids = {
        row.get("source_locator", "")[len(LOCATOR_PREFIX):]
        for row in reviewed_rows
        if row.get("source_locator", "").startswith(LOCATOR_PREFIX)
    }
    decision_fields = (
        "human_decision", "reviewer", "timestamp", "final_value", "human_revision", "human_notes",
    )
    for item_id, row in shadows.items():
        if row.get("product_write_forbidden") is not True or row.get("product_write_allowed") is True:
            raise MaterializationError(f"higher-authority shadow permits product write: {item_id}")
        if item_id in reviewed_ids:
            raise MaterializationError(f"higher-authority shadow entered human canonical input: {item_id}")
        decision = decisions.get(item_id)
        if decision is None or any(decision.get(field, "") for field in decision_fields):
            raise MaterializationError(f"higher-authority shadow carries a human decision: {item_id}")
        source_key = row.get("source_key")
        expected_cn = row.get("effective_cn")
        expected_authority = row.get("effective_tier")
        if not all(isinstance(value, str) and value for value in (
            source_key, expected_cn, expected_authority, row.get("evidence"),
        )):
            raise MaterializationError(f"higher-authority shadow evidence is incomplete: {item_id}")
        low_tier = provenance.get(source_key)
        if low_tier is None:
            raise MaterializationError(f"higher-authority shadow source provenance is missing: {item_id}")
        if (
            low_tier.get("source_file") != row.get("source_path")
            or low_tier.get("source_text") != row.get("japanese_or_source_original")
            or low_tier.get("candidate_cn") != row.get("machine_current_cn")
            or low_tier.get("selected") != "false"
            or low_tier.get("authority") not in {
                "legacy_unverified_ai_assisted", "new_llm_translation", "machine_translation",
            }
        ):
            raise MaterializationError(f"higher-authority shadow low-tier binding drift: {item_id}")
        semantic_key = low_tier.get("key")
        if not semantic_key:
            raise MaterializationError(f"higher-authority shadow semantic key is missing: {item_id}")
        winner = effective.get(semantic_key)
        if winner is None:
            raise MaterializationError(f"higher-authority effective winner is missing: {item_id}")
        if (
            winner.get("selected_cn") != expected_cn
            or winner.get("authority") != expected_authority
            or winner.get("source_file") != row.get("effective_source_file")
            or str(winner.get("source_line")) != str(row.get("effective_source_line"))
            or winner.get("authority") in {
                "legacy_unverified_ai_assisted", "new_llm_translation", "machine_translation",
            }
        ):
            raise MaterializationError(f"higher-authority effective winner drift: {item_id}")
    return {
        "higher_authority_shadowed_items": len(shadows),
        "product_write_forbidden_items": len(shadows),
        "shadowed_low_tier_candidates_written": 0,
        "shadowed_product_writes": 0,
    }


def verify(repo_root: Path = ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    tools_root = ROOT / "tools"
    validator = load_module("pass20_materialization_validator", tools_root / "validate-dsv4-human-review.py")
    gate = validator.validate(
        repo_root / SOURCE_REL,
        repo_root / DECISIONS_REL,
        repo_root / RESOLUTIONS_REL,
        repo_root / SHADOWED_REL,
    )
    stage_contract = load_module(
        "pass20_materialization_contract", tools_root / "stage-pass20-human-review-product.py"
    )
    _, source_rows = load_tsv(repo_root / SOURCE_REL)
    _, queue_rows = load_tsv(repo_root / QUEUE_REL)
    _, resolution_rows = load_tsv(repo_root / RESOLUTIONS_REL)
    _, decision_rows = load_tsv(repo_root / DECISIONS_REL)
    _, provenance_rows = load_tsv(repo_root / PROVENANCE_REL)
    _, effective_rows = load_tsv(repo_root / EFFECTIVE_REL)
    reviewed_rows = load_reviewed_candidates(repo_root / REVIEWED_REL)
    target_path = repo_root / TARGETS_REL
    shadow_path = repo_root / SHADOWED_REL
    target_payload = json.loads(target_path.read_text(encoding="utf-8"))
    if (
        target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1"
        or target_payload.get("status") != "PASS"
        or not isinstance(target_payload.get("items"), list)
    ):
        raise MaterializationError("Pass20 product target manifest schema or items drifted")
    try:
        target_contract = stage_contract.derive_target_contract(
            target_payload["items"], target_payload.get("summary")
        )
        shadow_contract = stage_contract.load_shadowed_contract(shadow_path)
    except Exception as exc:
        raise MaterializationError(f"Pass20 materialization contract is invalid: {exc}") from exc
    if target_contract["shadowed_ids"]:
        raise MaterializationError("higher-authority shadow leaked into human product targets")
    queue_ids = {row.get("item_id") for row in queue_rows}
    resolution_ids = {row.get("item_id") for row in resolution_rows}
    source_ids = {row.get("item_id") for row in source_rows}
    if (
        len(queue_ids) != len(queue_rows)
        or len(resolution_ids) != len(resolution_rows)
        or len(source_ids) != len(source_rows)
        or queue_ids.intersection(resolution_ids)
        or queue_ids.intersection(shadow_contract["item_ids"])
        or resolution_ids.intersection(shadow_contract["item_ids"])
        or source_ids != queue_ids.union(resolution_ids, shadow_contract["item_ids"])
    ):
        raise MaterializationError("source/review/resolution/shadow partition drifted")
    try:
        stage_contract.validate_queue_source_bindings(queue_rows, source_rows)
    except Exception as exc:
        raise MaterializationError(f"Pass20 queue/source binding is invalid: {exc}") from exc
    shadow_bindings = verify_higher_authority_shadows(
        shadow_contract["items"], decision_rows, reviewed_rows, provenance_rows, effective_rows,
    )
    protection = load_module("pass20_materialization_protection", tools_root / "v26_authority_protection.py")
    protected_rows = protection.read_tsv(repo_root / PROTECTED_REL)
    protection.validate_row_hashes(protected_rows)
    protection.verify_current_product_values(repo_root, protected_rows)
    review_contract = {
        "machine_inventory_items": len(queue_rows) + shadow_contract["count"],
        "human_review_items": len(queue_rows),
        "materialization_items": target_contract["materialization_items"],
        "higher_authority_shadowed_items": shadow_contract["count"],
        "product_write_forbidden_items": shadow_contract["count"],
        "authority_resolution_items": len(resolution_rows),
        "exact_runtime_items": target_contract["exact_runtime_items"],
        "maintenance_only_items": target_contract["maintenance_only_items"],
        "runtime_occurrences": target_contract["runtime_occurrences"],
        "global_items": target_contract["global_items"],
        "override_items": target_contract["override_items"],
        "fragment_items": target_contract["fragment_items"],
        "shadowed_low_tier_candidates_written": 0,
        "shadowed_product_writes": 0,
        "source_records_sha256": sha256((repo_root / QUEUE_REL).read_bytes()).hexdigest(),
        "target_contract_sha256": sha256(target_path.read_bytes()).hexdigest(),
        "authority_shadow_manifest_sha256": sha256(shadow_path.read_bytes()).hexdigest(),
        "authority_resolutions_sha256": sha256((repo_root / RESOLUTIONS_REL).read_bytes()).hexdigest(),
    }
    if (
        review_contract["human_review_items"] != review_contract["materialization_items"]
        or review_contract["machine_inventory_items"]
        != review_contract["materialization_items"] + review_contract["higher_authority_shadowed_items"]
        or gate.get("decision_required") != review_contract["human_review_items"]
    ):
        raise MaterializationError("human gate and materialization contract counts differ")
    result: dict[str, Any] = {
        "schema": "magireco-cn-pass20-human-materialization-verification/1",
        "status": "PASS",
        "release_gate_open": gate["release_gate_open"],
        "decision_required": gate["decision_required"],
        "decided": gate["decided"],
        "pending": gate["states"]["pending"],
        "unresolved": gate["states"]["unresolved"],
        "materialization_verified": False,
        "product_tree_writes": False,
        "protected_text_changes": 0,
        "review_contract": review_contract,
        "machine_inventory_items": review_contract["machine_inventory_items"],
        "human_review_items": review_contract["human_review_items"],
        "higher_authority_shadowed_items": shadow_contract["count"],
        "product_write_forbidden_items": shadow_contract["count"],
        "shadowed_low_tier_candidates_written": 0,
        "shadowed_product_writes": 0,
        "protected_fields_checked": len(protected_rows),
    }
    result.update(shadow_bindings)
    if not gate["release_gate_open"]:
        return result

    importer = load_module("pass20_materialization_importer", tools_root / "import-pass20-human-review-xlsx.py")
    with tempfile.TemporaryDirectory(prefix="pass20-materialization-verify-") as temp:
        imported_path = Path(temp) / "imported-decisions.tsv"
        workbook_result = importer.import_workbook(
            repo_root / WORKBOOK_REL,
            repo_root / QUEUE_REL,
            repo_root / SOURCE_REL,
            repo_root / DECISIONS_REL,
            repo_root / TARGETS_REL,
            imported_path,
        )
        validate_workbook_receipt(
            workbook_result,
            imported_path.read_bytes(),
            (repo_root / DECISIONS_REL).read_bytes(),
            expected_items=len(queue_rows),
        )
    bindings = verify_materialized_bindings(
        repo_root,
        queue_rows,
        decision_rows,
        target_payload["items"],
        reviewed_rows,
        effective_rows,
        expected_items=review_contract["materialization_items"],
        expected_runtime_items=review_contract["exact_runtime_items"],
        expected_maintenance_items=review_contract["maintenance_only_items"],
        expected_occurrences=review_contract["runtime_occurrences"],
        structure_check=stage_contract.validate_translation_structure,
    )
    result.update(bindings)
    result.update({
        "materialization_verified": True,
        "completed_workbook_reproduces_decisions": True,
        "protected_fields_checked": len(protected_rows),
    })
    return result


def write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--require-release-open", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify(args.repo_root)
        if args.report:
            write_report(args.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        if args.require_release_open and not result["release_gate_open"]:
            print(
                f"release gate closed: {result['pending']} decisions remain",
                file=sys.stderr,
            )
            return 3
        return 0
    except (MaterializationError, OSError, UnicodeError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
