#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
import csv
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
import warnings
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
WORKBOOK = AUDIT / "magireco_v26_translation_review_1565.xlsx"
SOURCE = AUDIT / "pass20_remaining_manual_review.tsv"
PRIORITY = AUDIT / "pass20_priority_manual_review.tsv"
INVENTORY = AUDIT / "pass20_machine_source_inventory.tsv"
SHADOW = AUDIT / "pass20_authority_shadowed_machine_items.tsv"
RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
SEALED = AUDIT / "dsv4_terminal_handoff/full_review.tsv"
DECISIONS = AUDIT / "dsv4_human_decisions.tsv"
TARGETS = AUDIT / "pass20_product_targets.json"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
Q = lambda tag: f"{{{NS}}}{tag}"


def load_tool():
    path = ROOT / "tools/import-pass20-human-review-xlsx.py"
    spec = importlib.util.spec_from_file_location("pass20_xlsx_import", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


def rewrite_workbook(source: Path, target: Path, mutate) -> None:
    with zipfile.ZipFile(source) as package:
        infos = package.infolist()
        blobs = {info.filename: package.read(info.filename) for info in infos}
        paths = TOOL._sheet_paths(package)
    sheets = {name: ET.fromstring(blobs[path]) for name, path in paths.items()}
    mutate(sheets)
    for name, root in sheets.items():
        blobs[paths[name]] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(target, "w") as package:
        for info in infos:
            package.writestr(info, blobs[info.filename])


def set_text(sheet: ET.Element, ref: str, value: str) -> None:
    cell = next((node for node in sheet.findall(f".//{Q('c')}") if node.get("r") == ref), None)
    if cell is None:
        raise AssertionError(f"cell absent: {ref}")
    for child in list(cell):
        if child.tag in {Q("v"), Q("is"), Q("f")}:
            cell.remove(child)
    cell.set("t", "inlineStr")
    inline = ET.SubElement(cell, Q("is"))
    text = ET.SubElement(inline, Q("t"))
    text.text = value


def set_formula(sheet: ET.Element, ref: str, formula: str) -> None:
    cell = next(node for node in sheet.findall(f".//{Q('c')}") if node.get("r") == ref)
    for child in list(cell):
        if child.tag in {Q("v"), Q("is"), Q("f")}:
            cell.remove(child)
    cell.attrib.pop("t", None)
    ET.SubElement(cell, Q("f")).text = formula


def _move_row(row: ET.Element, destination: int) -> ET.Element:
    moved = deepcopy(row)
    moved.set("r", str(destination))
    for cell in moved.findall(Q("c")):
        column = re.match(r"[A-Z]+", cell.get("r", ""))
        assert column is not None
        cell.set("r", f"{column.group(0)}{destination}")
    return moved


def swap_rows(sheet: ET.Element, first: int, second: int) -> None:
    data = sheet.find(Q("sheetData"))
    assert data is not None
    children = list(data)
    first_index = next(index for index, row in enumerate(children) if row.get("r") == str(first))
    second_index = next(index for index, row in enumerate(children) if row.get("r") == str(second))
    first_row, second_row = children[first_index], children[second_index]
    data[first_index] = _move_row(second_row, first)
    data[second_index] = _move_row(first_row, second)


def rewrite_tsv(source: Path, target: Path, mutate) -> None:
    with source.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)
    mutate(rows)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parsed_workbook(path: Path) -> dict[str, dict]:
    with zipfile.ZipFile(path) as package:
        paths = TOOL._sheet_paths(package)
        shared = TOOL._shared_strings(package)
        return {name: TOOL._parse_sheet(package, member, shared) for name, member in paths.items()}


