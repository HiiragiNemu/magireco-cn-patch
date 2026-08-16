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
    def fixture(self, provenance_mode: str = "human-review"):
        temp = tempfile.TemporaryDirectory(prefix="pass20-promote-test-")
        base = Path(temp.name)
        repo = base / "repo"
        stage = base / "stage"
        records = []
        if provenance_mode == "human-review":
            review_status = "human-confirmed-machine-origin-retained"
            authority = "existing_human_reviewed"
            source_batch = "pass20-human-final-values-v1"
            canonical_human = 3
            canonical_rough = 0
        elif provenance_mode == "rough-production":
            review_status = "rough-production-machine-current-retained"
            authority = "new_proposal"
            source_batch = "pass20-rough-production-final-values-v1"
            canonical_human = 0
            canonical_rough = 3
        else:
            raise AssertionError(f"unsupported fixture provenance: {provenance_mode}")
        final_rows = []
        candidate_rows = []
        target_rows = []
        for number in range(1, 4):
            item_id = f"LOW-MT-{number:05d}"
            source_text = f"source-{number}"
            final_value = f"candidate-{number}"
            target = {
                "item_id": item_id,
                "maintenance_scope": "global",
                "maintenance_table": "i18n/frontend-strings.tsv",
                "path_prefix": "",
                "source_key": f"fixture-{number}",
                "source_text": source_text,
                "stable_business_key": f"fixture#{number}/candidate_cn",
                "match_status": "exact-current-runtime-literal",
            }
            target_rows.append(target)
            final_row = {
                field: "" for field in PROMOTE.FINAL_VALUE_FIELDS
            }
            final_row.update({
                "item_id": item_id,
                "stable_business_key": f"fixture#{number}/candidate_cn",
                "source_path": "i18n/frontend-strings.tsv",
                "source_key": f"fixture-{number}",
                "source_field": "candidate_cn",
                "japanese_or_source_original": source_text,
                "seed_cn": final_value,
                "seed_origin": "current",
                "current_cn": final_value,
                "final_value": final_value,
                "source_record_sha256": str(number) * 64,
                "target_contract_sha256": PROMOTE._canonical_json_digest(target),
                "review_status": review_status,
                "final_origin": "machine-current",
                "machine_translated": "unknown",
            })
            final_rows.append(final_row)
            candidate_row = {field: "" for field in PROMOTE.REVIEWED_COLUMNS}
            candidate_row.update({
                "scope": "global",
                "source_text": source_text,
                "candidate_cn": final_value,
                "status": "present",
                "authority": authority,
                "source_batch": source_batch,
                "source_locator": f"{PROMOTE.FINAL_VALUE_LOCATOR_BASE}{provenance_mode}:{item_id}",
                "match_method": (
                    "exact-semantic-key-human-review"
                    if provenance_mode == "human-review"
                    else "exact-semantic-key-user-directed-rough-production"
                ),
                "machine_translated": "unknown",
                "confidence": (
                    "human-approved"
                    if provenance_mode == "human-review"
                    else "user-directed-rough-production-unreviewed"
                ),
                "review_status": review_status,
                "evidence": (
                    f"item_id={item_id}; final_origin=machine-current; "
                    f"provenance_mode={provenance_mode}; "
                    "target_status=exact-current-runtime-literal"
                ),
            })
            candidate_rows.append(candidate_row)
        final_values_after = (
            "\t".join(PROMOTE.FINAL_VALUE_FIELDS) + "\n"
            + "".join(
                "\t".join(row[field] for field in PROMOTE.FINAL_VALUE_FIELDS) + "\n"
                for row in final_rows
            )
        ).encode("utf-8")
        candidates_after = (
            "# " + "\t".join(PROMOTE.REVIEWED_COLUMNS) + "\n"
            + "".join(
                "\t".join(row[field] for field in PROMOTE.REVIEWED_COLUMNS) + "\n"
                for row in candidate_rows
            )
        ).encode("utf-8")
        materialized_contract_after = (
            json.dumps({
                "schema": "magireco-cn-pass20-review-contract/2",
                "status": "PASS",
                "post_final_value_materialization": {
                    "items": 3,
                    "provenance_mode": provenance_mode,
                    "queue_and_targets_frozen": True,
                    "machine_provenance_retained": provenance_mode == "rough-production",
                },
            }, sort_keys=True) + "\n"
        ).encode("utf-8")
        files = {
            "magica/template/fixture.html": (b"<p>old</p>\n", b"<p>new</p>\n", "runtime-product"),
            "i18n/reviewed-candidates.tsv": (b"old-candidate\n", candidates_after, "canonical-i18n"),
            "magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv": (
                b"blank-final-values\n", final_values_after, "human-final-values-audit",
            ),
            "magica/i18n_audit/release_v26_authority/pass20_review_contract.json": (
                b"old-review-contract\n", materialized_contract_after, "review-contract-audit",
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
        target_manifest = (
            json.dumps({
                "schema": "magireco-cn-pass20-product-target-manifest/1",
                "status": "PASS",
                "items": target_rows,
            }, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")
        contract_sources = {
            "magica/i18n_audit/release_v26_authority/pass20_remaining_manual_review.tsv": b"queue\n",
            "magica/i18n_audit/release_v26_authority/pass20_product_targets.json": target_manifest,
            "magica/i18n_audit/release_v26_authority/pass20_authority_shadowed_machine_items.json": b"{}\n",
            "magica/i18n_audit/release_v26_authority/pass20_authority_resolutions.tsv": b"resolutions\n",
        }
        for rel, data in contract_sources.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        review_contract = {
            "provenance_mode": provenance_mode,
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
            "final_values_receipt_sha256": PROMOTE.digest(final_values_after),
            "reviewed_candidates_sha256": PROMOTE.digest(candidates_after),
            "materialized_review_contract_sha256": PROMOTE.digest(materialized_contract_after),
        }
        report = {
            "schema": "magireco-cn-pass20-product-staging/1",
            "status": "PASS",
            "repository_product_writes": 0,
            "protected_text_changes": 0,
            "review_contract": review_contract,
            "machine_inventory_items": 4,
            "human_review_items": 3,
            "provenance_mode": provenance_mode,
            "canonical_human_review_items": canonical_human,
            "canonical_rough_production_items": canonical_rough,
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

    @staticmethod
    def rebind_staged_file(stage: Path, rel: str, data: bytes, contract_field: str) -> None:
        """Simulate internally rehashed, but semantically inconsistent, staged content."""
        (stage / rel).write_bytes(data)
        (stage / "rollback/after" / rel).write_bytes(data)
        manifest_path = stage / "rollback/rollback.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        record = next(item for item in manifest["files"] if item["path"] == rel)
        record["after_sha256"] = PROMOTE.digest(data)
        record["after_size"] = len(data)
        manifest["review_contract"][contract_field] = PROMOTE.digest(data)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        report_path = stage / "staging_verification.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["review_contract"][contract_field] = PROMOTE.digest(data)
        report_path.write_text(json.dumps(report), encoding="utf-8")

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

    def test_13_report_only_provenance_tamper_rejects_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        report_path = stage / "staging_verification.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["provenance_mode"] = "rough-production"
        report["canonical_human_review_items"] = 0
        report["canonical_rough_production_items"] = 3
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(
            PROMOTE.PromotionError, "provenance mode differs from its rollback contract",
        ):
            self.run_promote(repo, stage, FakeProtection())
        for rel, (before, _after, _role) in files.items():
            self.assertEqual((repo / rel).read_bytes(), before)

    def test_14_rough_production_accepts_identical_preexisting_workbook_receipt(self):
        temp, repo, stage, files = self.fixture("rough-production")
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

    def test_15_rehashed_candidate_semantic_drift_rejects_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        rel = "i18n/reviewed-candidates.tsv"
        tampered = (stage / rel).read_bytes().replace(b"candidate-1", b"tampered-1", 1)
        self.rebind_staged_file(stage, rel, tampered, "reviewed_candidates_sha256")
        with self.assertRaisesRegex(
            PROMOTE.PromotionError, "reviewed candidate differs from its final-value receipt",
        ):
            self.run_promote(repo, stage, FakeProtection())
        for path, (before, _after, _role) in files.items():
            self.assertEqual((repo / path).read_bytes(), before)

    def test_16_rehashed_materialized_contract_mode_drift_rejects_without_writes(self):
        temp, repo, stage, files = self.fixture()
        self.addCleanup(temp.cleanup)
        rel = "magica/i18n_audit/release_v26_authority/pass20_review_contract.json"
        payload = json.loads((stage / rel).read_text(encoding="utf-8"))
        post = payload["post_final_value_materialization"]
        post["provenance_mode"] = "rough-production"
        post["machine_provenance_retained"] = True
        tampered = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        self.rebind_staged_file(
            stage, rel, tampered, "materialized_review_contract_sha256",
        )
        with self.assertRaisesRegex(
            PROMOTE.PromotionError, "materialized review contract provenance drifted",
        ):
            self.run_promote(repo, stage, FakeProtection())
        for path, (before, _after, _role) in files.items():
            self.assertEqual((repo / path).read_bytes(), before)

    def test_17_rehashed_low_tier_human_label_rejects_without_writes(self):
        temp, repo, stage, files = self.fixture("rough-production")
        self.addCleanup(temp.cleanup)
        rel = "i18n/reviewed-candidates.tsv"
        tampered = (stage / rel).read_bytes().replace(
            b"exact-semantic-key-user-directed-rough-production",
            b"exact-semantic-key-human-review",
        ).replace(
            b"user-directed-rough-production-unreviewed", b"human-approved",
        )
        self.rebind_staged_file(stage, rel, tampered, "reviewed_candidates_sha256")
        with self.assertRaisesRegex(
            PROMOTE.PromotionError, "reviewed candidate differs from its final-value receipt",
        ):
            self.run_promote(repo, stage, FakeProtection())
        for path, (before, _after, _role) in files.items():
            self.assertEqual((repo / path).read_bytes(), before)

    def test_18_rehashed_rough_user_origin_rejects_without_writes(self):
        temp, repo, stage, files = self.fixture("rough-production")
        self.addCleanup(temp.cleanup)
        receipt_rel = (
            "magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv"
        )
        receipt = (stage / receipt_rel).read_bytes().replace(
            b"rough-production-machine-current-retained\tmachine-current\tunknown",
            b"rough-production-user-edited-retained\tuser-edited\tunknown",
        )
        self.rebind_staged_file(
            stage, receipt_rel, receipt, "final_values_receipt_sha256",
        )
        candidate_rel = "i18n/reviewed-candidates.tsv"
        candidate = (stage / candidate_rel).read_bytes().replace(
            b"rough-production-machine-current-retained\t",
            b"rough-production-user-edited-retained\t",
        ).replace(
            b"final_origin=machine-current", b"final_origin=user-edited",
        )
        self.rebind_staged_file(
            stage, candidate_rel, candidate, "reviewed_candidates_sha256",
        )
        with self.assertRaisesRegex(
            PROMOTE.PromotionError, "receipt origin is invalid for its mode",
        ):
            self.run_promote(repo, stage, FakeProtection())
        for path, (before, _after, _role) in files.items():
            self.assertEqual((repo / path).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
