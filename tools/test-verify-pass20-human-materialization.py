#!/usr/bin/env python3
"""Focused regressions for Pass20 final-value materialization verification."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = Path(__file__).resolve().parents[1]

def load_tool():
    path = ROOT / "tools/verify-pass20-human-materialization.py"
    spec = importlib.util.spec_from_file_location("pass20_materialization_tested", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

TOOL = load_tool()

class Pass20MaterializationTests(unittest.TestCase):
    def test_01_current_repository_is_explicitly_closed(self):
        result = TOOL.verify(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["release_gate_open"])
        self.assertFalse(result["materialization_verified"])
        self.assertEqual(result["pending"], 1565)
        self.assertEqual(result["protected_text_changes"], 0)

    def test_02_release_flag_follows_current_final_value_gate(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(TOOL.main(["--repo-root", str(ROOT), "--require-release-open"]), 3)

    def test_03_completed_workbook_receipt_has_no_decision_metadata(self):
        complete = {
            "status": "PASS", "returned_workbook_accepted": True,
            "receipt_rows_written": 2, "pending_in_workbook": 0,
        }
        TOOL.validate_workbook_receipt(complete, b"same", b"same", expected_items=2)
        for bad in (
            {**complete, "returned_workbook_accepted": False},
            {**complete, "receipt_rows_written": 1, "pending_in_workbook": 1},
        ):
            with self.assertRaises(TOOL.MaterializationError):
                TOOL.validate_workbook_receipt(bad, b"same", b"same", expected_items=2)
        with self.assertRaisesRegex(TOOL.MaterializationError, "does not reproduce"):
            TOOL.validate_workbook_receipt(complete, b"new", b"old", expected_items=2)

    def binding_fixture(self, root: Path):
        original = 'const first="旧一";const second="旧二";\n'
        after = 'const first="建议一";const second="人工二";\n'
        product = root / "magica/js/fixture.js"
        product.parent.mkdir(parents=True, exist_ok=True)
        product.write_text(after, encoding="utf-8", newline="\n")
        queue = [
            {"item_id": "ITEM-1", "japanese_or_source_original": "源一", "current_cn": "旧一"},
            {"item_id": "ITEM-2", "japanese_or_source_original": "源二", "current_cn": "旧二"},
        ]
        final_values = [
            {"item_id": "ITEM-1", "final_value": "建议一", "review_status": "human-confirmed-machine-suggestion-adopted", "machine_translated": "true"},
            {"item_id": "ITEM-2", "final_value": "人工二", "review_status": "human-revised", "machine_translated": "false"},
        ]
        def target(item_id, key, current, start):
            return {
                "item_id": item_id, "semantic_key": key, "maintenance_scope": "global",
                "path_prefix": "", "current_cn": current, "application_allowed": True,
                "product_target_paths": ["js/fixture.js"],
                "occurrences": [{"path": "js/fixture.js", "start": start, "end": start + len(current)}],
            }
        targets = [target("ITEM-1", "global:one", "旧一", original.index("旧一")), target("ITEM-2", "global:two", "旧二", original.index("旧二"))]
        reviewed, effective = [], []
        for source, receipt, target_row in zip(queue, final_values, targets):
            reviewed.append({
                "scope": "global", "path_prefix": "", "source_text": source["japanese_or_source_original"],
                "candidate_cn": receipt["final_value"], "status": "present", "authority": "existing_human_reviewed",
                "source_batch": "pass20-human-final-values-v1",
                "source_locator": TOOL.LOCATOR_PREFIX + receipt["item_id"],
                "match_method": "exact-semantic-key-human-review",
                "review_status": receipt["review_status"], "machine_translated": receipt["machine_translated"],
            })
            effective.append({
                "key": target_row["semantic_key"], "selected_cn": receipt["final_value"],
                "authority": "existing_human_reviewed", "source_file": "i18n/reviewed-candidates.tsv",
                "source_batch": "pass20-human-final-values-v1",
            })
        return queue, final_values, targets, reviewed, effective, product

    def test_04_machine_suggestion_and_human_revision_provenance_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = self.binding_fixture(root)
            result = TOOL.verify_materialized_bindings(
                root, *rows[:5], expected_items=2, expected_runtime_items=2,
                expected_maintenance_items=0, expected_occurrences=2,
            )
        self.assertEqual(result["canonical_human_reviewed"], 2)

    def test_05_machine_suggestion_must_not_be_labeled_human_translation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            queue, receipts, targets, reviewed, effective, _ = self.binding_fixture(root)
            reviewed[0]["machine_translated"] = "false"
            with self.assertRaisesRegex(TOOL.MaterializationError, "machine-origin"):
                TOOL.verify_materialized_bindings(root, queue, receipts, targets, reviewed, effective)

    def test_06_shadow_never_enters_final_value_canonical_layer(self):
        effective = [{"key": "global:shadow", "selected_cn": "官方值", "authority": "wiki", "source_file": "i18n/glossary.tsv", "source_line": "7"}]
        provenance = [{"candidate_id": "machine-1", "key": "global:shadow", "source_text": "源", "candidate_cn": "旧机翻", "selected": "false", "authority": "legacy_unverified_ai_assisted", "source_file": "i18n/frontend-strings.tsv"}]
        shadow = [{"item_id": "SHADOW-1", "source_key": "machine-1", "source_path": "i18n/frontend-strings.tsv", "japanese_or_source_original": "源", "machine_current_cn": "旧机翻", "effective_cn": "官方值", "effective_tier": "wiki", "effective_source_file": "i18n/glossary.tsv", "effective_source_line": 7, "evidence": "wiki", "product_write_allowed": False, "product_write_forbidden": True}]
        result = TOOL.verify_higher_authority_shadows(ROOT, shadow, [], provenance, effective, {})
        self.assertEqual(result["higher_authority_shadowed_items"], 1)
        reviewed = [{"source_locator": TOOL.LOCATOR_PREFIX + "SHADOW-1"}]
        with self.assertRaisesRegex(TOOL.MaterializationError, "entered human canonical"):
            TOOL.verify_higher_authority_shadows(ROOT, shadow, reviewed, provenance, effective, {})

if __name__ == "__main__":
    unittest.main(verbosity=2)
