#!/usr/bin/env python3
"""Restore a Pass20 staging product from its exact before-file snapshots."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import sys
from typing import Any


class RollbackError(RuntimeError):
    pass


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


def rollback(stage_root: Path, product_root: Path | None = None) -> dict[str, Any]:
    manifest_path = stage_root / "rollback/rollback.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "magireco-cn-pass20-product-rollback/1":
        raise RollbackError("rollback manifest schema drifted")
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
        prepared.append((rel, current, before_bytes, before_digest, before_size))
    for rel, current, before_bytes, before_digest, before_size in prepared:
        current.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=current.parent) as stream:
            temp = Path(stream.name)
            stream.write(before_bytes)
        temp.replace(current)
        restored = current.read_bytes()
        if len(restored) != before_size or sha256(restored).hexdigest() != before_digest:
            raise RollbackError(f"rollback verification failed: {rel}")
    return {
        "schema": "magireco-cn-pass20-product-rollback-result/1",
        "status": "PASS",
        "restored_files": len(prepared),
        "exact_after_gate": True,
        "exact_before_restored": True,
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
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
