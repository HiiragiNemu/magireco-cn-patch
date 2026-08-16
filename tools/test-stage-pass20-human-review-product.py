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
            with self.assertRaisesRegex(STAGE.StageError, "release gate is closed"):
                STAGE.stage(
                    AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                    AUDIT / "pass20_human_final_values.tsv",
                    AUDIT / "pass20_authority_resolutions.tsv",
                    AUDIT / "pass20_product_targets.json",
                    Path(temp) / "stage",
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
        by_id = {row["source_locator"].rsplit("#", 1)[1]: row for row in rows}
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

if __name__ == "__main__":
    unittest.main(verbosity=2)
