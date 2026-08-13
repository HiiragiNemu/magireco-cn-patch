#!/usr/bin/env python3
"""Apply or roll back a DSV4 terminal patch in an isolated low-tier staging file.

The executor deliberately accepts only the dedicated staging JSON contract.  It
does not understand product files and rejects protected or product-writable
records.  Every mutation is located by the complete stable-key tuple and is
guarded by the literal before-value SHA-256 before an atomic replacement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT_SCHEMA = "magireco-cn-dsv4-v3-low-tier-staging-root/1"
VALUES_SCHEMA = "magireco-cn-dsv4-v3-low-tier-staging-values/1"
PATCH_SCHEMAS = {
    "magireco-cn-dsv4-v3-terminal-assembly/2-correction-patch",
    "magireco-cn-dsv4-v3-terminal-assembly/2-rollback",
}
MARKER_NAME = ".dsv4-low-tier-staging.json"
TARGET_NAME = "low_tier_values.json"
HEX64 = set("0123456789abcdef")
LOCATOR_FIELDS = ("source_path", "source_key", "source_field", "stable_business_key")


class PatchError(RuntimeError):
    """Fail-closed staging-patch error."""


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise PatchError(f"regular non-symlink JSON required: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise PatchError(f"UTF-8 BOM forbidden: {path}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PatchError(f"invalid UTF-8 JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PatchError(f"JSON object required: {path}")
    return value


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in HEX64 for ch in value):
        raise PatchError(f"invalid SHA-256: {label}")
    return value


def _locator(record: dict[str, Any]) -> dict[str, str]:
    return {field: str(record.get(field, "")) for field in LOCATOR_FIELDS}


def _validate_stage(stage_root: Path, target: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    stage_root = stage_root.resolve()
    target = target.resolve()
    if not stage_root.is_dir() or target.name != TARGET_NAME or not _inside(target, stage_root):
        raise PatchError("target must be low_tier_values.json inside the explicit staging root")
    marker = _parse_json(stage_root / MARKER_NAME)
    if marker != {"product_tree_writes": False, "schema": ROOT_SCHEMA, "staging_only": True}:
        raise PatchError("dedicated low-tier staging marker invalid")
    document = _parse_json(target)
    if document.get("schema") != VALUES_SCHEMA or document.get("staging_only") is not True or document.get("product_tree_writes") is not False:
        raise PatchError("dedicated low-tier staging values contract invalid")
    records = document.get("records")
    if not isinstance(records, list):
        raise PatchError("staging records list required")
    seen_ids: set[str] = set()
    seen_locators: set[str] = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise PatchError(f"staging record object required: {index}")
        if record.get("product_write_allowed") is not False or record.get("protected_authority_text") is not False:
            raise PatchError(f"only unprotected non-product records are mutable: {index}")
        item_id = record.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in seen_ids:
            raise PatchError(f"unique item_id required: {index}")
        locator = _locator(record)
        if any(not locator[field] for field in LOCATOR_FIELDS):
            raise PatchError(f"complete stable locator required: {item_id}")
        locator_hash = sha256_bytes(canonical_json_bytes(locator))
        if locator_hash in seen_locators:
            raise PatchError(f"unique stable locator required: {item_id}")
        value = record.get("value")
        if not isinstance(value, str) or record.get("value_sha256") != sha256_bytes(value.encode("utf-8")):
            raise PatchError(f"staging value/hash invalid: {item_id}")
        seen_ids.add(item_id)
        seen_locators.add(locator_hash)
    return marker, document


def transform_document(document: dict[str, Any], manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    schema = manifest.get("schema")
    if schema not in PATCH_SCHEMAS or manifest.get("staging_only") is not True or manifest.get("product_tree_writes") is not False:
        raise PatchError("terminal patch/rollback manifest contract invalid")
    expected_mode = "apply" if schema.endswith("-correction-patch") else "rollback"
    if manifest.get("machine_executable") is not True or manifest.get("executor_mode") != expected_mode:
        raise PatchError("terminal patch/rollback executor mode invalid")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise PatchError("manifest entries list required")
    records = document.get("records")
    if not isinstance(records, list):
        raise PatchError("staging records list required")
    by_item = {record["item_id"]: record for record in records}
    seen: set[str] = set()
    changes: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise PatchError("manifest entry object required")
        item_id = entry.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in seen or item_id not in by_item:
            raise PatchError(f"manifest item identity missing, duplicate, or absent: {item_id!r}")
        seen.add(item_id)
        record = by_item[item_id]
        locator = entry.get("locator")
        if not isinstance(locator, dict) or locator != _locator(record):
            raise PatchError(f"stable locator mismatch: {item_id}")
        locator_hash = sha256_bytes(canonical_json_bytes(locator))
        if entry.get("locator_sha256") != locator_hash:
            raise PatchError(f"locator SHA-256 mismatch: {item_id}")
        before = entry.get("before")
        after = entry.get("after")
        if not isinstance(before, str) or not isinstance(after, str):
            raise PatchError(f"literal before/after required: {item_id}")
        before_sha = _require_sha(entry.get("before_sha256"), f"{item_id}/before")
        after_sha = _require_sha(entry.get("after_sha256"), f"{item_id}/after")
        if before_sha != sha256_bytes(before.encode("utf-8")) or after_sha != sha256_bytes(after.encode("utf-8")):
            raise PatchError(f"manifest literal/hash mismatch: {item_id}")
        if record["value"] != before or record["value_sha256"] != before_sha:
            raise PatchError(f"before SHA gate failed: {item_id}")
        record["value"] = after
        record["value_sha256"] = after_sha
        changes.append({"item_id": item_id, "before_sha256": before_sha, "after_sha256": after_sha})
    return document, {"changes": changes, "entries": len(entries), "status": "PASS"}


def execute(stage_root: Path, target: Path, manifest_path: Path) -> dict[str, Any]:
    stage_root = stage_root.resolve()
    target = target.resolve()
    manifest_path = manifest_path.resolve()
    _, document = _validate_stage(stage_root, target)
    manifest = _parse_json(manifest_path)
    before_bytes = target.read_bytes()
    before_sha = sha256_bytes(before_bytes)
    transformed, detail = transform_document(document, manifest)
    after_bytes = pretty_json_bytes(transformed)
    temp_fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(temp_fd, "wb") as stream:
            stream.write(after_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    _, reopened = _validate_stage(stage_root, target)
    if reopened != transformed:
        raise PatchError("atomic output reopen verification failed")
    return {
        **detail,
        "manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
        "target_before_sha256": before_sha,
        "target_after_sha256": sha256_bytes(target.read_bytes()),
        "product_tree_writes": False,
        "protected_text_changes": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = execute(args.stage_root, args.target, args.manifest)
    except PatchError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
