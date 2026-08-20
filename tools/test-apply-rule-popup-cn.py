#!/usr/bin/env python3

from __future__ import annotations

import csv
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("apply-rule-popup-cn.py")
SPEC = importlib.util.spec_from_file_location("apply_rule_popup_cn", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class RulePopupCnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="rule-popup-cn-"))
        self.repo = self.temp / "repo"
        self.source = self.temp / "source" / "RulePopup.html"
        self.input_dir = self.repo / MODULE.INPUT_REL
        self.state = self.repo / MODULE.STATE_REL
        self.product = self.repo / MODULE.PRODUCT_REL
        self.source.parent.mkdir(parents=True, exist_ok=True)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(MODULE.SOURCE_DEFAULT, self.source)
        shutil.copyfile(MODULE.REPO_DEFAULT / MODULE.INPUT_REL / "RulePopup.ja.html", self.input_dir / "RulePopup.ja.html")
        shutil.copyfile(
            MODULE.REPO_DEFAULT / MODULE.INPUT_REL / "reviewed_translation_lines.tsv",
            self.input_dir / "reviewed_translation_lines.tsv",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def prepare(self) -> dict:
        return MODULE.prepare(self.repo, self.source, self.input_dir, self.state)

    def rewrite_translation(self, mutate) -> None:
        path = self.input_dir / "reviewed_translation_lines.tsv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        rows = mutate(rows)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["line_no", "final_html"], delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_happy_prepare_apply_verify_rollback(self) -> None:
        manifest = self.prepare()
        self.assertEqual(manifest["translation_records"], 146)
        self.assertEqual(manifest["translated_records"], 144)
        self.assertEqual(manifest["preserved_records"], 2)
        MODULE.apply(self.repo, self.state)
        report = MODULE.verify(self.repo, self.state)
        self.assertEqual(report["checked_files"], 1)
        self.assertEqual(report["unexpected_kana_records"], 0)
        MODULE.rollback(self.repo, self.state)
        self.assertFalse(self.product.exists())

    def test_existing_product_rejected_without_change(self) -> None:
        self.product.parent.mkdir(parents=True, exist_ok=True)
        self.product.write_text("existing", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(self.product.read_text(encoding="utf-8"), "existing")

    def test_source_mirror_drift_rejected(self) -> None:
        self.source.write_bytes(self.source.read_bytes() + b"drift")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.product.exists())

    def test_missing_translation_row_rejected(self) -> None:
        self.rewrite_translation(lambda rows: rows[:-1])
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.product.exists())

    def test_tag_drift_rejected(self) -> None:
        def mutate(rows):
            rows[0]["final_html"] = rows[0]["final_html"].replace("<br>", "<hr>")
            return rows
        self.rewrite_translation(mutate)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.product.exists())

    def test_dom_id_drift_rejected(self) -> None:
        def mutate(rows):
            row = next(row for row in rows if row["line_no"] == "61")
            row["final_html"] = row["final_html"].replace("rulePolicyLink", "changedPolicyLink")
            return rows
        self.rewrite_translation(mutate)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.product.exists())

    def test_url_drift_rejected(self) -> None:
        def mutate(rows):
            row = next(row for row in rows if row["line_no"] == "91")
            row["final_html"] = row["final_html"].replace("https://", "http://")
            return rows
        self.rewrite_translation(mutate)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.product.exists())

    def test_protected_company_name_drift_rejected(self) -> None:
        def mutate(rows):
            row = next(row for row in rows if row["line_no"] == "171")
            row["final_html"] = row["final_html"].replace("Aniplex股份有限公司", "Aniplex")
            return rows
        self.rewrite_translation(mutate)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.product.exists())

    def test_apply_failure_removes_created_product(self) -> None:
        self.prepare()
        with self.assertRaises(RuntimeError):
            MODULE.apply(self.repo, self.state, fail_after_write=True)
        self.assertFalse(self.product.exists())

    def test_prepared_drift_rejected(self) -> None:
        manifest = self.prepare()
        prepared = self.repo / manifest["prepared_state_path"]
        prepared.write_text(prepared.read_text(encoding="utf-8") + "drift", encoding="utf-8")
        with self.assertRaises(ValueError):
            MODULE.apply(self.repo, self.state)
        self.assertFalse(self.product.exists())

    def test_product_drift_blocks_verify_and_rollback(self) -> None:
        self.prepare()
        MODULE.apply(self.repo, self.state)
        self.product.write_text(self.product.read_text(encoding="utf-8") + "drift", encoding="utf-8")
        with self.assertRaises(ValueError):
            MODULE.verify(self.repo, self.state)
        with self.assertRaises(ValueError):
            MODULE.rollback(self.repo, self.state)
        self.assertTrue(self.product.exists())

    def test_rollback_failure_restores_product(self) -> None:
        self.prepare()
        MODULE.apply(self.repo, self.state)
        before = self.product.read_bytes()
        with self.assertRaises(RuntimeError):
            MODULE.rollback(self.repo, self.state, fail_after_remove=True)
        self.assertEqual(self.product.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
