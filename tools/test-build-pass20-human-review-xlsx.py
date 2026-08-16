#!/usr/bin/env python3

from __future__ import annotations

from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import tempfile
import time
import unittest
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("pass20_workbook_builder", ROOT / "tools/build-pass20-human-review-xlsx.py")
IMPORTER = load_module("pass20_workbook_importer", ROOT / "tools/import-pass20-human-review-xlsx.py")


def normalized_package(path: Path) -> str:
    """Hash logical bytes after canonicalizing generated relationship IDs."""
    document_rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    digest = sha256()
    with zipfile.ZipFile(path) as package:
        names = sorted(package.namelist())
        if len(names) != len(set(names)) or package.testzip() is not None:
            raise AssertionError("invalid XLSX package")
        blobs = {name: package.read(name) for name in names}
    for rel_path in sorted(name for name in names if name.endswith(".rels")):
        rel_root = ET.fromstring(blobs[rel_path])
        relationships = sorted(
            list(rel_root),
            key=lambda node: (node.get("Type", ""), node.get("Target", ""), node.get("TargetMode", "")),
        )
        id_map = {node.get("Id", ""): f"rId{index}" for index, node in enumerate(relationships, 1)}
        for index, node in enumerate(relationships, 1):
            node.set("Id", f"rId{index}")
        rel_root[:] = relationships
        blobs[rel_path] = ET.tostring(rel_root, encoding="utf-8", xml_declaration=True)
        if rel_path == "_rels/.rels":
            continue
        rel_dir, rel_name = posixpath.split(rel_path)
        source_path = posixpath.join(posixpath.dirname(rel_dir), rel_name.removesuffix(".rels"))
        if source_path not in blobs:
            continue
        source_root = ET.fromstring(blobs[source_path])
        relationship_id = f"{{{document_rel_ns}}}id"
        for node in source_root.iter():
            if node.get(relationship_id, "") in id_map:
                node.set(relationship_id, id_map[node.get(relationship_id, "")])
        blobs[source_path] = ET.tostring(source_root, encoding="utf-8", xml_declaration=True)
    for name in names:
        blob = blobs[name]
        if name == "docProps/core.xml":
            blob = re.sub(
                rb"<dcterms:(?:created|modified)[^>]*>[^<]*</dcterms:(?:created|modified)>",
                b"",
                blob,
            )
        digest.update(name.encode("utf-8") + b"\0" + blob + b"\0")
    return digest.hexdigest()


