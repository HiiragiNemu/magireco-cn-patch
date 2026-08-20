#!/usr/bin/env python3
"""Promote a closed Pass20 staging tree into the repository under exact gates."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_REL = Path("magica/i18n_audit/release_v26_authority")
PROTECTED_REL = AUDIT_REL / "protected_authority/protected_translation_fields.tsv"
QUEUE_REL = AUDIT_REL / "pass20_remaining_manual_review.tsv"
TARGETS_REL = AUDIT_REL / "pass20_product_targets.json"
SHADOWED_REL = AUDIT_REL / "pass20_authority_shadowed_machine_items.json"
RESOLUTIONS_REL = AUDIT_REL / "pass20_authority_resolutions.tsv"
FINAL_VALUES_RECEIPT = "magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv"
WORKBOOK_RECEIPT = (
    "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1564.xlsx"
)
REVIEW_CONTRACT_RECEIPT = (
    "magica/i18n_audit/release_v26_authority/pass20_review_contract.json"
)
REVIEWED_CANDIDATES_RECEIPT = "i18n/reviewed-candidates.tsv"
FINAL_VALUE_LOCATOR_BASE = f"{FINAL_VALUES_RECEIPT}#"
FINAL_VALUE_FIELDS = (
    "item_id", "stable_business_key", "source_path", "source_key", "source_field",
    "japanese_or_source_original", "seed_cn", "seed_origin", "current_cn",
    "suggested_cn", "final_value", "source_record_sha256", "target_contract_sha256",
    "review_status", "final_origin", "machine_translated",
)
REVIEWED_COLUMNS = (
    "scope", "path_prefix", "source_text", "candidate_cn", "status", "authority",
    "source_batch", "source_locator", "source_sha256", "match_method",
    "machine_translated", "confidence", "review_status", "evidence",
)
CANONICAL_I18N_FILES = {
    "i18n/reviewed-candidates.tsv",
    "i18n/generated/conflicts.tsv",
    "i18n/generated/effective.tsv",
    "i18n/generated/input-provenance.tsv",
    "i18n/generated/summary.json",
}
class PromotionError(RuntimeError):
    pass


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PromotionError(f"could not load tool module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PromotionError(f"JSON root must be an object: {path}")
    return payload


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def atomic_replace(source: Path, target: Path) -> None:
    source.replace(target)


def expected_bytes(record: dict[str, Any], kind: str, data: bytes) -> None:
    expected_digest = record.get(f"{kind}_sha256")
    expected_size = record.get(f"{kind}_size")
    if not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise PromotionError(f"invalid {kind} digest in rollback record: {record.get('path')}")
    if not isinstance(expected_size, int) or expected_size < 0:
        raise PromotionError(f"invalid {kind} size in rollback record: {record.get('path')}")
    if len(data) != expected_size or digest(data) != expected_digest:
        raise PromotionError(f"{kind} bytes differ from rollback contract: {record.get('path')}")


def run_node_checks(node: str, root: Path, paths: list[str]) -> int:
    checked = 0
    for rel in paths:
        if not rel.endswith(".js"):
            continue
        process = subprocess.run(
            [node, "--check", str(root / rel)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if process.returncode != 0:
            raise PromotionError(f"JavaScript syntax check failed after promotion: {rel}\n{process.stderr}")
        checked += 1
    return checked


def role_path_valid(role: str, path: str) -> bool:
    if role == "runtime-product":
        return (
            path.startswith("magica/")
            and not path.startswith("magica/i18n_audit/")
            and not path.startswith("magica/research/")
            and Path(path).suffix.lower() in {".js", ".html", ".json"}
        )
    if role == "canonical-i18n":
        return path in CANONICAL_I18N_FILES
    if role == "human-final-values-audit":
        return path == FINAL_VALUES_RECEIPT
    if role == "human-review-workbook-receipt":
        return path == WORKBOOK_RECEIPT
    if role == "review-contract-audit":
        return path == REVIEW_CONTRACT_RECEIPT
    return False


def _decode_tsv(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PromotionError(f"{label} is not valid UTF-8") from exc


def _receipt_rows(data: bytes) -> list[dict[str, str]]:
    reader = csv.reader(io.StringIO(_decode_tsv(data, "final-value receipt"), newline=""), delimiter="\t")
    try:
        header = tuple(next(reader))
    except StopIteration as exc:
        raise PromotionError("final-value receipt is empty") from exc
    if header != FINAL_VALUE_FIELDS:
        raise PromotionError("final-value receipt header drifted")
    rows: list[dict[str, str]] = []
    for number, values in enumerate(reader, start=2):
        if not values:
            continue
        if len(values) != len(FINAL_VALUE_FIELDS):
            raise PromotionError(f"final-value receipt row {number} has the wrong field count")
        rows.append(dict(zip(FINAL_VALUE_FIELDS, values)))
    return rows


def _reviewed_candidate_rows(data: bytes) -> list[dict[str, str]]:
    reader = csv.reader(
        io.StringIO(_decode_tsv(data, "reviewed candidates"), newline=""), delimiter="\t",
    )
    rows: list[dict[str, str]] = []
    for number, values in enumerate(reader, start=1):
        if not values or values[0].startswith("#"):
            continue
        if len(values) != len(REVIEWED_COLUMNS):
            raise PromotionError(f"reviewed-candidates row {number} has the wrong field count")
        rows.append(dict(zip(REVIEWED_COLUMNS, values)))
    return rows


def _canonical_json_digest(value: Any) -> str:
    return digest(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8"))


def validate_staged_provenance(
    stage_root: Path, contract: dict[str, Any], target_manifest_path: Path,
) -> dict[str, Any]:
    """Bind promotion claims to the exact staged receipt, candidates, and review contract."""
    bound_files = {
        "final_values_receipt_sha256": FINAL_VALUES_RECEIPT,
        "reviewed_candidates_sha256": REVIEWED_CANDIDATES_RECEIPT,
        "materialized_review_contract_sha256": REVIEW_CONTRACT_RECEIPT,
    }
    payloads: dict[str, bytes] = {}
    for field, rel in bound_files.items():
        path = stage_root / rel
        if path.is_symlink() or not path.is_file():
            raise PromotionError(f"staged provenance input is missing or unsafe: {rel}")
        data = path.read_bytes()
        if digest(data) != contract[field]:
            raise PromotionError(f"staged {field} gate failed")
        payloads[rel] = data

    mode = contract["provenance_mode"]
    expected_items = contract["materialization_items"]
    target_payload = read_json(target_manifest_path)
    target_rows = target_payload.get("items")
    if (
        target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1"
        or target_payload.get("status") != "PASS"
        or not isinstance(target_rows, list)
    ):
        raise PromotionError("product target provenance manifest is invalid")
    targets: dict[str, dict[str, Any]] = {}
    for target in target_rows:
        if not isinstance(target, dict):
            raise PromotionError("product target provenance row is invalid")
        item_id = target.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in targets:
            raise PromotionError("product target provenance has a missing or duplicate item_id")
        targets[item_id] = target
    receipts = _receipt_rows(payloads[FINAL_VALUES_RECEIPT])
    receipt_by_id: dict[str, dict[str, str]] = {}
    receipt_modes: set[str] = set()
    for row in receipts:
        item_id = row.get("item_id", "")
        if not item_id or item_id in receipt_by_id:
            raise PromotionError("final-value receipt has a missing or duplicate item_id")
        status = row.get("review_status", "")
        if status.startswith("rough-production-"):
            row_mode = "rough-production"
        elif status.startswith("human-"):
            row_mode = "human-review"
        else:
            raise PromotionError(f"final-value receipt has an invalid review_status: {item_id}")
        receipt_modes.add(row_mode)
        receipt_by_id[item_id] = row
    if (
        len(receipts) != expected_items
        or receipt_modes != {mode}
        or set(receipt_by_id) != set(targets)
    ):
        raise PromotionError("final-value receipt provenance differs from rollback contract")

    prefix = f"{FINAL_VALUE_LOCATOR_BASE}{mode}:"
    candidates: dict[str, dict[str, str]] = {}
    for row in _reviewed_candidate_rows(payloads[REVIEWED_CANDIDATES_RECEIPT]):
        locator = row.get("source_locator", "")
        if not locator.startswith(prefix):
            continue
        item_id = locator[len(prefix):]
        if not item_id or item_id in candidates:
            raise PromotionError("reviewed candidates have a missing or duplicate bound item_id")
        candidates[item_id] = row
    if len(candidates) != expected_items or set(candidates) != set(receipt_by_id):
        raise PromotionError("reviewed candidate provenance differs from final-value receipt")
    expected_authority = "existing_human_reviewed" if mode == "human-review" else "new_proposal"
    expected_batch = (
        "pass20-human-final-values-v1"
        if mode == "human-review"
        else "pass20-rough-production-final-values-v1"
    )
    expected_match_method = (
        "exact-semantic-key-human-review"
        if mode == "human-review"
        else "exact-semantic-key-user-directed-rough-production"
    )
    expected_confidence = (
        "human-approved"
        if mode == "human-review"
        else "user-directed-rough-production-unreviewed"
    )
    for item_id, receipt in receipt_by_id.items():
        candidate = candidates[item_id]
        target = targets[item_id]
        receipt_origin = receipt.get("final_origin")
        if mode == "rough-production":
            allowed_receipt_provenance = {
                "machine-current": (
                    "rough-production-machine-current-retained", "unknown", "current",
                ),
                "machine-suggestion": (
                    "rough-production-machine-suggestion-adopted", "true", "suggestion",
                ),
            }
        else:
            allowed_receipt_provenance = {
                "machine-current": (
                    "human-confirmed-machine-origin-retained", "unknown", "current",
                ),
                "machine-suggestion": (
                    "human-confirmed-machine-suggestion-adopted", "true", "suggestion",
                ),
                "human-revision": ("human-revised", "false", "revision"),
            }
        expected_receipt = allowed_receipt_provenance.get(receipt_origin)
        if expected_receipt is None:
            raise PromotionError(f"final-value receipt origin is invalid for its mode: {item_id}")
        expected_review_status, expected_machine_flag, value_rule = expected_receipt
        if (
            receipt.get("review_status") != expected_review_status
            or receipt.get("machine_translated") != expected_machine_flag
            or (
                value_rule == "current"
                and (
                    receipt.get("seed_origin") != "current"
                    or receipt.get("seed_cn") != receipt.get("current_cn")
                    or receipt.get("final_value") != receipt.get("current_cn")
                )
            )
            or (
                value_rule == "suggestion"
                and (
                    receipt.get("seed_origin") not in {"suggested", "adopted_suggestion"}
                    or receipt.get("final_value") != receipt.get("seed_cn")
                )
            )
        ):
            raise PromotionError(f"final-value receipt status is invalid for its mode: {item_id}")
        expected_evidence = (
            f"item_id={item_id}; final_origin={receipt['final_origin']}; "
            f"provenance_mode={mode}; target_status={target.get('match_status', '')}"
        )
        if any((
            candidate.get("candidate_cn") != receipt.get("final_value"),
            candidate.get("source_text") != receipt.get("japanese_or_source_original"),
            candidate.get("status") != "present",
            candidate.get("review_status") != receipt.get("review_status"),
            candidate.get("machine_translated") != receipt.get("machine_translated"),
            candidate.get("authority") != expected_authority,
            candidate.get("source_batch") != expected_batch,
            candidate.get("match_method") != expected_match_method,
            candidate.get("confidence") != expected_confidence,
            candidate.get("evidence") != expected_evidence,
            candidate.get("source_sha256") != "",
            candidate.get("scope") != target.get("maintenance_scope"),
            candidate.get("path_prefix") != target.get("path_prefix"),
            receipt.get("source_field") != "candidate_cn",
            receipt.get("stable_business_key") != target.get("stable_business_key"),
            receipt.get("source_path") != target.get("maintenance_table"),
            receipt.get("source_key") != target.get("source_key"),
            receipt.get("target_contract_sha256") != _canonical_json_digest(target),
        )):
            raise PromotionError(f"reviewed candidate differs from its final-value receipt: {item_id}")

    materialized = json.loads(payloads[REVIEW_CONTRACT_RECEIPT].decode("utf-8-sig"))
    post = materialized.get("post_final_value_materialization", {})
    if (
        materialized.get("schema") != "magireco-cn-pass20-review-contract/2"
        or materialized.get("status") != "PASS"
        or post.get("items") != expected_items
        or post.get("provenance_mode") != mode
        or post.get("machine_provenance_retained") is not (mode == "rough-production")
    ):
        raise PromotionError("materialized review contract provenance drifted")
    return {
        "provenance_mode": mode,
        "items": expected_items,
        "final_values_receipt_sha256": contract["final_values_receipt_sha256"],
        "reviewed_candidates_sha256": contract["reviewed_candidates_sha256"],
        "materialized_review_contract_sha256": contract["materialized_review_contract_sha256"],
    }


def promote(stage_root: Path, repo_root: Path, report_path: Path | None = None) -> dict[str, Any]:
    stage_root = stage_root.resolve()
    repo_root = repo_root.resolve()
    if stage_root == repo_root or repo_root in stage_root.parents:
        raise PromotionError("staging root must be separate from the repository")
    report = read_json(stage_root / "staging_verification.json")
    if (
        report.get("schema") != "magireco-cn-pass20-product-staging/1"
        or report.get("status") != "PASS"
        or report.get("repository_product_writes") != 0
        or report.get("protected_text_changes") != 0
        or not report.get("human_gate", {}).get("release_gate_open")
        or report.get("rollback_rehearsal", {}).get("status") != "PASS"
        or report.get("rollback_rehearsal", {}).get("relocated_stage_copy") is not True
    ):
        raise PromotionError("staging verification does not open the promotion gate")

    rollback_tool = load_module(
        "pass20_promotion_rollback", repo_root / "tools/rollback-pass20-product-stage.py"
        if (repo_root / "tools/rollback-pass20-product-stage.py").is_file()
        else ROOT / "tools/rollback-pass20-product-stage.py",
    )
    manifest = read_json(stage_root / "rollback/rollback.json")
    if manifest.get("schema") != "magireco-cn-pass20-product-rollback/1":
        raise PromotionError("rollback manifest schema drifted")
    try:
        review_contract = rollback_tool.validate_review_contract(manifest.get("review_contract"))
    except Exception as exc:
        raise PromotionError(f"rollback review contract is invalid: {exc}") from exc
    if report.get("review_contract") != review_contract:
        raise PromotionError("staging and rollback review contracts differ")
    provenance_mode = review_contract["provenance_mode"]
    if report.get("provenance_mode") != provenance_mode:
        raise PromotionError("staging provenance mode differs from its rollback contract")
    report_contract_fields = {
        "machine_inventory_items": "machine_inventory_items",
        "human_review_items": "human_review_items",
        "higher_authority_shadowed_items": "higher_authority_shadowed_items",
        "product_write_forbidden_items": "product_write_forbidden_items",
        "exact_target_items": "exact_runtime_items",
        "maintenance_only_items_persisted": "maintenance_only_items",
        "runtime_occurrences_bound": "runtime_occurrences",
        "shadowed_low_tier_candidates_written": "shadowed_low_tier_candidates_written",
        "shadowed_product_writes": "shadowed_product_writes",
    }
    if any(
        report.get(report_key) != review_contract[contract_key]
        for report_key, contract_key in report_contract_fields.items()
    ):
        raise PromotionError("staging report counts differ from its review contract")
    expected_human = review_contract["materialization_items"] if provenance_mode == "human-review" else 0
    expected_rough = review_contract["materialization_items"] if provenance_mode == "rough-production" else 0
    if (
        report.get("canonical_human_review_items") != expected_human
        or report.get("canonical_rough_production_items", 0) != expected_rough
    ):
        raise PromotionError("staging provenance counts differ from the materialization contract")
    if report.get("reviewed_candidates_appended") != review_contract["materialization_items"]:
        raise PromotionError("staging canonical append count drifted")
    if report.get("human_gate", {}).get("final_values_required") != review_contract["human_review_items"]:
        raise PromotionError("human gate count differs from the materialization contract")
    source_files = {
        "source_records_sha256": repo_root / QUEUE_REL,
        "target_contract_sha256": repo_root / TARGETS_REL,
        "authority_shadow_manifest_sha256": repo_root / SHADOWED_REL,
        "authority_resolutions_sha256": repo_root / RESOLUTIONS_REL,
    }
    for field, path in source_files.items():
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != review_contract[field]:
            raise PromotionError(f"repository {field} gate failed")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise PromotionError("rollback manifest contains no promotion files")
    paths = [record.get("path") for record in records if isinstance(record, dict)]
    if len(paths) != len(records) or any(not isinstance(path, str) for path in paths):
        raise PromotionError("rollback manifest contains an invalid path")
    if len(set(paths)) != len(paths):
        raise PromotionError("rollback manifest contains duplicate paths")
    promotion_files = report.get("repository_promotion_files")
    if not isinstance(promotion_files, list) or sorted(paths) != sorted(promotion_files):
        raise PromotionError("promotion allowlist differs from rollback manifest")
    allowed_roles = {
        "runtime-product", "canonical-i18n", "human-final-values-audit",
        "human-review-workbook-receipt", "review-contract-audit",
    }
    unknown_roles = sorted(
        {record.get("role") for record in records} - allowed_roles,
        key=lambda value: str(value),
    )
    if unknown_roles:
        raise PromotionError(f"rollback manifest contains unknown promotion roles: {unknown_roles}")
    for record in records:
        if not role_path_valid(record["role"], record["path"]):
            raise PromotionError(
                f"promotion role/path contract mismatch: {record['role']} {record['path']}"
            )
    runtime_files = sorted(
        record["path"] for record in records if record.get("role") == "runtime-product"
    )
    canonical_files = sorted(
        record["path"] for record in records
        if record.get("role") in {
            "canonical-i18n", "human-final-values-audit", "human-review-workbook-receipt",
            "review-contract-audit",
        }
    )
    if runtime_files != sorted(report.get("changed_files", [])):
        raise PromotionError("runtime promotion allowlist drifted")
    if canonical_files != sorted(report.get("canonical_changed_files", [])):
        raise PromotionError("canonical promotion allowlist drifted")
    if sorted(runtime_files + canonical_files) != sorted(paths):
        raise PromotionError("classified promotion allowlists do not cover every manifest path")
    report_paths = list(report.get("changed_files", [])) + list(report.get("canonical_changed_files", []))
    if len(report_paths) != len(set(report_paths)) or sorted(report_paths) != sorted(paths):
        raise PromotionError("staging changed-file lists do not exactly cover the promotion manifest")
    if "i18n/reviewed-candidates.tsv" not in canonical_files:
        raise PromotionError("canonical final-value provenance input is absent from promotion")
    if FINAL_VALUES_RECEIPT not in canonical_files:
        raise PromotionError("completed human final-value receipt is absent from promotion")
    if REVIEW_CONTRACT_RECEIPT not in canonical_files:
        raise PromotionError("refreshed review contract is absent from promotion")
    receipt = report.get("human_review_workbook_receipt")
    if receipt != WORKBOOK_RECEIPT:
        raise PromotionError("completed review workbook receipt contract drifted")
    workbook_receipt_preexisting_identical = False
    if receipt not in canonical_files:
        if provenance_mode != "rough-production":
            raise PromotionError("completed review workbook receipt is absent from promotion")
        try:
            repository_receipt = rollback_tool.safe_join(repo_root, receipt)
            staged_receipt = rollback_tool.safe_join(stage_root, receipt)
        except Exception as exc:
            raise PromotionError("unsafe preexisting rough workbook receipt path") from exc
        if any(
            path.is_symlink() or not path.is_file()
            for path in (repository_receipt, staged_receipt)
        ):
            raise PromotionError("preexisting rough workbook receipt is missing or unsafe")
        if repository_receipt.read_bytes() != staged_receipt.read_bytes():
            raise PromotionError("preexisting rough workbook receipt differs from staging")
        workbook_receipt_preexisting_identical = True

    prepared: list[dict[str, Any]] = []
    for record in records:
        rel = record["path"]
        try:
            current = rollback_tool.safe_join(repo_root, rel)
            staged = rollback_tool.safe_join(stage_root, rel)
            before_snapshot = rollback_tool.safe_snapshot(
                stage_root, rel, "before", str(record.get("before_snapshot", ""))
            )
            after_snapshot = rollback_tool.safe_snapshot(
                stage_root, rel, "after", str(record.get("after_snapshot", ""))
            )
        except Exception as exc:
            raise PromotionError(f"unsafe promotion path contract: {rel!r}") from exc
        if any(path.is_symlink() or not path.is_file() for path in (current, staged, before_snapshot, after_snapshot)):
            raise PromotionError(f"promotion role is missing or unsafe: {rel}")
        current_bytes = current.read_bytes()
        staged_bytes = staged.read_bytes()
        before_bytes = before_snapshot.read_bytes()
        after_bytes = after_snapshot.read_bytes()
        expected_bytes(record, "before", before_bytes)
        expected_bytes(record, "after", after_bytes)
        if current_bytes != before_bytes:
            raise PromotionError(f"repository before gate failed: {rel}")
        if staged_bytes != after_bytes:
            raise PromotionError(f"staged after gate failed: {rel}")
        prepared.append({
            "record": record,
            "path": current,
            "before": before_bytes,
            "after": after_bytes,
            "temp": None,
        })

    provenance_binding = validate_staged_provenance(
        stage_root, review_contract, repo_root / TARGETS_REL,
    )

    node = shutil.which("node")
    if not node:
        raise PromotionError("Node.js is required for promotion syntax validation")
    run_node_checks(node, stage_root, runtime_files)
    for rel in runtime_files:
        if rel.endswith(".json"):
            json.loads((stage_root / rel).read_text(encoding="utf-8"))

    protection = load_module("pass20_promotion_protection", ROOT / "tools/v26_authority_protection.py")
    protected_rows = protection.read_tsv(repo_root / PROTECTED_REL)
    protection.validate_row_hashes(protected_rows)
    protection.verify_current_product_values(repo_root, protected_rows)
    protection.verify_current_product_values(stage_root, protected_rows)

    report_path = (report_path or stage_root / "promotion_verification.json").resolve()
    if report_path == repo_root or repo_root in report_path.parents:
        raise PromotionError("promotion report must remain outside the repository transaction")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not report_path.parent.is_dir() or report_path.parent.is_symlink():
        raise PromotionError("promotion report directory is missing or unsafe")
    if report_path.exists() and (report_path.is_dir() or report_path.is_symlink()):
        raise PromotionError("promotion report path is not a regular file target")

    replaced: list[dict[str, Any]] = []
    report_temp: Path | None = None
    try:
        for item in prepared:
            target = item["path"]
            if target.read_bytes() != item["before"]:
                raise PromotionError(f"repository changed during promotion preflight: {item['record']['path']}")
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=target.parent) as stream:
                temp = Path(stream.name)
                stream.write(item["after"])
                stream.flush()
                os.fsync(stream.fileno())
            item["temp"] = temp
        for item in prepared:
            atomic_replace(item["temp"], item["path"])
            item["temp"] = None
            replaced.append(item)
        for item in prepared:
            if item["path"].read_bytes() != item["after"]:
                raise PromotionError(f"repository after gate failed: {item['record']['path']}")

        protection.verify_current_product_values(repo_root, protected_rows)
        js_checked = run_node_checks(node, repo_root, runtime_files)
        for rel in runtime_files:
            if rel.endswith(".json"):
                json.loads((repo_root / rel).read_text(encoding="utf-8"))
        result = {
            "schema": "magireco-cn-pass20-repository-promotion/1",
            "status": "PASS",
            "promoted_files": sorted(paths),
            "runtime_product_files": runtime_files,
            "canonical_i18n_and_audit_files": canonical_files,
            "human_review_workbook_receipt": receipt,
            "workbook_receipt_preexisting_identical": workbook_receipt_preexisting_identical,
            "review_contract": review_contract,
            "provenance_binding": provenance_binding,
            "machine_inventory_items": review_contract["machine_inventory_items"],
            "human_review_items": review_contract["human_review_items"],
            "provenance_mode": provenance_mode,
            "canonical_human_review_items": expected_human,
            "canonical_rough_production_items": expected_rough,
            "higher_authority_shadowed_items": review_contract["higher_authority_shadowed_items"],
            "product_write_forbidden_items": review_contract["product_write_forbidden_items"],
            "maintenance_only_items_persisted": review_contract["maintenance_only_items"],
            "shadowed_low_tier_candidates_written": 0,
            "shadowed_product_writes": 0,
            "protected_fields_checked": len(protected_rows),
            "protected_text_changes": 0,
            "js_syntax_checked": js_checked,
            "exact_before_gate": True,
            "exact_after_gate": True,
            "atomic_per_file_replace": True,
            "automatic_failure_rollback": True,
            "rollback_manifest": "rollback/rollback.json",
            "stable_release_requires_post_promotion_package_gate": True,
        }
        with tempfile.NamedTemporaryFile("w", delete=False, dir=report_path.parent, encoding="utf-8", newline="\n") as stream:
            report_temp = Path(stream.name)
            stream.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        report_temp.replace(report_path)
        report_temp = None
        return result
    except Exception as exc:
        if report_temp is not None and report_temp.exists():
            report_temp.unlink()
        for item in prepared:
            temp = item.get("temp")
            if isinstance(temp, Path) and temp.exists():
                temp.unlink()
        for item in reversed(replaced):
            target = item["path"]
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=target.parent) as stream:
                recovery = Path(stream.name)
                stream.write(item["before"])
                stream.flush()
                os.fsync(stream.fileno())
            recovery.replace(target)
            if target.read_bytes() != item["before"]:
                raise PromotionError(
                    f"promotion failed and automatic rollback verification failed: {item['record']['path']}"
                ) from exc
        if isinstance(exc, PromotionError):
            raise
        raise PromotionError(f"promotion failed and changed files were restored: {exc}") from exc

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--allow-repository-write", action="store_true",
        help="required explicit acknowledgement that all closed review gates will write exact repository files",
    )
    args = parser.parse_args(argv)
    if not args.allow_repository_write:
        print(json.dumps({"status": "FAIL", "error": "--allow-repository-write is required"}, ensure_ascii=False), file=sys.stderr)
        return 2
    try:
        result = promote(args.stage_root, args.repo_root, args.report)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (PromotionError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
