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
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_REL = Path("magica/i18n_audit/release_v26_authority")
SOURCE_REL = AUDIT_REL / "dsv4_terminal_handoff/full_review.tsv"
FINAL_VALUES_REL = AUDIT_REL / "pass20_human_final_values.tsv"
RESOLUTIONS_REL = AUDIT_REL / "pass20_authority_resolutions.tsv"
QUEUE_REL = AUDIT_REL / "pass20_remaining_manual_review.tsv"
WORKBOOK_REL = AUDIT_REL / "magireco_v26_translation_review_1564.xlsx"
TARGETS_REL = AUDIT_REL / "pass20_product_targets.json"
SHADOWED_REL = AUDIT_REL / "pass20_authority_shadowed_machine_items.json"
PROTECTED_REL = AUDIT_REL / "protected_authority/protected_translation_fields.tsv"
REVIEWED_REL = Path("i18n/reviewed-candidates.tsv")
EFFECTIVE_REL = Path("i18n/generated/effective.tsv")
PROVENANCE_REL = Path("i18n/generated/input-provenance.tsv")

LOCATOR_PREFIX = (
    "magica/i18n_audit/release_v26_authority/"
    "pass20_human_final_values.tsv#"
)
FINAL_VALUE_MODES = {"human-review", "rough-production"}
JS_LITERAL = re.compile(r'(["\'])((?:(?!\1)[^\\]|\\.)*)\1')
HTML_TEXT = re.compile(r'>([^<>{}]*)<')
HTML_ATTR = re.compile(r'((?:placeholder|title|alt|value)=")([^"]*)(")')


class MaterializationError(RuntimeError):
    pass


def final_value_locator(provenance_mode: str, item_id: str) -> str:
    if provenance_mode not in FINAL_VALUE_MODES or not item_id:
        raise MaterializationError("invalid final-value locator components")
    return f"{LOCATOR_PREFIX}{provenance_mode}:{item_id}"


def parse_final_value_locator(locator: str) -> tuple[str, str] | None:
    if not locator.startswith(LOCATOR_PREFIX):
        return None
    suffix = locator[len(LOCATOR_PREFIX):]
    if ":" not in suffix:
        # Backward compatibility for a pre-mode human-review receipt.
        if not suffix:
            raise MaterializationError("empty legacy final-value locator")
        return "human-review", suffix
    mode, item_id = suffix.split(":", 1)
    if mode not in FINAL_VALUE_MODES or not item_id:
        raise MaterializationError(f"invalid final-value locator: {locator!r}")
    return mode, item_id


def receipt_provenance_profile(receipt: dict[str, str]) -> dict[str, str]:
    review_status = receipt.get("review_status", "")
    if review_status.startswith("rough-production-"):
        return {
            "mode": "rough-production", "authority": "new_proposal",
            "source_batch": "pass20-rough-production-final-values-v1",
            "match_method": "exact-semantic-key-user-directed-rough-production",
        }
    if review_status.startswith("human-"):
        return {
            "mode": "human-review", "authority": "existing_human_reviewed",
            "source_batch": "pass20-human-final-values-v1",
            "match_method": "exact-semantic-key-human-review",
        }
    raise MaterializationError("unsupported final-value provenance")


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


def exact_product_literal_count(repo_root: Path, rel: str, literal: str) -> int:
    posix = PurePosixPath(rel)
    if posix.is_absolute() or not rel or ".." in posix.parts or "\\" in rel or ":" in rel:
        raise MaterializationError(f"unsafe authority materialization path: {rel!r}")
    path = repo_root / "magica" / Path(*posix.parts)
    if not path.is_file() or path.is_symlink():
        raise MaterializationError(f"authority materialization path missing or unsafe: {rel}")
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".js":
        return sum(match.group(2) == literal for match in JS_LITERAL.finditer(text))
    if suffix == ".html":
        count = 0
        for match in HTML_TEXT.finditer(text):
            body = match.group(1)
            count += body.strip() == literal
        count += sum(match.group(2) == literal for match in HTML_ATTR.finditer(text))
        return count
    raise MaterializationError(f"unsupported authority materialization target: {rel}")


def validate_workbook_receipt(
    result: dict[str, Any], imported: bytes, committed: bytes,
    expected_items: int, expected_provenance_mode: str | None = None,
) -> None:
    if (
        result.get("status") != "PASS"
        or result.get("returned_workbook_accepted") is not True
        or result.get("receipt_rows_written") != expected_items
        or result.get("pending_in_workbook") != 0
    ):
        raise MaterializationError(
            f"completed workbook must return {expected_items} final values"
        )
    if (
        expected_provenance_mode is not None
        and result.get("provenance_mode") != expected_provenance_mode
    ):
        raise MaterializationError("completed workbook provenance mode drifted")
    if imported != committed:
        raise MaterializationError("completed workbook does not reproduce the committed final-value TSV")


