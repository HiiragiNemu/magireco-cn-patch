#!/usr/bin/env python3
"""Focused fail-closed tests for the v26 product authority verifier."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_TOOL = ROOT / "tools" / "build-v26-package.py"
PACKAGE_SPEC = importlib.util.spec_from_file_location("build_v26_package_for_product_test", PACKAGE_TOOL)
assert PACKAGE_SPEC and PACKAGE_SPEC.loader
PACKAGE = importlib.util.module_from_spec(PACKAGE_SPEC)
sys.modules[PACKAGE_SPEC.name] = PACKAGE
PACKAGE_SPEC.loader.exec_module(PACKAGE)

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

    @staticmethod
    def pass18_review_rows() -> list[dict[str, str]]:
        return MOD.read_tsv(
            MOD.MACHINE_REVIEW / "pass18_authority_corrections_939.tsv"
        )

    @staticmethod
    def visible_term_closure_rows() -> list[dict[str, str]]:
        return MOD.read_tsv(
            MOD.MACHINE_REVIEW / "visible_term_closure_3136.tsv"
        )

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
        rows = self.frontend_empty_rows()
        frontend = MOD.verify_frontend_empty_closure(rows)
        self.assertEqual(frontend["status_counts"], MOD.FRONTEND_EMPTY_STATUS_COUNTS)
        self.assertEqual(
            frontend["official_stable_key"], MOD.FRONTEND_OFFICIAL_STABLE_KEY
        )

        # Aggregate record numbers are presentation metadata.  A legitimate
        # earlier-component row addition must not invalidate the source set.
        renumbered = copy.deepcopy(rows)
        for index, row in enumerate(renumbered, 90000):
            row["record_id"] = f"MT-{index:05d}"
        shifted = MOD.verify_frontend_empty_closure(renumbered)
        self.assertEqual(
            shifted["official_stable_key"], MOD.FRONTEND_OFFICIAL_STABLE_KEY
        )

        pass19 = MOD.verify_pass19_product_closure(self.pass19_rows())
        self.assertEqual(pass19["manifest_rows"], 6)
        self.assertEqual(pass19["source_tiers"], {"official_cn_dump": 4, "wiki": 2})
        self.assertEqual(pass19["corrected_occurrences"], 11)
        self.assertEqual(pass19["product_terms"]["心魔战"], {"occurrences": 20, "files": 11})
        self.assertEqual(pass19["product_terms"]["属性克制"], {"occurrences": 29, "files": 5})
        self.assertEqual(
            pass19["post_pass19_product_terms"]["心魔战"],
            {"occurrences": 10, "files": 3},
        )
        self.assertEqual(
            pass19["post_pass19_product_terms"]["属性克制"],
            {"occurrences": 1, "files": 1},
        )
        self.assertEqual(pass19["retired_terms"], {"心情战": 0, "属性相性": 0})

    def test_product_inventory_counts_follow_selected_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repair_member = MOD.REPAIR_PREFIX + "chara/sample.png"
            repair_bytes = b"repair-png"
            files = {
                "madomagi/engine_i18n.tsv": "戻る\t返回\n",
                "magica/js/a.js": "define(function(){return true;});\n",
                "magica/template/a.html": "<p>ok</p>\n",
                "magica/css/a.css": "body{}\n",
                "magica/image/a.png": "not-a-real-png",
                "magica/research/notes.html": "excluded\n",
                "magica/i18n_audit/report.html": "excluded\n",
            }
            for relative, value in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8", newline="\n")
            repair_path = root / repair_member
            repair_path.parent.mkdir(parents=True, exist_ok=True)
            repair_path.write_bytes(repair_bytes)
            manifest_path = root / MOD.REPAIR_MANIFEST
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "magireco-cn-madomagi-repair/v1",
                        "file_count": 1,
                        "total_bytes": len(repair_bytes),
                        "entries": [
                            {"path": repair_member, "bytes": len(repair_bytes)}
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            first = MOD.verify_product_inventory(root)
            self.assertEqual(first["inventory_entries"], 7)
            self.assertEqual(first["package_entries"], 6)
            self.assertEqual(first["magica_entries"], 4)
            self.assertEqual(first["engine_entries"], 1)
            self.assertEqual(first["repair_manifest_entries"], 1)
            self.assertEqual(first["repair_entries"], 1)
            self.assertEqual(first["repair_total_bytes"], len(repair_bytes))
            self.assertEqual(first["repair_validation"]["errors"], [])
            self.assertEqual(first["audit_research_entries"], 0)
            self.assertEqual(
                first["suffix_counts"],
                {".css": 1, ".html": 1, ".js": 1, ".png": 1},
            )

            added = root / "magica/template/reviewed-new.html"
            added.write_text("<p>new</p>\n", encoding="utf-8", newline="\n")
            second = MOD.verify_product_inventory(root)
            self.assertEqual(second["inventory_entries"], 8)
            self.assertEqual(second["package_entries"], 7)
            self.assertEqual(second["suffix_counts"][".html"], 2)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"][0]["bytes"] += 1
            manifest["total_bytes"] += 1
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(AssertionError, "byte count mismatch"):
                MOD.verify_product_inventory(root)

    def test_product_inventory_rejects_repair_path_set_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "magica/js").mkdir(parents=True)
            (root / "magica/js/a.js").write_text("ok\n", encoding="utf-8")
            engine = root / MOD.ENGINE
            engine.parent.mkdir(parents=True)
            engine.write_text("source\ttarget\n", encoding="utf-8")
            repair = root / MOD.REPAIR_PREFIX / "chara/actual.png"
            repair.parent.mkdir(parents=True)
            repair.write_bytes(b"actual")
            manifest = root / MOD.REPAIR_MANIFEST
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "magireco-cn-madomagi-repair/v1",
                        "file_count": 1,
                        "total_bytes": 6,
                        "entries": [{
                            "path": MOD.REPAIR_PREFIX + "chara/missing.png",
                            "bytes": 6,
                        }],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(AssertionError, "path set mismatch"):
                MOD.verify_product_inventory(root)

    def test_all_30_product_json_files_parse(self) -> None:
        report = MOD.verify_product_json()
        self.assertEqual(report["files"], 30)
        self.assertEqual(report["runtime_dictionaries"], 23)
        self.assertEqual(report["auxiliary_files"], 7)
        self.assertEqual(report["parse_failures"], 0)
        self.assertEqual(tuple(report["paths"]), MOD.EXPECTED_PRODUCT_JSON_PATHS)

    def test_all_225_html_files_match_frozen_structure_contract(self) -> None:
        report = MOD.verify_html_structure_contract()
        self.assertEqual(report["html_files"], 225)
        self.assertEqual(report["strict_source_structure_matches"], 213)
        self.assertEqual(report["version_divergent_frozen_product"], 12)
        self.assertEqual(report["source_path_missing"], 0)
        self.assertEqual(report["product_structure_drift"], 0)
        self.assertEqual(report["source_structure_drift"], 0)

    def test_auxiliary_product_json_parse_and_path_drift_are_rejected(self) -> None:
        expected = (
            "magica/js/libs/runtime.json",
            "magica/resource/image_web/_json/help.json",
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in expected:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"ok": true}\n', encoding="utf-8", newline="\n")

            report = MOD.verify_product_json(root, expected)
            self.assertEqual(report["files"], 2)
            self.assertEqual(report["runtime_dictionaries"], 1)
            self.assertEqual(report["auxiliary_files"], 1)

            auxiliary = root / expected[1]
            auxiliary.write_text('{"broken":', encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(AssertionError, "invalid product JSON"):
                MOD.verify_product_json(root, expected)

            auxiliary.write_text('{"ok": true}\n', encoding="utf-8", newline="\n")
            extra = root / "magica/json/extra.json"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text('{}\n', encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(AssertionError, "path set mismatch"):
                MOD.verify_product_json(root, expected)

    def test_round3_manifest_bound_product_members_exist(self) -> None:
        report = MOD.verify_round3_package_contract()
        self.assertEqual(report, {
            "required_members": 207,
            "visible_text_items": 52,
            "css_records": 110,
            "official_image_members": 151,
            "current_canvas_image_members": 9,
        })

    def test_round3_zip_reopens_with_all_manifest_members(self) -> None:
        inventory = MOD.verify_product_inventory(ROOT)
        self.assertEqual(inventory["repair_manifest_entries"], 1)
        self.assertEqual(inventory["repair_entries"], 91)
        self.assertEqual(inventory["repair_validation"]["errors"], [])
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "round3-contract.zip"
            PACKAGE.build_package(ROOT, archive)
            report = MOD.verify_zip(archive)
            self.assertEqual(report["engine_entries"], 1)
            self.assertEqual(report["repair_entries"], 91)
            self.assertEqual(report["file_entries"], inventory["package_entries"])
            self.assertEqual(report["scenario_entries"], 0)
            self.assertEqual(report["audit_entries"], 0)
            self.assertEqual(report["round3_package_contract"]["required_members"], 207)

    def test_frontend53_status_drift_is_rejected(self) -> None:
        rows = copy.deepcopy(self.frontend_empty_rows())
        row = next(item for item in rows if item["review_status"] == "visible-cn-compatible-identity")
        row["review_status"] = "runtime-absent/not-backlog"
        with self.assertRaises(AssertionError):
            MOD.verify_frontend_empty_closure(rows)

        rows = copy.deepcopy(self.frontend_empty_rows())
        rows[0]["stable_key_or_line"] = "global:00000000000000000000"
        with self.assertRaises(AssertionError):
            MOD.verify_frontend_empty_closure(rows)

    def test_current_machine_review_contract_is_exact(self) -> None:
        closure_rows = self.visible_term_closure_rows()
        closure = MOD.verify_visible_term_closure_review(closure_rows)
        self.assertEqual(closure["rows"], 3136)
        self.assertEqual(closure["unique_targets"], 3136)
        self.assertEqual(
            closure["partition"], MOD.EXPECTED_VISIBLE_TERM_CLOSURE_PARTITION
        )

        pass18 = MOD.verify_pass18_review_contract(
            self.pass18_review_rows(), closure_rows
        )
        self.assertEqual(pass18["runtime_direct_current"], 536)
        self.assertEqual(pass18["runtime_exact_visible_term_supersession"], 402)
        self.assertEqual(pass18["static_direct_current"], 1)

        complete = MOD.verify_machine_review()
        self.assertEqual(complete["counts"], MOD.EXPECTED_MACHINE_REVIEW_COUNTS)
        self.assertEqual(complete["engine_partition"], MOD.EXPECTED_ENGINE_PARTITION)

    def test_machine_review_supersession_and_provenance_drift_are_rejected(self) -> None:
        pass18_rows = self.pass18_review_rows()
        closure_rows = self.visible_term_closure_rows()
        changed = copy.deepcopy(pass18_rows)
        superseded = next(
            row for row in changed
            if row["pass18_current_status"] == "visible-term-closure-exact-supersession"
        )
        superseded["current_product_cn"] += "漂移"
        with self.assertRaises(AssertionError):
            MOD.verify_pass18_review_contract(changed, closure_rows)

        changed_closure = copy.deepcopy(closure_rows)
        changed_closure[0]["machine_translated"] = "unknown"
        with self.assertRaises(AssertionError):
            MOD.verify_visible_term_closure_review(changed_closure)

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
