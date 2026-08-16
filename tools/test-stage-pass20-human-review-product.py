#!/usr/bin/env python3
"""End-to-end contract tests for the guarded Pass20 product staging chain."""

from __future__ import annotations

import csv
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import sys
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"


def load_tool(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STAGE = load_tool("pass20_stage_tested", ROOT / "tools/stage-pass20-human-review-product.py")
PROMOTE = load_tool("pass20_promote_tested", ROOT / "tools/promote-pass20-product-stage.py")
ROLLBACK = load_tool("pass20_rollback_integrated", ROOT / "tools/rollback-pass20-product-stage.py")
IMPORTER = load_tool("pass20_import_integrated", ROOT / "tools/import-pass20-human-review-xlsx.py")


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_tsv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def set_xlsx_text(sheet: ET.Element, ref: str, value: str) -> None:
    cell = next(node for node in sheet.findall(f".//{IMPORTER.Q('c')}") if node.get("r") == ref)
    for child in list(cell):
        if child.tag in {IMPORTER.Q("v"), IMPORTER.Q("is"), IMPORTER.Q("f")}:
            cell.remove(child)
    cell.set("t", "inlineStr")
    inline = ET.SubElement(cell, IMPORTER.Q("is"))
    text = ET.SubElement(inline, IMPORTER.Q("t"))
    text.text = value


def completed_workbook(source: Path, target: Path, rows: list[dict[str, str]]) -> None:
    with zipfile.ZipFile(source) as package:
        infos = package.infolist()
        blobs = {info.filename: package.read(info.filename) for info in infos}
        paths = IMPORTER._sheet_paths(package)
    sheets = {name: ET.fromstring(blobs[path]) for name, path in paths.items()}
    set_xlsx_text(sheets["说明"], "B13", "synthetic-contract-test")
    set_xlsx_text(sheets["说明"], "B14", "2026-08-15T12:00:00+08:00")
    for sequence, row in enumerate(rows, 2):
        if row["item_id"] in {"LOW-MT-00312", "LOW-MT-00322"}:
            set_xlsx_text(sheets["审核"], f"O{sequence}", "修改译文")
            set_xlsx_text(sheets["审核"], f"P{sequence}", row["final_value"])
        else:
            set_xlsx_text(sheets["审核"], f"O{sequence}", "保留现译")
    for name, root in sheets.items():
        blobs[paths[name]] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(target, "w") as package:
        for info in infos:
            package.writestr(info, blobs[info.filename])


class Pass20ProductStageTests(unittest.TestCase):
    def test_00_child_python_stdout_is_forced_to_utf8(self):
        result = STAGE.run_command(
            [sys.executable, "-c", "print('中文通过 ✔')"],
            ROOT,
        )
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "中文通过 ✔\n")

    def test_00b_any_saved_target_field_drift_is_rejected(self):
        saved = json.loads((AUDIT / "pass20_product_targets.json").read_text(encoding="utf-8"))
        tampered = deepcopy(saved)
        tampered["items"][0]["maintenance_scope"] = "override"
        with self.assertRaisesRegex(STAGE.StageError, "fresh exact scan"):
            STAGE.require_fresh_target_manifest(tampered, saved)

    def test_01_current_human_gate_is_closed_before_any_product_copy(self):
        with tempfile.TemporaryDirectory(prefix="pass20-stage-gate-") as temp:
            stage_root = Path(temp) / "stage"
            with self.assertRaisesRegex(STAGE.StageError, "human review release gate is closed"):
                STAGE.stage(
                    AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                    AUDIT / "dsv4_human_decisions.tsv",
                    AUDIT / "pass20_authority_resolutions.tsv",
                    AUDIT / "pass20_product_targets.json",
                    stage_root,
                )
            self.assertFalse((stage_root / "magica").exists())

    def test_02_synthetic_closed_review_stages_exact_diff_and_rehearses_rollback(self):
        decisions_header, decisions = read_tsv(AUDIT / "dsv4_human_decisions.tsv")
        _, remaining = read_tsv(AUDIT / "pass20_remaining_manual_review.tsv")
        remaining_ids = {row["item_id"] for row in remaining}
        self.assertEqual(len(remaining_ids), 199)
        for row in decisions:
            if row["item_id"] not in remaining_ids:
                continue
            row["human_decision"] = "approve-current"
            row["reviewer"] = "synthetic-contract-test"
            row["timestamp"] = "2026-08-15T12:00:00+08:00"
            row["final_value"] = row["current_cn"]
            row["human_revision"] = ""
            row["human_notes"] = ""
        revised = next(row for row in decisions if row["item_id"] == "LOW-MT-00312")
        revised["human_decision"] = "revise"
        revised["final_value"] = "+c+a+l+e"
        revised["human_revision"] = "+c+a+l+e"
        revised_global = next(row for row in decisions if row["item_id"] == "LOW-MT-00322")
        revised_global["human_decision"] = "revise"
        revised_global["final_value"] = revised_global["current_cn"][:-1] + "？"
        revised_global["human_revision"] = revised_global["final_value"]

        source_product = ROOT / "magica/js/event/EventArenaRankMatch/Utility.js"
        source_before = source_product.read_bytes()
        reviewed_source = ROOT / "i18n/reviewed-candidates.tsv"
        reviewed_before = reviewed_source.read_bytes()
        with tempfile.TemporaryDirectory(prefix="pass20-stage-e2e-") as temp:
            temp_root = Path(temp)
            decisions_path = temp_root / "synthetic-decisions.tsv"
            write_tsv(decisions_path, decisions_header, decisions)
            workbook_path = temp_root / "completed-review.xlsx"
            completed_workbook(
                AUDIT / "pass20_human_review.xlsx",
                workbook_path,
                [row for row in decisions if row["item_id"] in remaining_ids],
            )
            stage_root = temp_root / "stage"
            report = STAGE.stage(
                AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                decisions_path,
                AUDIT / "pass20_authority_resolutions.tsv",
                AUDIT / "pass20_product_targets.json",
                stage_root,
                workbook_path,
            )
            self.assertEqual(report["status"], "PASS")
            self.assertTrue(report["human_gate"]["release_gate_open"])
            self.assertEqual(report["reviewed_candidates_appended"], 199)
            self.assertEqual(report["exact_target_items"], 180)
            self.assertEqual(report["maintenance_only_items"], 19)
            self.assertEqual(report["canonical_human_review_items"], 199)
            self.assertEqual(report["maintenance_only_items_persisted"], 19)
            self.assertEqual(report["runtime_occurrences_bound"], 246)
            self.assertEqual(report["patch_items"], 2)
            self.assertEqual(report["patch_records"], 2)
            self.assertEqual(report["changed_files"], [
                "magica/js/event/EventArenaRankMatch/Utility.js",
                "magica/js/regularEvent/extermination/RegularEventExterminationFormation.js",
            ])
            self.assertEqual(report["protected_text_changes"], 0)
            self.assertEqual(report["repository_product_writes"], 0)
            self.assertEqual(report["rollback_rehearsal"]["status"], "PASS")

            staged_product = stage_root / "magica/js/event/EventArenaRankMatch/Utility.js"
            self.assertNotEqual(staged_product.read_bytes(), source_before)
            self.assertIn("+c+a+l+e", staged_product.read_text(encoding="utf-8"))
            self.assertNotIn(b"\r", staged_product.read_bytes())
            self.assertEqual(source_product.read_bytes(), source_before)
            patch = json.loads((stage_root / "review_application/product_patch.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [item["item_id"] for item in patch["items"]],
                ["LOW-MT-00312", "LOW-MT-00322"],
            )
            self.assertTrue((stage_root / "review_application/product.diff").read_text(encoding="utf-8"))
            self.assertTrue((stage_root / "rollback/rollback.json").is_file())
            self.assertTrue((stage_root / "staging_verification.json").is_file())

            repo_copy = temp_root / "promotion-repository"
            STAGE.copy_tree(ROOT / "magica", repo_copy / "magica", product=True)
            STAGE.copy_tree(ROOT / "i18n", repo_copy / "i18n")
            STAGE.copy_tree(ROOT / "madomagi", repo_copy / "madomagi")
            for rel in (
                Path("magica/i18n_audit/release_v26_authority/protected_authority/protected_translation_fields.tsv"),
                Path("magica/i18n_audit/release_v26_authority/pass19_official_static_corrections.tsv"),
                Path("magica/i18n_audit/release_v26_authority/dsv4_human_decisions.tsv"),
                Path("magica/i18n_audit/release_v26_authority/pass20_human_review.xlsx"),
            ):
                target = repo_copy / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, target)
            promotion = PROMOTE.promote(stage_root, repo_copy)
            self.assertEqual(promotion["status"], "PASS")
            self.assertEqual(promotion["canonical_human_review_items"], 199)
            self.assertEqual(promotion["protected_text_changes"], 0)
            self.assertIn("i18n/reviewed-candidates.tsv", promotion["canonical_i18n_and_audit_files"])
            self.assertIn(
                "+c+a+l+e",
                (repo_copy / "magica/js/event/EventArenaRankMatch/Utility.js").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "#LOW-MT-00312",
                (repo_copy / "i18n/reviewed-candidates.tsv").read_text(encoding="utf-8"),
            )
            rollback_result = ROLLBACK.rollback(stage_root, repo_copy)
            self.assertEqual(rollback_result["status"], "PASS")
            self.assertEqual(
                (repo_copy / "magica/js/event/EventArenaRankMatch/Utility.js").read_bytes(),
                source_before,
            )
            self.assertEqual(
                (repo_copy / "i18n/reviewed-candidates.tsv").read_bytes(),
                reviewed_before,
            )

        self.assertEqual(source_product.read_bytes(), source_before)
        self.assertEqual(reviewed_source.read_bytes(), reviewed_before)

    def test_03_filled_decision_tsv_cannot_use_blank_workbook_as_receipt(self):
        decisions_header, decisions = read_tsv(AUDIT / "dsv4_human_decisions.tsv")
        _, remaining = read_tsv(AUDIT / "pass20_remaining_manual_review.tsv")
        remaining_ids = {row["item_id"] for row in remaining}
        for row in decisions:
            if row["item_id"] in remaining_ids:
                row["human_decision"] = "approve-current"
                row["reviewer"] = "synthetic-contract-test"
                row["timestamp"] = "2026-08-15T12:00:00+08:00"
                row["final_value"] = row["current_cn"]
                row["human_revision"] = ""
                row["human_notes"] = ""
        with tempfile.TemporaryDirectory(prefix="pass20-blank-receipt-") as temp:
            temp_root = Path(temp)
            decisions_path = temp_root / "closed-decisions.tsv"
            write_tsv(decisions_path, decisions_header, decisions)
            with self.assertRaisesRegex(STAGE.StageError, "separate external copy"):
                STAGE.stage(
                    AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                    decisions_path,
                    AUDIT / "pass20_authority_resolutions.tsv",
                    AUDIT / "pass20_product_targets.json",
                    temp_root / "same-path-stage",
                    AUDIT / "pass20_human_review.xlsx",
                )
            blank_workbook = temp_root / "blank-review.xlsx"
            shutil.copy2(AUDIT / "pass20_human_review.xlsx", blank_workbook)
            stage_root = temp_root / "stage"
            with self.assertRaisesRegex(STAGE.StageError, "workbook itself must contain 199 closed decisions"):
                STAGE.stage(
                    AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                    decisions_path,
                    AUDIT / "pass20_authority_resolutions.tsv",
                    AUDIT / "pass20_product_targets.json",
                    stage_root,
                    blank_workbook,
                )
            self.assertFalse((stage_root / "magica").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
