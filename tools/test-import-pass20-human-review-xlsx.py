#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
import csv
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
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
TARGETS = AUDIT / "pass20_product_targets.json"
ADOPTIONS = AUDIT / "pass21_user_directed_suggested_adoptions.tsv"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
Q = lambda tag: f"{{{NS}}}{tag}"


def load_tool():
    path = ROOT / "tools/import-pass20-human-review-xlsx.py"
    spec = importlib.util.spec_from_file_location("pass20_xlsx_import", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
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
    ET.SubElement(inline, Q("t")).text = value


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


def parsed_workbook(path: Path) -> dict[str, dict]:
    with zipfile.ZipFile(path) as package:
        paths = TOOL._sheet_paths(package)
        shared = TOOL._shared_strings(package)
        return {name: TOOL._parse_sheet(package, member, shared) for name, member in paths.items()}


class Pass20WorkbookImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells = parsed_workbook(WORKBOOK)[TOOL.REVIEW_SHEET]["cells"]

    def invoke(self, workbook: Path, output: Path, *, accept: bool = False):
        return TOOL.import_workbook(
            workbook, SOURCE, SEALED, TARGETS, output,
            priority_path=PRIORITY, inventory_path=INVENTORY,
            shadow_path=SHADOW, resolutions_path=RESOLUTIONS,
            adoptions_path=ADOPTIONS,
            accept_returned=accept,
        )

    def assert_rejected(self, mutate, message: str, *, accept: bool = False):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "bad.xlsx"
            rewrite_workbook(WORKBOOK, fixture, mutate)
            with self.assertRaisesRegex(TOOL.WorkbookImportError, message):
                self.invoke(fixture, Path(temp) / "out.tsv", accept=accept)

    def test_01_template_is_prefilled_and_verification_writes_no_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "decisions.tsv"
            result = self.invoke(WORKBOOK, output)
            self.assertEqual(result["schema"], "magireco-cn-v26-translation-xlsx-import/5")
            self.assertEqual(result["workbook_rows"], 1565)
            self.assertEqual(result["prefilled_from_suggestion"], 29)
            self.assertEqual(result["prefilled_from_current"], 1536)
            self.assertEqual(result["receipt_rows_written"], 0)
            self.assertEqual(result["pending_in_workbook"], 1565)
            self.assertFalse(result["returned_workbook_accepted"])
            self.assertFalse(output.exists())

    def test_02_explicit_acceptance_turns_every_final_value_into_a_receipt_row(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "decisions.tsv"
            result = self.invoke(WORKBOOK, output, accept=True)
            self.assertEqual(result["receipt_rows_written"], 1565)
            self.assertEqual(result["pending_in_workbook"], 0)
            with output.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream, delimiter="\t")
                self.assertEqual(tuple(reader.fieldnames or ()), TOOL.RECEIPT_FIELDS)
                rows = {row["item_id"]: row for row in reader}
            suggestion_id = next(
                self.cells[f"D{row}"] for row in range(2, 1567)
                if self.cells[f"E{row}"] == "adopted_suggestion"
            )
            current_id = next(
                self.cells[f"D{row}"] for row in range(2, 1567)
                if self.cells[f"E{row}"] == "current"
            )
            self.assertEqual(rows[suggestion_id]["seed_origin"], "adopted_suggestion")
            self.assertEqual(rows[suggestion_id]["final_value"], rows[suggestion_id]["seed_cn"])
            self.assertEqual(rows[suggestion_id]["review_status"], "human-confirmed-machine-suggestion-adopted")
            self.assertEqual(rows[suggestion_id]["final_origin"], "machine-suggestion")
            self.assertEqual(rows[suggestion_id]["machine_translated"], "true")
            self.assertEqual(rows[current_id]["seed_origin"], "current")
            self.assertEqual(rows[current_id]["final_value"], rows[current_id]["current_cn"])
            self.assertEqual(rows[current_id]["review_status"], "human-confirmed-machine-origin-retained")
            self.assertEqual(rows[current_id]["final_origin"], "machine-current")
            self.assertEqual(rows[current_id]["machine_translated"], "unknown")
            self.assertNotIn("reviewer", rows[current_id])
            self.assertNotIn("timestamp", rows[current_id])
            self.assertNotIn("human_decision", rows[current_id])

    def test_03_manual_final_value_is_accepted_without_decision_or_notes_columns(self):
        row = next(row for row in range(2, 1567) if self.cells[f"E{row}"] == "current")
        item_id = self.cells[f"D{row}"]
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "edited.xlsx"
            output = Path(temp) / "decisions.tsv"
            rewrite_workbook(WORKBOOK, fixture, lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], f"C{row}", "人工最终译文"))
            result = self.invoke(fixture, output, accept=True)
            self.assertEqual(result["receipt_rows_written"], 1565)
            with output.open(encoding="utf-8", newline="") as stream:
                decisions = {entry["item_id"]: entry for entry in csv.DictReader(stream, delimiter="\t")}
            self.assertEqual(decisions[item_id]["final_value"], "人工最终译文")
            self.assertEqual(decisions[item_id]["review_status"], "human-revised")
            self.assertEqual(decisions[item_id]["final_origin"], "human-revision")
            self.assertEqual(decisions[item_id]["machine_translated"], "false")

    def test_04_physical_row_sorting_is_bound_by_hidden_item_id(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "sorted.xlsx"
            output = Path(temp) / "decisions.tsv"
            rewrite_workbook(WORKBOOK, fixture, lambda sheets: swap_rows(sheets[TOOL.REVIEW_SHEET], 2, 1566))
            result = self.invoke(fixture, output)
            self.assertEqual(result["receipt_rows_written"], 0)
            self.assertFalse(output.exists())

    def test_05_template_mode_rejects_an_edit_and_writes_nothing(self):
        row = next(row for row in range(2, 1567) if self.cells[f"E{row}"] == "current")
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "edited.xlsx"
            output = Path(temp) / "out.tsv"
            rewrite_workbook(WORKBOOK, fixture, lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], f"C{row}", "未显式接受"))
            with self.assertRaisesRegex(TOOL.WorkbookImportError, "explicit returned-workbook acceptance"):
                self.invoke(fixture, output)
            self.assertFalse(output.exists())

    def test_06_stable_id_and_binding_tamper_are_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], "D2", "BAD-ID"), "stable ID set drifted")
        item_id = self.cells["D2"]
        self.assert_rejected(lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], "D3", item_id), "blank or duplicate stable ID")
        for column in "EFGHIJKMN":
            with self.subTest(column=column):
                self.assert_rejected(
                    lambda sheets, column=column: set_text(sheets[TOOL.REVIEW_SHEET], f"{column}2", "tampered"),
                    f"bound workbook field drift {column}",
                )
        self.assert_rejected(lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], "L2", "999999"), "bound workbook field drift L")

    def test_07_visible_source_formula_and_empty_final_are_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], "A2", "源文漂移"), "bound workbook field drift A")
        self.assert_rejected(lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], "B2", "旧译漂移"), "bound workbook field drift B")
        self.assert_rejected(lambda sheets: set_formula(sheets[TOOL.REVIEW_SHEET], "C2", "1+1"), "contain a formula")
        self.assert_rejected(lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], "C2", ""), "final Chinese is empty", accept=True)

    def test_08_reserved_deletion_token_is_rejected(self):
        self.assert_rejected(
            lambda sheets: set_text(sheets[TOOL.REVIEW_SHEET], "C2", "<DELETE>"),
            "reserved deletion token", accept=True,
        )

    def test_09_authority_resolved_ids_are_absent_from_every_sheet(self):
        visible = {self.cells[f"D{row}"] for row in range(2, 1567)}
        for path in (SHADOW, RESOLUTIONS):
            with path.open(encoding="utf-8", newline="") as stream:
                external = {row["item_id"] for row in csv.DictReader(stream, delimiter="\t")}
            self.assertFalse(visible & external)


if __name__ == "__main__":
    unittest.main(verbosity=2)