class Pass20WorkbookImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells = parsed_workbook(WORKBOOK)

    def invoke(
        self,
        workbook: Path,
        output: Path,
        *,
        source: Path = SOURCE,
        targets: Path = TARGETS,
        decisions: Path = DECISIONS,
    ):
        return TOOL.import_workbook(
            workbook, source, SEALED, decisions, targets, output,
            priority_path=PRIORITY, inventory_path=INVENTORY,
            shadow_path=SHADOW, resolutions_path=RESOLUTIONS,
        )

    def assert_rejected(self, mutate, message: str):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "bad.xlsx"
            rewrite_workbook(WORKBOOK, fixture, mutate)
            with self.assertRaisesRegex(TOOL.WorkbookImportError, message):
                self.invoke(fixture, Path(temp) / "out.tsv")

    def test_01_blank_workbook_is_valid_and_byte_preserving(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "decisions.tsv"
            result = self.invoke(WORKBOOK, output)
            self.assertEqual(result["schema"], "magireco-cn-v26-translation-xlsx-import/3")
            self.assertEqual(result["workbook_rows"], 1565)
            self.assertEqual(result["priority_rows"], 199)
            self.assertEqual(result["approved_machine_rows"], 1366)
            self.assertEqual(result["workbook_excluded_rows"], 0)
            self.assertEqual(result["external_authority_audit_rows"], 347)
            self.assertEqual(result["higher_authority_shadowed_rows"], 24)
            self.assertEqual(result["decisions_imported"], 0)
            self.assertEqual(output.read_bytes(), DECISIONS.read_bytes())

    def test_02_chinese_labels_map_and_machine_approval_is_explicit(self):
        priority_cells = self.cells["①优先审核199"]["cells"]
        approved_cells = self.cells["②DS已审1366"]["cells"]
        suggestion_row = next(row for row in range(2, 201) if priority_cells.get(f"E{row}", ""))
        other_rows = [row for row in range(2, 201) if row != suggestion_row][:2]
        approved_row = 2
        expected_suggestion = priority_cells[f"E{suggestion_row}"]
        suggestion_id = priority_cells[f"B{suggestion_row}"]
        revision_id = priority_cells[f"B{other_rows[0]}"]
        unresolved_id = priority_cells[f"B{other_rows[1]}"]
        approved_id = approved_cells[f"B{approved_row}"]

        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "filled.xlsx"
            output = Path(temp) / "decisions.tsv"

            def mutate(sheets):
                set_text(sheets["说明"], "B18", "人工审校员")
                set_text(sheets["说明"], "B19", "2026-08-16T23:30:00+08:00")
                set_text(sheets["①优先审核199"], f"O{suggestion_row}", "采用建议")
                set_text(sheets["①优先审核199"], f"O{other_rows[0]}", "自行修改")
                set_text(sheets["①优先审核199"], f"P{other_rows[0]}", "人工修订后的中文")
                set_text(sheets["①优先审核199"], f"O{other_rows[1]}", "暂时无法判断")
                set_text(sheets["①优先审核199"], f"Q{other_rows[1]}", "需要更多剧情上下文")
                set_text(sheets["②DS已审1366"], f"O{approved_row}", "保留现译")

            rewrite_workbook(WORKBOOK, fixture, mutate)
            result = self.invoke(fixture, output)
            self.assertEqual(result["decisions_imported"], 4)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = {row["item_id"]: row for row in csv.DictReader(stream, delimiter="\t")}
            self.assertEqual(rows[suggestion_id]["human_decision"], "revise")
            self.assertEqual(rows[suggestion_id]["review_status"], "human-reviewed-revised")
            self.assertEqual(rows[suggestion_id]["final_value"], expected_suggestion)
            self.assertIn("人工采用DS建议", rows[suggestion_id]["human_notes"])
            self.assertEqual(rows[revision_id]["final_value"], "人工修订后的中文")
            self.assertEqual(rows[revision_id]["review_status"], "human-reviewed-revised")
            self.assertEqual(rows[unresolved_id]["human_decision"], "unresolved")
            self.assertEqual(rows[unresolved_id]["review_status"], "human-reviewed-unresolved")
            self.assertEqual(rows[unresolved_id]["final_value"], "")
            self.assertEqual(rows[approved_id]["human_decision"], "approve-current")
            self.assertEqual(rows[approved_id]["review_status"], "human-reviewed-approved-current")
            self.assertIn("机器来源、人工已批准", rows[approved_id]["human_notes"])

    def test_03_physical_row_sorting_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "sorted.xlsx"
            output = Path(temp) / "decisions.tsv"
            rewrite_workbook(WORKBOOK, fixture, lambda sheets: swap_rows(sheets["②DS已审1366"], 2, 3))
            result = self.invoke(fixture, output)
            self.assertEqual(result["decisions_imported"], 0)
            self.assertEqual(output.read_bytes(), DECISIONS.read_bytes())

    def test_04_stable_id_tamper_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["①优先审核199"], "B2", "BAD-ID"), "stable ID set drifted")

    def test_05_duplicate_id_is_rejected(self):
        item_id = self.cells["①优先审核199"]["cells"]["B2"]
        self.assert_rejected(lambda sheets: set_text(sheets["①优先审核199"], "B3", item_id), "blank or duplicate stable ID")

    def test_06_source_record_hash_tamper_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["①优先审核199"], "S2", "0" * 64), "visible source field drift S")

    def test_07_source_record_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.tsv"
            rewrite_tsv(SOURCE, source, lambda rows: rows[0].update({"effective_cn": rows[0]["effective_cn"] + "漂移"}))
            with self.assertRaisesRegex(TOOL.WorkbookImportError, "visible source field drift S"):
                self.invoke(WORKBOOK, Path(temp) / "out.tsv", source=source)

    def test_08_target_contract_hash_binds_raw_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            targets = Path(temp) / "targets.json"
            targets.write_bytes(TARGETS.read_bytes() + b"\n")
            with self.assertRaisesRegex(TOOL.WorkbookImportError, "visible source field drift T"):
                self.invoke(WORKBOOK, Path(temp) / "out.tsv", targets=targets)

    def test_09_target_visible_drift_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["①优先审核199"], "L2", "magica/unknown.js"), "visible source field drift L")

    def test_09a_target_row_hash_tamper_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["①优先审核199"], "U2", "0" * 64), "visible source field drift U")

    def test_09b_stable_business_key_tamper_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["①优先审核199"], "V2", "bad#stable/key"), "visible source field drift V")

    def test_09c_target_manifest_index_tamper_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["①优先审核199"], "W2", "999999"), "visible source field drift W")

    def test_10_formula_in_human_cell_is_rejected(self):
        self.assert_rejected(lambda sheets: set_formula(sheets["①优先审核199"], "P2", "1+1"), "contain a formula")

    def test_11_authority_rows_are_external_only_and_not_editable(self):
        editable = {
            self.cells[sheet]["cells"][f"B{row}"]
            for sheet, count in (("①优先审核199", 199), ("②DS已审1366", 1366))
            for row in range(2, count + 2)
        }
        with SHADOW.open(encoding="utf-8", newline="") as stream:
            shadow = {row["item_id"] for row in csv.DictReader(stream, delimiter="\t")}
        with RESOLUTIONS.open(encoding="utf-8", newline="") as stream:
            resolutions = {row["item_id"] for row in csv.DictReader(stream, delimiter="\t")}
        self.assertTrue(shadow.isdisjoint(editable))
        self.assertTrue(resolutions.isdisjoint(editable))
        self.assertEqual(set(self.cells), set(TOOL.SHEETS))
        external_id = sorted(shadow | resolutions)[0]
        self.assert_rejected(
            lambda sheets: set_text(sheets["说明"], "B35", external_id),
            "external authority item appears in workbook",
        )

    def test_12_reserved_deletion_token_is_rejected(self):
        def mutate(sheets):
            set_text(sheets["说明"], "B18", "人工审校员")
            set_text(sheets["说明"], "B19", "2026-08-16T23:30:00+08:00")
            set_text(sheets["①优先审核199"], "O2", "自行修改")
            set_text(sheets["①优先审核199"], "P2", "<DELETE>")
        self.assert_rejected(mutate, "reserved deletion token")

    def test_13_blank_decision_with_value_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["①优先审核199"], "P2", "未作决定的值"), "blank decision carries output")

    def test_14_duplicate_zip_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "duplicate.xlsx"
            with zipfile.ZipFile(WORKBOOK) as source:
                infos = source.infolist()
                blobs = {info.filename: source.read(info.filename) for info in infos}
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(fixture, "w") as package:
                    for info in infos:
                        package.writestr(info, blobs[info.filename])
                    package.writestr("xl/workbook.xml", blobs["xl/workbook.xml"])
            with self.assertRaisesRegex(TOOL.WorkbookImportError, "duplicate ZIP members"):
                self.invoke(fixture, Path(temp) / "out.tsv")


if __name__ == "__main__":
    unittest.main(verbosity=2)
