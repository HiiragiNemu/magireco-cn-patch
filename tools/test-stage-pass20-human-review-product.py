#!/usr/bin/env python3
"""Focused regressions for Pass20 final-value staging."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"

def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

STAGE = load("pass20_stage_tested", ROOT / "tools/stage-pass20-human-review-product.py")

class FinalValueStageTests(unittest.TestCase):
    def test_01_header_only_final_values_keep_stage_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            final_values = root / "header-only.tsv"
            final_values.write_text(
                (AUDIT / "pass20_human_final_values.tsv").read_text(
                    encoding="utf-8"
                ).splitlines()[0] + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(STAGE.StageError, "release gate is closed"):
                STAGE.stage(
                    AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                    final_values,
                    AUDIT / "pass20_authority_resolutions.tsv",
                    AUDIT / "pass20_product_targets.json",
                    root / "stage",
                    AUDIT / "magireco_v26_translation_review_1565.xlsx",
                )

    def test_02_reviewed_candidate_provenance_is_derived_from_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "reviewed.tsv"
            path.write_text("# " + "\t".join(STAGE.REVIEWED_COLUMNS) + "\n", encoding="utf-8")
            queue = {
                "CUR": {"japanese_or_source_original": "源一", "current_cn": "旧一"},
                "SUG": {"japanese_or_source_original": "源二", "current_cn": "旧二"},
                "HUM": {"japanese_or_source_original": "源三", "current_cn": "旧三"},
            }
            target = {
                key: {"maintenance_scope": "global", "path_prefix": "", "match_status": "fixture"}
                for key in queue
            }
            receipts = [
                {"item_id": "CUR", "final_value": "旧一", "final_origin": "machine-current", "machine_translated": "unknown", "review_status": "human-confirmed-machine-origin-retained"},
                {"item_id": "SUG", "final_value": "建议二", "final_origin": "machine-suggestion", "machine_translated": "true", "review_status": "human-confirmed-machine-suggestion-adopted"},
                {"item_id": "HUM", "final_value": "人工三", "final_origin": "human-revision", "machine_translated": "false", "review_status": "human-revised"},
            ]
            self.assertEqual(STAGE.append_reviewed_candidates(path, queue, receipts, target, set(queue)), 3)
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
            rows = list(csv.DictReader(lines, fieldnames=STAGE.REVIEWED_COLUMNS, delimiter="\t"))
        by_id = {row["source_locator"].rsplit(":", 1)[1]: row for row in rows}
        self.assertEqual(by_id["CUR"]["machine_translated"], "unknown")
        self.assertEqual(by_id["SUG"]["machine_translated"], "true")
        self.assertEqual(by_id["HUM"]["machine_translated"], "false")
        self.assertNotIn("reviewer=", by_id["HUM"]["evidence"])
        self.assertNotIn("timestamp=", by_id["HUM"]["evidence"])

    def test_03_preapplied_pass21_runtime_baseline_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "js").mkdir()
            (root / "js/fixture.js").write_text('const a="已采纳"; const b="已采纳";\n', encoding="utf-8")
            targets = {"A": {"maintenance_scope": "global", "occurrences": [{"path": "js/fixture.js"}, {"path": "js/fixture.js"}]}}
            adoptions = {"A": {"runtime_strategy": "target-manifest-exact", "adopted_cn": "已采纳", "runtime_rewrites_parsed": []}}
            self.assertEqual(
                STAGE.verify_pass21_runtime_baselines(root, targets, adoptions),
                {"items": 1, "paths": 1, "occurrences": 2},
            )
            (root / "js/fixture.js").write_text('const a="旧值";\n', encoding="utf-8")
            with self.assertRaisesRegex(STAGE.StageError, "not materialized"):
                STAGE.verify_pass21_runtime_baselines(root, targets, adoptions)

    def test_04_explicit_and_canonical_only_adoptions_are_distinguished(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "js").mkdir()
            (root / "js/fixture.js").write_text('const a="新值"; const b="新值";\n', encoding="utf-8")
            targets = {
                "E": {"maintenance_scope": "global", "occurrences": []},
                "C": {"maintenance_scope": "global", "occurrences": []},
            }
            adoptions = {
                "E": {"runtime_strategy": "explicit-safe-paths", "adopted_cn": "新值", "runtime_rewrites_parsed": [{"path": "js/fixture.js", "expected_count": 2}]},
                "C": {"runtime_strategy": "canonical-only", "adopted_cn": "仅维护", "runtime_rewrites_parsed": []},
            }
            result = STAGE.verify_pass21_runtime_baselines(root, targets, adoptions)
        self.assertEqual(result, {"items": 1, "paths": 1, "occurrences": 2})

    def test_05_target_contract_remains_frozen_at_1565(self):
        payload = json.loads((AUDIT / "pass20_product_targets.json").read_text(encoding="utf-8"))
        contract = STAGE.derive_target_contract(payload["items"], payload["summary"])
        self.assertEqual(contract["materialization_items"], 1565)
        self.assertEqual(contract["exact_runtime_items"], 1443)
        self.assertEqual(contract["maintenance_only_items"], 122)

    def test_06_rough_production_candidate_stays_low_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "reviewed.tsv"
            path.write_text("# " + "\t".join(STAGE.REVIEWED_COLUMNS) + "\n", encoding="utf-8")
            queue = {"ROUGH": {"japanese_or_source_original": "源", "current_cn": "粗译"}}
            targets = {
                "ROUGH": {
                    "maintenance_scope": "global", "path_prefix": "", "match_status": "fixture",
                }
            }
            receipts = [{
                "item_id": "ROUGH", "final_value": "粗译", "final_origin": "machine-current",
                "machine_translated": "unknown",
                "review_status": "rough-production-machine-current-retained",
            }]
            self.assertEqual(
                STAGE.append_reviewed_candidates(path, queue, receipts, targets, {"ROUGH"}), 1,
            )
            lines = [
                line for line in path.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")
            ]
            row = next(csv.DictReader(lines, fieldnames=STAGE.REVIEWED_COLUMNS, delimiter="\t"))
        self.assertEqual(row["authority"], "new_proposal")
        self.assertEqual(row["source_batch"], "pass20-rough-production-final-values-v1")
        self.assertEqual(row["confidence"], "user-directed-rough-production-unreviewed")
        self.assertNotIn("human", row["review_status"])
        self.assertNotIn("human", row["match_method"])

    def test_07_human_review_can_follow_existing_rough_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "reviewed.tsv"
            path.write_text("# " + "\t".join(STAGE.REVIEWED_COLUMNS) + "\n", encoding="utf-8")
            queue = {"ITEM": {"japanese_or_source_original": "源", "current_cn": "粗译"}}
            targets = {
                "ITEM": {
                    "maintenance_scope": "global", "path_prefix": "", "match_status": "fixture",
                }
            }
            rough = [{
                "item_id": "ITEM", "final_value": "粗译", "final_origin": "machine-current",
                "machine_translated": "unknown",
                "review_status": "rough-production-machine-current-retained",
            }]
            human = [{
                "item_id": "ITEM", "final_value": "人工精修", "final_origin": "human-revision",
                "machine_translated": "false", "review_status": "human-revised",
            }]
            STAGE.append_reviewed_candidates(path, queue, rough, targets, {"ITEM"})
            STAGE.append_reviewed_candidates(path, queue, human, targets, {"ITEM"})
            lines = [
                line for line in path.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")
            ]
            rows = list(csv.DictReader(lines, fieldnames=STAGE.REVIEWED_COLUMNS, delimiter="\t"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["source_locator"].rsplit("#", 1)[1] for row in rows},
            {"rough-production:ITEM", "human-review:ITEM"},
        )
        self.assertEqual({row["authority"] for row in rows}, {"new_proposal", "existing_human_reviewed"})

    def test_08_review_contract_is_rebound_to_staged_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            contract_path = stage / STAGE.REVIEW_CONTRACT_REL
            contract_path.parent.mkdir(parents=True)
            contract_path.write_bytes((ROOT / STAGE.REVIEW_CONTRACT_REL).read_bytes())
            generated = stage / "i18n/generated"
            generated.mkdir(parents=True)
            generated.joinpath("input-provenance.tsv").write_bytes(
                (ROOT / "i18n/generated/input-provenance.tsv").read_bytes() + b"# rough\n"
            )
            generated.joinpath("effective.tsv").write_bytes(
                (ROOT / "i18n/generated/effective.tsv").read_bytes()
            )
            STAGE.refresh_review_contract(
                stage,
                AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                AUDIT / "pass20_authority_resolutions.tsv",
                "rough-production",
            )
            refreshed = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(
            refreshed["post_final_value_materialization"]["provenance_mode"],
            "rough-production",
        )
        self.assertTrue(
            refreshed["post_final_value_materialization"]["machine_provenance_retained"]
        )
        self.assertNotEqual(
            refreshed["source_sha256"]["input_provenance"],
            json.loads((ROOT / STAGE.REVIEW_CONTRACT_REL).read_text(encoding="utf-8"))[
                "source_sha256"
            ]["input_provenance"],
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)
