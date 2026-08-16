#!/usr/bin/env python3
"""End-to-end contract tests for the guarded Pass20 product staging chain."""

from __future__ import annotations

import csv
from copy import deepcopy
from hashlib import sha256
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
        shared = IMPORTER._shared_strings(package)
        parsed = {
            name: IMPORTER._parse_sheet(package, path, shared) for name, path in paths.items()
        }
    sheets = {name: ET.fromstring(blobs[path]) for name, path in paths.items()}
    set_xlsx_text(sheets["说明"], "B18", "synthetic-contract-test")
    set_xlsx_text(sheets["说明"], "B19", "2026-08-15T12:00:00+08:00")
    decision_by_id = {row["item_id"]: row for row in rows}
    seen: set[str] = set()
    for sheet_name, (_partition, count) in IMPORTER.EDIT_SHEETS.items():
        cells = parsed[sheet_name]["cells"]
        for sequence in range(2, count + 2):
            item_id = cells.get(f"B{sequence}", "")
            row = decision_by_id[item_id]
            seen.add(item_id)
            if row["item_id"] in {"LOW-MT-00312", "LOW-MT-00322"}:
                set_xlsx_text(sheets[sheet_name], f"O{sequence}", "自行修改")
                set_xlsx_text(sheets[sheet_name], f"P{sequence}", row["final_value"])
            else:
                set_xlsx_text(sheets[sheet_name], f"O{sequence}", "保留现译")
    if seen != set(decision_by_id):
        raise AssertionError("synthetic workbook item partition drifted")
    for name, root in sheets.items():
        blobs[paths[name]] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(target, "w") as package:
        for info in infos:
            package.writestr(info, blobs[info.filename])