def verify_materialized_bindings(
    repo_root: Path,
    queue_rows: list[dict[str, str]],
    final_value_rows: list[dict[str, str]],
    target_rows: list[dict[str, Any]],
    reviewed_rows: list[dict[str, str]],
    effective_rows: list[dict[str, str]],
    *,
    expected_items: int | None = None,
    expected_runtime_items: int | None = None,
    expected_maintenance_items: int | None = None,
    expected_occurrences: int | None = None,
    structure_check: Any | None = None,
) -> dict[str, Any]:
    queue = index_unique(queue_rows, "item_id", "Pass20 queue")
    final_values = index_unique(final_value_rows, "item_id", "final-value table")
    targets = index_unique(target_rows, "item_id", "product target manifest")
    effective = index_unique(effective_rows, "key", "effective i18n table")
    expected_items = len(queue) if expected_items is None else expected_items
    if (
        len(queue) != expected_items or set(queue) != set(targets)
        or set(final_values) != set(queue)
    ):
        raise MaterializationError("Pass20 queue and product target IDs/count differ")

    profiles = {item_id: receipt_provenance_profile(row) for item_id, row in final_values.items()}
    provenance_modes = {profile["mode"] for profile in profiles.values()}
    if len(provenance_modes) != 1:
        raise MaterializationError("canonical final values mix provenance modes")
    provenance_mode = next(iter(provenance_modes))

    pass20_reviewed = [
        (parsed, row) for row in reviewed_rows
        if (parsed := parse_final_value_locator(row.get("source_locator", ""))) is not None
        and parsed[0] == provenance_mode
    ]
    reviewed_by_id: dict[str, dict[str, str]] = {}
    for parsed, row in pass20_reviewed:
        _mode, item_id = parsed
        if not item_id or item_id in reviewed_by_id:
            raise MaterializationError(f"duplicate or invalid Pass20 reviewed candidate: {item_id!r}")
        reviewed_by_id[item_id] = row
    if set(reviewed_by_id) != set(queue):
        raise MaterializationError("current-mode canonical rows do not exactly cover the Pass20 queue")

    operations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    runtime_items = 0
    maintenance_items = 0
    occurrence_count = 0
    for item_id, source in queue.items():
        receipt = final_values.get(item_id)
        target = targets[item_id]
        reviewed = reviewed_by_id[item_id]
        if receipt is None:
            raise MaterializationError(f"final-value row missing: {item_id}")
        final_value = receipt.get("final_value", "")
        if not final_value:
            raise MaterializationError(f"returned final value is empty: {item_id}")
        if structure_check is not None:
            try:
                structure_check(item_id, source.get("current_cn", ""), final_value)
            except Exception as exc:
                raise MaterializationError(f"translation structure gate failed: {item_id}: {exc}") from exc
        profile = profiles[item_id]
        authority = profile["authority"]
        source_batch = profile["source_batch"]
        match_method = profile["match_method"]
        expected_reviewed = {
            "scope": target.get("maintenance_scope", ""),
            "path_prefix": target.get("path_prefix", ""),
            "source_text": source.get("japanese_or_source_original", ""),
            "candidate_cn": final_value,
            "status": "present",
            "authority": authority,
            "source_batch": source_batch,
            "source_locator": final_value_locator(provenance_mode, item_id),
            "match_method": match_method,
        }
        for field, expected in expected_reviewed.items():
            if reviewed.get(field) != expected:
                raise MaterializationError(f"canonical reviewed candidate drift {field}: {item_id}")
        if reviewed.get("review_status") != receipt.get("review_status"):
            raise MaterializationError(f"canonical review status drift: {item_id}")
        if reviewed.get("machine_translated") != receipt.get("machine_translated"):
            raise MaterializationError(f"canonical machine-origin status drift: {item_id}")

        semantic_key = target.get("semantic_key")
        winner = effective.get(semantic_key)
        if winner is None:
            raise MaterializationError(f"effective i18n winner missing: {item_id}")
        if winner.get("selected_cn") != final_value:
            raise MaterializationError(f"effective final-value winner drift: {item_id}")
        if provenance_mode == "human-review":
            if (
                winner.get("authority") != "existing_human_reviewed"
                or winner.get("source_file") != "i18n/reviewed-candidates.tsv"
                or winner.get("source_batch") != "pass20-human-final-values-v1"
            ):
                raise MaterializationError(f"effective human-reviewed winner drift: {item_id}")
        elif winner.get("authority") != "legacy_unverified_ai_assisted":
            raise MaterializationError(f"effective rough-production low-tier winner drift: {item_id}")

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
                "scope": target.get("maintenance_scope", ""),
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
        expected_literals: dict[tuple[str, str], int] = defaultdict(int)
        for operation in file_operations:
            expected_literals[(operation["after"], operation["scope"])] += 1
        for (after, scope), expected_count in expected_literals.items():
            actual_count = (
                text.count(after)
                if scope == "fragment"
                else exact_product_literal_count(repo_root, rel, after)
            )
            if actual_count != expected_count:
                item_ids = sorted({
                    operation["item_id"] for operation in file_operations
                    if operation["after"] == after and operation["scope"] == scope
                })
                raise MaterializationError(
                    "final runtime semantic count drift: "
                    f"{rel} items={item_ids} expected={expected_count} actual={actual_count}"
                )

    return {
        "provenance_mode": provenance_mode,
        "canonical_human_reviewed": (
            len(reviewed_by_id) if provenance_mode == "human-review" else 0
        ),
        "effective_human_reviewed": (
            expected_items if provenance_mode == "human-review" else 0
        ),
        "canonical_rough_production": (
            len(reviewed_by_id) if provenance_mode == "rough-production" else 0
        ),
        "effective_low_tier_rough_production": (
            expected_items if provenance_mode == "rough-production" else 0
        ),
        "exact_runtime_items": runtime_items,
        "maintenance_only_items": maintenance_items,
        "runtime_occurrences": occurrence_count,
    }


