#!/usr/bin/env python3
"""Failure-injection tests for transactional Release asset promotion."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from hotupdate_promotion import PromotionError, promote_available_assets


class FakeBackend:
    def __init__(self, assets: dict[str, bytes]):
        self.assets = {
            name: {"id": index + 1, "data": data}
            for index, (name, data) in enumerate(assets.items())
        }
        self.fail_renames: set[tuple[str, str]] = set()
        self.fail_deletes: set[str] = set()
        self.fail_verifies: set[str] = set()

    def list_assets(self):
        return {name: dict(asset) for name, asset in self.assets.items()}

    def _by_id(self, asset_id: int):
        return next((name for name, asset in self.assets.items() if asset["id"] == asset_id), None)

    def rename_asset(self, asset_id: int, old_name: str, new_name: str) -> bool:
        if (old_name, new_name) in self.fail_renames:
            return False
        actual = self._by_id(asset_id)
        if actual != old_name or new_name in self.assets:
            return False
        self.assets[new_name] = self.assets.pop(old_name)
        return True

    def delete_asset(self, asset_id: int, name: str) -> bool:
        if name in self.fail_deletes or self._by_id(asset_id) != name:
            return False
        del self.assets[name]
        return True

    def verify_asset(self, name: str, local_path: Path) -> bool:
        return (
            name not in self.fail_verifies
            and name in self.assets
            and self.assets[name]["data"] == local_path.read_bytes()
        )


def make_js_triplet(root: Path) -> dict[str, bytes]:
    archive = b"new-js-package"
    digest = hashlib.md5(archive).hexdigest()
    version = {"version": 26, "size": len(archive), "md5": digest}
    manifest = {
        "package": "cn_js_update",
        "version": 26,
        "zip_size": len(archive),
        "zip_md5": digest,
    }
    files = {
        "cn_js_update_new.zip": archive,
        "cn_js_update_manifest_new.json": json.dumps(manifest).encode(),
        "version_js_new.json": json.dumps(version).encode(),
        "manifest_new.json": json.dumps(
            {
                "cn_js_update.zip": {
                    "size": len(archive),
                    "chunk_size": 4,
                    "chunks": [
                        hashlib.md5(archive[i : i + 4]).hexdigest()
                        for i in range(0, len(archive), 4)
                    ],
                }
            }
        ).encode(),
    }
    for name, data in files.items():
        (root / name).write_bytes(data)
    return files


def backend_with_old_and_new(root: Path) -> FakeBackend:
    preview = make_js_triplet(root)
    assets = dict(preview)
    assets.update(
        {
            "cn_js_update.zip": b"old-zip",
            "cn_js_update_manifest.json": b"old-manifest",
            "version_js.json": b"old-version",
            "manifest.json": b"old-chunk-manifest",
        }
    )
    return FakeBackend(assets)


class PromotionTest(unittest.TestCase):
    def test_success_promotes_js_only_with_shared_manifest_and_version_last(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            result = promote_available_assets(backend, root, "42")
            self.assertEqual(
                [final for _, final in result],
                [
                    "cn_js_update.zip",
                    "cn_js_update_manifest.json",
                    "manifest.json",
                    "version_js.json",
                ],
            )
            self.assertFalse(any("scenario" in name for name in backend.assets))
            self.assertFalse(any("_new" in name or ".rollback-" in name for name in backend.assets))

    def test_old_rename_failure_leaves_all_assets_unchanged(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            before = backend.list_assets()
            backend.fail_renames.add(("cn_js_update.zip", "cn_js_update.zip.rollback-42"))
            with self.assertRaisesRegex(PromotionError, "backed up"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.list_assets(), before)

    def test_new_rename_failure_restores_old_stable(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            backend.fail_renames.add(("cn_js_update_new.zip", "cn_js_update.zip"))
            with self.assertRaisesRegex(PromotionError, "cannot be promoted"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.assets["cn_js_update.zip"]["data"], b"old-zip")
            self.assertIn("cn_js_update_new.zip", backend.assets)

    def test_lost_old_stable_backup_response_is_reconciled_by_asset_id(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            original_rename = backend.rename_asset

            def persist_then_lose_response(asset_id, old_name, new_name):
                result = original_rename(asset_id, old_name, new_name)
                if old_name == "cn_js_update.zip" and new_name.endswith(".rollback-42"):
                    self.assertTrue(result)
                    return False
                return result

            backend.rename_asset = persist_then_lose_response
            promote_available_assets(backend, root, "42")
            self.assertEqual(backend.assets["cn_js_update.zip"]["data"], b"new-js-package")
            self.assertFalse(any(".rollback-" in name for name in backend.assets))

    def test_lost_backup_response_and_reconciliation_read_rolls_back_by_ids(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            original_rename = backend.rename_asset
            original_list = backend.list_assets
            lose_next_list = False

            def persist_then_lose_response(asset_id, old_name, new_name):
                nonlocal lose_next_list
                result = original_rename(asset_id, old_name, new_name)
                if old_name == "cn_js_update.zip" and new_name.endswith(".rollback-42"):
                    self.assertTrue(result)
                    lose_next_list = True
                    return False
                return result

            def lose_one_reconciliation_read():
                nonlocal lose_next_list
                if lose_next_list:
                    lose_next_list = False
                    raise OSError("lost reconciliation list response")
                return original_list()

            backend.rename_asset = persist_then_lose_response
            backend.list_assets = lose_one_reconciliation_read
            before = original_list()
            with self.assertRaisesRegex(PromotionError, "backed up"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.list_assets(), before)

    def test_lost_candidate_promotion_response_is_reconciled_by_asset_id(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            original_rename = backend.rename_asset

            def persist_then_lose_response(asset_id, old_name, new_name):
                result = original_rename(asset_id, old_name, new_name)
                if old_name == "cn_js_update_new.zip" and new_name == "cn_js_update.zip":
                    self.assertTrue(result)
                    return False
                return result

            backend.rename_asset = persist_then_lose_response
            promote_available_assets(backend, root, "42")
            self.assertEqual(backend.assets["cn_js_update.zip"]["data"], b"new-js-package")
            self.assertNotIn("cn_js_update_new.zip", backend.assets)

    def test_verify_failure_rolls_back_entire_prior_batch(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            backend.fail_verifies.add("cn_js_update_manifest.json")
            with self.assertRaisesRegex(PromotionError, "verification failed"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.assets["cn_js_update.zip"]["data"], b"old-zip")
            self.assertEqual(
                backend.assets["cn_js_update_manifest.json"]["data"], b"old-manifest"
            )
            self.assertIn("cn_js_update_new.zip", backend.assets)
            self.assertIn("cn_js_update_manifest_new.json", backend.assets)

    def test_version_last_failure_restores_shared_manifest_and_all_assets(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            backend.fail_verifies.add("version_js.json")
            with self.assertRaisesRegex(PromotionError, "verification failed"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.assets["cn_js_update.zip"]["data"], b"old-zip")
            self.assertEqual(
                backend.assets["cn_js_update_manifest.json"]["data"],
                b"old-manifest",
            )
            self.assertEqual(
                backend.assets["manifest.json"]["data"], b"old-chunk-manifest"
            )
            self.assertEqual(
                backend.assets["version_js.json"]["data"], b"old-version"
            )
            for name in (
                "cn_js_update_new.zip",
                "cn_js_update_manifest_new.json",
                "manifest_new.json",
                "version_js_new.json",
            ):
                self.assertIn(name, backend.assets)

    def test_lost_rollback_rename_responses_restore_original_batch(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            backend.fail_verifies.add("cn_js_update_manifest.json")
            original_rename = backend.rename_asset

            def persist_then_lose_rollback_response(asset_id, old_name, new_name):
                result = original_rename(asset_id, old_name, new_name)
                is_move_preview_back = old_name.endswith(".json") and new_name.endswith(
                    "_new.json"
                )
                is_restore_stable = ".rollback-42" in old_name
                if result and (is_move_preview_back or is_restore_stable):
                    return False
                return result

            backend.rename_asset = persist_then_lose_rollback_response
            with self.assertRaisesRegex(PromotionError, "verification failed"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.assets["cn_js_update.zip"]["data"], b"old-zip")
            self.assertEqual(
                backend.assets["cn_js_update_manifest.json"]["data"], b"old-manifest"
            )
            self.assertIn("cn_js_update_new.zip", backend.assets)
            self.assertIn("cn_js_update_manifest_new.json", backend.assets)
            self.assertFalse(any(".rollback-" in name for name in backend.assets))

    def test_backup_delete_failure_reports_but_keeps_new_stable(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            backend.fail_deletes.add("cn_js_update.zip.rollback-42")
            with self.assertRaisesRegex(PromotionError, "rollback cleanup failed"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.assets["cn_js_update.zip"]["data"], b"new-js-package")
            self.assertIn("cn_js_update.zip.rollback-42", backend.assets)

    def test_lost_cleanup_delete_response_is_reconciled(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            backend = backend_with_old_and_new(root)
            original_delete = backend.delete_asset

            def delete_then_lose_response(asset_id, name):
                result = original_delete(asset_id, name)
                if name.endswith(".rollback-42"):
                    self.assertTrue(result)
                    raise OSError("lost DELETE response")
                return result

            backend.delete_asset = delete_then_lose_response
            promote_available_assets(backend, root, "42")
            self.assertEqual(backend.assets["cn_js_update.zip"]["data"], b"new-js-package")
            self.assertFalse(any(".rollback-" in name for name in backend.assets))

    def test_incomplete_triplet_fails_before_any_rename(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "cn_js_update_new.zip").write_bytes(b"partial")
            backend = FakeBackend({"cn_js_update_new.zip": b"partial"})
            before = backend.list_assets()
            with self.assertRaisesRegex(PromotionError, "incomplete"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.list_assets(), before)

    def test_missing_shared_chunk_manifest_fails_before_any_rename(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            preview = make_js_triplet(root)
            del preview["manifest_new.json"]
            (root / "manifest_new.json").unlink()
            backend = FakeBackend(preview)
            before = backend.list_assets()
            with self.assertRaisesRegex(PromotionError, "chunk manifest is missing"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.list_assets(), before)

    def test_mismatched_shared_chunk_manifest_fails_before_any_rename(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            preview = make_js_triplet(root)
            bad = json.loads(preview["manifest_new.json"])
            bad["cn_js_update.zip"]["chunks"][0] = "0" * 32
            data = json.dumps(bad).encode()
            (root / "manifest_new.json").write_bytes(data)
            preview["manifest_new.json"] = data
            backend = FakeBackend(preview)
            before = backend.list_assets()
            with self.assertRaisesRegex(PromotionError, "does not match"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.list_assets(), before)

    def test_orphan_shared_chunk_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            data = b"{}"
            (root / "manifest_new.json").write_bytes(data)
            backend = FakeBackend({"manifest_new.json": data})
            before = backend.list_assets()
            with self.assertRaisesRegex(PromotionError, "without a package"):
                promote_available_assets(backend, root, "42")
            self.assertEqual(backend.list_assets(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
