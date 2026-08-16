#!/usr/bin/env python3

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
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


class Pass20MaterializationTests(unittest.TestCase):
    def test_01_current_repository_is_explicitly_closed_or_fully_materialized(self):
        result = TOOL.verify(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["product_tree_writes"])
        self.assertEqual(result["protected_text_changes"], 0)
        self.assertEqual(result["authority_materialization_items"], 2)
        self.assertEqual(result["authority_materialization_paths_checked"], 6)
        self.assertEqual(result["authority_verified_occurrences"], 10)
        self.assertEqual(result["authority_materialized_occurrences"], 9)
        self.assertEqual(result["shadowed_low_tier_candidates_written"], 0)
        self.assertEqual(result["shadowed_product_writes"], 0)
        if result["release_gate_open"]:
            self.assertTrue(result["materialization_verified"])
            self.assertEqual(
                result["canonical_human_reviewed"], result["review_contract"]["materialization_items"]
            )
            self.assertEqual(result["shadowed_low_tier_candidates_written"], 0)
            self.assertEqual(result["shadowed_product_writes"], 0)
        else:
            self.assertFalse(result["materialization_verified"])
            self.assertGreater(result["pending"], 0)

    def test_02_release_flag_follows_the_current_repository_gate(self):
        expected = 0 if TOOL.verify(ROOT)["release_gate_open"] else 3
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = TOOL.main(["--repo-root", str(ROOT), "--require-release-open"])
        self.assertEqual(code, expected)

    def test_03_incomplete_or_unresolved_workbook_receipt_is_rejected(self):
        complete = {
            "status": "PASS",
            "decisions_imported": 2,
            "pending_in_workbook": 0,
            "decision_counts": {"approve-current": 1, "revise": 1, "unresolved": 0},
        }
        TOOL.validate_workbook_receipt(complete, b"same", b"same", expected_items=2)
        for bad in (
            {**complete, "decisions_imported": 1, "pending_in_workbook": 1},
            {**complete, "decision_counts": {"approve-current": 1, "revise": 0, "unresolved": 1}},
        ):
            with self.assertRaises(TOOL.MaterializationError):
                TOOL.validate_workbook_receipt(bad, b"same", b"same", expected_items=2)
        with self.assertRaisesRegex(TOOL.MaterializationError, "does not reproduce"):
            TOOL.validate_workbook_receipt(complete, b"new", b"old", expected_items=2)

    def binding_fixture(self, root: Path):
        original = 'const first="旧一";const second="旧二";\n'
        after = 'const first="较长的新一";const second="旧二";\n'
        product = root / "magica/js/fixture.js"
        product.parent.mkdir(parents=True, exist_ok=True)
        product.write_text(after, encoding="utf-8", newline="\n")
        first_start = original.index("旧一")
        second_start = original.index("旧二")
        queue = [
            {"item_id": "ITEM-1", "japanese_or_source_original": "源一"},
            {"item_id": "ITEM-2", "japanese_or_source_original": "源二"},
            {"item_id": "ITEM-3", "japanese_or_source_original": "源三"},
        ]
        decisions = [
            {"item_id": "ITEM-1", "human_decision": "revise", "final_value": "较长的新一"},
            {"item_id": "ITEM-2", "human_decision": "approve-current", "final_value": "旧二"},
            {"item_id": "ITEM-3", "human_decision": "approve-current", "final_value": "维护值"},
        ]
        def target(item_id, key, current, start, end):
            occurrence = {"path": "js/fixture.js", "start": start, "end": end}
            return {
                "item_id": item_id, "semantic_key": key, "maintenance_scope": "global",
                "path_prefix": "", "current_cn": current, "application_allowed": True,
                "product_target_paths": ["js/fixture.js"], "occurrences": [occurrence],
            }
        targets = [
            target("ITEM-1", "global:one", "旧一", first_start, first_start + 2),
            target("ITEM-2", "global:two", "旧二", second_start, second_start + 2),
            {
                "item_id": "ITEM-3", "semantic_key": "global:three",
                "maintenance_scope": "global", "path_prefix": "", "current_cn": "维护值",
                "application_allowed": False,
                "match_status": "maintenance-only-count-or-path-drift",
                "product_target_paths": ["js/declared-but-unsafe.js"], "occurrences": [],
            },
        ]
        reviewed = []
        effective = []
        for source, decision, target_row in zip(queue, decisions, targets):
            item_id = source["item_id"]
            reviewed.append({
                "scope": "global", "path_prefix": "", "source_text": source["japanese_or_source_original"],
                "candidate_cn": decision["final_value"], "status": "present",
                "authority": "existing_human_reviewed", "source_batch": "pass20-human-review-v1",
                "source_locator": TOOL.LOCATOR_PREFIX + item_id,
                "match_method": "exact-semantic-key-human-review",
                "review_status": (
                    "human-reviewed-revised"
                    if decision["human_decision"] == "revise"
                    else "human-reviewed-approved-machine-origin-retained"
                ),
                "machine_translated": (
                    "false" if decision["human_decision"] == "revise" else "unknown"
                ),
            })
            effective.append({
                "key": target_row["semantic_key"], "selected_cn": decision["final_value"],
                "authority": "existing_human_reviewed", "source_file": "i18n/reviewed-candidates.tsv",
                "source_batch": "pass20-human-review-v1",
            })
        return queue, decisions, targets, reviewed, effective, product

    def test_04_exact_shifted_runtime_and_maintenance_bindings_pass(self):
        with tempfile.TemporaryDirectory(prefix="pass20-materialization-unit-") as temp:
            root = Path(temp)
            rows = self.binding_fixture(root)
            result = TOOL.verify_materialized_bindings(
                root, *rows[:5], expected_items=3, expected_runtime_items=2,
                expected_maintenance_items=1, expected_occurrences=2,
            )
            self.assertEqual(result["canonical_human_reviewed"], 3)
            self.assertEqual(result["runtime_occurrences"], 2)

    def test_05_runtime_or_canonical_drift_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="pass20-materialization-unit-") as temp:
            root = Path(temp)
            queue, decisions, targets, reviewed, effective, product = self.binding_fixture(root)
            product.write_text('const first="错误";const second="旧二";\n', encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(TOOL.MaterializationError, "not materialized"):
                TOOL.verify_materialized_bindings(
                    root, queue, decisions, targets, reviewed, effective,
                    expected_items=3, expected_runtime_items=2,
                    expected_maintenance_items=1, expected_occurrences=2,
                )
            product.write_text('const first="较长的新一";const second="旧二";\n', encoding="utf-8", newline="\n")
            reviewed[0]["candidate_cn"] = "错误"
            with self.assertRaisesRegex(TOOL.MaterializationError, "canonical reviewed candidate drift"):
                TOOL.verify_materialized_bindings(
                    root, queue, decisions, targets, reviewed, effective,
                    expected_items=3, expected_runtime_items=2,
                    expected_maintenance_items=1, expected_occurrences=2,
                )

    def test_06_higher_authority_shadow_never_enters_human_layer(self):
        decisions = [{
            "item_id": "SHADOW-1", "human_decision": "", "reviewer": "", "timestamp": "",
            "final_value": "", "human_revision": "", "human_notes": "",
        }]
        effective = [{
            "key": "global:shadow", "selected_cn": "官方值", "authority": "official_cn_dump",
            "source_file": "i18n/official-cn.tsv", "source_line": "7",
        }]
        provenance = [{
            "candidate_id": "machine-candidate-1", "key": "global:shadow",
            "source_text": "源文", "candidate_cn": "旧机翻", "selected": "false",
            "authority": "legacy_unverified_ai_assisted",
            "source_file": "i18n/frontend-strings.tsv",
        }]
        shadows = [{
            "item_id": "SHADOW-1", "source_key": "machine-candidate-1",
            "source_path": "i18n/frontend-strings.tsv",
            "japanese_or_source_original": "源文", "machine_current_cn": "旧机翻",
            "effective_cn": "官方值", "effective_tier": "official_cn_dump",
            "effective_source_file": "i18n/official-cn.tsv", "effective_source_line": 7,
            "evidence": "official stable ID", "product_write_allowed": False,
            "product_write_forbidden": True,
        }]
        result = TOOL.verify_higher_authority_shadows(
            ROOT, shadows, decisions, [], provenance, effective, {},
        )
        self.assertEqual(result["higher_authority_shadowed_items"], 1)
        self.assertEqual(result["shadowed_product_writes"], 0)
        reviewed = [{"source_locator": TOOL.LOCATOR_PREFIX + "SHADOW-1"}]
        with self.assertRaisesRegex(TOOL.MaterializationError, "entered human canonical"):
            TOOL.verify_higher_authority_shadows(
                ROOT, shadows, decisions, reviewed, provenance, effective, {},
            )

    def test_07_higher_authority_runtime_materialization_is_read_from_product(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            product = root / "magica/js/shadow.js"
            product.parent.mkdir(parents=True)
            product.write_text(
                'const winner="官方值"; const composite="旧机翻Pt";\n',
                encoding="utf-8", newline="\n",
            )
            decisions = [{
                "item_id": "SHADOW-1", "human_decision": "", "reviewer": "", "timestamp": "",
                "final_value": "", "human_revision": "", "human_notes": "",
            }]
            effective = [{
                "key": "global:shadow", "selected_cn": "官方值", "authority": "wiki",
                "source_file": "i18n/glossary.tsv", "source_line": "7",
            }]
            provenance = [{
                "candidate_id": "machine-candidate-1", "key": "global:shadow",
                "source_text": "源文", "candidate_cn": "旧机翻", "selected": "false",
                "authority": "legacy_unverified_ai_assisted",
                "source_file": "i18n/frontend-strings.tsv",
            }]
            contracts = {
                "SHADOW-1": {
                    "machine_cn": "旧机翻", "effective_cn": "官方值",
                    "paths": {"js/shadow.js": 1},
                    "repaired_paths": {"js/shadow.js"},
                }
            }
            shadows = [{
                "item_id": "SHADOW-1", "source_key": "machine-candidate-1",
                "source_path": "i18n/frontend-strings.tsv",
                "japanese_or_source_original": "源文", "machine_current_cn": "旧机翻",
                "effective_cn": "官方值", "effective_tier": "wiki",
                "effective_source_file": "i18n/glossary.tsv", "effective_source_line": 7,
                "evidence": "Wiki exact term", "product_write_allowed": False,
                "product_write_forbidden": True,
                "authority_materialization": {
                    "machine_cn": "旧机翻", "effective_cn": "官方值",
                    "expected_effective_occurrences": 1,
                    "materialized_from_machine_occurrences": 1,
                    "product_paths": [{
                        "path": "js/shadow.js", "machine_count": 0,
                        "effective_count": 1, "expected_effective_count": 1,
                        "materialized_from_machine": True,
                    }],
                },
            }]
            result = TOOL.verify_higher_authority_shadows(
                root, shadows, decisions, [], provenance, effective, contracts,
            )
            self.assertEqual(result["authority_materialized_occurrences"], 1)
            self.assertEqual(result["shadowed_product_writes"], 0)

            product.write_text('const winner="旧机翻";\n', encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(TOOL.MaterializationError, "not materialized"):
                TOOL.verify_higher_authority_shadows(
                    root, shadows, decisions, [], provenance, effective, contracts,
                )

            product.write_text('const winner="别的";\n', encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(TOOL.MaterializationError, "not materialized"):
                TOOL.verify_higher_authority_shadows(
                    root, shadows, decisions, [], provenance, effective, contracts,
                )

            product.write_text('const winner="官方值";\n', encoding="utf-8", newline="\n")
            shadows[0]["authority_materialization"]["product_paths"][0]["effective_count"] = 2
            with self.assertRaisesRegex(TOOL.MaterializationError, "manifest count drift"):
                TOOL.verify_higher_authority_shadows(
                    root, shadows, decisions, [], provenance, effective, contracts,
                )
            shadows[0]["authority_materialization"]["product_paths"][0]["effective_count"] = 1
            contracts["SHADOW-1"]["paths"] = {"../escape.js": 1}
            with self.assertRaises(TOOL.MaterializationError):
                TOOL.verify_higher_authority_shadows(
                    root, shadows, decisions, [], provenance, effective, contracts,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