def verify_higher_authority_shadows(
    repo_root: Path,
    shadow_rows: list[dict[str, Any]],
    reviewed_rows: list[dict[str, str]],
    provenance_rows: list[dict[str, str]],
    effective_rows: list[dict[str, str]],
    materialization_contracts: dict[str, dict[str, Any]],
) -> dict[str, int]:
    shadows = index_unique(shadow_rows, "item_id", "higher-authority shadow manifest")
    provenance = index_unique(provenance_rows, "candidate_id", "input provenance table")
    effective = index_unique(effective_rows, "key", "effective i18n table")
    reviewed_ids = {
        parsed[1]
        for row in reviewed_rows
        if (parsed := parse_final_value_locator(row.get("source_locator", ""))) is not None
    }
    materialized_ids: set[str] = set()
    checked_paths = 0
    machine_occurrences = 0
    effective_occurrences = 0
    materialized_occurrences = 0
    for item_id, row in shadows.items():
        if row.get("product_write_forbidden") is not True or row.get("product_write_allowed") is True:
            raise MaterializationError(f"higher-authority shadow permits product write: {item_id}")
        if item_id in reviewed_ids:
            raise MaterializationError(f"higher-authority shadow entered human canonical input: {item_id}")
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
        expected_materialization = materialization_contracts.get(item_id)
        recorded_materialization = row.get("authority_materialization")
        if expected_materialization is None:
            if recorded_materialization is not None:
                raise MaterializationError(
                    f"unexpected authority materialization contract: {item_id}"
                )
            continue
        if not isinstance(recorded_materialization, dict):
            raise MaterializationError(f"authority materialization contract is missing: {item_id}")
        if (
            row.get("machine_current_cn") != expected_materialization.get("machine_cn")
            or row.get("effective_cn") != expected_materialization.get("effective_cn")
            or recorded_materialization.get("machine_cn") != expected_materialization.get("machine_cn")
            or recorded_materialization.get("effective_cn") != expected_materialization.get("effective_cn")
        ):
            raise MaterializationError(f"authority materialization literal drift: {item_id}")
        expected_paths = expected_materialization.get("paths")
        repaired_paths = expected_materialization.get("repaired_paths")
        recorded_paths = recorded_materialization.get("product_paths")
        if (
            not isinstance(expected_paths, dict) or not isinstance(repaired_paths, set)
            or not repaired_paths or not repaired_paths.issubset(expected_paths)
            or not isinstance(recorded_paths, list)
        ):
            raise MaterializationError(f"authority materialization paths are invalid: {item_id}")
        recorded_by_path = index_unique(
            recorded_paths, "path", f"authority materialization path list for {item_id}"
        )
        if set(recorded_by_path) != set(expected_paths):
            raise MaterializationError(f"authority materialization path set drift: {item_id}")
        expected_total = sum(expected_paths.values())
        materialized_total = sum(expected_paths[rel] for rel in repaired_paths)
        if recorded_materialization.get("expected_effective_occurrences") != expected_total:
            raise MaterializationError(f"authority materialization total drift: {item_id}")
        if recorded_materialization.get("materialized_from_machine_occurrences") != materialized_total:
            raise MaterializationError(f"authority materialization repair total drift: {item_id}")
        for rel, expected_count in expected_paths.items():
            if not isinstance(expected_count, int) or expected_count <= 0:
                raise MaterializationError(
                    f"authority materialization expected count is invalid: {item_id} {rel}"
                )
            recorded = recorded_by_path[rel]
            if (
                recorded.get("machine_count") != 0
                or recorded.get("effective_count") != expected_count
                or recorded.get("expected_effective_count") != expected_count
                or recorded.get("materialized_from_machine") is not (rel in repaired_paths)
            ):
                raise MaterializationError(
                    f"authority materialization manifest count drift: {item_id} {rel}"
                )
            actual_machine = exact_product_literal_count(
                repo_root, rel, expected_materialization["machine_cn"]
            )
            actual_effective = exact_product_literal_count(
                repo_root, rel, expected_materialization["effective_cn"]
            )
            if actual_machine != 0 or actual_effective != expected_count:
                raise MaterializationError(
                    "authority runtime value is not materialized: "
                    f"{item_id} {rel} machine={actual_machine} "
                    f"effective={actual_effective} expected={expected_count}"
                )
            checked_paths += 1
            machine_occurrences += actual_machine
            effective_occurrences += actual_effective
            if rel in repaired_paths:
                materialized_occurrences += actual_effective
        materialized_ids.add(item_id)
    if materialized_ids != set(materialization_contracts):
        raise MaterializationError("authority materialization item set drift")
    return {
        "higher_authority_shadowed_items": len(shadows),
        "product_write_forbidden_items": len(shadows),
        "authority_materialization_items": len(materialized_ids),
        "authority_materialization_paths_checked": checked_paths,
        "authority_verified_occurrences": effective_occurrences,
        "authority_materialized_occurrences": materialized_occurrences,
        "shadowed_low_tier_candidates_written": machine_occurrences,
        "shadowed_product_writes": machine_occurrences,
    }


