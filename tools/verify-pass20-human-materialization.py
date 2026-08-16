#!/usr/bin/env python3
"""Verify that a closed Pass20 review is materialized into i18n and magica."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
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
WORKBOOK_REL = AUDIT_REL / "pass20_human_review.xlsx"
TARGETS_REL = AUDIT_REL / "pass20_product_targets.json"
PROTECTED_REL = AUDIT_REL / "protected_authority/protected_translation_fields.tsv"
REVIEWED_REL = Path("i18n/reviewed-candidates.tsv")
EFFECTIVE_REL = Path("i18n/generated/effective.tsv")

REVIEW_ITEMS = 199
EXACT_RUNTIME_ITEMS = 180
MAINTENANCE_ONLY_ITEMS = 19
RUNTIME_OCCURRENCES = 246
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
    expected_items: int = REVIEW_ITEMS,
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
    expected_items: int = REVIEW_ITEMS,
    expected_runtime_items: int = EXACT_RUNTIME_ITEMS,
    expected_maintenance_items: int = MAINTENANCE_ONLY_ITEMS,
    expected_occurrences: int = RUNTIME_OCCURRENCES,
) -> dict[str, int]:
    queue = index_unique(queue_rows, "item_id", "Pass20 queue")
    decisions = index_unique(decision_rows, "item_id", "decision table")
    targets = index_unique(target_rows, "item_id", "product target manifest")
    effective = index_unique(effective_rows, "key", "effective i18n table")
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
            "review_status": "human-reviewed",
        }
        for field, expected in expected_reviewed.items():
            if reviewed.get(field) != expected:
                raise MaterializationError(f"canonical reviewed candidate drift {field}: {item_id}")

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


def verify(repo_root: Path = ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    tools_root = ROOT / "tools"
    validator = load_module("pass20_materialization_validator", tools_root / "validate-dsv4-human-review.py")
    gate = validator.validate(
        repo_root / SOURCE_REL,
        repo_root / DECISIONS_REL,
        repo_root / RESOLUTIONS_REL,
    )
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
    }
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
        )

    _, queue_rows = load_tsv(repo_root / QUEUE_REL)
    _, decision_rows = load_tsv(repo_root / DECISIONS_REL)
    _, effective_rows = load_tsv(repo_root / EFFECTIVE_REL)
    reviewed_rows = load_reviewed_candidates(repo_root / REVIEWED_REL)
    target_payload = json.loads((repo_root / TARGETS_REL).read_text(encoding="utf-8"))
    expected_summary = {
        "items": REVIEW_ITEMS,
        "maintenance_rows_bound": REVIEW_ITEMS,
        "exact_runtime_items": EXACT_RUNTIME_ITEMS,
        "maintenance_only_items": MAINTENANCE_ONLY_ITEMS,
        "runtime_occurrences": RUNTIME_OCCURRENCES,
        "occurrence_collisions": 0,
        "unclassified_items": 0,
    }
    if (
        target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1"
        or target_payload.get("status") != "PASS"
        or not isinstance(target_payload.get("items"), list)
        or any(target_payload.get("summary", {}).get(key) != value for key, value in expected_summary.items())
    ):
        raise MaterializationError("Pass20 product target manifest summary or schema drifted")
    bindings = verify_materialized_bindings(
        repo_root,
        queue_rows,
        decision_rows,
        target_payload["items"],
        reviewed_rows,
        effective_rows,
    )

    protection = load_module("pass20_materialization_protection", tools_root / "v26_authority_protection.py")
    protected_rows = protection.read_tsv(repo_root / PROTECTED_REL)
    protection.validate_row_hashes(protected_rows)
    protection.verify_current_product_values(repo_root, protected_rows)
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
