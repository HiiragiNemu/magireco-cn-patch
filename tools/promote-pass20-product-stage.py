#!/usr/bin/env python3
"""Promote a closed Pass20 staging tree into the repository under exact gates."""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
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
DECISIONS_RECEIPT = "magica/i18n_audit/release_v26_authority/dsv4_human_decisions.tsv"
WORKBOOK_RECEIPT = "magica/i18n_audit/release_v26_authority/pass20_human_review.xlsx"
CANONICAL_I18N_FILES = {
    "i18n/reviewed-candidates.tsv",
    "i18n/generated/conflicts.tsv",
    "i18n/generated/effective.tsv",
    "i18n/generated/input-provenance.tsv",
    "i18n/generated/summary.json",
}
REVIEW_ITEMS = 199
MAINTENANCE_ONLY_ITEMS = 19


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
    if role == "human-decision-audit":
        return path == DECISIONS_RECEIPT
    if role == "human-review-workbook-receipt":
        return path == WORKBOOK_RECEIPT
    return False


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
        or report.get("canonical_human_review_items") != REVIEW_ITEMS
        or report.get("maintenance_only_items_persisted") != MAINTENANCE_ONLY_ITEMS
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
        "runtime-product", "canonical-i18n", "human-decision-audit",
        "human-review-workbook-receipt",
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
            "canonical-i18n", "human-decision-audit", "human-review-workbook-receipt",
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
        raise PromotionError("canonical human-reviewed authority input is absent from promotion")
    if DECISIONS_RECEIPT not in canonical_files:
        raise PromotionError("completed human decision receipt is absent from promotion")
    receipt = report.get("human_review_workbook_receipt")
    if receipt != WORKBOOK_RECEIPT:
        raise PromotionError("completed review workbook receipt contract drifted")
    if receipt not in canonical_files:
        raise PromotionError("completed review workbook receipt is absent from promotion")

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
            "canonical_human_review_items": REVIEW_ITEMS,
            "maintenance_only_items_persisted": MAINTENANCE_ONLY_ITEMS,
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
