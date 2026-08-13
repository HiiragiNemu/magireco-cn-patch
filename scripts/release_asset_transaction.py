#!/usr/bin/env python3
"""Transactional replacement of a GitHub Release asset set.

The caller uploads changed assets under unique temporary names.  This module
then uses the Release Asset PATCH endpoint to swap names while retaining every
old stable asset under a rollback name until the complete batch verifies.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence


class AssetTransactionError(RuntimeError):
    """Raised when staging, promotion, verification, or rollback fails closed."""


@dataclass(frozen=True)
class AssetExpectation:
    """Expected metadata and source needed by the backend uploader."""

    size: int
    digest: str
    source_url: str


class ReleaseAssetBackend(Protocol):
    def list_assets(self) -> dict[str, dict]: ...
    def upload_asset(self, name: str, expected: AssetExpectation) -> bool: ...
    def rename_asset(self, asset_id: int, old_name: str, new_name: str) -> bool: ...
    def delete_asset(self, asset_id: int, name: str) -> bool: ...
    def verify_asset(self, name: str, expected: AssetExpectation) -> bool: ...


def _asset_id(asset: dict) -> int:
    try:
        return int(asset["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AssetTransactionError(f"asset has no valid id: {asset!r}") from exc


def _run_token(run_id: str) -> str:
    token = re.sub(r"[^A-Za-z0-9-]", "-", str(run_id)).strip("-")
    if not token:
        raise AssetTransactionError("run id does not contain a usable token")
    return token[:40]


def _transaction_name(stable_name: str, kind: str, run_id: str) -> str:
    # Use only characters GitHub preserves in uploaded asset names.  A hash
    # keeps the name short and collision-free even for long/non-ASCII names.
    stable_hash = hashlib.sha256(stable_name.encode("utf-8")).hexdigest()[:16]
    return f"mirror-txn-{_run_token(run_id)}-{stable_hash}-{kind}"


def _rename_and_confirm(
    backend: ReleaseAssetBackend,
    asset: dict,
    old_name: str,
    new_name: str,
) -> bool:
    """Rename, reconciling a lost response against the asset's immutable id."""

    asset_id = _asset_id(asset)
    try:
        if backend.rename_asset(asset_id, old_name, new_name):
            return True
    except Exception:
        pass
    try:
        current = backend.list_assets()
        target = current.get(new_name)
        source = current.get(old_name)
        return (
            target is not None
            and _asset_id(target) == asset_id
            and (source is None or _asset_id(source) != asset_id)
        )
    except Exception:
        return False


def _delete_if_present(
    backend: ReleaseAssetBackend,
    name: str,
    errors: list[str],
) -> None:
    try:
        current = backend.list_assets()
        asset = current.get(name)
        if asset:
            try:
                deleted = backend.delete_asset(_asset_id(asset), name)
            except Exception:
                deleted = False
            if not deleted and name in backend.list_assets():
                errors.append(f"delete {name}")
    except Exception as exc:  # backend/network errors must remain visible
        errors.append(f"delete {name} ({exc})")


def _rollback(
    backend: ReleaseAssetBackend,
    records: list[dict],
    staged_names: Sequence[str],
) -> list[str]:
    errors: list[str] = []
    for record in reversed(records):
        stable_name = record["stable_name"]
        incoming_name = record.get("incoming_name")
        backup_name = record["backup_name"]

        if record.get("new_promoted"):
            try:
                current = backend.list_assets()
                stable = current.get(stable_name)
                if not stable or not _rename_and_confirm(
                    backend, stable, stable_name, incoming_name
                ):
                    errors.append(f"move new stable aside {stable_name}")
            except Exception as exc:
                errors.append(f"move new stable aside {stable_name} ({exc})")

        if record.get("old_backed_up"):
            try:
                current = backend.list_assets()
                backup = current.get(backup_name)
                if not backup or not _rename_and_confirm(
                    backend, backup, backup_name, stable_name
                ):
                    errors.append(f"restore stable {stable_name}")
            except Exception as exc:
                errors.append(f"restore stable {stable_name} ({exc})")

    # Staged/new assets are disposable only after every original name has had
    # a restore attempt.  A failed cleanup is reported rather than hidden.
    for name in staged_names:
        _delete_if_present(backend, name, errors)
    return errors