def verify(repo_root: Path = ROOT) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    tools_root = ROOT / "tools"
    validator = load_module("pass20_materialization_validator", tools_root / "validate-dsv4-human-review.py")
    gate = validator.validate(
        repo_root / SOURCE_REL,
        repo_root / FINAL_VALUES_REL,
        repo_root / RESOLUTIONS_REL,
        repo_root / SHADOWED_REL,
        targets_path=repo_root / TARGETS_REL,
        adoptions_path=repo_root / AUDIT_REL / "pass21_user_directed_suggested_adoptions.tsv",
    )
    stage_contract = load_module(
        "pass20_materialization_contract", tools_root / "stage-pass20-human-review-product.py"
    )
    _, source_rows = load_tsv(repo_root / SOURCE_REL)
    _, queue_rows = load_tsv(repo_root / QUEUE_REL)
    _, resolution_rows = load_tsv(repo_root / RESOLUTIONS_REL)
    _, final_value_rows = load_tsv(repo_root / FINAL_VALUES_REL)
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
    review_constants = load_module(
        "pass20_review_contract_constants", tools_root / "pass20_review_contract.py"
    )
    shadow_bindings = verify_higher_authority_shadows(
        repo_root, shadow_contract["items"], reviewed_rows,
        provenance_rows, effective_rows,
        review_constants.SHADOW_RUNTIME_MATERIALIZATIONS,
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
        or gate.get("final_values_required") != review_contract["human_review_items"]
    ):
        raise MaterializationError("human gate and materialization contract counts differ")
    result: dict[str, Any] = {
        "schema": "magireco-cn-pass20-final-value-materialization-verification/2",
        "status": "PASS",
        "release_gate_open": gate["release_gate_open"],
        "final_values_required": gate["final_values_required"],
        "final_values_received": gate["final_values_received"],
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
        imported_path = Path(temp) / "imported-final-values.tsv"
        workbook_result = importer.import_workbook(
            repo_root / WORKBOOK_REL,
            repo_root / QUEUE_REL,
            repo_root / SOURCE_REL,
            repo_root / TARGETS_REL,
            imported_path,
            accept_returned=gate.get("provenance_mode") == "human-review",
            accept_rough_production=gate.get("provenance_mode") == "rough-production",
        )
        validate_workbook_receipt(
            workbook_result,
            imported_path.read_bytes(),
            (repo_root / FINAL_VALUES_REL).read_bytes(),
            expected_items=len(queue_rows),
            expected_provenance_mode=gate.get("provenance_mode"),
        )
    bindings = verify_materialized_bindings(
        repo_root,
        queue_rows,
        final_value_rows,
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
        "completed_workbook_reproduces_final_values": True,
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
                f"release gate closed: {result['pending']} final values remain",
                file=sys.stderr,
            )
            return 3
        return 0
    except (MaterializationError, OSError, UnicodeError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
