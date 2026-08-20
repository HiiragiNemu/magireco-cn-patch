#!/usr/bin/env python3
"""Validate the one-sheet Pass20 workbook and optionally accept all returned final values."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import importlib.util
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys
import tempfile
from typing import Any
import zipfile
import xml.etree.ElementTree as ET

from pass20_review_contract import (
    AUTHORITY_EXCLUDED_ITEMS, AUTHORITY_RESOLUTIONS, DS_APPROVED_ITEMS,
    HUMAN_REVIEW_ITEMS, MACHINE_SOURCE_ITEMS, PRIORITY_ITEMS, SHADOWED_ITEMS,
    WORKBOOK_FILE_NAME, WORKBOOK_SHEET_NAME,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
DEFAULT_XLSX = AUDIT / WORKBOOK_FILE_NAME
DEFAULT_SOURCE = AUDIT / "pass20_remaining_manual_review.tsv"
DEFAULT_PRIORITY = AUDIT / "pass20_priority_manual_review.tsv"
DEFAULT_INVENTORY = AUDIT / "pass20_machine_source_inventory.tsv"
DEFAULT_SHADOW = AUDIT / "pass20_authority_shadowed_machine_items.tsv"
DEFAULT_RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
DEFAULT_SEALED = AUDIT / "dsv4_terminal_handoff/full_review.tsv"
DEFAULT_ADOPTIONS = AUDIT / "pass21_user_directed_suggested_adoptions.tsv"
DEFAULT_RECEIPT = AUDIT / "pass20_human_final_values.tsv"
DEFAULT_TARGETS = AUDIT / "pass20_product_targets.json"
SCHEMA = "magireco-cn-v26-translation-human-review-workbook/5"
EXPECTED_COUNTS = {
    "inventory": MACHINE_SOURCE_ITEMS,
    "human": HUMAN_REVIEW_ITEMS,
    "priority": PRIORITY_ITEMS,
    "approved": DS_APPROVED_ITEMS,
    "excluded": AUTHORITY_EXCLUDED_ITEMS,
    "authority": AUTHORITY_RESOLUTIONS,
    "shadowed": SHADOWED_ITEMS,
}
SHEETS = (WORKBOOK_SHEET_NAME,)
REVIEW_SHEET = WORKBOOK_SHEET_NAME
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
Q = lambda tag: f"{{{NS}}}{tag}"

HEADERS = (
    "日文原文", "旧中文", "最终中文", "__item_id", "__seed_origin",
    "__seed_final_sha256", "__source_text_sha256", "__source_record_sha256",
    "__target_contract_sha256", "__target_row_sha256", "__stable_business_key",
    "__target_manifest_index", "__schema_version", "__partition",
)
SOURCE_FIELDS = (
    "source_index", "batch_number", "item_id", "stable_business_key",
    "source_path", "source_key", "source_field", "review_kind", "allowed_action",
    "japanese_or_source_original", "old_cn", "current_cn", "parent_verdict",
    "suggested_cn", "parent_rationale", "role_verdicts", "role_details",
    "protected_authority_text", "product_write_allowed", "highest_authority_tier",
    "authority_status", "authority_evidence", "official_cn", "wiki_cn", "confirmed_human_cn",
)


def load_final_values_contract():
    path = Path(__file__).with_name("pass20_final_values_contract.py")
    spec = importlib.util.spec_from_file_location("pass20_final_values_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("final-values contract could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FINAL_VALUES = load_final_values_contract()
RECEIPT_FIELDS = FINAL_VALUES.FINAL_VALUE_FIELDS


class WorkbookImportError(RuntimeError):
    pass


def load_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file() or path.is_symlink():
        raise WorkbookImportError(f"TSV missing or unsafe: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise WorkbookImportError(f"TSV must be UTF-8-no-BOM with LF endings: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if not header or any(None in row for row in rows):
        raise WorkbookImportError(f"invalid TSV structure: {path}")
    return header, rows


def unique_by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result = {str(row.get("item_id", "")): row for row in rows}
    if "" in result or len(result) != len(rows):
        raise WorkbookImportError(f"{label} has a missing or duplicate item_id")
    return result


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_digest(value: object) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _column_number(reference: str) -> int:
    match = re.fullmatch(r"([A-Z]+)(\d+)", reference)
    if not match:
        raise WorkbookImportError(f"invalid cell reference: {reference}")
    number = 0
    for char in match.group(1):
        number = number * 26 + ord(char) - 64
    return number


def _row_number(reference: str) -> int:
    match = re.fullmatch(r"[A-Z]+(\d+)", reference)
    if not match:
        raise WorkbookImportError(f"invalid cell reference: {reference}")
    return int(match.group(1))


def _column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _shared_strings(package: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in package.namelist():
        return []
    root = ET.fromstring(package.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.iter(Q("t"))) for item in root.findall(Q("si"))]


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.get("t", "")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(Q("t")))
    value = cell.find(Q("v"))
    raw = "" if value is None or value.text is None else value.text
    if kind == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError) as exc:
            raise WorkbookImportError("invalid shared-string index") from exc
    if kind == "b":
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def _sheet_paths(package: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(package.read("xl/workbook.xml"))
    rels = ET.fromstring(package.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target", "") for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")}
    result: dict[str, str] = {}
    for sheet in workbook.findall(f"./{Q('sheets')}/{Q('sheet')}"):
        name = sheet.get("name", "")
        raw_target = targets.get(sheet.get(f"{{{REL_NS}}}id", ""), "")
        try:
            target = _safe_relationship_target("xl/workbook.xml", raw_target, "xl/worksheets/")
        except WorkbookImportError as exc:
            raise WorkbookImportError(f"unsafe worksheet relationship for {name!r}") from exc
        if not target.startswith("xl/worksheets/"):
            raise WorkbookImportError(f"unsafe worksheet relationship for {name!r}")
        if name in result or target not in package.namelist():
            raise WorkbookImportError(f"missing or duplicate worksheet: {name!r}")
        result[name] = target
    return result


def _safe_relationship_target(source_path: str, raw_target: str, required_prefix: str) -> str:
    if not raw_target or "\\" in raw_target:
        raise WorkbookImportError("empty or non-POSIX relationship target")
    if raw_target.startswith("/") or raw_target.startswith("xl/"):
        candidate = raw_target.lstrip("/")
    else:
        candidate = posixpath.join(posixpath.dirname(source_path), raw_target)
    normalized = posixpath.normpath(candidate)
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or not normalized.startswith(required_prefix):
        raise WorkbookImportError("relationship target escapes its expected package area")
    return normalized


def _require_table_ranges(package: zipfile.ZipFile, sheet_paths: dict[str, str]) -> None:
    expected = {REVIEW_SHEET: f"A1:N{HUMAN_REVIEW_ITEMS + 1}"}
    for sheet_name, table_ref in expected.items():
        sheet_path = sheet_paths[sheet_name]
        sheet_root = ET.fromstring(package.read(sheet_path))
        table_parts = sheet_root.findall(f"./{Q('tableParts')}/{Q('tablePart')}")
        if len(table_parts) != 1:
            raise WorkbookImportError(f"{sheet_name} must contain exactly one table")
        sheet_pure = PurePosixPath(sheet_path)
        rel_path = str(sheet_pure.parent / "_rels" / f"{sheet_pure.name}.rels")
        if rel_path not in package.namelist():
            raise WorkbookImportError(f"{sheet_name} table relationship is missing")
        rels = ET.fromstring(package.read(rel_path))
        targets = {
            rel.get("Id"): rel.get("Target", "")
            for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        raw_target = targets.get(table_parts[0].get(f"{{{REL_NS}}}id", ""), "")
        table_path = _safe_relationship_target(sheet_path, raw_target, "xl/tables/")
        if table_path not in package.namelist():
            raise WorkbookImportError(f"{sheet_name} table definition is missing")
        table = ET.fromstring(package.read(table_path))
        auto_filter = table.find(Q("autoFilter"))
        if table.get("ref") != table_ref or auto_filter is None or auto_filter.get("ref") != table_ref:
            raise WorkbookImportError(f"{sheet_name} table/filter range must be {table_ref}")


def _parse_sheet(package: zipfile.ZipFile, path: str, shared: list[str]) -> dict[str, Any]:
    root = ET.fromstring(package.read(path))
    cells: dict[str, str] = {}
    formulas: set[str] = set()
    styles: dict[str, int] = {}
    for cell in root.findall(f".//{Q('c')}"):
        ref = cell.get("r", "")
        if not ref or ref in cells:
            raise WorkbookImportError(f"missing or duplicate cell reference in {path}")
        cells[ref] = _cell_value(cell, shared)
        styles[ref] = int(cell.get("s", "0"))
        if cell.find(Q("f")) is not None:
            formulas.add(ref)
    return {"root": root, "cells": cells, "formulas": formulas, "styles": styles}


def _require_external_authority_ids_absent(
    sheets: dict[str, dict[str, Any]], external_item_ids: set[str]
) -> None:
    """Keep authority-resolved records entirely outside the human workbook."""
    pattern = re.compile("|".join(re.escape(item_id) for item_id in sorted(external_item_ids, key=len, reverse=True)))
    for sheet_name, sheet in sheets.items():
        for reference, value in sheet["cells"].items():
            matched = pattern.search(value)
            if matched is not None:
                raise WorkbookImportError(
                    f"external authority item appears in workbook: {matched.group(0)} at {sheet_name}!{reference}"
                )


def _styles_unlocked(package: zipfile.ZipFile) -> dict[int, bool]:
    root = ET.fromstring(package.read("xl/styles.xml"))
    cell_xfs = root.find(Q("cellXfs"))
    if cell_xfs is None:
        raise WorkbookImportError("XLSX has no cellXfs")
    result = {}
    for index, xf in enumerate(cell_xfs):
        protection = xf.find(Q("protection"))
        result[index] = protection is not None and protection.get("locked") == "0"
    return result


def _hidden_columns(sheet: dict[str, Any]) -> set[int]:
    cols = sheet["root"].find(Q("cols"))
    hidden: set[int] = set()
    for col in list(cols) if cols is not None else []:
        if col.get("hidden") == "1":
            hidden.update(range(int(col.get("min", "0")), int(col.get("max", "0")) + 1))
    return hidden


def _require_pane(sheet: dict[str, Any], label: str) -> None:
    pane = sheet["root"].find(f"./{Q('sheetViews')}/{Q('sheetView')}/{Q('pane')}")
    if pane is None or pane.get("state") != "frozen":
        raise WorkbookImportError(f"{label} freeze pane drifted")
    if pane.get("xSplit") not in {None, "0"} or pane.get("ySplit") != "1":
        raise WorkbookImportError(f"{label} freeze pane drifted")


def _require_workbook_ui(sheets: dict[str, dict[str, Any]], unlocked: dict[int, bool]) -> None:
    for name, sheet in sheets.items():
        protection = sheet["root"].find(Q("sheetProtection"))
        if protection is None:
            raise WorkbookImportError(f"{name} sheet protection is missing")
    sheet = sheets[REVIEW_SHEET]
    _require_pane(sheet, REVIEW_SHEET)
    if not set(range(4, 15)).issubset(_hidden_columns(sheet)):
        raise WorkbookImportError(f"{REVIEW_SHEET} hidden audit columns D:N drifted")
    for row in range(2, EXPECTED_COUNTS["human"] + 2):
        editable_ref = f"C{row}"
        if not unlocked.get(sheet["styles"].get(editable_ref, -1), False):
            raise WorkbookImportError(f"final Chinese cell is locked: {REVIEW_SHEET}!{editable_ref}")
        for column in "ABDEFGHIJKLMN":
            ref = f"{column}{row}"
            if unlocked.get(sheet["styles"].get(ref, -1), False):
                raise WorkbookImportError(f"immutable review cell is unlocked: {REVIEW_SHEET}!{ref}")


def _literal_equal(actual: str, expected: str) -> bool:
    actual = actual.replace("\r\n", "\n").replace("\r", "\n").rstrip(" \t\n")
    expected = expected.replace("\r\n", "\n").replace("\r", "\n").rstrip(" \t\n")
    return actual == expected or (expected.startswith("=") and actual == "'" + expected)


def _integer_cell(value: str, label: str) -> int:
    if not re.fullmatch(r"\d+(?:\.0+)?", value):
        raise WorkbookImportError(f"numeric cell drift: {label}")
    return int(float(value))


def _write_tsv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent) as stream:
        temp = Path(stream.name)
        writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def _sheet_data_rows(sheet: dict[str, Any], headers: tuple[str, ...], count: int, label: str) -> dict[str, int]:
    cells = sheet["cells"]
    actual_headers = tuple(cells.get(f"{_column_name(index)}1", "") for index in range(1, len(headers) + 1))
    if actual_headers != headers:
        raise WorkbookImportError(f"{label} workbook columns drifted")
    if sheet["formulas"].intersection(
        {f"{_column_name(column)}{row}" for column in range(1, len(headers) + 1) for row in range(1, count + 2)}
    ):
        raise WorkbookImportError(f"{label} data or audit cells contain a formula")
    nonempty_extra = [
        ref for ref, value in cells.items()
        if value and (_row_number(ref) > count + 1 or _column_number(ref) > len(headers))
    ]
    if nonempty_extra:
        raise WorkbookImportError(f"{label} workbook has unexpected data cells: {nonempty_extra[:3]}")
    row_by_id: dict[str, int] = {}
    for row_number in range(2, count + 2):
        item_id = cells.get(f"D{row_number}", "")
        if not item_id or item_id in row_by_id:
            raise WorkbookImportError(f"{label} has blank or duplicate stable ID")
        row_by_id[item_id] = row_number
    return row_by_id


def import_workbook(
    xlsx: Path,
    source_path: Path,
    sealed_path: Path,
    targets_path: Path,
    out_path: Path,
    *,
    priority_path: Path = DEFAULT_PRIORITY,
    inventory_path: Path = DEFAULT_INVENTORY,
    shadow_path: Path = DEFAULT_SHADOW,
    resolutions_path: Path = DEFAULT_RESOLUTIONS,
    adoptions_path: Path = DEFAULT_ADOPTIONS,
    accept_returned: bool = False,
    accept_rough_production: bool = False,
) -> dict[str, Any]:
    if accept_returned and accept_rough_production:
        raise WorkbookImportError("returned-workbook acceptance modes are mutually exclusive")
    source_header, source_rows = load_tsv(source_path)
    _priority_header, priority_rows = load_tsv(priority_path)
    _inventory_header, inventory_rows = load_tsv(inventory_path)
    _shadow_header, shadow_rows = load_tsv(shadow_path)
    _resolution_header, resolution_rows = load_tsv(resolutions_path)
    sealed_header, sealed_rows = load_tsv(sealed_path)
    _adoption_header, adoption_rows = load_tsv(adoptions_path)
    source = unique_by_id(source_rows, "human queue")
    priority = unique_by_id(priority_rows, "priority queue")
    inventory = unique_by_id(inventory_rows, "machine inventory")
    shadow = unique_by_id(shadow_rows, "higher-authority shadow")
    resolutions = unique_by_id(resolution_rows, "authority resolutions")
    sealed = unique_by_id(sealed_rows, "sealed review")
    adoptions = unique_by_id(adoption_rows, "user-directed suggested adoptions")
    actual_counts = {
        "inventory": len(inventory), "human": len(source), "priority": len(priority),
        "approved": len(source) - len(priority), "excluded": len(resolutions) + len(shadow),
        "authority": len(resolutions), "shadowed": len(shadow),
    }
    if actual_counts != EXPECTED_COUNTS:
        raise WorkbookImportError(f"review partition counts drifted: {actual_counts}")
    if not set(priority) < set(source):
        raise WorkbookImportError("priority queue is not a strict subset of the human queue")
    approved_ids = set(source) - set(priority)
    if any(source[item_id].get("parent_verdict") != "approved" for item_id in approved_ids):
        raise WorkbookImportError("non-priority human queue item is not DS-approved")
    if set(inventory) != set(source) | set(shadow) or set(source) & set(shadow):
        raise WorkbookImportError("1,589-item machine inventory partition drifted")
    if set(resolutions) & set(shadow):
        raise WorkbookImportError("authority and shadow exclusions overlap")
    if set(sealed) != set(source) | set(resolutions) | set(shadow):
        raise WorkbookImportError("1,912-item sealed partition drifted")
    if len(sealed_rows) != 1912:
        raise WorkbookImportError("sealed review must contain 1,912 unique items")
    if not set(SOURCE_FIELDS + ("source_text_sha256",)).issubset(sealed_header):
        raise WorkbookImportError("sealed source lacks immutable fields or source hash")
    for sealed_row in sealed_rows:
        item_id = sealed_row["item_id"]
        expected_text_hash = sha256(sealed_row["japanese_or_source_original"].encode("utf-8")).hexdigest()
        if sealed_row["source_text_sha256"] != expected_text_hash:
            raise WorkbookImportError(f"sealed source hash does not match source text: {item_id}")
    for item_id, row in source.items():
        sealed_row = sealed[item_id]
        for field in SOURCE_FIELDS:
            if row.get(field, "") != sealed_row.get(field, ""):
                raise WorkbookImportError(f"bound human source drift {field}: {item_id}")
    for item_id, row in shadow.items():
        allowed = row.get("product_write_allowed", "").lower()
        forbidden = row.get("product_write_forbidden", "").lower()
        if allowed != "false" and forbidden != "true":
            raise WorkbookImportError(f"shadowed item is not product-write-forbidden: {item_id}")
    if len(adoptions) != 29 or not set(adoptions) < set(source):
        raise WorkbookImportError("29-row user-directed suggested adoption set drifted")
    for item_id, adoption in adoptions.items():
        row = source[item_id]
        binding = {
            "source_index": row.get("source_index", ""),
            "stable_business_key": row.get("stable_business_key", ""),
            "source_key": row.get("source_key", ""),
            "source_text": row.get("japanese_or_source_original", ""),
            "current_cn": row.get("current_cn", ""),
            "ds_suggested_cn": row.get("suggested_cn", ""),
        }
        if any(adoption.get(field, "") != value for field, value in binding.items()):
            raise WorkbookImportError(f"user-directed suggestion adoption binding drifted: {item_id}")
        if not adoption.get("adopted_cn", ""):
            raise WorkbookImportError(f"user-directed adopted Chinese is empty: {item_id}")

    target_raw = targets_path.read_bytes()
    target_payload = json.loads(target_raw.decode("utf-8"))
    if target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1" or target_payload.get("status") != "PASS":
        raise WorkbookImportError("product target manifest schema or status drifted")
    target_rows = target_payload.get("items", [])
    if not isinstance(target_rows, list):
        raise WorkbookImportError("product target manifest items are invalid")
    targets = unique_by_id(target_rows, "product target manifest")
    if set(targets) != set(source):
        raise WorkbookImportError(
            f"product target manifest differs from the {HUMAN_REVIEW_ITEMS}-item human queue"
        )
    target_indices = {str(row.get("item_id", "")): index for index, row in enumerate(target_rows)}
    if "" in target_indices or len(target_indices) != len(target_rows):
        raise WorkbookImportError("product target manifest external index is not unique")
    summary = target_payload.get("summary", {})
    if (
        summary.get("items") != HUMAN_REVIEW_ITEMS
        or summary.get("maintenance_rows_bound") != HUMAN_REVIEW_ITEMS
    ):
        raise WorkbookImportError("product target manifest item count drifted")
    if summary.get("occurrence_collisions") != 0 or summary.get("unclassified_items") != 0:
        raise WorkbookImportError("product target manifest is not closed")
    target_contract_hash = sha256(target_raw).hexdigest()

    if not xlsx.is_file() or xlsx.is_symlink():
        raise WorkbookImportError(f"workbook missing or unsafe: {xlsx}")
    with zipfile.ZipFile(xlsx) as package:
        if package.testzip() is not None:
            raise WorkbookImportError("workbook CRC failure")
        names = package.namelist()
        if len(names) != len(set(names)):
            raise WorkbookImportError("workbook contains duplicate ZIP members")
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts:
                raise WorkbookImportError("unsafe workbook member path")
        paths = _sheet_paths(package)
        if tuple(paths) != SHEETS:
            raise WorkbookImportError(f"workbook sheets drifted: {tuple(paths)}")
        _require_table_ranges(package, paths)
        shared = _shared_strings(package)
        sheets = {name: _parse_sheet(package, paths[name], shared) for name in SHEETS}
        _require_workbook_ui(sheets, _styles_unlocked(package))

    expected_excluded = set(resolutions) | set(shadow)
    _require_external_authority_ids_absent(sheets, expected_excluded)

    expected_partitions = {item_id: ("priority" if item_id in priority else "approved") for item_id in source}
    parsed_receipts: dict[str, dict[str, str]] = {}
    sheet = sheets[REVIEW_SHEET]
    row_by_id = _sheet_data_rows(sheet, HEADERS, EXPECTED_COUNTS["human"], REVIEW_SHEET)
    if set(row_by_id) != set(source):
        raise WorkbookImportError(f"{REVIEW_SHEET} stable ID set drifted")
    for item_id, row_number in row_by_id.items():
        row = source[item_id]
        sealed_row = sealed[item_id]
        target = targets[item_id]
        suggested = row["suggested_cn"]
        adoption = adoptions.get(item_id)
        adopted_cn = adoption["adopted_cn"] if adoption else ""
        seed, seed_origin = FINAL_VALUES.seed_for_source(row, adopted_cn)
        if not row["japanese_or_source_original"] or not row["current_cn"] or not seed:
            raise WorkbookImportError(f"visible review text is empty: {item_id}")
        bound = {
            "A": row["japanese_or_source_original"],
            "B": row["current_cn"],
            "D": item_id,
            "E": seed_origin,
            "F": sha256(seed.encode("utf-8")).hexdigest(),
            "G": sealed_row["source_text_sha256"],
            "H": FINAL_VALUES.source_record_sha256(row),
            "I": target_contract_hash,
            "J": FINAL_VALUES.target_contract_sha256(target),
            "K": row["stable_business_key"],
            "L": str(target_indices[item_id]),
            "M": SCHEMA,
            "N": expected_partitions[item_id],
        }
        for column, expected in bound.items():
            actual = sheet["cells"].get(f"{column}{row_number}", "")
            if column == "L":
                if _integer_cell(actual, f"{item_id}:{column}") != int(expected):
                    raise WorkbookImportError(f"bound workbook field drift {column}: {item_id}")
            elif not _literal_equal(actual, expected):
                raise WorkbookImportError(f"bound workbook field drift {column}: {item_id}")
        final_value = sheet["cells"].get(f"C{row_number}", "")
        if not final_value:
            raise WorkbookImportError(f"final Chinese is empty: {item_id}")
        if final_value == "<DELETE>" and row["current_cn"] != "<DELETE>":
            raise WorkbookImportError(f"reserved deletion token is forbidden as review text: {item_id}")
        if accept_rough_production and not _literal_equal(final_value, seed):
            raise WorkbookImportError(
                "rough-production acceptance only permits the bound prefilled final value; "
                f"edited text requires later human review: {item_id}"
            )
        if not accept_returned and not accept_rough_production:
            if not _literal_equal(final_value, seed):
                raise WorkbookImportError(
                    f"template verification found an edited final value; use explicit returned-workbook acceptance: {item_id}"
                )
            continue
        provenance_mode = (
            FINAL_VALUES.ROUGH_PRODUCTION_MODE
            if accept_rough_production else FINAL_VALUES.HUMAN_REVIEW_MODE
        )
        parsed_receipts[item_id] = FINAL_VALUES.expected_final_value_row(
            row, target, final_value, adopted_cn, provenance_mode,
        )

    accepted = accept_returned or accept_rough_production
    if accepted:
        priority_rank = {"correction": 0, "unresolved": 1, "manual-required": 2}
        priority_order = sorted(
            priority,
            key=lambda item_id: (
                priority_rank.get(source[item_id].get("parent_verdict", ""), 9),
                int(source[item_id].get("source_index", "0")), item_id,
            ),
        )
        approved_order = sorted(
            set(source) - set(priority),
            key=lambda item_id: (int(source[item_id].get("source_index", "0")), item_id),
        )
        _write_tsv(out_path, list(RECEIPT_FIELDS), [parsed_receipts[item_id] for item_id in priority_order + approved_order])
    prefilled_suggestion = len(adoptions)
    return {
        "schema": "magireco-cn-v26-translation-xlsx-import/5",
        "status": "PASS",
        "workbook_rows": EXPECTED_COUNTS["human"],
        "priority_rows": EXPECTED_COUNTS["priority"],
        "approved_machine_rows": EXPECTED_COUNTS["approved"],
        "workbook_excluded_rows": 0,
        "external_authority_audit_rows": EXPECTED_COUNTS["excluded"],
        "higher_authority_shadowed_rows": EXPECTED_COUNTS["shadowed"],
        "prefilled_from_suggestion": prefilled_suggestion,
        "prefilled_from_current": EXPECTED_COUNTS["human"] - prefilled_suggestion,
        "returned_workbook_accepted": accepted,
        "provenance_mode": (
            FINAL_VALUES.ROUGH_PRODUCTION_MODE if accept_rough_production
            else FINAL_VALUES.HUMAN_REVIEW_MODE if accept_returned
            else "template"
        ),
        "receipt_rows_written": len(parsed_receipts),
        "pending_in_workbook": EXPECTED_COUNTS["human"] - len(parsed_receipts),
        "target_contract_sha256": target_contract_hash,
        "output": str(out_path) if accepted else "",
        "product_tree_writes": False,
        "protected_text_changes": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--priority", type=Path, default=DEFAULT_PRIORITY)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--shadow", type=Path, default=DEFAULT_SHADOW)
    parser.add_argument("--authority-resolutions", type=Path, default=DEFAULT_RESOLUTIONS)
    parser.add_argument("--sealed", type=Path, default=DEFAULT_SEALED)
    parser.add_argument("--suggested-adoptions", type=Path, default=DEFAULT_ADOPTIONS)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--out", type=Path, default=DEFAULT_RECEIPT)
    acceptance = parser.add_mutually_exclusive_group()
    acceptance.add_argument(
        "--accept-returned-workbook", action="store_true",
        help="treat every non-empty final Chinese cell as the user's returned whole-workbook confirmation",
    )
    acceptance.add_argument(
        "--accept-prefilled-rough-production", action="store_true",
        help=(
            "accept only unchanged bound prefilled values for a user-directed rough build; "
            "retain machine provenance and do not claim human review"
        ),
    )
    args = parser.parse_args(argv)
    try:
        result = import_workbook(
            args.xlsx, args.source, args.sealed, args.targets, args.out,
            priority_path=args.priority, inventory_path=args.inventory, shadow_path=args.shadow,
            resolutions_path=args.authority_resolutions, adoptions_path=args.suggested_adoptions,
            accept_returned=args.accept_returned_workbook,
            accept_rough_production=args.accept_prefilled_rough_production,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (WorkbookImportError, OSError, UnicodeError, ValueError, zipfile.BadZipFile, ET.ParseError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
