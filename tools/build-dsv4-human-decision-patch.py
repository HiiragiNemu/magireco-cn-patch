#!/usr/bin/env python3
"""Build a deterministic, staging-only patch after all 522 human decisions close.

The builder delegates the complete decision-table contract to
``validate-dsv4-human-review.py`` and then emits only literal changes meeting
all of these conditions:

* ``review_kind == current-low-tier-translation-review``;
* ``human_decision == revise``;
* ``final_value != current_cn``;
* the record is explicitly unprotected and remains product-write-disabled.

The destination must be a new directory outside the repository.  The emitted
patch and rollback use the existing ``dsv4-v3-staging-patch.py`` executor
contract and can mutate only the included dedicated low-tier staging document.
No product path is opened for writing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = Path(__file__).with_name("validate-dsv4-human-review.py")
EXECUTOR_PATH = Path(__file__).with_name("dsv4-v3-staging-patch.py")
PATCH_SCHEMA = "magireco-cn-dsv4-v3-terminal-assembly/2-correction-patch"
ROLLBACK_SCHEMA = "magireco-cn-dsv4-v3-terminal-assembly/2-rollback"
PACKAGE_SCHEMA = "magireco-cn-dsv4-human-decision-staging-package/1"
VERIFY_SCHEMA = "magireco-cn-dsv4-human-decision-staging-verification/1"
ROOT_SCHEMA = "magireco-cn-dsv4-v3-low-tier-staging-root/1"
VALUES_SCHEMA = "magireco-cn-dsv4-v3-low-tier-staging-values/1"
LOCATOR_FIELDS = ("source_path", "source_key", "source_field", "stable_business_key")


class BuildError(RuntimeError):
    """Fail-closed package construction error."""


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise BuildError(f"cannot load required module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_record(data: bytes) -> dict[str, Any]:
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def _safe_output_path(output_dir: Path) -> Path:
    repo = REPO_ROOT.resolve()
    output = output_dir.expanduser().resolve()
    try:
        output.relative_to(repo)
    except ValueError:
        pass
    else:
        raise BuildError("output directory must be outside the repository")
    if output.exists() or output.is_symlink():
        raise BuildError("output directory must be new and absent")
    parent = output.parent
    if not parent.is_dir() or parent.is_symlink():
        raise BuildError("output parent must be an existing regular directory")
    return output


def _safe_locator(row: dict[str, str]) -> dict[str, str]:
    locator = {field: row[field] for field in LOCATOR_FIELDS}
    if any(not value or any(ch in value for ch in ("\x00", "\r", "\n")) for value in locator.values()):
        raise BuildError(f"unsafe or empty stable locator: {row.get('item_id', '')}")
    source_path = locator["source_path"]
    pure = PurePosixPath(source_path)
    if (
        "\\" in source_path
        or pure.is_absolute()
        or source_path != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or (pure.parts and ":" in pure.parts[0])
    ):
        raise BuildError(f"unsafe source_path in stable locator: {row.get('item_id', '')}")
    return locator


def _read_stable_inputs(source: Path, decisions: Path, validator: Any) -> tuple[dict[str, Any], list[str], list[dict[str, str]], list[str], list[dict[str, str]]]:
    before = {"source": validator.sha256(source), "decisions": validator.sha256(decisions)}
    try:
        result = validator.validate(source, decisions)
    except validator.HumanReviewError as exc:
        raise BuildError(f"human decision validation failed: {exc}") from exc
    source_header, source_rows = validator.load_tsv(source)
    decision_header, decision_rows = validator.load_tsv(decisions)
    after = {"source": validator.sha256(source), "decisions": validator.sha256(decisions)}
    if before != after:
        raise BuildError("input changed while it was being validated")
    if result.get("all_decided") is not True:
        raise BuildError("human decision gate closed: all_decided is not true")
    if result.get("release_gate_open") is not True:
        raise BuildError("human decision gate closed: release_gate_open is not true")
    if result.get("states", {}).get("unresolved") != 0:
        raise BuildError("human decision gate closed: unresolved decisions remain")
    return result, source_header, source_rows, decision_header, decision_rows


def _build_entries(
    source_header: list[str],
    source_rows: list[dict[str, str]],
    decision_header: list[str],
    decision_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    staging_records: list[dict[str, Any]] = []
    seen_items: set[str] = set()
    seen_locators: set[str] = set()
    for source, decision in zip(source_rows, decision_rows):
        if decision["human_decision"] != "revise":
            continue
        item_id = decision["item_id"]
        if decision["review_kind"] != "current-low-tier-translation-review":
            raise BuildError(f"historical/protected revision is forbidden: {item_id}")
        if decision["allowed_action"] != "review-and-stage-low-tier-only":
            raise BuildError(f"revision is outside low-tier staging scope: {item_id}")
        if decision["protected_authority_text"] != "false":
            raise BuildError(f"protected authority text is never writable: {item_id}")
        if decision["product_write_allowed"] != "false":
            raise BuildError(f"product write permission is forbidden: {item_id}")
        before = decision["current_cn"]
        after = decision["final_value"]
        if not after or after == before:
            raise BuildError(f"revise must carry a changed final value: {item_id}")
        locator = _safe_locator(decision)
        locator_sha = sha256_bytes(canonical_json_bytes(locator))
        if item_id in seen_items or locator_sha in seen_locators:
            raise BuildError(f"duplicate item or stable locator: {item_id}")
        seen_items.add(item_id)
        seen_locators.add(locator_sha)
        before_sha = sha256_bytes(before.encode("utf-8"))
        after_sha = sha256_bytes(after.encode("utf-8"))
        source_row_sha = sha256_bytes(canonical_json_bytes({field: source[field] for field in source_header}))
        decision_row_sha = sha256_bytes(canonical_json_bytes({field: decision[field] for field in decision_header}))
        entry = {
            "after": after,
            "after_sha256": after_sha,
            "before": before,
            "before_sha256": before_sha,
            "decision_row_sha256": decision_row_sha,
            "human_decision": "revise",
            "item_id": item_id,
            "locator": locator,
            "locator_sha256": locator_sha,
            "reviewer": decision["reviewer"],
            "source_index": int(decision["source_index"]),
            "source_row_sha256": source_row_sha,
            "target_preconditions": {
                "product_write_allowed": False,
                "protected_authority_text": False,
                "review_kind": "current-low-tier-translation-review",
            },
            "timestamp": decision["timestamp"],
        }
        entries.append(entry)
        staging_records.append({
            "item_id": item_id,
            **locator,
            "product_write_allowed": False,
            "protected_authority_text": False,
            "source_index": int(decision["source_index"]),
            "value": before,
            "value_sha256": before_sha,
        })
    order = sorted(range(len(entries)), key=lambda index: (entries[index]["source_index"], entries[index]["item_id"]))
    entries = [entries[index] for index in order]
    staging_records = [staging_records[index] for index in order]
    if any(entry["target_preconditions"]["review_kind"] != "current-low-tier-translation-review" for entry in entries):
        raise BuildError("historical review entry reached the writable set")
    return entries, staging_records


def _patch_text(entries: list[dict[str, Any]]) -> bytes:
    lines = [
        "# Magireco v26 closed human-decision patch",
        "# STAGING ONLY; no product tree path is writable by this package.",
    ]
    for entry in entries:
        locator = entry["locator"]
        label = "::".join(locator[field] for field in LOCATOR_FIELDS)
        lines.extend([
            f"diff --magireco-staging-key {entry['item_id']} {label}",
            f"--- {label}",
            f"+++ {label}",
            f"@@ before-sha256 {entry['before_sha256']} after-sha256 {entry['after_sha256']} @@",
            "-" + json.dumps(entry["before"], ensure_ascii=False),
            "+" + json.dumps(entry["after"], ensure_ascii=False),
        ])
    return ("\n".join(lines) + "\n").encode("utf-8")


def _manifest_document(schema: str, mode: str, entries: list[dict[str, Any]], executor_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "entries": entries,
        "executor": executor_record,
        "executor_mode": mode,
        "human_approval_completed": True,
        "machine_executable": True,
        "product_tree_writes": False,
        "protected_text_changes": 0,
        "schema": schema,
        "staging_only": True,
        "target_contract": {
            "marker": ".dsv4-low-tier-staging.json",
            "product_tree_writes": False,
            "protected_text_changes": 0,
            "target": "low_tier_values.json",
        },
        "terminal_mode": "human_decisions_closed",
    }


def _self_verify(
    parent: Path,
    executor: Any,
    marker_bytes: bytes,
    stage_bytes: bytes,
    patch_bytes: bytes,
    rollback_bytes: bytes,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dsv4-human-patch-selftest-", dir=parent) as td:
        root = Path(td)
        stage_root = root / "baseline_staging"
        stage_root.mkdir()
        marker = stage_root / ".dsv4-low-tier-staging.json"
        target = stage_root / "low_tier_values.json"
        patch = root / "correction_patch.json"
        rollback = root / "rollback.json"
        marker.write_bytes(marker_bytes)
        target.write_bytes(stage_bytes)
        patch.write_bytes(patch_bytes)
        rollback.write_bytes(rollback_bytes)
        baseline_sha = sha256_bytes(stage_bytes)
        apply_report = executor.execute(stage_root, target, patch)
        applied_sha = sha256_bytes(target.read_bytes())
        rollback_report = executor.execute(stage_root, target, rollback)
        restored_sha = sha256_bytes(target.read_bytes())
        if restored_sha != baseline_sha:
            raise BuildError("staging apply/rollback did not restore the exact baseline bytes")
        return {
            "apply": {"exit_status": 0, "literal_output": apply_report},
            "baseline_staging_sha256": baseline_sha,
            "commands": {
                "apply": "python staging_patch_executor.py --stage-root baseline_staging --target baseline_staging/low_tier_values.json --manifest correction_patch.json",
                "rollback": "python staging_patch_executor.py --stage-root baseline_staging --target baseline_staging/low_tier_values.json --manifest rollback.json",
            },
            "post_apply_staging_sha256": applied_sha,
            "post_rollback_staging_sha256": restored_sha,
            "rollback": {"exit_status": 0, "literal_output": rollback_report},
        }


def build(source: Path, decisions: Path, output_dir: Path) -> dict[str, Any]:
    output = _safe_output_path(output_dir)
    validator = _load_module(VALIDATOR_PATH, "validate_dsv4_human_review_for_patch")
    executor = _load_module(EXECUTOR_PATH, "dsv4_v3_staging_patch_for_human_review")
    if PATCH_SCHEMA not in executor.PATCH_SCHEMAS or ROLLBACK_SCHEMA not in executor.PATCH_SCHEMAS:
        raise BuildError("existing staging executor schema contract is incompatible")
    validation, source_header, source_rows, decision_header, decision_rows = _read_stable_inputs(
        source.resolve(), decisions.resolve(), validator
    )
    entries, staging_records = _build_entries(source_header, source_rows, decision_header, decision_rows)
    executor_bytes = EXECUTOR_PATH.read_bytes()
    executor_record = {"path": "staging_patch_executor.py", **file_record(executor_bytes)}
    patch_document = _manifest_document(PATCH_SCHEMA, "apply", entries, executor_record)
    rollback_entries = [
        {
            **entry,
            "after": entry["before"],
            "after_sha256": entry["before_sha256"],
            "before": entry["after"],
            "before_sha256": entry["after_sha256"],
        }
        for entry in entries
    ]
    rollback_document = _manifest_document(ROLLBACK_SCHEMA, "rollback", rollback_entries, executor_record)
    marker_bytes = canonical_json_bytes({"product_tree_writes": False, "schema": ROOT_SCHEMA, "staging_only": True})
    stage_bytes = pretty_json_bytes({
        "product_tree_writes": False,
        "records": staging_records,
        "schema": VALUES_SCHEMA,
        "staging_only": True,
    })
    patch_bytes = pretty_json_bytes(patch_document)
    rollback_bytes = pretty_json_bytes(rollback_document)
    artifacts: dict[str, bytes] = {
        "baseline_staging/.dsv4-low-tier-staging.json": marker_bytes,
        "baseline_staging/low_tier_values.json": stage_bytes,
        "correction_patch.json": patch_bytes,
        "corrections.patch": _patch_text(entries),
        "rollback.json": rollback_bytes,
        "staging_patch_executor.py": executor_bytes,
    }
    selftest = _self_verify(output.parent, executor, marker_bytes, stage_bytes, patch_bytes, rollback_bytes)
    verification = {
        "decision_gate": {
            "all_decided": validation["all_decided"],
            "release_gate_open": validation["release_gate_open"],
            "states": validation["states"],
            "unresolved": validation["states"]["unresolved"],
        },
        "history_entries_written": 0,
        "inputs": {
            "decisions": {"sha256": validation["decisions_sha256"]},
            "source": {"sha256": validation["source_sha256"]},
        },
        "product_tree_writes": False,
        "protected_text_changes": 0,
        "schema": VERIFY_SCHEMA,
        "selected_revisions": len(entries),
        "self_test": selftest,
        "status": "PASS",
    }
    artifacts["verification_record.json"] = pretty_json_bytes(verification)
    inventory = {name: file_record(data) for name, data in sorted(artifacts.items())}
    package_manifest = {
        "artifacts": inventory,
        "decision_gate": {
            "all_decided": True,
            "release_gate_open": True,
            "unresolved": 0,
        },
        "inputs": {
            "decisions_sha256": validation["decisions_sha256"],
            "source_sha256": validation["source_sha256"],
        },
        "product_tree_writes": False,
        "protected_text_changes": 0,
        "schema": PACKAGE_SCHEMA,
        "selection": {
            "human_decision": "revise",
            "review_kind": "current-low-tier-translation-review",
            "selected_revisions": len(entries),
            "unchanged_values_excluded": True,
            "historical_rows_excluded": True,
        },
        "status": "PASS",
    }
    artifacts["manifest.json"] = pretty_json_bytes(package_manifest)

    temp_root = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        for relative, data in sorted(artifacts.items()):
            destination = temp_root / PurePosixPath(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        for relative, data in artifacts.items():
            reopened = (temp_root / PurePosixPath(relative)).read_bytes()
            if reopened != data:
                raise BuildError(f"artifact reopen verification failed: {relative}")
        os.replace(temp_root, output)
    except Exception:
        if temp_root.exists():
            shutil.rmtree(temp_root)
        raise
    return {
        "decision_gate": package_manifest["decision_gate"],
        "output_dir": str(output),
        "package_manifest_sha256": sha256_bytes(artifacts["manifest.json"]),
        "product_tree_writes": False,
        "protected_text_changes": 0,
        "selected_revisions": len(entries),
        "status": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new repo-external output directory")
    args = parser.parse_args(argv)
    try:
        result = build(args.source, args.decisions, args.out)
    except (BuildError, OSError, UnicodeDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "status": "FAIL"}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
