#!/usr/bin/env python3
"""Focused promotion tests for the Pass20 repository write boundary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROMOTE = load_module("pass20_promote_tested", ROOT / "tools/promote-pass20-product-stage.py")
ROLLBACK = load_module("pass20_rollback_for_promote", ROOT / "tools/rollback-pass20-product-stage.py")


class FakeProtection:
    def __init__(self, fail_on_verify: int | None = None):
        self.calls = 0
        self.fail_on_verify = fail_on_verify

    @staticmethod
    def read_tsv(_path: Path):
        return [{"fixture": "protected"}]

    @staticmethod
    def validate_row_hashes(_rows):
        return None

    def verify_current_product_values(self, _root: Path, _rows):
        self.calls += 1
        if self.fail_on_verify == self.calls:
            raise ValueError("synthetic post-write protection failure")


class Pass20PromotionTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="pass20-promote-test-")
        base = Path(temp.name)
        repo = base / "repo"
        stage = base / "stage"
        records = []
        files = {
            "magica/template/fixture.html": (b"<p>old</p>\n", b"<p>new</p>\n", "runtime-product"),
            "i18n/reviewed-candidates.tsv": (b"old-candidate\n", b"new-candidate\n", "canonical-i18n"),
            "magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv": (
                b"blank-final-values\n", b"completed-final-values\n", "human-final-values-audit",
            ),
            "magica/i18n_audit/release_v26_authority/pass20_review_contract.json": (
                b"old-review-contract\n", b"new-review-contract\n", "review-contract-audit",
            ),
            "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx": (
                b"blank-workbook", b"completed-workbook", "human-review-workbook-receipt",
            ),
        }
        for rel, (before, after, role) in files.items():
            repo_path = repo / rel
            staged_path = stage / rel
            before_path = stage / "rollback/before" / rel
            after_path = stage / "rollback/after" / rel
            for path, data in (
                (repo_path, before), (staged_path, after),
                (before_path, before), (after_path, after),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            records.append({
                "path": rel,
                "role": role,
                "before_snapshot": f"rollback/before/{rel}",
                "after_snapshot": f"rollback/after/{rel}",
                "before_sha256": PROMOTE.digest(before),
                "after_sha256": PROMOTE.digest(after),
                "before_size": len(before),
                "after_size": len(after),
            })
        contract_sources = {
            "magica/i18n_audit/release_v26_authority/pass20_remaining_manual_review.tsv": b"queue\n",
            "magica/i18n_audit/release_v26_authority/pass20_product_targets.json": b"{}\n",
            "magica/i18n_audit/release_v26_authority/pass20_authority_shadowed_machine_items.json": b"{}\n",
            "magica/i18n_audit/release_v26_authority/pass20_authority_resolutions.tsv": b"resolutions\n",
        }
        for rel, data in contract_sources.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        review_contract = {
            "machine_inventory_items": 4,
            "human_review_items": 3,
            "materialization_items": 3,
            "higher_authority_shadowed_items": 1,
            "product_write_forbidden_items": 1,
            "authority_resolution_items": 2,
            "exact_runtime_items": 2,
            "maintenance_only_items": 1,
            "runtime_occurrences": 2,
            "global_items": 3,
            "override_items": 0,
            "fragment_items": 0,
            "shadowed_low_tier_candidates_written": 0,
            "shadowed_product_writes": 0,
            "source_records_sha256": PROMOTE.digest(contract_sources[
                "magica/i18n_audit/release_v26_authority/pass20_remaining_manual_review.tsv"
            ]),
            "target_contract_sha256": PROMOTE.digest(contract_sources[
                "magica/i18n_audit/release_v26_authority/pass20_product_targets.json"
            ]),
            "authority_shadow_manifest_sha256": PROMOTE.digest(contract_sources[
                "magica/i18n_audit/release_v26_authority/pass20_authority_shadowed_machine_items.json"
            ]),
            "authority_resolutions_sha256": PROMOTE.digest(contract_sources[
                "magica/i18n_audit/release_v26_authority/pass20_authority_resolutions.tsv"
            ]),
        }
        report = {
            "schema": "magireco-cn-pass20-product-staging/1",
            "status": "PASS",
            "repository_product_writes": 0,
            "protected_text_changes": 0,
            "review_contract": review_contract,
            "machine_inventory_items": 4,
            "human_review_items": 3,
            "provenance_mode": "human-review",
            "canonical_human_review_items": 3,
            "canonical_rough_production_items": 0,
            "reviewed_candidates_appended": 3,
            "higher_authority_shadowed_items": 1,
            "product_write_forbidden_items": 1,
            "exact_target_items": 2,
            "maintenance_only_items_persisted": 1,
            "runtime_occurrences_bound": 2,
            "shadowed_low_tier_candidates_written": 0,
            "shadowed_product_writes": 0,
            "human_gate": {"release_gate_open": True, "final_values_required": 3},
            "rollback_rehearsal": {"status": "PASS", "relocated_stage_copy": True},
            "repository_promotion_files": sorted(files),
            "changed_files": ["magica/template/fixture.html"],
            "canonical_changed_files": sorted(
                rel for rel, (_before, _after, role) in files.items()
                if role != "runtime-product"
            ),
            "human_review_workbook_receipt": "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx",
        }
        (stage / "staging_verification.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        manifest = {
            "schema": "magireco-cn-pass20-product-rollback/1",
            "review_contract": review_contract,
            "files": records,
        }
        (stage / "rollback/rollback.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return temp, repo, stage, files

    def run_promote(
        self, repo: Path, stage: Path, protection: FakeProtection,
        report_path: Path | None = None,
    ):
        with (
            mock.patch.object(PROMOTE, "load_module", side_effect=[ROLLBACK, protection]),
            mock.patch.object(PROMOTE.shutil, "which", return_value="node"),
            mock.patch.object(PROMOTE, "run_node_checks", return_value=0),
        ):
            return PROMOTE.promote(stage, repo, report_path)

    def test_01_success_promotes_exact_runtime_and_canonical_files(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        result = self.run_promote(repo, stage, FakeProtection())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["canonical_human_review_items"], 3)
        for rel, (_before, after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), after)

    def test_02_repository_before_drift_rejects_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        drifted = repo / "magica/template/fixture.html"
        drifted.write_bytes(b"unexpected\n")
        with self.assertRaisesRegex(PROMOTE.PromotionError, "repository before gate failed"):
            self.run_promote(repo, stage, FakeProtection())
        self.assertEqual(drifted.read_bytes(), b"unexpected\n")
        self.assertEqual(
            (repo / "i18n/reviewed-candidates.tsv").read_bytes(),
            files["i18n/reviewed-candidates.tsv"][0],
        )

    def test_03_staged_after_drift_rejects_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        (stage / "magica/template/fixture.html").write_bytes(b"unexpected\n")
        with self.assertRaisesRegex(PROMOTE.PromotionError, "staged after gate failed"):
            self.run_promote(repo, stage, FakeProtection())
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_04_duplicate_manifest_path_is_rejected(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        manifest_path = stage / "rollback/rollback.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].append(dict(manifest["files"][0]))
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(PROMOTE.PromotionError, "duplicate paths"):
            self.run_promote(repo, stage, FakeProtection())
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_05_post_write_failure_restores_every_file(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        # Calls 1-2 are the repository/staging preflight.  Call 3 occurs only
        # after every candidate file has been replaced in the repository.
        with self.assertRaisesRegex(PROMOTE.PromotionError, "changed files were restored"):
            self.run_promote(repo, stage, FakeProtection(fail_on_verify=3))
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_06_mid_write_failure_restores_every_already_replaced_file(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        real_replace = PROMOTE.atomic_replace
        calls = 0

        def fail_second(source: Path, target: Path):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic second replace failure")
            return real_replace(source, target)

        with (
            mock.patch.object(PROMOTE, "atomic_replace", side_effect=fail_second),
            self.assertRaisesRegex(PROMOTE.PromotionError, "changed files were restored"),
        ):
            self.run_promote(repo, stage, FakeProtection())
        self.assertEqual(calls, 2)
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_07_backslash_traversal_path_is_rejected_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        manifest_path = stage / "rollback/rollback.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        malicious = "magica/..\\outside.txt"
        manifest["files"][0]["path"] = malicious
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report_path = stage / "staging_verification.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["repository_promotion_files"] = sorted([
            malicious,
            "i18n/reviewed-candidates.tsv",
            "magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv",
            "magica/i18n_audit/release_v26_authority/pass20_review_contract.json",
            "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx",
        ])
        report["changed_files"] = [malicious]
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(PROMOTE.PromotionError, "role/path contract mismatch|unsafe promotion path contract"):
            self.run_promote(repo, stage, FakeProtection())
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_08_unknown_role_is_rejected_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        manifest_path = stage / "rollback/rollback.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["role"] = "unknown-role"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(PROMOTE.PromotionError, "unknown promotion roles"):
            self.run_promote(repo, stage, FakeProtection())
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_09_cli_requires_explicit_repository_write_acknowledgement(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(PROMOTE.main(["--stage-root", "unused"]), 2)

    def test_10_mislabeled_role_path_is_rejected_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        manifest_path = stage / "rollback/rollback.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["role"] = "canonical-i18n"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(PROMOTE.PromotionError, "role/path contract mismatch"):
            self.run_promote(repo, stage, FakeProtection())
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_11_report_write_failure_restores_every_promoted_file(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        report_path = stage / "reports/promotion.json"
        real_replace = Path.replace

        def fail_report(source: Path, target: Path):
            if Path(target) == report_path:
                raise OSError("synthetic report write failure")
            return real_replace(source, target)

        with (
            mock.patch.object(Path, "replace", new=fail_report),
            self.assertRaisesRegex(PROMOTE.PromotionError, "changed files were restored"),
        ):
            self.run_promote(repo, stage, FakeProtection(), report_path)
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_12_target_contract_hash_drift_rejects_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        (repo / "magica/i18n_audit/release_v26_authority/pass20_product_targets.json").write_bytes(
            b'{"drift":true}\n'
        )
        with self.assertRaisesRegex(PROMOTE.PromotionError, "target_contract_sha256 gate failed"):
            self.run_promote(repo, stage, FakeProtection())
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_13_rough_production_promotes_without_human_review_claim(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        report_path = stage / "staging_verification.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["provenance_mode"] = "rough-production"
        report["canonical_human_review_items"] = 0
        report["canonical_rough_production_items"] = 3
        report_path.write_text(json.dumps(report), encoding="utf-8")
        result = self.run_promote(repo, stage, FakeProtection())
        self.assertEqual(result["provenance_mode"], "rough-production")
        self.assertEqual(result["canonical_human_review_items"], 0)
        self.assertEqual(result["canonical_rough_production_items"], 3)
        for rel, (_before, after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), after)

    def test_14_rough_production_accepts_identical_preexisting_workbook_receipt(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        workbook = (
            "magica/i18n_audit/release_v26_authority/"
            "magireco_v26_translation_review_1565.xlsx"
        )
        _before, workbook_after, _role = files[workbook]
        (repo / workbook).write_bytes(workbook_after)

        manifest_path = stage / "rollback/rollback.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"] = [
            record for record in manifest["files"] if record["path"] != workbook
        ]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        report_path = stage / "staging_verification.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["provenance_mode"] = "rough-production"
        report["canonical_human_review_items"] = 0
        report["canonical_rough_production_items"] = 3
        report["repository_promotion_files"].remove(workbook)
        report["canonical_changed_files"].remove(workbook)
        report_path.write_text(json.dumps(report), encoding="utf-8")

        result = self.run_promote(repo, stage, FakeProtection())
        self.assertTrue(result["workbook_receipt_preexisting_identical"])
        self.assertNotIn(workbook, result["promoted_files"])
        self.assertEqual((repo / workbook).read_bytes(), workbook_after)
        for rel, (_before, after, _role) in files.items():
            if rel != workbook:
                self.assertEqual((repo / rel).read_bytes(), after)


if __name__ == "__main__":
    unittest.main()
