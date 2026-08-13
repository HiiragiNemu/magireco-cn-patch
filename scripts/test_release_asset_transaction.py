#!/usr/bin/env python3
"""Failure-injection tests for downstream Release asset transactions."""

from __future__ import annotations

import hashlib
import unittest

from release_asset_transaction import (
    AssetExpectation,
    AssetTransactionError,
    replace_release_asset_set,
)


def expectation(data: bytes) -> AssetExpectation:
    return AssetExpectation(
        size=len(data),
        digest="sha256:" + hashlib.sha256(data).hexdigest(),
        source_url="memory://fixture",
    )


def source_expectation(data: bytes, source_url: str) -> AssetExpectation:
    expected = expectation(data)
    return AssetExpectation(expected.size, expected.digest, source_url)


class FakeBackend:
    def __init__(self, assets: dict[str, bytes], sources: dict[str, bytes]):
        self.assets: dict[str, dict] = {}
        self.next_id = 1
        for name, data in assets.items():
            self._add(name, data)
        self.sources = sources
        self.actions: list[tuple] = []
        self.fail_uploads: set[str] = set()
        self.fail_renames: set[tuple[str, str]] = set()
        self.fail_deletes: set[str] = set()
        self.fail_verifies: set[str] = set()

    def _add(self, name: str, data: bytes) -> None:
        self.assets[name] = {"id": self.next_id, "data": data}
        self.next_id += 1

    def _by_id(self, asset_id: int) -> str | None:
        return next(
            (name for name, asset in self.assets.items() if asset["id"] == asset_id),
            None,
        )

    def list_assets(self) -> dict[str, dict]:
        return {name: dict(asset) for name, asset in self.assets.items()}

    def upload_asset(self, name: str, expected: AssetExpectation) -> bool:
        self.actions.append(("upload", name))
        if name in self.fail_uploads or name in self.assets:
            return False
        self._add(name, self.sources[expected.source_url])
        return True

    def rename_asset(self, asset_id: int, old_name: str, new_name: str) -> bool:
        self.actions.append(("rename", old_name, new_name))
        if (old_name, new_name) in self.fail_renames:
            return False
        if self._by_id(asset_id) != old_name or new_name in self.assets:
            return False
        self.assets[new_name] = self.assets.pop(old_name)
        return True

    def delete_asset(self, asset_id: int, name: str) -> bool:
        self.actions.append(("delete", name))
        if name in self.fail_deletes or self._by_id(asset_id) != name:
            return False
        del self.assets[name]
        return True

    def verify_asset(self, name: str, expected: AssetExpectation) -> bool:
        self.actions.append(("verify", name))
        if name in self.fail_verifies or name not in self.assets:
            return False
        data = self.assets[name]["data"]
        return (
            len(data) == expected.size
            and "sha256:" + hashlib.sha256(data).hexdigest() == expected.digest
        )