class Pass20WorkbookBuildTests(unittest.TestCase):
    def test_01_tracked_builder_uses_artifact_tool_and_new_filename(self):
        source = (ROOT / "tools/build-pass20-human-review-xlsx.mjs").read_text(encoding="utf-8")
        self.assertIn("@oai/artifact-tool", source)
        self.assertIn("magireco_v26_translation_review_1565.xlsx", source)
        self.assertNotIn("pass20_human_review.xlsx", source)
        self.assertNotIn("__target_row_json", source)
        self.assertIn("__target_manifest_index", source)
        self.assertNotIn("openpyxl", source.lower())

    def test_02_existing_workbook_has_four_bound_sheets_and_ui_contract(self):
        result = BUILDER.verify_outputs()
        self.assertEqual(result["counts"]["workbook_rows"], 1565)
        with zipfile.ZipFile(BUILDER.CANONICAL) as package:
            paths = IMPORTER._sheet_paths(package)
            self.assertEqual(tuple(paths), IMPORTER.SHEETS)
            shared = IMPORTER._shared_strings(package)
            parsed = {
                name: IMPORTER._parse_sheet(package, member, shared)
                for name, member in paths.items()
            }
            approved = parsed["②DS已审1366"]
            priority = parsed["①优先审核199"]
        self.assertEqual(
            approved["cells"]["F2"],
            "DS已审通过／仍属机器来源，待人工确认",
        )
        self.assertEqual(approved["cells"]["W1"], "__target_manifest_index")
        self.assertEqual(priority["cells"]["W1"], "__target_manifest_index")
        max_cell_chars = max(
            len(value)
            for sheet in parsed.values()
            for value in sheet["cells"].values()
        )
        self.assertLessEqual(max_cell_chars, 32767)

    def test_03_two_artifact_tool_builds_are_logically_deterministic(self):
        try:
            BUILDER.find_node()
            BUILDER.find_artifact_tool()
        except BUILDER.BuildError as exc:
            self.skipTest(str(exc))
        first = BUILDER.build()
        first_hash = normalized_package(BUILDER.CANONICAL)
        second = BUILDER.build()
        second_hash = normalized_package(BUILDER.CANONICAL)
        self.assertEqual(first["counts"], second["counts"])
        self.assertEqual(first["target_contract_sha256"], second["target_contract_sha256"])
        self.assertEqual(first_hash, second_hash)
        self.assertEqual(BUILDER.CANONICAL.read_bytes(), BUILDER.DELIVERY.read_bytes())

    def test_04_excel_com_sort_save_close_import_when_available(self):
        if os.name != "nt":
            self.skipTest("Excel COM is Windows-only")
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            self.skipTest("PowerShell is unavailable")
        def excel_pids() -> set[int]:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", "@(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object Id) -join ','"],
                text=True, capture_output=True, timeout=20,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return set()
            return {int(value) for value in result.stdout.strip().split(",") if value}

        def stop_new_excel(before: set[int]) -> None:
            new_pids = excel_pids() - before
            if not new_pids:
                return
            subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", f"Stop-Process -Id {','.join(str(value) for value in sorted(new_pids))} -Force"],
                text=True, capture_output=True, timeout=20,
            )

        before_pids = excel_pids()
        if before_pids:
            self.skipTest("pre-existing Excel session detected; COM test did not touch it")
        script = r'''
$ErrorActionPreference = 'Stop'
$excel = $null
$book = $null
try {
    try { $excel = New-Object -ComObject Excel.Application }
    catch { Write-Output 'EXCEL_NOT_AVAILABLE'; exit 3 }
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $workbooks = $excel.Workbooks
    $book = $workbooks.Open($env:PASS20_XLSX_INPUT, 0, $true)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbooks)
    $worksheets = $book.Worksheets
    foreach ($name in @('①优先审核199', '②DS已审1366')) {
        $sheet = $worksheets.Item($name)
        $listObjects = $sheet.ListObjects
        $table = $listObjects.Item(1)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($listObjects)
        $tableRange = $table.Range
        $tableColumns = $tableRange.Columns
        if ($tableColumns.Count -ne 25) { throw "$name table does not bind A:Y" }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($tableColumns)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($tableRange)
        $sort = $table.Sort
        $sort.SortFields.Clear()
        $keyColumn = $table.ListColumns.Item(2)
        $keyRange = $keyColumn.DataBodyRange
        [void]$sort.SortFields.Add($keyRange, 0, 2)
        $sort.Header = 1
        $sort.MatchCase = $false
        $sort.Orientation = 1
        $sort.Apply()
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($keyRange)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($keyColumn)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($sort)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($table)
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($sheet)
    }
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($worksheets)
    $book.SaveAs($env:PASS20_XLSX_OUTPUT, 51)
    $book.Close($false)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($book)
    $book = $null
    if (-not (Test-Path -LiteralPath $env:PASS20_XLSX_OUTPUT)) { throw 'SaveAs output missing' }
    Write-Output 'EXCEL_COM_SORT_PASS'
}
catch {
    [Console]::Error.WriteLine($_.Exception.ToString())
    exit 1
}
finally {
    if ($book -ne $null) {
        try { $book.Close($false) } catch {}
        try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($book) } catch {}
    }
    if ($excel -ne $null) {
        try { $excel.Quit() } catch {}
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
'''
        original = BUILDER.CANONICAL.read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            saved = Path(temp) / "excel-com-saveas.xlsx"
            env = dict(os.environ)
            env["PASS20_XLSX_INPUT"] = str(BUILDER.CANONICAL)
            env["PASS20_XLSX_OUTPUT"] = str(saved)
            try:
                completed = subprocess.run(
                    [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=120,
                )
            except subprocess.TimeoutExpired:
                stop_new_excel(before_pids)
                self.fail("Excel COM Sort/SaveAs/Close timed out; test-created Excel was terminated")
            if completed.returncode == 3 and "EXCEL_NOT_AVAILABLE" in completed.stdout:
                self.skipTest("Microsoft Excel COM is unavailable")
            if completed.returncode != 0:
                stop_new_excel(before_pids)
            self.assertEqual(
                completed.returncode, 0,
                msg=f"Excel COM failed\nstdout={completed.stdout}\nstderr={completed.stderr}",
            )
            self.assertIn("EXCEL_COM_SORT_PASS", completed.stdout)
            self.assertTrue(saved.is_file())
            with zipfile.ZipFile(BUILDER.CANONICAL) as original_package, zipfile.ZipFile(saved) as saved_package:
                original_paths = IMPORTER._sheet_paths(original_package)
                saved_paths = IMPORTER._sheet_paths(saved_package)
                original_shared = IMPORTER._shared_strings(original_package)
                saved_shared = IMPORTER._shared_strings(saved_package)
                for sheet_name in ("①优先审核199", "②DS已审1366"):
                    original_sheet = IMPORTER._parse_sheet(
                        original_package, original_paths[sheet_name], original_shared,
                    )
                    saved_sheet = IMPORTER._parse_sheet(
                        saved_package, saved_paths[sheet_name], saved_shared,
                    )
                    self.assertNotEqual(original_sheet["cells"]["B2"], saved_sheet["cells"]["B2"])
            output = Path(temp) / "saved-decisions.tsv"
            result = IMPORTER.import_workbook(
                saved,
                AUDIT / "pass20_remaining_manual_review.tsv",
                AUDIT / "dsv4_terminal_handoff/full_review.tsv",
                AUDIT / "dsv4_human_decisions.tsv",
                AUDIT / "pass20_product_targets.json",
                output,
                priority_path=AUDIT / "pass20_priority_manual_review.tsv",
                inventory_path=AUDIT / "pass20_machine_source_inventory.tsv",
                shadow_path=AUDIT / "pass20_authority_shadowed_machine_items.tsv",
                resolutions_path=AUDIT / "pass20_authority_resolutions.tsv",
            )
            self.assertEqual(result["decisions_imported"], 0)
        for _attempt in range(20):
            lingering = excel_pids() - before_pids
            if not lingering:
                break
            time.sleep(0.5)
        lingering = excel_pids() - before_pids
        if lingering:
            stop_new_excel(before_pids)
            self.fail(f"Excel COM process did not exit cleanly: {sorted(lingering)}")
        self.assertEqual(BUILDER.CANONICAL.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