class Pass20ProductStageTests(unittest.TestCase):
    def test_00_dynamic_target_contract_and_structure_gate(self):
        rows = [
            {
                "item_id": "GLOBAL", "maintenance_scope": "global",
                "application_allowed": True, "occurrences": [{"path": "js/a.js"}],
            },
            {
                "item_id": "OVERRIDE", "maintenance_scope": "override",
                "application_allowed": False, "occurrences": [],
            },
            {
                "item_id": "FRAGMENT", "maintenance_scope": "fragment",
                "application_allowed": True, "occurrences": [{"path": "js/b.js"}],
            },
        ]
        summary = {
            "items": 3, "maintenance_rows_bound": 3, "exact_runtime_items": 2,
            "maintenance_only_items": 1, "runtime_occurrences": 2,
            "occurrence_collisions": 0, "unclassified_items": 0,
        }
        contract = STAGE.derive_target_contract(rows, summary)
        self.assertEqual(contract["materialization_items"], 3)
        self.assertEqual((contract["global_items"], contract["override_items"], contract["fragment_items"]), (1, 1, 1))
        STAGE.validate_translation_structure("OK", "获得{0}<br><%= name %>", "取得{0}<br><%= name %>")
        with self.assertRaisesRegex(STAGE.StageError, "placeholder structure drift"):
            STAGE.validate_translation_structure("BAD", "获得{0}", "获得{1}")
        with self.assertRaisesRegex(STAGE.StageError, "escape structure drift"):
            STAGE.validate_translation_structure("BAD-ESCAPE", r"第一行\n第二行", "第一行第二行")

        source = {
            "source_index": "1", "batch_number": "1", "item_id": "ITEM",
            "stable_business_key": "table#key/candidate_cn", "source_path": "i18n/table.tsv",
            "source_key": "key", "source_field": "candidate_cn",
            "japanese_or_source_original": "原文", "old_cn": "旧译", "current_cn": "现译",
            "source_text_sha256": sha256("原文".encode("utf-8")).hexdigest(),
        }
        queue = {field: source[field] for field in STAGE.SOURCE_BINDING_FIELDS}
        STAGE.validate_queue_source_bindings([queue], [source])
        with self.assertRaisesRegex(STAGE.StageError, "binding drifted"):
            STAGE.validate_queue_source_bindings([{**queue, "current_cn": "漂移"}], [source])
        with self.assertRaisesRegex(STAGE.StageError, "text hash drifted"):
            STAGE.validate_queue_source_bindings([queue], [{**source, "source_text_sha256": "0" * 64}])

        shadow = STAGE.load_shadowed_contract(
            AUDIT / "pass20_authority_shadowed_machine_items.json"
        )
        self.assertEqual(shadow["count"], 24)
        self.assertEqual(shadow["runtime_effective_occurrences"], 171)
        self.assertEqual(shadow["runtime_machine_occurrences"], 150)
        self.assertEqual(shadow["authority_materialization_items"], 2)
        self.assertEqual(shadow["authority_materialized_occurrences"], 9)
        self.assertEqual(shadow["authority_verified_occurrences"], 10)
        with tempfile.TemporaryDirectory(prefix="pass20-shadow-contract-") as temp:
            bad_shadow = json.loads(
                (AUDIT / "pass20_authority_shadowed_machine_items.json").read_text(encoding="utf-8")
            )
            bad_shadow["schema"] = "magireco-cn-pass20-authority-shadowed-machine-items/1"
            bad_path = Path(temp) / "shadow.json"
            bad_path.write_text(json.dumps(bad_shadow), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(STAGE.StageError, "schema"):
                STAGE.load_shadowed_contract(bad_path)

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
        self.assertEqual(len(remaining_ids), len(remaining))
        for row in decisions:
            if row["item_id"] not in remaining_ids:
                continue
            row["human_decision"] = "approve-current"
            row["reviewer"] = "synthetic-contract-test"
            row["timestamp"] = "2026-08-15T12:00:00+08:00"
            row["final_value"] = row["current_cn"]
            row["human_revision"] = ""
            row["human_notes"] = "机器来源、人工已批准"
            row["review_status"] = "human-reviewed-approved-current"
        revised = next(row for row in decisions if row["item_id"] == "LOW-MT-00312")
        revised["human_decision"] = "revise"
        revised["final_value"] = "+c+a+l+e"
        revised["human_revision"] = "+c+a+l+e"
        revised["human_notes"] = "人工自行修订"
        revised["review_status"] = "human-reviewed-revised"
        revised_global = next(row for row in decisions if row["item_id"] == "LOW-MT-00322")
        revised_global["human_decision"] = "revise"
        revised_global["final_value"] = revised_global["current_cn"][:-1] + "？"
        revised_global["human_revision"] = revised_global["final_value"]
        revised_global["human_notes"] = "人工自行修订"
        revised_global["review_status"] = "human-reviewed-revised"

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
                AUDIT / "magireco_v26_translation_review_1565.xlsx",
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
            contract = report["review_contract"]
            self.assertEqual(report["reviewed_candidates_appended"], len(remaining))
            self.assertEqual(report["canonical_human_review_items"], len(remaining))
            self.assertEqual(contract["human_review_items"], len(remaining))
            self.assertEqual(
                contract["machine_inventory_items"],
                contract["materialization_items"] + contract["higher_authority_shadowed_items"],
            )
            self.assertEqual(report["shadowed_low_tier_candidates_written"], 0)
            self.assertEqual(report["shadowed_product_writes"], 0)
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
                Path("magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx"),
                Path("magica/i18n_audit/release_v26_authority/pass20_remaining_manual_review.tsv"),
                Path("magica/i18n_audit/release_v26_authority/pass20_product_targets.json"),
                Path("magica/i18n_audit/release_v26_authority/pass20_authority_shadowed_machine_items.json"),
                Path("magica/i18n_audit/release_v26_authority/pass20_authority_resolutions.tsv"),
            ):
                target = repo_copy / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, target)
            promotion = PROMOTE.promote(stage_root, repo_copy)
            self.assertEqual(promotion["status"], "PASS")
            self.assertEqual(promotion["canonical_human_review_items"], len(remaining))
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
                row["human_notes"] = "机器来源、人工已批准"
                row["review_status"] = "human-reviewed-approved-current"
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
                    AUDIT / "magireco_v26_translation_review_1565.xlsx",
                )
            blank_workbook = temp_root / "blank-review.xlsx"
            shutil.copy2(AUDIT / "magireco_v26_translation_review_1565.xlsx", blank_workbook)
            stage_root = temp_root / "stage"
            with self.assertRaisesRegex(
                STAGE.StageError, rf"workbook itself must contain {len(remaining_ids)} closed decisions"
            ):
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
