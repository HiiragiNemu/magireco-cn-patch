#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
WORKBOOK = AUDIT / "pass20_human_review.xlsx"
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


class Pass20WorkbookImportTests(unittest.TestCase):
    def invoke(self, workbook: Path, output: Path):
        return TOOL.import_workbook(
            workbook,
            AUDIT / "pass20_remaining_manual_review.tsv",
            AUDIT / "dsv4_terminal_handoff/full_review.tsv",
            AUDIT / "dsv4_human_decisions.tsv",
            AUDIT / "pass20_product_targets.json",
            output,
        )

    def test_01_blank_workbook_is_valid_and_byte_preserving(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "decisions.tsv"
            result = self.invoke(WORKBOOK, output)
            self.assertEqual(result["workbook_rows"], 199)
            self.assertEqual(result["decisions_imported"], 0)
            self.assertEqual(output.read_bytes(), (AUDIT / "dsv4_human_decisions.tsv").read_bytes())

    def test_02_chinese_labels_map_to_internal_decisions(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "filled.xlsx"
            output = Path(temp) / "decisions.tsv"
            def mutate(sheets):
                set_text(sheets["说明"], "B13", "人工审校员")
                set_text(sheets["说明"], "B14", "2026-08-15T20:30:00+08:00")
                set_text(sheets["审核"], "O2", "保留现译")
                set_text(sheets["审核"], "Q2", "已核对上下文")
                set_text(sheets["审核"], "O3", "修改译文")
                set_text(sheets["审核"], "P3", "修订后的中文")
                set_text(sheets["审核"], "O4", "暂时无法判断")
                set_text(sheets["审核"], "Q4", "需要更多剧情上下文")
            rewrite_workbook(WORKBOOK, fixture, mutate)
            result = self.invoke(fixture, output)
            self.assertEqual(result["decisions_imported"], 3)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = {row["item_id"]: row for row in csv.DictReader(stream, delimiter="\t")}
            first = rows["LOW-MT-00312"]
            self.assertEqual(first["human_decision"], "approve-current")
            self.assertEqual(first["final_value"], first["current_cn"])
            second = rows["LOW-MT-00317"]
            self.assertEqual(second["human_decision"], "revise")
            self.assertEqual(second["final_value"], "修订后的中文")
            self.assertEqual(second["human_revision"], "修订后的中文")
            third = rows["LOW-MT-00322"]
            self.assertEqual(third["human_decision"], "unresolved")
            self.assertEqual(third["final_value"], "")

    def assert_rejected(self, mutate, message: str):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "bad.xlsx"
            rewrite_workbook(WORKBOOK, fixture, mutate)
            with self.assertRaisesRegex(TOOL.WorkbookImportError, message):
                self.invoke(fixture, Path(temp) / "out.tsv")

    def test_03_stable_id_tamper_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["审核"], "B2", "BAD-ID"), "visible source field drift")

    def test_04_row_count_drift_is_rejected(self):
        def mutate(sheets):
            data = sheets["审核"].find(Q("sheetData"))
            row = next(node for node in data.findall(Q("row")) if node.get("r") == "200")
            data.remove(row)
        self.assert_rejected(mutate, "visible source field drift|numeric cell drift|review input cell is locked")

    def test_05_sealed_source_hash_tamper_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["审核"], "object-storage", "0" * 64), "sealed source hash mismatch")

    def test_06_product_target_drift_is_rejected(self):
        self.assert_rejected(lambda sheets: set_text(sheets["审核"], "L2", "magica/unknown.js"), "visible source field drift")

    def test_07_formula_in_human_cell_is_rejected(self):
        def mutate(sheets):
            cell = next(node for node in sheets["审核"].findall(f".//{Q('c')}") if node.get("r") == "P2")
            cell.append(ET.Element(Q("f")))
            cell.find(Q("f")).text = "1+1"
        self.assert_rejected(mutate, "contain a formula")

    def test_08_source_hash_is_recomputed_not_only_compared(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workbook = root / "fake-hash.xlsx"
            sealed = root / "full-review.tsv"
            fake = "0" * 64
            rewrite_workbook(WORKBOOK, workbook, lambda sheets: set_text(sheets["审核"], "object-storage", fake))
            rewrite_tsv(
                AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                sealed,
                lambda rows: next(row for row in rows if row["item_id"] == "LOW-MT-00312").update(
                    {"source_text_sha256": fake}
                ),
            )
            with self.assertRaisesRegex(TOOL.WorkbookImportError, "source hash does not match source text"):
                TOOL.import_workbook(
                    workbook,
                    AUDIT / "pass20_remaining_manual_review.tsv",
                    sealed,
                    AUDIT / "dsv4_human_decisions.tsv",
                    AUDIT / "pass20_product_targets.json",
                    root / "out.tsv",
                )

    def test_09_non_queue_immutable_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            decisions = root / "decisions.tsv"
            rewrite_tsv(
                AUDIT / "dsv4_human_decisions.tsv",
                decisions,
                lambda rows: rows[0].update({"current_cn": rows[0]["current_cn"] + "漂移"}),
            )
            with self.assertRaisesRegex(TOOL.WorkbookImportError, "full decision immutable field drift current_cn"):
                TOOL.import_workbook(
                    WORKBOOK,
                    AUDIT / "pass20_remaining_manual_review.tsv",
                    AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                    decisions,
                    AUDIT / "pass20_product_targets.json",
                    root / "out.tsv",
                )

    def test_10_duplicate_zip_member_is_rejected(self):
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

    def test_11_reserved_deletion_token_is_rejected(self):
        def mutate(sheets):
            set_text(sheets["说明"], "B13", "人工审校员")
            set_text(sheets["说明"], "B14", "2026-08-15T20:30:00+08:00")
            set_text(sheets["审核"], "O2", "修改译文")
            set_text(sheets["审核"], "P2", "<DELETE>")
        self.assert_rejected(mutate, "reserved deletion token")



if __name__ == "__main__":
    unittest.main(verbosity=2)
