#!/usr/bin/env python3
"""Focused fail-closed tests for the v26 product authority verifier."""

from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "verify-v26-product.py"
SPEC = importlib.util.spec_from_file_location("verify_v26_product", TOOL)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class V26ProductAuthorityTests(unittest.TestCase):
    @staticmethod
    def pass19_rows() -> list[dict[str, str]]:
        return MOD.read_tsv(MOD.PASS19_CORRECTIONS)

    @staticmethod
    def frontend_empty_rows() -> list[dict[str, str]]:
        return MOD.read_tsv(MOD.MACHINE_REVIEW / "frontend_untranslated_53.tsv")

    def product_fixture(self, root: Path) -> None:
        content: dict[str, list[str]] = {}
        for term, files in MOD.EXPECTED_PRODUCT_TERM_FILES.items():
            for relative, count in files.items():
                content.setdefault(relative, []).append(term * count)
        formation = "magica/template/formation/FormationQuest.html"
        content[formation] = [
            '<div class="deckDetailCongeniality"><p>属性克制</p></div>\n'
        ]
        for relative, fragments in content.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("|".join(fragments), encoding="utf-8", newline="\n")

    def test_current_frontend53_partition_and_pass19_product(self) -> None:
        frontend = MOD.verify_frontend_empty_closure(self.frontend_empty_rows())
        self.assertEqual(frontend["status_counts"], MOD.FRONTEND_EMPTY_STATUS_COUNTS)
        self.assertEqual(frontend["official_record"], "MT-01965")

        pass19 = MOD.verify_pass19_product_closure(self.pass19_rows())
        self.assertEqual(pass19["manifest_rows"], 6)
        self.assertEqual(pass19["source_tiers"], {"official_cn_dump": 4, "wiki": 2})
        self.assertEqual(pass19["corrected_occurrences"], 11)
        self.assertEqual(pass19["product_terms"]["心魔战"], {"occurrences": 20, "files": 11})
        self.assertEqual(pass19["product_terms"]["属性克制"], {"occurrences": 29, "files": 5})
        self.assertEqual(pass19["retired_terms"], {"心情战": 0, "属性相性": 0})

    def test_frontend53_status_drift_is_rejected(self) -> None:
        rows = copy.deepcopy(self.frontend_empty_rows())
        row = next(item for item in rows if item["review_status"] == "visible-cn-compatible-identity")
        row["review_status"] = "runtime-absent/not-backlog"
        with self.assertRaises(AssertionError):
            MOD.verify_frontend_empty_closure(rows)

    def test_old_kimochi_term_reflux_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.product_fixture(root)
            target = root / "magica/js/regularEvent/groupBattle/view/BossPageView.js"
            target.write_text(
                target.read_text(encoding="utf-8").replace("心魔战", "心情战", 1),
                encoding="utf-8", newline="\n",
            )
            with self.assertRaises(AssertionError):
                MOD.verify_pass19_product_closure(self.pass19_rows(), root)

    def test_official_formation_node_reflux_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.product_fixture(root)
            target = root / "magica/template/formation/FormationQuest.html"
            target.write_text(
                '<div class="deckDetailCongeniality"><p>属性相性</p></div>\n',
                encoding="utf-8", newline="\n",
            )
            with self.assertRaises(AssertionError):
                MOD.verify_pass19_product_closure(self.pass19_rows(), root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
