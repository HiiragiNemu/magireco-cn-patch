#!/usr/bin/env python3
"""Restore a Pass20 staging product from its exact before-file snapshots."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import sys
from typing import Any


class RollbackError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        product_state: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.product_state = product_state


def atomic_replace(source: Path, target: Path) -> None:
    """Single indirection used by the focused transaction-failure test."""
    source.replace(target)


def write_temp(target: Path, data: bytes) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=target.parent) as stream:
        temp = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return temp


def exact_bytes(path: Path, data: bytes, digest: str, size: int) -> bool:
    try:
        current = path.read_bytes()
    except OSError:
        return False
    return len(current) == size and sha256(current).hexdigest() == digest and current == data


def safe_join(root: Path, rel: str) -> Path:
    if "\\" in rel or ":" in rel:
        raise RollbackError(f"unsafe rollback product path: {rel!r}")
    pure = PurePosixPath(rel)
    if (
        pure.is_absolute() or ".." in pure.parts or not pure.parts
        or pure.parts[0] not in {"magica", "i18n"}
    ):
        raise RollbackError(f"unsafe rollback product path: {rel!r}")
    base = (root / pure.parts[0]).resolve()
    raw = root.joinpath(*pure.parts)
    candidate = raw.resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise RollbackError(f"rollback product path escapes product root: {rel!r}") from exc
    return raw


def safe_snapshot(stage_root: Path, rel: str, kind: str, value: str) -> Path:
    expected = f"rollback/{kind}/{rel}"
    if value != expected or "\\" in value or ":" in value:
        raise RollbackError(f"rollback {kind} snapshot path drifted: {rel}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise RollbackError(f"unsafe rollback {kind} snapshot path: {value!r}")
    base = (stage_root / "rollback" / kind).resolve()
    raw = stage_root.joinpath(*pure.parts)
    candidate = raw.resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise RollbackError(f"rollback {kind} snapshot escapes its root: {rel}") from exc
    return raw


def checked_digest(value: object, label: str, rel: str) -> str:
    text = str(value or "")
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise RollbackError(f"invalid {label} for rollback file: {rel}")
    return text


def validate_review_contract(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RollbackError("rollback manifest review contract is missing")
    names = (
        "machine_inventory_items", "human_review_items", "materialization_items",
        "higher_authority_shadowed_items", "product_write_forbidden_items",
        "authority_resolution_items", "exact_runtime_items", "maintenance_only_items",
        "runtime_occurrences", "global_items", "override_items", "fragment_items",
        "shadowed_low_tier_candidates_written", "shadowed_product_writes",
    )
    result: dict[str, Any] = {}
    for name in names:
        raw = value.get(name)
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise RollbackError(f"rollback review contract has an invalid {name}")
        result[name] = raw
    if result["human_review_items"] != result["materialization_items"]:
        raise RollbackError("rollback human review/materialization count drifted")
    if result["machine_inventory_items"] != (
        result["materialization_items"] + result["higher_authority_shadowed_items"]
    ):
        raise RollbackError("rollback machine inventory partition drifted")
    if result["product_write_forbidden_items"] != result["higher_authority_shadowed_items"]:
        raise RollbackError("rollback protected shadow/write-forbidden count drifted")
    if result["shadowed_low_tier_candidates_written"] != 0 or result["shadowed_product_writes"] != 0:
        raise RollbackError("rollback contract records a protected shadow write")
    if result["materialization_items"] != (
        result["exact_runtime_items"] + result["maintenance_only_items"]
    ):
        raise RollbackError("rollback runtime/maintenance partition drifted")
    if result["materialization_items"] != (
        result["global_items"] + result["override_items"] + result["fragment_items"]
    ):
        raise RollbackError("rollback global/override/fragment partition drifted")
    for name in (
        "source_records_sha256", "target_contract_sha256", "authority_shadow_manifest_sha256",
        "authority_resolutions_sha256",
    ):
        digest = value.get(name)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RollbackError(f"rollback review contract has an invalid {name}")
        result[name] = digest
    return result


def rollback(stage_root: Path, product_root: Path | None = None) -> dict[str, Any]:
    manifest_path = stage_root / "rollback/rollback.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "magireco-cn-pass20-product-rollback/1":
        raise RollbackError("rollback manifest schema drifted")
    review_contract = validate_review_contract(payload.get("review_contract"))
    files = payload.get("files")
    if not isinstance(files, list):
        raise RollbackError("rollback manifest files are invalid")
    product_root = product_root or stage_root
    prepared = []
    seen: set[str] = set()
    for record in files:
        rel = record.get("path", "")
        if not isinstance(rel, str) or rel in seen:
            raise RollbackError(f"duplicate or invalid rollback product path: {rel!r}")
        seen.add(rel)
        current = safe_join(product_root, rel)
        before = safe_snapshot(stage_root, rel, "before", str(record.get("before_snapshot", "")))
        after = safe_snapshot(stage_root, rel, "after", str(record.get("after_snapshot", "")))
        if (
            not current.is_file() or current.is_symlink()
            or not before.is_file() or before.is_symlink()
            or not after.is_file() or after.is_symlink()
        ):
            raise RollbackError(f"rollback role is missing: {rel}")
        current_bytes = current.read_bytes()
        after_bytes = after.read_bytes()
        before_bytes = before.read_bytes()
        before_digest = checked_digest(record.get("before_sha256"), "before_sha256", rel)
        after_digest = checked_digest(record.get("after_sha256"), "after_sha256", rel)
        try:
            before_size = int(record.get("before_size"))
            after_size = int(record.get("after_size"))
        except (TypeError, ValueError) as exc:
            raise RollbackError(f"invalid rollback snapshot size: {rel}") from exc
        if len(before_bytes) != before_size or sha256(before_bytes).hexdigest() != before_digest:
            raise RollbackError(f"before snapshot digest or size drifted: {rel}")
        if len(after_bytes) != after_size or sha256(after_bytes).hexdigest() != after_digest:
            raise RollbackError(f"after snapshot digest or size drifted: {rel}")
        if len(current_bytes) != after_size or sha256(current_bytes).hexdigest() != after_digest:
            raise RollbackError(f"current product differs from exact after snapshot: {rel}")
        prepared.append({
            "rel": rel,
            "current": current,
            "before": before_bytes,
            "before_digest": before_digest,
            "before_size": before_size,
            "after": after_bytes,
            "after_digest": after_digest,
            "after_size": after_size,
            "temp": None,
        })

    try:
        # Prepare and flush every replacement before changing the first product file.
        for item in prepared:
            item["temp"] = write_temp(item["current"], item["before"])
        for item in prepared:
            current = item["current"]
            if not exact_bytes(
                current, item["after"], item["after_digest"], item["after_size"]
            ):
                raise RollbackError(
                    f"current product changed during rollback: {item['rel']}"
                )
            atomic_replace(item["temp"], current)
            item["temp"] = None
            if not exact_bytes(
                current, item["before"], item["before_digest"], item["before_size"]
            ):
                raise RollbackError(f"rollback verification failed: {item['rel']}")
    except Exception as exc:
        # A rollback is all-or-nothing.  If any later replacement fails, restore
        # every target to the exact after snapshot so the same manifest can be
        # retried without a mixed before/after product tree.
        compensation_errors: list[str] = []
        for item in prepared:
            current = item["current"]
            if exact_bytes(
                current, item["after"], item["after_digest"], item["after_size"]
            ):
                continue
            recovery: Path | None = None
            try:
                recovery = write_temp(current, item["after"])
                atomic_replace(recovery, current)
                recovery = None
                if not exact_bytes(
                    current, item["after"], item["after_digest"], item["after_size"]
                ):
                    raise RollbackError("exact after verification failed")
            except Exception as recovery_exc:
                compensation_errors.append(f"{item['rel']}: {recovery_exc}")
            finally:
                if recovery is not None and recovery.exists():
                    recovery.unlink()
        for item in prepared:
            temp = item.get("temp")
            if isinstance(temp, Path) and temp.exists():
                temp.unlink()
        if compensation_errors:
            raise RollbackError(
                "rollback failed and transaction compensation was incomplete: "
                + "; ".join(compensation_errors),
                product_state="mixed-or-unknown",
            ) from exc
        raise RollbackError(
            f"rollback failed; exact after state restored and operation is retryable: {exc}",
            retryable=True,
            product_state="exact-after-restored",
        ) from exc
    finally:
        for item in prepared:
            temp = item.get("temp")
            if isinstance(temp, Path) and temp.exists():
                temp.unlink()
    return {
        "schema": "magireco-cn-pass20-product-rollback-result/1",
        "status": "PASS",
        "restored_files": len(prepared),
        "exact_after_gate": True,
        "exact_before_restored": True,
        "review_contract": review_contract,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--product-root", type=Path)
    args = parser.parse_args(argv)
    try:
        result = rollback(args.stage_root, args.product_root)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (RollbackError, OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        report = {"status": "FAIL", "error": str(exc)}
        if isinstance(exc, RollbackError):
            report["retryable"] = exc.retryable
            report["product_state"] = exc.product_state
        print(json.dumps(report, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
