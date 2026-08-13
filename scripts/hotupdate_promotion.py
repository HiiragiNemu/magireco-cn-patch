#!/usr/bin/env python3
"""Transactional promotion of hot-update preview assets to stable names."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Protocol


PROMOTION_ORDER = (
    ("js", "cn_js_update_new.zip", "cn_js_update.zip"),
    ("js", "cn_js_update_manifest_new.json", "cn_js_update_manifest.json"),
    ("scenario", "cn_scenario_update_new.zip", "cn_scenario_update.zip"),
    (
        "scenario",
        "cn_scenario_update_manifest_new.json",
        "cn_scenario_update_manifest.json",
    ),
    # The shared chunk manifest describes the stable zip names.  Promote it
    # only after every package byte/manifest pair is present, then publish the
    # version files last so clients cannot observe a new version with old
    # package or chunk metadata.
    ("shared", "manifest_new.json", "manifest.json"),
    ("js", "version_js_new.json", "version_js.json"),
    ("scenario", "version_scenario_new.json", "version_scenario.json"),
)

TRIPLETS = {
    "js": (
        "cn_js_update_new.zip",
        "cn_js_update_manifest_new.json",
        "version_js_new.json",
        "cn_js_update",
    ),
    "scenario": (
        "cn_scenario_update_new.zip",
        "cn_scenario_update_manifest_new.json",
        "version_scenario_new.json",
        "cn_scenario_update",
    ),
}


class PromotionError(RuntimeError):
    """Raised when validation, promotion, or rollback fails closed."""


class AssetBackend(Protocol):
    def list_assets(self) -> dict[str, dict]: ...
    def rename_asset(self, asset_id: int, old_name: str, new_name: str) -> bool: ...
    def delete_asset(self, asset_id: int, name: str) -> bool: ...
    def verify_asset(self, name: str, local_path: Path) -> bool: ...


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _chunk_hashes(path: Path, chunk_size: int) -> tuple[int, list[str]]:
    size = 0
    chunks: list[str] = []
    with path.open("rb") as handle:
        while block := handle.read(chunk_size):
            size += len(block)
            chunks.append(hashlib.md5(block).hexdigest().lower())
    return size, chunks


def _validate_shared_chunk_manifest(root: Path, active: list[str]) -> None:
    path = root / "manifest_new.json"
    if not path.is_file():
        raise PromotionError("shared preview chunk manifest is missing: manifest_new.json")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromotionError("shared preview chunk manifest is malformed") from exc
    if not isinstance(manifest, dict):
        raise PromotionError("shared preview chunk manifest is malformed")

    for scope in active:
        zip_name = TRIPLETS[scope][0]
        stable_name = TRIPLETS[scope][3] + ".zip"
        entry = manifest.get(stable_name)
        try:
            chunk_size = int(entry["chunk_size"])
            recorded_size = int(entry["size"])
            recorded_chunks = list(entry["chunks"])
        except (TypeError, KeyError, ValueError) as exc:
            raise PromotionError(
                f"shared preview chunk manifest has no valid {stable_name} entry"
            ) from exc
        if chunk_size <= 0 or any(
            not isinstance(value, str)
            or re.fullmatch(r"[0-9a-f]{32}", value.lower()) is None
            for value in recorded_chunks
        ):
            raise PromotionError(
                f"shared preview chunk manifest has invalid {stable_name} chunks"
            )
        actual_size, actual_chunks = _chunk_hashes(root / zip_name, chunk_size)
        if recorded_size != actual_size or [c.lower() for c in recorded_chunks] != actual_chunks:
            raise PromotionError(
                f"shared preview chunk manifest does not match {zip_name}"
            )


def validate_candidate_triplets(artifacts_dir: str | Path) -> tuple[str, ...]:
    """Validate package triplets and their shared preview chunk manifest."""

    root = Path(artifacts_dir)
    active: list[str] = []
    for scope, (zip_name, manifest_name, version_name, package_name) in TRIPLETS.items():
        paths = [root / zip_name, root / manifest_name, root / version_name]
        present = [path.is_file() for path in paths]
        if not any(present):
            continue
        if not all(present):
            raise PromotionError(
                f"{scope} candidate triplet is incomplete: "
                + ", ".join(f"{path.name}={exists}" for path, exists in zip(paths, present))
            )
        archive, manifest_path, version_path = paths
        size = archive.stat().st_size
        digest = _md5(archive)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            version = json.loads(version_path.read_text(encoding="utf-8"))
            version_pair = (int(version["size"]), str(version["md5"]).lower())
            manifest_pair = (
                int(manifest["zip_size"]),
                str(manifest["zip_md5"]).lower(),
            )
            same_version = int(manifest["version"]) == int(version["version"])
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise PromotionError(f"{scope} candidate metadata is malformed") from exc
        if version_pair != (size, digest) or manifest_pair != (size, digest):
            raise PromotionError(f"{scope} candidate size/md5 mismatch")
        if manifest.get("package") != package_name or not same_version:
            raise PromotionError(f"{scope} candidate package/version mismatch")
        active.append(scope)
    if active:
        _validate_shared_chunk_manifest(root, active)
        active.append("shared")
    elif (root / "manifest_new.json").exists():
        raise PromotionError(
            "shared preview chunk manifest exists without a package candidate"
        )
    return tuple(active)


def _asset_id(asset: dict) -> int:
    try:
        return int(asset["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PromotionError(f"asset has no valid id: {asset!r}") from exc


def _rename_and_confirm(
    backend: AssetBackend,
    asset: dict,
    old_name: str,
    new_name: str,
) -> bool:
    """Rename an asset and reconcile a lost response by immutable asset id."""

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


def _delete_and_confirm(
    backend: AssetBackend,
    asset: dict,
    name: str,
) -> bool:
    """Delete an asset and reconcile a lost response by re-listing assets."""

    try:
        if backend.delete_asset(_asset_id(asset), name):
            return True
    except Exception:
        pass
    try:
        return name not in backend.list_assets()
    except Exception:
        return False


def _rollback(backend: AssetBackend, records: list[dict]) -> list[str]:
    errors: list[str] = []
    for record in reversed(records):
        try:
            current = backend.list_assets()
            final_asset = current.get(record["final_name"])
            if (
                final_asset
                and _asset_id(final_asset) == record["new_asset_id"]
                and not _rename_and_confirm(
                    backend, final_asset, record["final_name"], record["new_name"]
                )
            ):
                errors.append(f"restore preview {record['final_name']}")
        except Exception as exc:
            errors.append(f"restore preview {record['final_name']} ({exc})")
        if record["had_old"]:
            try:
                current = backend.list_assets()
                final_asset = current.get(record["final_name"])
                backup = current.get(record["backup_name"])
                old_is_already_stable = (
                    final_asset is not None
                    and _asset_id(final_asset) == record["old_asset_id"]
                )
                if not old_is_already_stable and (
                    not backup
                    or _asset_id(backup) != record["old_asset_id"]
                    or not _rename_and_confirm(
                        backend,
                        backup,
                        record["backup_name"],
                        record["final_name"],
                    )
                ):
                    errors.append(f"restore stable {record['final_name']}")
            except Exception as exc:
                errors.append(f"restore stable {record['final_name']} ({exc})")
    return errors


def promote_available_assets(
    backend: AssetBackend,
    artifacts_dir: str | Path,
    run_id: str,
) -> list[tuple[str, str]]:
    """Promote all locally present scopes; rollback the whole batch on failure."""

    root = Path(artifacts_dir)
    active = set(validate_candidate_triplets(root))
    records: list[dict] = []
    promoted: list[tuple[str, str]] = []
    try:
        for scope, new_name, final_name in PROMOTION_ORDER:
            if scope not in active:
                continue
            source = root / new_name
            current = backend.list_assets()
            new_asset = current.get(new_name)
            if new_asset is None:
                raise PromotionError(f"candidate asset is missing: {new_name}")
            old_asset = current.get(final_name)
            backup_name = f"{final_name}.rollback-{run_id}"
            stale = current.get(backup_name)
            if stale and not _delete_and_confirm(backend, stale, backup_name):
                raise PromotionError(f"stale rollback asset cannot be deleted: {backup_name}")
            record = {
                "new_name": new_name,
                "new_asset_id": _asset_id(new_asset),
                "final_name": final_name,
                "backup_name": backup_name,
                "had_old": old_asset is not None,
                "old_asset_id": _asset_id(old_asset) if old_asset else None,
            }
            # Record identities before either rename.  If an API response and
            # the immediate reconciliation read are both lost, rollback can
            # still infer the persisted state from immutable asset ids.
            records.append(record)
            if old_asset and not _rename_and_confirm(
                backend, old_asset, final_name, backup_name
            ):
                raise PromotionError(f"stable asset cannot be backed up: {final_name}")
            if not _rename_and_confirm(backend, new_asset, new_name, final_name):
                raise PromotionError(f"candidate asset cannot be promoted: {new_name}")
            if not backend.verify_asset(final_name, source):
                raise PromotionError(f"promoted asset verification failed: {final_name}")
            promoted.append((new_name, final_name))
    except PromotionError as exc:
        rollback_errors = _rollback(backend, records)
        if rollback_errors:
            raise PromotionError(
                f"{exc}; rollback also failed: {', '.join(rollback_errors)}"
            ) from exc
        raise

    cleanup_errors: list[str] = []
    for record in records:
        if not record["had_old"]:
            continue
        current = backend.list_assets()
        backup = current.get(record["backup_name"])
        if backup and not _delete_and_confirm(backend, backup, record["backup_name"]):
            cleanup_errors.append(record["backup_name"])
    if cleanup_errors:
        raise PromotionError(
            "promoted assets are valid but rollback cleanup failed: "
            + ", ".join(cleanup_errors)
        )
    return promoted
