#!/usr/bin/env python3
"""Materialize returned Pass20 final values into an external product copy."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import difflib
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
SOURCE = AUDIT / "dsv4_terminal_handoff/full_review.tsv"
FINAL_VALUES = AUDIT / "pass20_human_final_values.tsv"
RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
TARGETS = AUDIT / "pass20_product_targets.json"
SHADOWED = AUDIT / "pass20_authority_shadowed_machine_items.json"
QUEUE = AUDIT / "pass20_remaining_manual_review.tsv"
PROTECTED = AUDIT / "protected_authority/protected_translation_fields.tsv"
FINAL_VALUES_REL = Path("magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv")
REVIEW_CONTRACT_REL = Path("magica/i18n_audit/release_v26_authority/pass20_review_contract.json")
ADOPTIONS = AUDIT / "pass21_user_directed_suggested_adoptions.tsv"
WORKBOOK_REL = Path(
    "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx"
)
CANONICAL_I18N_RELS = (
    Path("i18n/reviewed-candidates.tsv"),
    Path("i18n/generated/conflicts.tsv"),
    Path("i18n/generated/effective.tsv"),
    Path("i18n/generated/input-provenance.tsv"),
    Path("i18n/generated/summary.json"),
)
REVIEWED_COLUMNS = (
    "scope", "path_prefix", "source_text", "candidate_cn", "status", "authority",
    "source_batch", "source_locator", "source_sha256", "match_method",
    "machine_translated", "confidence", "review_status", "evidence",
)
FINAL_VALUE_LOCATOR_BASE = (
    "magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv#"
)
JS_LIT = re.compile(r'(["\'])((?:(?!\1)[^\\]|\\.)*)\1')
HTML_TEXT = re.compile(r'>([^<>{}]*)<')
HTML_ATTR = re.compile(r'((?:placeholder|title|alt|value)=")([^"]*)(")')
SENSITIVE_HTML_ATTR = re.compile(
    r"\b(id|class|href|src|name|data-[A-Za-z0-9_.:-]+)\s*=\s*([\"'])(.*?)\2",
    re.IGNORECASE | re.DOTALL,
)
PLACEHOLDER = re.compile(
    r"\{\d+\}|\{\{[^{}]+\}\}|%(?:\d+\$)?[-+#0 .'\d]*(?:hh|h|ll|l|L|z|j|t)?[diuoxXfFeEgGaAcspn]"
)
EJS_TOKEN = re.compile(r"<%[-_=#]?[\s\S]*?%>")
HTML_TOKEN = re.compile(r"</?[A-Za-z][^<>]*?>")
BACKSLASH_ESCAPE = re.compile(
    r"\\(?:[\\'\"bfnrtv0]|x[0-9A-Fa-f]{2}|u(?:[0-9A-Fa-f]{4}|\{[0-9A-Fa-f]+\})|\r?\n)"
)


class StageError(RuntimeError):
    pass


def _contract_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def target_is_higher_authority_shadowed(target: dict[str, Any]) -> bool:
    """Recognize both the v2 review contract and the legacy target fields."""
    scope = _contract_token(target.get("review_scope_status"))
    policy = _contract_token(target.get("application_policy"))
    status = _contract_token(target.get("match_status"))
    return bool(
        target.get("shadowed_by_higher_authority") is True
        or scope in {
            "higher-authority-shadowed",
            "protected-higher-authority",
            "protected-higher-authority-selected",
        }
        or policy in {
            "higher-authority-shadowed",
            "protected-higher-authority",
            "protected-authority-only",
            "product-write-forbidden",
        }
        or status == "protected-higher-authority-selected"
    )


def target_product_write_is_forbidden(target: dict[str, Any]) -> bool:
    policy = _contract_token(target.get("application_policy"))
    if policy:
        return policy in {
            "higher-authority-shadowed",
            "protected-higher-authority",
            "protected-authority-only",
            "product-write-forbidden",
            "no-product-write-protected",
        }
    if "product_write_allowed" in target:
        return target.get("product_write_allowed") is False
    return target.get("application_allowed") is False


def derive_target_contract(
    rows: list[dict[str, Any]], summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive review/materialization counts without trusting scattered constants."""
    if not rows:
        raise StageError("product target manifest contains no review items")
    item_ids = [row.get("item_id") for row in rows]
    if any(not isinstance(item_id, str) or not item_id for item_id in item_ids):
        raise StageError("product target manifest contains an invalid item ID")
    if len(set(item_ids)) != len(item_ids):
        raise StageError("product target manifest contains duplicate item IDs")

    shadowed_ids: set[str] = set()
    materializable_ids: set[str] = set()
    runtime_items = 0
    maintenance_items = 0
    runtime_occurrences = 0
    scope_counts: Counter[str] = Counter()
    for target in rows:
        item_id = str(target["item_id"])
        occurrences = target.get("occurrences")
        if not isinstance(occurrences, list):
            raise StageError(f"target occurrences are invalid: {item_id}")
        shadowed = target_is_higher_authority_shadowed(target)
        if shadowed:
            if not target_product_write_is_forbidden(target):
                raise StageError(f"higher-authority shadow is not product-write-forbidden: {item_id}")
            if target.get("application_allowed") is True or occurrences:
                raise StageError(f"higher-authority shadow claims a runtime write: {item_id}")
            shadowed_ids.add(item_id)
            continue

        materializable_ids.add(item_id)
        scope = target.get("maintenance_scope")
        if scope not in {"global", "override", "fragment"}:
            raise StageError(f"target maintenance scope is invalid: {item_id}")
        scope_counts[str(scope)] += 1
        if target.get("application_allowed") is True:
            if not occurrences:
                raise StageError(f"runtime target has no exact occurrence: {item_id}")
            runtime_items += 1
            runtime_occurrences += len(occurrences)
        else:
            if occurrences:
                raise StageError(f"maintenance-only target claims a runtime occurrence: {item_id}")
            maintenance_items += 1

    contract = {
        "review_items": len(rows),
        "materialization_items": len(materializable_ids),
        "higher_authority_shadowed_items": len(shadowed_ids),
        "product_write_forbidden_items": len(shadowed_ids),
        "exact_runtime_items": runtime_items,
        "maintenance_only_items": maintenance_items,
        "runtime_occurrences": runtime_occurrences,
        "global_items": scope_counts["global"],
        "override_items": scope_counts["override"],
        "fragment_items": scope_counts["fragment"],
        "shadowed_low_tier_candidates_written": 0,
        "shadowed_product_writes": 0,
        "materializable_ids": materializable_ids,
        "shadowed_ids": shadowed_ids,
    }
    if contract["review_items"] != (
        contract["materialization_items"] + contract["higher_authority_shadowed_items"]
    ):
        raise StageError("review/materialization/shadow partition drifted")
    if contract["materialization_items"] != (
        contract["global_items"] + contract["override_items"] + contract["fragment_items"]
    ):
        raise StageError("global/override/fragment partition drifted")

    if summary is not None:
        fixed = {
            "items": contract["review_items"],
            "maintenance_rows_bound": contract["review_items"],
            "exact_runtime_items": runtime_items,
            "runtime_occurrences": runtime_occurrences,
            "occurrence_collisions": 0,
            "unclassified_items": 0,
        }
        if any(summary.get(key) != value for key, value in fixed.items()):
            raise StageError("product target manifest summary drifted")
        # Legacy manifests counted protected shadows as maintenance-only.  The
        # v2 contract excludes them because they are never materialized.
        allowed_maintenance_counts = {maintenance_items, maintenance_items + len(shadowed_ids)}
        if summary.get("maintenance_only_items") not in allowed_maintenance_counts:
            raise StageError("product target maintenance count drifted")
        optional = {
            "human_review_materialization_items": contract["materialization_items"],
            "materialization_items": contract["materialization_items"],
            "higher_authority_shadowed_items": contract["higher_authority_shadowed_items"],
            "product_write_forbidden_items": contract["product_write_forbidden_items"],
            "global_items": contract["global_items"],
            "override_items": contract["override_items"],
            "fragment_items": contract["fragment_items"],
        }
        for key, expected in optional.items():
            if key in summary and summary.get(key) != expected:
                raise StageError(f"product target {key} drifted")
    return contract