class ReleaseAssetTransactionTest(unittest.TestCase):
    def make_backend(self) -> FakeBackend:
        return FakeBackend(
            {"a.zip": b"old-a", "b.json": b"old-b", "remove.txt": b"old-r"},
            {"memory://new-a": b"new-a", "memory://new-b": b"new-b"},
        )

    def changed(self) -> dict[str, AssetExpectation]:
        return {
            "a.zip": source_expectation(b"new-a", "memory://new-a"),
            "b.json": source_expectation(b"new-b", "memory://new-b"),
        }

    def test_success_replaces_batch_and_removes_only_after_verification(self):
        backend = self.make_backend()
        result = replace_release_asset_set(
            backend, self.changed(), ["remove.txt"], "42-1"
        )
        self.assertEqual(result, ["a.zip", "b.json"])
        self.assertEqual(backend.assets["a.zip"]["data"], b"new-a")
        self.assertEqual(backend.assets["b.json"]["data"], b"new-b")
        self.assertNotIn("remove.txt", backend.assets)
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))
        first_stable_rename = next(
            i for i, action in enumerate(backend.actions)
            if action[0] == "rename" and action[1] == "a.zip"
        )
        stage_verifies = [
            i for i, action in enumerate(backend.actions)
            if action[0] == "verify" and action[1].endswith("-incoming")
        ]
        self.assertTrue(stage_verifies)
        self.assertLess(max(stage_verifies), first_stable_rename)

    def test_second_staging_upload_failure_leaves_stable_set_unchanged(self):
        backend = self.make_backend()
        # Generated names are opaque hashes; fail the second upload by observing
        # its call instead of coupling this test to the hashing implementation.
        original_upload = backend.upload_asset
        calls = 0
        def fail_second(name, expected):
            nonlocal calls
            calls += 1
            return False if calls == 2 else original_upload(name, expected)
        backend.upload_asset = fail_second
        with self.assertRaisesRegex(AssetTransactionError, "staging upload failed"):
            replace_release_asset_set(backend, self.changed(), [], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"old-a")
        self.assertEqual(backend.assets["b.json"]["data"], b"old-b")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_ambiguous_upload_failure_cleans_server_side_temp_asset(self):
        backend = self.make_backend()
        original_upload = backend.upload_asset
        def persist_then_report_failure(name, expected):
            original_upload(name, expected)
            return False
        backend.upload_asset = persist_then_report_failure
        with self.assertRaisesRegex(AssetTransactionError, "staging upload failed"):
            replace_release_asset_set(backend, {"a.zip": self.changed()["a.zip"]}, [], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"old-a")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_promotion_failure_restores_old_stable_and_cleans_staging(self):
        backend = self.make_backend()
        original_rename = backend.rename_asset
        def fail_first_incoming(asset_id, old_name, new_name):
            if old_name.endswith("-incoming") and new_name == "a.zip":
                return False
            return original_rename(asset_id, old_name, new_name)
        backend.rename_asset = fail_first_incoming
        with self.assertRaisesRegex(AssetTransactionError, "cannot be promoted"):
            replace_release_asset_set(backend, self.changed(), [], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"old-a")
        self.assertEqual(backend.assets["b.json"]["data"], b"old-b")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_staging_verification_failure_never_moves_stable_names(self):
        backend = self.make_backend()
        original_verify = backend.verify_asset
        calls = 0
        def fail_first_verify(name, expected):
            nonlocal calls
            calls += 1
            return False if calls == 1 else original_verify(name, expected)
        backend.verify_asset = fail_first_verify
        with self.assertRaisesRegex(AssetTransactionError, "staging verification failed"):
            replace_release_asset_set(backend, self.changed(), [], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"old-a")
        self.assertEqual(backend.assets["b.json"]["data"], b"old-b")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_backup_rename_failure_never_removes_stable_asset(self):
        backend = self.make_backend()
        original_rename = backend.rename_asset
        def fail_backup(asset_id, old_name, new_name):
            if old_name == "a.zip" and new_name.endswith("-rollback"):
                return False
            return original_rename(asset_id, old_name, new_name)
        backend.rename_asset = fail_backup
        with self.assertRaisesRegex(AssetTransactionError, "cannot be backed up"):
            replace_release_asset_set(backend, self.changed(), [], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"old-a")
        self.assertEqual(backend.assets["b.json"]["data"], b"old-b")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_second_final_verify_failure_rolls_back_first_replacement(self):
        backend = self.make_backend()
        backend.fail_verifies.add("b.json")
        with self.assertRaisesRegex(AssetTransactionError, "verification failed"):
            replace_release_asset_set(backend, self.changed(), ["remove.txt"], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"old-a")
        self.assertEqual(backend.assets["b.json"]["data"], b"old-b")
        self.assertEqual(backend.assets["remove.txt"]["data"], b"old-r")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_unexpected_backend_exception_still_rolls_back_batch(self):
        backend = self.make_backend()
        original_verify = backend.verify_asset
        def raise_on_second_stable(name, expected):
            if name == "b.json":
                raise OSError("injected API outage")
            return original_verify(name, expected)
        backend.verify_asset = raise_on_second_stable
        with self.assertRaisesRegex(AssetTransactionError, "promotion backend error"):
            replace_release_asset_set(backend, self.changed(), [], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"old-a")
        self.assertEqual(backend.assets["b.json"]["data"], b"old-b")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_lost_rename_responses_are_reconciled_by_asset_id(self):
        backend = self.make_backend()
        original_rename = backend.rename_asset
        def persist_then_report_failure(asset_id, old_name, new_name):
            self.assertTrue(original_rename(asset_id, old_name, new_name))
            return False
        backend.rename_asset = persist_then_report_failure
        replace_release_asset_set(
            backend, {"a.zip": self.changed()["a.zip"]}, ["remove.txt"], "42-1"
        )
        self.assertEqual(backend.assets["a.zip"]["data"], b"new-a")
        self.assertNotIn("remove.txt", backend.assets)
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_lost_delete_response_is_reconciled_as_success(self):
        backend = self.make_backend()
        original_delete = backend.delete_asset
        def delete_then_report_failure(asset_id, name):
            self.assertTrue(original_delete(asset_id, name))
            return False
        backend.delete_asset = delete_then_report_failure
        replace_release_asset_set(
            backend, {"a.zip": self.changed()["a.zip"]}, [], "42-1"
        )
        self.assertEqual(backend.assets["a.zip"]["data"], b"new-a")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_delete_exception_after_persist_is_reconciled_as_success(self):
        backend = self.make_backend()
        original_delete = backend.delete_asset
        def delete_then_raise(asset_id, name):
            self.assertTrue(original_delete(asset_id, name))
            raise OSError("lost DELETE response")
        backend.delete_asset = delete_then_raise
        replace_release_asset_set(
            backend, {"a.zip": self.changed()["a.zip"]}, [], "42-1"
        )
        self.assertEqual(backend.assets["a.zip"]["data"], b"new-a")
        self.assertFalse(any(name.startswith("mirror-txn-") for name in backend.assets))

    def test_removal_rename_failure_rolls_back_all_changes(self):
        backend = self.make_backend()
        original_rename = backend.rename_asset
        def fail_removal(asset_id, old_name, new_name):
            if old_name == "remove.txt":
                return False
            return original_rename(asset_id, old_name, new_name)
        backend.rename_asset = fail_removal
        with self.assertRaisesRegex(AssetTransactionError, "retained for rollback"):
            replace_release_asset_set(backend, self.changed(), ["remove.txt"], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"old-a")
        self.assertEqual(backend.assets["b.json"]["data"], b"old-b")
        self.assertEqual(backend.assets["remove.txt"]["data"], b"old-r")

    def test_backup_cleanup_failure_keeps_new_stable_asset(self):
        backend = self.make_backend()
        original_delete = backend.delete_asset
        def fail_first_rollback(asset_id, name):
            if name.endswith("-rollback"):
                return False
            return original_delete(asset_id, name)
        backend.delete_asset = fail_first_rollback
        with self.assertRaisesRegex(AssetTransactionError, "rollback cleanup failed"):
            replace_release_asset_set(backend, {"a.zip": self.changed()["a.zip"]}, [], "42-1")
        self.assertEqual(backend.assets["a.zip"]["data"], b"new-a")
        self.assertTrue(any(name.endswith("-rollback") for name in backend.assets))

    def test_transaction_name_collision_fails_before_stable_mutation(self):
        backend = self.make_backend()
        changed = {"a.zip": self.changed()["a.zip"]}
        # Capture the deterministic incoming name from a successful dry backend
        # upload hook, then create a fresh backend containing that name.
        captured = []
        def capture_and_fail(name, expected):
            captured.append(name)
            return False
        backend.upload_asset = capture_and_fail
        with self.assertRaises(AssetTransactionError):
            replace_release_asset_set(backend, changed, [], "42-1")
        collision = self.make_backend()
        collision._add(captured[0], b"orphan")
        with self.assertRaisesRegex(AssetTransactionError, "already exists"):
            replace_release_asset_set(collision, changed, [], "42-1")
        self.assertEqual(collision.assets["a.zip"]["data"], b"old-a")


if __name__ == "__main__":
    unittest.main(verbosity=2)