def replace_release_asset_set(
    backend: ReleaseAssetBackend,
    changed: Mapping[str, AssetExpectation],
    removed: Sequence[str],
    run_id: str,
) -> list[str]:
    """Atomically replace/remove logical assets, retaining rollback copies.

    All changed bytes are uploaded and verified before any stable name moves.
    Old stable assets and removals are renamed to transaction-private backup
    names, not deleted.  The full logical result is verified before backups are
    deleted.  Any pre-commit failure restores the entire original batch.
    """

    changed_names = list(changed)
    removed_names = list(dict.fromkeys(removed))
    overlap = set(changed_names) & set(removed_names)
    if overlap:
        raise AssetTransactionError(
            f"assets cannot be both changed and removed: {sorted(overlap)}"
        )
    if any(expectation.size < 0 for expectation in changed.values()):
        raise AssetTransactionError("asset size cannot be negative")

    initial = backend.list_assets()
    records: list[dict] = []
    staged_names: list[str] = []

    # Preflight every generated name before uploading.  We intentionally fail
    # rather than delete a collision because a previous interrupted run may
    # have left the only rollback copy under that name.
    generated: set[str] = set()
    for stable_name in changed_names + removed_names:
        incoming = (
            _transaction_name(stable_name, "incoming", run_id)
            if stable_name in changed
            else None
        )
        backup = _transaction_name(stable_name, "rollback", run_id)
        for candidate in (incoming, backup):
            if candidate is None:
                continue
            if candidate in generated or candidate in initial:
                raise AssetTransactionError(
                    f"transaction asset name already exists: {candidate}"
                )
            generated.add(candidate)

    # Stage and verify all replacement bytes before touching stable names.
    try:
        for stable_name, expected in changed.items():
            incoming = _transaction_name(stable_name, "incoming", run_id)
            # Track before the call: an HTTP client may report failure after
            # GitHub has already persisted the upload response server-side.
            staged_names.append(incoming)
            if not backend.upload_asset(incoming, expected):
                raise AssetTransactionError(f"staging upload failed: {stable_name}")
            if not backend.verify_asset(incoming, expected):
                raise AssetTransactionError(f"staging verification failed: {stable_name}")
    except Exception as exc:
        cleanup_errors: list[str] = []
        for name in staged_names:
            _delete_if_present(backend, name, cleanup_errors)
        failure = (
            exc
            if isinstance(exc, AssetTransactionError)
            else AssetTransactionError(f"staging backend error: {exc}")
        )
        if cleanup_errors:
            raise AssetTransactionError(
                f"{failure}; staging cleanup also failed: {', '.join(cleanup_errors)}"
            ) from exc
        if failure is exc:
            raise
        raise failure from exc

    try:
        for stable_name, expected in changed.items():
            incoming_name = _transaction_name(stable_name, "incoming", run_id)
            backup_name = _transaction_name(stable_name, "rollback", run_id)
            record = {
                "stable_name": stable_name,
                "incoming_name": incoming_name,
                "backup_name": backup_name,
                "old_backed_up": False,
                "new_promoted": False,
            }
            records.append(record)

            current = backend.list_assets()
            old = current.get(stable_name)
            if old:
                if not _rename_and_confirm(
                    backend, old, stable_name, backup_name
                ):
                    raise AssetTransactionError(
                        f"stable asset cannot be backed up: {stable_name}"
                    )
                record["old_backed_up"] = True

            current = backend.list_assets()
            incoming = current.get(incoming_name)
            if not incoming or not _rename_and_confirm(
                backend, incoming, incoming_name, stable_name
            ):
                raise AssetTransactionError(
                    f"staged asset cannot be promoted: {stable_name}"
                )
            record["new_promoted"] = True
            if not backend.verify_asset(stable_name, expected):
                raise AssetTransactionError(
                    f"promoted asset verification failed: {stable_name}"
                )

        # Logical removals remain recoverable until every change has verified.
        for stable_name in removed_names:
            current = backend.list_assets()
            old = current.get(stable_name)
            if old is None:
                continue
            backup_name = _transaction_name(stable_name, "rollback", run_id)
            record = {
                "stable_name": stable_name,
                "incoming_name": None,
                "backup_name": backup_name,
                "old_backed_up": False,
                "new_promoted": False,
            }
            records.append(record)
            if not _rename_and_confirm(backend, old, stable_name, backup_name):
                raise AssetTransactionError(
                    f"removed asset cannot be retained for rollback: {stable_name}"
                )
            record["old_backed_up"] = True

        current = backend.list_assets()
        missing = [name for name in changed_names if name not in current]
        retained = [name for name in removed_names if name in current]
        if missing or retained:
            raise AssetTransactionError(
                f"logical set verification failed: missing={missing}, retained={retained}"
            )
    except Exception as exc:
        failure = (
            exc
            if isinstance(exc, AssetTransactionError)
            else AssetTransactionError(f"promotion backend error: {exc}")
        )
        rollback_errors = _rollback(backend, records, staged_names)
        if rollback_errors:
            raise AssetTransactionError(
                f"{failure}; rollback also failed: {', '.join(rollback_errors)}"
            ) from exc
        if failure is exc:
            raise
        raise failure from exc

    # Commit point: all logical names and changed bytes have verified.  Failure
    # to remove a backup leaves the new stable set usable and is surfaced for a
    # later cleanup run; rolling back after partial backup deletion is unsafe.
    cleanup_errors: list[str] = []
    for record in records:
        if not record["old_backed_up"]:
            continue
        _delete_if_present(backend, record["backup_name"], cleanup_errors)
    if cleanup_errors:
        raise AssetTransactionError(
            "new stable asset set is valid but rollback cleanup failed: "
            + ", ".join(cleanup_errors)
        )
    return changed_names
