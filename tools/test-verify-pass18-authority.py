#!/usr/bin/env python3
"""Focused regressions for the layered Pass18 release gate."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("verify-pass18-authority.py")
SPEC = importlib.util.spec_from_file_location("verify_pass18_authority", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LayeredPass18GateTests(unittest.TestCase):
    def test_manifest_identity_is_preserved_across_later_authority_enrichment(self) -> None:
        rows, read_errors = MODULE.read_manifest()
        baseline = MODULE.load_json(MODULE.BASELINE_RECORD)
        result, errors = MODULE.verify_manifest_lineage(
            rows, baseline["manifest_sha256"]
        )
        self.assertEqual(read_errors + errors, [])
        self.assertEqual(result["pinned_rows"], 939)
        self.assertEqual(result["current_rows"], 939)
        self.assertEqual(result["later_enriched_rows"], 2)

    def test_engine_keeps_pass18_and_binds_the_nine_later_rules(self) -> None:
        result, errors = MODULE.verify_engine()
        self.assertEqual(errors, [])
        self.assertEqual(result["actual_data_rows"], 615)
        self.assertEqual(result["actual_physical_lines"], 616)
        self.assertEqual(result["official_mapping_failures"], [])
        self.assertEqual(result["post_pass18_gap_rules"]["result"]["active_rules"], 308)
        self.assertEqual(result["post_pass18_gap_rules"]["result"]["generated_timer_rules"], 301)
        self.assertEqual(result["post_pass18_gap_rules"]["result"]["substring"], 0)
        self.assertEqual(result["post_pass18_gap_rules"]["active_substring_sources"], [])
        self.assertEqual(result["connect_authority"]["sources"], ["コネクト", "Connect"])
        self.assertEqual(result["connect_authority"]["target"], "连携")

    def test_css_uses_product_scope_and_all_approved_layers(self) -> None:
        result, errors = MODULE.verify_css()
        self.assertEqual(errors, [])
        self.assertEqual(result["baseline_files"], 19)
        self.assertEqual(result["current_files"], 44)
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["extra"], [])
        self.assertEqual(result["visible_round3"]["literal_failures"], [])
        self.assertEqual(result["manual_round3"]["errors"], [])
        self.assertEqual(result["connect_followup"]["errors"], [])

    def test_pass18_terminal_partition_requires_exact_closure_chains(self) -> None:
        rows, read_errors = MODULE.read_manifest()
        _, closure, closure_result, closure_errors = MODULE.read_visible_term_closure()
        self.assertEqual(read_errors + closure_errors, [])
        self.assertEqual(closure_result["rows"], 3136)
        self.assertEqual(closure_result["product_failures"], [])
        result, errors = MODULE.verify_manifest_after_images(rows, closure)
        self.assertEqual(errors, [])
        self.assertEqual(result["runtime_direct_matches"], 536)
        self.assertEqual(result["runtime_exact_approved_supersessions"], 402)
        self.assertEqual(result["static_direct_matches"], 1)
        self.assertEqual(result["strict_json_pointer_resolutions"], 938)
        self.assertEqual(result["failures"], [])

        target = next(row for row in rows if row["change_id"] == "P18-00018")
        identity = (target["file"], target["stable_key"], target["field"])
        without_chain = dict(closure)
        without_chain.pop(identity)
        failed, failed_errors = MODULE.verify_manifest_after_images(rows, without_chain)
        self.assertTrue(failed_errors)
        self.assertIn("P18-00018", {item["change_id"] for item in failed["failures"]})

    def test_json_pointer_is_strict_and_never_falls_back_to_stable_key(self) -> None:
        rows, _ = MODULE.read_manifest()
        _, closure, _, _ = MODULE.read_visible_term_closure()
        original = next(row for row in rows if row["change_id"] == "P18-00001")
        tampered = dict(original)
        tampered["json_pointer"] = "/999999/cardName"
        result, errors = MODULE.verify_manifest_after_images([tampered], closure)
        self.assertTrue(errors)
        self.assertEqual(result["strict_json_pointer_resolutions"], 0)
        self.assertEqual(result["failures"][0]["change_id"], "P18-00001")
        self.assertIn("exception", result["failures"][0]["actual"])

    def test_connect_followup_is_exact_and_structure_preserving(self) -> None:
        result, errors = MODULE.verify_connect_followup_layers()
        self.assertEqual(errors, [])
        self.assertEqual(result["visible_records"], 7)
        self.assertEqual(result["visible_failures"], [])
        self.assertEqual(result["html_ejs_structure_failures"], [])
        self.assertEqual(result["help_failures"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