def load_shadowed_contract(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise StageError(f"higher-authority shadow manifest is missing or unsafe: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "magireco-cn-pass20-authority-shadowed-machine-items/2"
        or payload.get("status") != "PASS"
    ):
        raise StageError("higher-authority shadow manifest root, schema, or status is invalid")
    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        raise StageError("higher-authority shadow manifest contains no items")
    item_ids: set[str] = set()
    effective_occurrences = 0
    machine_occurrences = 0
    authority_materialization_items = 0
    authority_materialized_occurrences = 0
    authority_verified_occurrences = 0
    for row in rows:
        if not isinstance(row, dict):
            raise StageError("higher-authority shadow manifest contains a non-object item")
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in item_ids:
            raise StageError(f"higher-authority shadow manifest has an invalid item ID: {item_id!r}")
        item_ids.add(item_id)
        required_text = (
            "stable_business_key", "source_path", "source_key", "japanese_or_source_original",
            "machine_current_cn", "effective_cn", "effective_tier", "effective_source_file",
            "evidence",
        )
        if any(not isinstance(row.get(field), str) or not row.get(field) for field in required_text):
            raise StageError(f"higher-authority shadow evidence is incomplete: {item_id}")
        expected_business_key = f"{row['source_path']}#{row['source_key']}/candidate_cn"
        if row["stable_business_key"] != expected_business_key:
            raise StageError(f"higher-authority shadow stable business key drifted: {item_id}")
        if not isinstance(row.get("effective_source_line"), int) or row["effective_source_line"] <= 0:
            raise StageError(f"higher-authority shadow source line is invalid: {item_id}")
        if row.get("match_status") != "protected-higher-authority-selected":
            raise StageError(f"higher-authority shadow match status drifted: {item_id}")
        if row.get("product_write_forbidden") is not True:
            raise StageError(f"higher-authority shadow is not product-write-forbidden: {item_id}")
        if row.get("product_write_allowed") is not False:
            raise StageError(f"higher-authority shadow permits a product write: {item_id}")
        for field in ("declared_product_paths", "runtime_effective_paths", "runtime_machine_paths"):
            paths = row.get(field)
            if not isinstance(paths, list) or any(
                not isinstance(rel, str) or not rel or rel.startswith(("/", "\\"))
                or "\\" in rel or ":" in rel or ".." in rel.split("/") for rel in paths
            ):
                raise StageError(f"higher-authority shadow {field} is invalid: {item_id}")
            if paths != sorted(set(paths)):
                raise StageError(f"higher-authority shadow {field} is not a stable set: {item_id}")
        for field in ("runtime_effective_count", "runtime_machine_count"):
            if not isinstance(row.get(field), int) or row[field] < 0:
                raise StageError(f"higher-authority shadow {field} is invalid: {item_id}")
        effective_occurrences += row["runtime_effective_count"]
        machine_occurrences += row["runtime_machine_count"]
        materialization = row.get("authority_materialization")
        if materialization is not None:
            if not isinstance(materialization, dict):
                raise StageError(f"authority materialization is invalid: {item_id}")
            if (
                materialization.get("machine_cn") != row["machine_current_cn"]
                or materialization.get("effective_cn") != row["effective_cn"]
            ):
                raise StageError(f"authority materialization literal drifted: {item_id}")
            path_rows = materialization.get("product_paths")
            if not isinstance(path_rows, list) or not path_rows:
                raise StageError(f"authority materialization paths are invalid: {item_id}")
            path_names: set[str] = set()
            expected_total = 0
            materialized_total = 0
            for path_row in path_rows:
                if not isinstance(path_row, dict):
                    raise StageError(f"authority materialization path is invalid: {item_id}")
                rel = path_row.get("path")
                expected = path_row.get("expected_effective_count")
                if (
                    not isinstance(rel, str) or not rel or rel in path_names
                    or rel.startswith(("/", "\\")) or "\\" in rel or ":" in rel
                    or ".." in rel.split("/") or not isinstance(expected, int) or expected <= 0
                    or path_row.get("machine_count") != 0
                    or path_row.get("effective_count") != expected
                ):
                    raise StageError(f"authority materialization path contract drifted: {item_id}")
                path_names.add(rel)
                expected_total += expected
                if path_row.get("materialized_from_machine") is True:
                    materialized_total += expected
                elif path_row.get("materialized_from_machine") is not False:
                    raise StageError(
                        f"authority materialization repair flag drifted: {item_id}"
                    )
            if materialization.get("expected_effective_occurrences") != expected_total:
                raise StageError(f"authority materialization total drifted: {item_id}")
            if materialization.get("materialized_from_machine_occurrences") != materialized_total:
                raise StageError(f"authority materialization repair total drifted: {item_id}")
            authority_materialization_items += 1
            authority_materialized_occurrences += materialized_total
            authority_verified_occurrences += expected_total
    summary = payload.get("summary")
    expected_summary = {
        "items": len(rows),
        "higher_authority_shadowed_items": len(rows),
        "product_write_forbidden_items": len(rows),
        "runtime_effective_occurrences": effective_occurrences,
        "runtime_machine_occurrences": machine_occurrences,
        "authority_materialization_items": authority_materialization_items,
        "authority_materialized_occurrences": authority_materialized_occurrences,
        "authority_verified_occurrences": authority_verified_occurrences,
    }
    if not isinstance(summary, dict) or any(summary.get(key) != value for key, value in expected_summary.items()):
        raise StageError("higher-authority shadow summary drifted")
    return {
        "items": rows, "item_ids": item_ids, "count": len(rows),
        "runtime_effective_occurrences": effective_occurrences,
        "runtime_machine_occurrences": machine_occurrences,
        "authority_materialization_items": authority_materialization_items,
        "authority_materialized_occurrences": authority_materialized_occurrences,
        "authority_verified_occurrences": authority_verified_occurrences,
    }


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise StageError(f"could not load tool module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise StageError(f"TSV must be UTF-8-no-BOM with LF endings: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if not header or any(None in row for row in rows):
        raise StageError(f"invalid TSV: {path}")
    return header, rows


SOURCE_BINDING_FIELDS = (
    "source_index", "batch_number", "item_id", "stable_business_key", "source_path",
    "source_key", "source_field", "japanese_or_source_original", "old_cn", "current_cn",
)


def validate_queue_source_bindings(
    queue_rows: list[dict[str, str]], source_rows: list[dict[str, str]],
) -> None:
    """Bind every editable queue row to the immutable DSV4 source record and its hash."""
    source_by_id = {row.get("item_id", ""): row for row in source_rows}
    if len(source_by_id) != len(source_rows) or "" in source_by_id:
        raise StageError("DSV4 source table contains an empty or duplicate item ID")
    for queue_row in queue_rows:
        item_id = queue_row.get("item_id", "")
        source = source_by_id.get(item_id)
        if source is None:
            raise StageError(f"queue source record is missing: {item_id}")
        if any(queue_row.get(field, "") != source.get(field, "") for field in SOURCE_BINDING_FIELDS):
            raise StageError(f"queue source record binding drifted: {item_id}")
        expected_hash = source.get("source_text_sha256", "")
        actual_hash = sha256(source.get("japanese_or_source_original", "").encode("utf-8")).hexdigest()
        if expected_hash != actual_hash:
            raise StageError(f"source-record text hash drifted: {item_id}")


def decode_cell(value: str) -> str:
    return value.replace("\\t", "\t").replace("\\n", "\n").replace("\\\\", "\\")


def _semantic_markup(value: str) -> str:
    return re.sub(r"\\x3[cC]", "<", re.sub(r"\\x3[eE]", ">", value))


def _invalid_escape_offsets(value: str) -> list[int]:
    valid_starts = {match.start() for match in BACKSLASH_ESCAPE.finditer(value)}
    invalid: list[int] = []
    index = 0
    while index < len(value):
        if value[index] != "\\":
            index += 1
            continue
        if index not in valid_starts:
            invalid.append(index)
            index += 1
            continue
        match = BACKSLASH_ESCAPE.match(value, index)
        assert match is not None
        index = match.end()
    return invalid


def validate_translation_structure(item_id: str, before: str, after: str) -> None:
    if Counter(PLACEHOLDER.findall(before)) != Counter(PLACEHOLDER.findall(after)):
        raise StageError(f"placeholder structure drift: {item_id}")
    before_markup = _semantic_markup(before)
    after_markup = _semantic_markup(after)
    if EJS_TOKEN.findall(before_markup) != EJS_TOKEN.findall(after_markup):
        raise StageError(f"EJS structure drift: {item_id}")
    if HTML_TOKEN.findall(before_markup) != HTML_TOKEN.findall(after_markup):
        raise StageError(f"HTML structure drift: {item_id}")
    if _invalid_escape_offsets(after):
        raise StageError(f"invalid output escape sequence: {item_id}")
    if BACKSLASH_ESCAPE.findall(before) != BACKSLASH_ESCAPE.findall(after):
        raise StageError(f"escape structure drift: {item_id}")


def semantic_spans(text: str, needle: str, rel: str, scope: str) -> list[tuple[int, int]]:
    if scope == "fragment":
        return [match.span() for match in re.finditer(re.escape(needle), text)]
    if rel.endswith(".js"):
        return [match.span(2) for match in JS_LIT.finditer(text) if match.group(2) == needle]
    if rel.endswith(".html"):
        spans: list[tuple[int, int]] = []
        for match in HTML_TEXT.finditer(text):
            body = match.group(1)
            if body.strip() == needle:
                offset = body.index(needle)
                spans.append((match.start(1) + offset, match.start(1) + offset + len(needle)))
        spans.extend(match.span(2) for match in HTML_ATTR.finditer(text) if match.group(2) == needle)
        return sorted(spans)
    return []


def verify_pass21_runtime_baselines(
    product_root: Path,
    targets: dict[str, dict[str, Any]],
    adoptions: dict[str, dict[str, Any]],
) -> dict[str, int]:
    checked_items = checked_paths = checked_occurrences = 0
    for item_id, adoption in adoptions.items():
        if adoption["runtime_strategy"] == "canonical-only":
            continue
        target = targets[item_id]
        expected_by_path: Counter[str] = Counter()
        if adoption["runtime_strategy"] == "explicit-safe-paths":
            for rewrite in adoption["runtime_rewrites_parsed"]:
                expected_by_path[rewrite["path"]] += rewrite["expected_count"]
        else:
            expected_by_path.update(row["path"] for row in target["occurrences"])
        literal = decode_cell(adoption["adopted_cn"])
        for rel, expected_count in expected_by_path.items():
            path = product_root / rel
            if not path.is_file() or path.is_symlink():
                raise StageError(f"Pass21 runtime baseline path is missing: {item_id} {rel}")
            text = path.read_text(encoding="utf-8")
            actual = len(semantic_spans(text, literal, rel, target["maintenance_scope"]))
            if actual != expected_count:
                raise StageError(
                    f"Pass21 runtime baseline is not materialized: {item_id} {rel} "
                    f"actual={actual} expected={expected_count}"
                )
            checked_paths += 1
            checked_occurrences += actual
        checked_items += 1
    return {
        "items": checked_items,
        "paths": checked_paths,
        "occurrences": checked_occurrences,
    }


def copy_tree(source: Path, target: Path, *, product: bool = False) -> None:
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        rel_posix = rel.as_posix()
        if product and (rel_posix.startswith("i18n_audit/") or rel_posix.startswith("research/")):
            continue
        destination = target / rel
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def append_reviewed_candidates(
    path: Path,
    queue: dict[str, dict[str, str]],
    final_values: list[dict[str, str]],
    targets: dict[str, dict[str, Any]],
    expected_ids: set[str],
) -> int:
    existing = path.read_text(encoding="utf-8")
    existing_locators = set()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream, delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            if len(row) == len(REVIEWED_COLUMNS):
                existing_locators.add(row[7])
    records = []
    modes: set[str] = set()
    for receipt in final_values:
        item_id = receipt["item_id"]
        if item_id not in expected_ids:
            continue
        source = queue[item_id]
        target = targets[item_id]
        final_value = receipt["final_value"]
        if not final_value:
            raise StageError(f"human return has no final value: {item_id}")
        if final_value == "<DELETE>" and not (
            receipt["final_origin"] == "machine-current" and source["current_cn"] == "<DELETE>"
        ):
            raise StageError(f"reserved deletion token is forbidden as review text: {item_id}")
        review_status = receipt["review_status"]
        if review_status.startswith("rough-production-"):
            mode = "rough-production"
            authority = "new_proposal"
            source_batch = "pass20-rough-production-final-values-v1"
            match_method = "exact-semantic-key-user-directed-rough-production"
            confidence = "user-directed-rough-production-unreviewed"
        elif review_status.startswith("human-"):
            mode = "human-review"
            authority = "existing_human_reviewed"
            source_batch = "pass20-human-final-values-v1"
            match_method = "exact-semantic-key-human-review"
            confidence = "human-approved"
        else:
            raise StageError(f"unsupported final-value provenance: {item_id}")
        modes.add(mode)
        locator = f"{FINAL_VALUE_LOCATOR_BASE}{mode}:{item_id}"
        if locator in existing_locators:
            raise StageError(f"reviewed candidate already exists: {mode}:{item_id}")
        record = {
            "scope": target["maintenance_scope"],
            "path_prefix": target["path_prefix"],
            "source_text": source["japanese_or_source_original"],
            "candidate_cn": final_value,
            "status": "present",
            "authority": authority,
            "source_batch": source_batch,
            "source_locator": locator,
            "source_sha256": "",
            "match_method": match_method,
            "machine_translated": receipt["machine_translated"],
            "confidence": confidence,
            "review_status": review_status,
            "evidence": (
                f"item_id={item_id}; final_origin={receipt['final_origin']}; "
                f"provenance_mode={mode}; "
                f"target_status={target['match_status']}"
            ),
        }
        records.append(record)
    if len(modes) != 1:
        raise StageError("final-value candidates mix provenance modes")
    if len(records) != len(expected_ids):
        raise StageError(f"expected {len(expected_ids)} reviewed candidates, got {len(records)}")
    if existing and not existing.endswith("\n"):
        raise StageError("reviewed-candidates.tsv lacks final LF")
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REVIEWED_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writerows(records)
    return len(records)


def refresh_review_contract(
    stage_root: Path,
    source_path: Path,
    resolutions_path: Path,
    provenance_mode: str,
) -> None:
    """Bind the frozen Pass20 queue contract to the newly generated provenance."""
    path = stage_root / REVIEW_CONTRACT_REL
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema") != "magireco-cn-pass20-review-contract/2" or contract.get("status") != "PASS":
        raise StageError("Pass20 review contract schema/status drifted")
    before_sources = {
        "full_review": sha256(source_path.read_bytes()).hexdigest(),
        "authority_resolutions": sha256(resolutions_path.read_bytes()).hexdigest(),
        "input_provenance": sha256((ROOT / "i18n/generated/input-provenance.tsv").read_bytes()).hexdigest(),
        "effective": sha256((ROOT / "i18n/generated/effective.tsv").read_bytes()).hexdigest(),
    }
    if contract.get("source_sha256") != before_sources:
        raise StageError("Pass20 frozen review contract preimage drifted")
    contract["source_sha256"] = {
        "full_review": before_sources["full_review"],
        "authority_resolutions": before_sources["authority_resolutions"],
        "input_provenance": sha256((stage_root / "i18n/generated/input-provenance.tsv").read_bytes()).hexdigest(),
        "effective": sha256((stage_root / "i18n/generated/effective.tsv").read_bytes()).hexdigest(),
    }
    contract["post_final_value_materialization"] = {
        "items": 1565,
        "provenance_mode": provenance_mode,
        "queue_and_targets_frozen": True,
        "machine_provenance_retained": provenance_mode == "rough-production",
    }
    path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def run_command(command: list[str], cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.run(
        command, cwd=cwd, text=True, encoding="utf-8", errors="strict",
        capture_output=True, env=env,
    )
    result = {
        "command": command,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
    if process.returncode != 0:
        raise StageError(
            f"command failed ({process.returncode}): {' '.join(command)}\n{process.stdout}\n{process.stderr}"
        )
    return result


def write_plan_table(path: Path, rows: list[tuple[str, str, str]], label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(f"# {label}\n")
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerows(rows)


def require_fresh_target_manifest(saved: dict[str, Any], fresh: dict[str, Any]) -> None:
    if fresh != saved:
        raise StageError("staging product target manifest differs from a fresh exact scan")


def html_sensitive_signature(text: str) -> list[tuple[str, str]]:
    return [(match.group(1).lower(), match.group(3)) for match in SENSITIVE_HTML_ATTR.finditer(text)]


def stage(
    source_path: Path,
    final_values_path: Path,
    resolutions_path: Path,
    targets_path: Path,
    stage_root: Path,
    review_workbook: Path | None = None,
    shadowed_path: Path | None = None,
) -> dict[str, Any]:
    root_resolved = ROOT.resolve()
    stage_resolved = stage_root.resolve()
    if stage_resolved == root_resolved or root_resolved in stage_resolved.parents:
        raise StageError("staging root must be outside the repository")
    if stage_root.exists() and any(stage_root.iterdir()):
        raise StageError(f"staging root must be absent or empty: {stage_root}")
    stage_root.mkdir(parents=True, exist_ok=True)

    resolved_shadowed_path = shadowed_path or SHADOWED
    validator = load_module("pass20_validate_human", ROOT / "tools/validate-dsv4-human-review.py")
    validation = validator.validate(
        source_path, final_values_path, resolutions_path, resolved_shadowed_path,
        targets_path=targets_path, adoptions_path=ADOPTIONS,
    )
    if not validation["release_gate_open"]:
        raise StageError("final-value release gate is closed")
    provenance_mode = validation.get("provenance_mode")
    if provenance_mode not in {"human-review", "rough-production"}:
        raise StageError("final-value provenance mode is invalid")
    if review_workbook is None or not review_workbook.is_file() or review_workbook.is_symlink():
        raise StageError("a regular completed review workbook is required")
    if review_workbook.resolve() == (ROOT / WORKBOOK_REL).resolve():
        raise StageError("completed review workbook must be a separate external copy; keep the repository template blank")

    source_header, source_rows = load_tsv(source_path)
    final_header, final_rows = load_tsv(final_values_path)
    if not source_header or not final_header:
        raise StageError("human review tables are empty")
    _, remaining = load_tsv(QUEUE)
    queue = {row["item_id"]: row for row in remaining}
    if len(queue) != len(remaining):
        raise StageError("Pass20 review queue contains an empty or duplicate item ID")
    review_items = len(queue)
    validate_queue_source_bindings(remaining, source_rows)
    source_records_sha256 = sha256(QUEUE.read_bytes()).hexdigest()
    final_by_id = {row["item_id"]: row for row in final_rows}
    if len(final_by_id) != len(final_rows) or set(final_by_id) != set(queue):
        raise StageError(f"final-value table must cover all {review_items} Pass20 items")
    if (
        validation.get("final_values_required") != review_items
        or validation.get("final_values_received") != review_items
    ):
        raise StageError("final-value gate and materialization queue counts differ")

    _, resolution_rows = load_tsv(resolutions_path)
    resolution_ids = {row["item_id"] for row in resolution_rows}
    authority_resolutions_sha256 = sha256(resolutions_path.read_bytes()).hexdigest()
    if len(resolution_ids) != len(resolution_rows) or resolution_ids.intersection(queue):
        raise StageError("authority resolution leaked into the human materialization queue")

    target_payload = json.loads(targets_path.read_text(encoding="utf-8"))
    target_contract_sha256 = sha256(targets_path.read_bytes()).hexdigest()
    if (
        target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1"
        or target_payload.get("status") != "PASS"
    ):
        raise StageError("product target manifest schema or status drifted")
    target_rows = target_payload.get("items")
    if not isinstance(target_rows, list):
        raise StageError("product target manifest items are invalid")
    target_contract = derive_target_contract(target_rows, target_payload.get("summary"))
    if target_contract["shadowed_ids"]:
        raise StageError("higher-authority shadow leaked into the human product target manifest")
    targets = {row["item_id"]: row for row in target_rows}
    if set(targets) != set(queue):
        raise StageError("product target manifest differs from the Pass20 queue")
    if target_contract["materialization_items"] != review_items:
        raise StageError("review queue contains a non-materializable target")
    adoption_tool = load_module(
        "pass21_adoption_contract", ROOT / "tools/apply-pass20-suggested-adoptions.py"
    )
    adoptions = adoption_tool.read_adoption_manifest(ADOPTIONS)
    if not set(adoptions).issubset(queue):
        raise StageError("Pass21 suggestion adoption contains an excluded final-value item")
    for item_id, source in queue.items():
        baseline = adoptions.get(item_id, {}).get("adopted_cn", source.get("current_cn", ""))
        validate_translation_structure(item_id, baseline, final_by_id[item_id]["final_value"])

    shadowed_contract = load_shadowed_contract(resolved_shadowed_path)
    authority_shadow_manifest_sha256 = sha256(resolved_shadowed_path.read_bytes()).hexdigest()
    shadowed_ids = shadowed_contract["item_ids"]
    if shadowed_ids.intersection(queue) or shadowed_ids.intersection(resolution_ids):
        raise StageError("higher-authority shadow overlaps a review or authority-resolution item")
    source_ids = {row.get("item_id") for row in source_rows}
    if (
        len(source_ids) != len(source_rows)
        or any(not isinstance(item_id, str) or not item_id for item_id in source_ids)
        or source_ids != set(queue).union(resolution_ids, shadowed_ids)
    ):
        raise StageError("source/review/resolution/shadow partition drifted")
    if shadowed_ids.intersection(final_by_id):
        raise StageError("higher-authority shadow entered the final-value receipt")
    machine_inventory_items = review_items + shadowed_contract["count"]

    importer = load_module("pass20_workbook_import", ROOT / "tools/import-pass20-human-review-xlsx.py")
    with tempfile.TemporaryDirectory(prefix="pass20-workbook-receipt-", dir=stage_root.parent) as temp:
        imported_final_values = Path(temp) / "imported-final-values.tsv"
        try:
            workbook_import = importer.import_workbook(
                review_workbook,
                AUDIT / "pass20_remaining_manual_review.tsv",
                source_path,
                targets_path,
                imported_final_values,
                accept_returned=provenance_mode == "human-review",
                accept_rough_production=provenance_mode == "rough-production",
            )
        except Exception as exc:
            raise StageError(f"completed review workbook validation failed: {exc}") from exc
        if (
            workbook_import.get("receipt_rows_written") != review_items
            or workbook_import.get("pending_in_workbook") != 0
            or workbook_import.get("returned_workbook_accepted") is not True
        ):
            raise StageError(
                f"review workbook itself must return all {review_items} final values"
            )
        if imported_final_values.read_bytes() != final_values_path.read_bytes():
            raise StageError("completed workbook differs from the committed final-value TSV")
    copy_tree(ROOT / "i18n", stage_root / "i18n")
    copy_tree(ROOT / "magica", stage_root / "magica", product=True)
    copy_tree(ROOT / "madomagi", stage_root / "madomagi")
    staged_workbook = stage_root / WORKBOOK_REL
    staged_workbook.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(review_workbook, staged_workbook)
    staged_review_contract = stage_root / REVIEW_CONTRACT_REL
    staged_review_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / REVIEW_CONTRACT_REL, staged_review_contract)
    canonical_before = {
        rel.as_posix(): (ROOT / rel).read_bytes()
        for rel in CANONICAL_I18N_RELS + (REVIEW_CONTRACT_REL, WORKBOOK_REL)
    }
    reviewed_count = append_reviewed_candidates(
        stage_root / "i18n/reviewed-candidates.tsv",
        queue,
        [final_by_id[item] for item in queue],
        targets,
        set(queue),
    )

    commands = []
    commands.append(run_command([
        sys.executable, str(ROOT / "tools/i18n-build-effective.py"),
        "--i18n-dir", str(stage_root / "i18n"),
        "--out-dir", str(stage_root / "i18n/generated"),
        "--policy", str(stage_root / "i18n/authority-policy.json"),
        "--migration-summary", str(stage_root / "i18n/migration-source-summary.json"),
    ], ROOT))
    refresh_review_contract(stage_root, source_path, resolutions_path, provenance_mode)
    _, effective_rows = load_tsv(stage_root / "i18n/generated/effective.tsv")
    effective = {row["key"]: row for row in effective_rows}

    override_rows: list[tuple[str, str, str]] = []
    fragment_rows: list[tuple[str, str, str]] = []
    patch_items: list[dict[str, Any]] = []
    maintenance_only_changes: list[str] = []
    for item_id in queue:
        source = queue[item_id]
        receipt = final_by_id[item_id]
        target = targets[item_id]
        winner = effective.get(target["semantic_key"])
        if winner is None:
            raise StageError(f"effective winner missing after final-value import: {item_id}")
        if winner["selected_cn"] != receipt["final_value"]:
            raise StageError(f"final-value effective winner drift: {item_id}")
        if provenance_mode == "human-review":
            if (
                winner["authority"] != "existing_human_reviewed"
                or winner.get("source_file") != "i18n/reviewed-candidates.tsv"
                or winner.get("source_batch") != "pass20-human-final-values-v1"
            ):
                raise StageError(f"human-reviewed effective winner drift: {item_id}")
        elif winner["authority"] != "legacy_unverified_ai_assisted":
            raise StageError(f"rough-production low-tier winner drift: {item_id}")
        adoption = adoptions.get(item_id)
        baseline = adoption["adopted_cn"] if adoption else source["current_cn"]
        if receipt["final_value"] == baseline:
            continue
        if adoption and adoption["runtime_strategy"] == "canonical-only":
            maintenance_only_changes.append(item_id)
            continue
        if adoption and adoption["runtime_strategy"] == "explicit-safe-paths":
            rewrites = adoption["runtime_rewrites_parsed"]
            paths = sorted({row["path"] for row in rewrites})
            expected_occurrences = [
                {"path": row["path"], "start": -1, "end": -1}
                for row in rewrites for _ in range(row["expected_count"])
            ]
        else:
            if not target["application_allowed"]:
                maintenance_only_changes.append(item_id)
                continue
            paths = target["product_target_paths"]
            expected_occurrences = target["occurrences"]
        if not paths:
            raise StageError(f"applicable final value has no product path: {item_id}")
        table_rows = fragment_rows if target["maintenance_scope"] == "fragment" else override_rows
        for rel in paths:
            row = (rel, baseline, receipt["final_value"])
            if row in table_rows:
                raise StageError(f"duplicate application row: {item_id} {rel}")
            table_rows.append(row)
        patch_items.append({
            "item_id": item_id,
            "semantic_key": target["semantic_key"],
            "scope": target["maintenance_scope"],
            "before": baseline,
            "after": receipt["final_value"],
            "paths": paths,
            "expected_occurrences": expected_occurrences,
        })

    product_before = {
        path.relative_to(stage_root).as_posix(): path.read_bytes()
        for path in (stage_root / "magica").rglob("*") if path.is_file()
    }
    pass21_runtime_baseline = verify_pass21_runtime_baselines(
        stage_root / "magica", targets, adoptions,
    )
    application = stage_root / "review_application"
    empty_table = application / "frontend-empty.tsv"
    write_plan_table(empty_table, [], "Pass20 overrides-only application; intentionally empty global table")
    overrides_table = application / "review-overrides.tsv"
    fragments_table = application / "review-fragments.tsv"
    write_plan_table(overrides_table, override_rows, "path-bound current-CN to final-CN plan")
    write_plan_table(fragments_table, fragment_rows, "path-bound current-fragment to final-fragment plan")

    commands.append(run_command([
        sys.executable, str(ROOT / "tools/i18n-apply.py"), str(stage_root / "magica"),
        str(empty_table), "--overrides", str(overrides_table), "--overrides-only",
        "--out", str(application / "changed-files.txt"),
    ], ROOT))
    commands.append(run_command([
        sys.executable, str(ROOT / "tools/i18n-fragments.py"), str(stage_root / "magica"),
        str(fragments_table),
    ], ROOT))

    product_after = {
        path.relative_to(stage_root).as_posix(): path.read_bytes()
        for path in (stage_root / "magica").rglob("*") if path.is_file()
    }
    if set(product_before) != set(product_after):
        raise StageError("staging application added or removed product files")
    changed_files = sorted(rel for rel in product_before if product_before[rel] != product_after[rel])
    expected_changed = sorted({f"magica/{rel}" for item in patch_items for rel in item["paths"]})
    if changed_files != expected_changed:
        raise StageError(f"changed file allowlist drift: expected {expected_changed}, got {changed_files}")

    patch_records = []
    for item in patch_items:
        before_literal = decode_cell(item["before"])
        after_literal = decode_cell(item["after"])
        for rel in item["paths"]:
            key = f"magica/{rel}"
            before_text = product_before[key].decode("utf-8")
            after_text = product_after[key].decode("utf-8")
            expected_count = sum(1 for occ in item["expected_occurrences"] if occ["path"] == rel)
            scope = item["scope"]
            before_pre = len(semantic_spans(before_text, before_literal, rel, scope))
            before_post = len(semantic_spans(after_text, before_literal, rel, scope))
            after_pre = len(semantic_spans(before_text, after_literal, rel, scope))
            after_post = len(semantic_spans(after_text, after_literal, rel, scope))
            if before_pre != expected_count or before_post != 0 or after_post - after_pre != expected_count:
                raise StageError(f"literal count verification failed: {item['item_id']} {rel}")
            patch_records.append({
                "item_id": item["item_id"], "path": rel, "scope": scope,
                "before": item["before"], "after": item["after"],
                "expected_count": expected_count, "before_count_before": before_pre,
                "before_count_after": before_post, "after_delta": after_post - after_pre,
            })

    staged_final_values = stage_root / FINAL_VALUES_REL
    staged_final_values.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final_values_path, staged_final_values)
    canonical_before[FINAL_VALUES_REL.as_posix()] = (ROOT / FINAL_VALUES_REL).read_bytes()
    canonical_after = {
        rel: (stage_root / rel).read_bytes()
        for rel in canonical_before
    }

    rollback_root = stage_root / "rollback"
    diff_parts = []
    rollback_files = []

    def add_rollback_record(rel: str, before_bytes: bytes, after_bytes: bytes, role: str) -> None:
        before_path = rollback_root / "before" / rel
        after_path = rollback_root / "after" / rel
        before_path.parent.mkdir(parents=True, exist_ok=True)
        after_path.parent.mkdir(parents=True, exist_ok=True)
        before_path.write_bytes(before_bytes)
        after_path.write_bytes(after_bytes)
        rollback_files.append({
            "path": rel,
            "role": role,
            "before_snapshot": before_path.relative_to(stage_root).as_posix(),
            "after_snapshot": after_path.relative_to(stage_root).as_posix(),
            "before_sha256": sha256(before_bytes).hexdigest(),
            "after_sha256": sha256(after_bytes).hexdigest(),
            "before_size": len(before_bytes),
            "after_size": len(after_bytes),
        })

    for rel in changed_files:
        add_rollback_record(rel, product_before[rel], product_after[rel], "runtime-product")
        before_text = product_before[rel].decode("utf-8")
        after_text = product_after[rel].decode("utf-8")
        diff_parts.extend(difflib.unified_diff(
            before_text.splitlines(True), after_text.splitlines(True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm="\n",
        ))
        if rel.endswith(".html") and html_sensitive_signature(before_text) != html_sensitive_signature(after_text):
            raise StageError(f"HTML sensitive attribute drift: {rel}")

    canonical_changed_files = []
    for rel in sorted(canonical_before):
        before_bytes = canonical_before[rel]
        after_bytes = canonical_after[rel]
        if before_bytes == after_bytes:
            continue
        if rel == FINAL_VALUES_REL.as_posix():
            role = "human-final-values-audit"
        elif rel == REVIEW_CONTRACT_REL.as_posix():
            role = "review-contract-audit"
        elif rel == WORKBOOK_REL.as_posix():
            role = "human-review-workbook-receipt"
        else:
            role = "canonical-i18n"
        add_rollback_record(rel, before_bytes, after_bytes, role)
        canonical_changed_files.append(rel)
    if "i18n/reviewed-candidates.tsv" not in canonical_changed_files:
        raise StageError("canonical final-value provenance input did not change")
    if FINAL_VALUES_REL.as_posix() not in canonical_changed_files:
        raise StageError("returned final-value audit did not change")
    repository_promotion_files = sorted(changed_files + canonical_changed_files)

    review_contract = {
        "machine_inventory_items": machine_inventory_items,
        "human_review_items": review_items,
        "materialization_items": target_contract["materialization_items"],
        "higher_authority_shadowed_items": shadowed_contract["count"],
        "product_write_forbidden_items": shadowed_contract["count"],
        "authority_resolution_items": len(resolution_ids),
        "exact_runtime_items": target_contract["exact_runtime_items"],
        "maintenance_only_items": target_contract["maintenance_only_items"],
        "runtime_occurrences": target_contract["runtime_occurrences"],
        "global_items": target_contract["global_items"],
        "override_items": target_contract["override_items"],
        "fragment_items": target_contract["fragment_items"],
        "shadowed_low_tier_candidates_written": 0,
        "shadowed_product_writes": 0,
        "source_records_sha256": source_records_sha256,
        "target_contract_sha256": target_contract_sha256,
        "authority_shadow_manifest_sha256": authority_shadow_manifest_sha256,
        "authority_resolutions_sha256": authority_resolutions_sha256,
    }
    if review_contract["machine_inventory_items"] != (
        review_contract["materialization_items"]
        + review_contract["higher_authority_shadowed_items"]
    ):
        raise StageError("machine inventory/materialization/shadow contract drifted")

    (application / "product.diff").write_text("".join(diff_parts), encoding="utf-8", newline="\n")
    (application / "product_patch.json").write_text(
        json.dumps({"schema": "magireco-cn-pass20-product-patch/1", "items": patch_records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    (rollback_root / "rollback.json").write_text(
        json.dumps({
            "schema": "magireco-cn-pass20-product-rollback/1",
            "review_contract": review_contract,
            "files": rollback_files,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    node = shutil.which("node")
    if not node:
        raise StageError("Node.js is required for staging JS syntax validation")
    js_files = sorted((stage_root / "magica/js").rglob("*.js"))
    for path in js_files:
        run_command([node, "--check", str(path)], ROOT)
    commands.append({
        "command": [node, "--check", f"<{len(js_files)} staged JS files>"],
        "exit_code": 0, "stdout": "", "stderr": "",
    })
    json_files = sorted((stage_root / "magica/js/libs").glob("*.json"))
    for path in json_files:
        json.loads(path.read_text(encoding="utf-8"))

    # The protected Pass19 occurrence extractor deliberately re-opens its
    # applied-authority manifest from the root being verified.  Keep audit
    # material out of the staged product snapshot/diff, then copy only this
    # immutable verification input immediately before the protection gate.
    pass19_rel = Path("magica/i18n_audit/release_v26_authority/pass19_official_static_corrections.tsv")
    pass19_support = stage_root / pass19_rel
    pass19_support.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / pass19_rel, pass19_support)

    protection = load_module("pass20_authority_protection", ROOT / "tools/v26_authority_protection.py")
    protected_rows = protection.read_tsv(PROTECTED)
    protection.validate_row_hashes(protected_rows)
    protection.verify_current_product_values(stage_root, protected_rows)

    rollback_tool = load_module("pass20_stage_rollback", ROOT / "tools/rollback-pass20-product-stage.py")
    with tempfile.TemporaryDirectory(prefix="pass20-rollback-relocated-", dir=stage_root.parent) as temp:
        relocation_root = Path(temp)
        relocated_stage = relocation_root / "relocated-stage"
        relocated_product = relocation_root / "relocated-product"
        shutil.copytree(rollback_root, relocated_stage / "rollback")
        for record in rollback_files:
            destination = relocated_product.joinpath(*Path(record["path"]).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage_root / record["after_snapshot"], destination)
        rollback_rehearsal = rollback_tool.rollback(relocated_stage, relocated_product)
        rollback_rehearsal["relocated_stage_copy"] = True

    report = {
        "schema": "magireco-cn-pass20-product-staging/1",
        "status": "PASS",
        "human_gate": validation,
        "review_contract": review_contract,
        "reviewed_candidates_appended": reviewed_count,
        "provenance_mode": provenance_mode,
        "effective_rows": len(effective_rows),
        "machine_inventory_items": machine_inventory_items,
        "human_review_items": review_items,
        "exact_target_items": target_contract["exact_runtime_items"],
        "maintenance_only_items": target_contract["maintenance_only_items"],
        "higher_authority_shadowed_items": shadowed_contract["count"],
        "product_write_forbidden_items": shadowed_contract["count"],
        "runtime_occurrences_bound": target_contract["runtime_occurrences"],
        "pass21_preapplied_runtime_baseline": pass21_runtime_baseline,
        "patch_items": len(patch_items),
        "maintenance_only_changed_items": maintenance_only_changes,
        "changed_files": changed_files,
        "canonical_changed_files": canonical_changed_files,
        "repository_promotion_files": repository_promotion_files,
        "canonical_human_review_items": (
            target_contract["materialization_items"] if provenance_mode == "human-review" else 0
        ),
        "canonical_rough_production_items": (
            target_contract["materialization_items"] if provenance_mode == "rough-production" else 0
        ),
        "maintenance_only_items_persisted": target_contract["maintenance_only_items"],
        "shadowed_low_tier_candidates_written": 0,
        "shadowed_product_writes": 0,
        "human_review_workbook_receipt": WORKBOOK_REL.as_posix(),
        "patch_records": len(patch_records),
        "protected_fields_checked": len(protected_rows),
        "protected_text_changes": 0,
        "js_syntax_checked": len(js_files),
        "json_parsed": len(json_files),
        "html_sensitive_attribute_changes": 0,
        "rollback_rehearsal": rollback_rehearsal,
        "repository_product_writes": 0,
        "commands": commands,
        "artifacts": {
            "product_diff": (application / "product.diff").relative_to(stage_root).as_posix(),
            "product_patch": (application / "product_patch.json").relative_to(stage_root).as_posix(),
            "rollback": (rollback_root / "rollback.json").relative_to(stage_root).as_posix(),
        },
    }
    (stage_root / "staging_verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--final-values", type=Path, default=FINAL_VALUES)
    parser.add_argument("--authority-resolutions", type=Path, default=RESOLUTIONS)
    parser.add_argument("--targets", type=Path, default=TARGETS)
    parser.add_argument("--authority-shadowed", type=Path, default=SHADOWED)
    parser.add_argument("--review-workbook", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = stage(
            args.source, args.final_values, args.authority_resolutions, args.targets, args.stage_root,
            args.review_workbook, args.authority_shadowed,
        )
        print(json.dumps({key: value for key, value in report.items() if key != "commands"}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (StageError, OSError, UnicodeError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
