#!/usr/bin/env python3
"""Validate the 1,565-row v26 review workbook and merge decisions by stable item ID."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys
import tempfile
from typing import Any
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
DEFAULT_XLSX = AUDIT / "magireco_v26_translation_review_1565.xlsx"
DEFAULT_SOURCE = AUDIT / "pass20_remaining_manual_review.tsv"
DEFAULT_PRIORITY = AUDIT / "pass20_priority_manual_review.tsv"
DEFAULT_INVENTORY = AUDIT / "pass20_machine_source_inventory.tsv"
DEFAULT_SHADOW = AUDIT / "pass20_authority_shadowed_machine_items.tsv"
DEFAULT_RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
DEFAULT_SEALED = AUDIT / "dsv4_terminal_handoff/full_review.tsv"
DEFAULT_DECISIONS = AUDIT / "dsv4_human_decisions.tsv"
DEFAULT_TARGETS = AUDIT / "pass20_product_targets.json"
SCHEMA = "magireco-cn-v26-translation-human-review-workbook/2"
EXPECTED_COUNTS = {
    "inventory": 1589,
    "human": 1565,
    "priority": 199,
    "approved": 1366,
    "excluded": 347,
    "authority": 323,
    "shadowed": 24,
}
SHEETS = ("说明", "①优先审核199", "②DS已审1366", "只读排除347")
EDIT_SHEETS = {"①优先审核199": ("priority", 199), "②DS已审1366": ("approved", 1366)}
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
Q = lambda tag: f"{{{NS}}}{tag}"

HEADERS = (
    "序号", "稳定ID", "原文（日文/源文）", "当前中文", "建议中文", "审查状态", "审查说明（含DS原始理由）",
    "维护层类型", "维护表", "原文键", "路径前缀", "产品目标路径", "匹配次数", "上下文片段",
    "人工决定", "最终中文", "人工备注", "__source_text_sha256", "__source_record_sha256",
    "__target_contract_sha256", "__target_row_sha256", "__stable_business_key", "__target_manifest_index", "__schema_version", "__partition",
)
EXCLUDED_HEADERS = (
    "序号", "稳定ID", "排除原因", "原文（日文/源文）", "机器候选", "高权威／最终中文", "权威层级", "权威证据",
    "来源位置", "产品回填状态", "__source_record_sha256", "__excluded_row_sha256", "__excluded_row_json", "__schema_version",
)
DECISION_LABELS = {
    "保留现译": "approve-current",
    "采用建议": "adopt-suggestion",
    "自行修改": "revise",
    "暂时无法判断": "unresolved",
}
VERDICT_LABELS = {
    "correction": "DS发现错误／建议修正但尚未应用",
    "unresolved": "DS未确定／需人工判断",
    "manual-required": "尚未完成DS审查／需人工判断",
    "approved": "DS已审通过／仍属机器来源，待人工确认",
}
SOURCE_FIELDS = (
    "source_index", "batch_number", "item_id", "stable_business_key",
    "source_path", "source_key", "source_field", "review_kind", "allowed_action",
    "japanese_or_source_original", "old_cn", "current_cn", "parent_verdict",
    "suggested_cn", "parent_rationale", "role_verdicts", "role_details",
    "protected_authority_text", "product_write_allowed", "highest_authority_tier",
    "authority_status", "authority_evidence", "official_cn", "wiki_cn", "confirmed_human_cn",
)
DECISION_FIELDS = ("human_decision", "reviewer", "timestamp", "final_value", "human_revision", "human_notes")
ISO_8601 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


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
    expected = {
        "①优先审核199": "A1:Y200",
        "②DS已审1366": "A1:Y1367",
        "只读排除347": "A1:N348",
    }
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


def _require_pane(sheet: dict[str, Any], label: str, *, instruction: bool = False) -> None:
    pane = sheet["root"].find(f"./{Q('sheetViews')}/{Q('sheetView')}/{Q('pane')}")
    if pane is None or pane.get("state") != "frozen":
        raise WorkbookImportError(f"{label} freeze pane drifted")
    if instruction:
        if pane.get("ySplit") != "2":
            raise WorkbookImportError(f"{label} freeze pane drifted")
    elif pane.get("xSplit") != "2" or pane.get("ySplit") != "1":
        raise WorkbookImportError(f"{label} freeze pane drifted")


def _require_workbook_ui(
    sheets: dict[str, dict[str, Any]], unlocked: dict[int, bool], row_counts: dict[str, int]
) -> None:
    for name, sheet in sheets.items():
        protection = sheet["root"].find(Q("sheetProtection"))
        if protection is None:
            raise WorkbookImportError(f"{name} sheet protection is missing")
    instruction = sheets["说明"]
    _require_pane(instruction, "说明", instruction=True)
    for ref in ("B18", "B19"):
        if not unlocked.get(instruction["styles"].get(ref, -1), False):
            raise WorkbookImportError(f"instruction input cell is locked: {ref}")
    for name, count in row_counts.items():
        sheet = sheets[name]
        _require_pane(sheet, name)
        if not set(range(18, 26)).issubset(_hidden_columns(sheet)):
            raise WorkbookImportError(f"{name} hidden audit columns R:Y drifted")
        for row in range(2, count + 2):
            for column in "OPQ":
                ref = f"{column}{row}"
                if not unlocked.get(sheet["styles"].get(ref, -1), False):
                    raise WorkbookImportError(f"review input cell is locked: {name}!{ref}")
            for column in "ABCDEFGHIJKLMNRSTUVWXY":
                ref = f"{column}{row}"
                if unlocked.get(sheet["styles"].get(ref, -1), False):
                    raise WorkbookImportError(f"immutable review cell is unlocked: {name}!{ref}")
        validations = sheet["root"].find(Q("dataValidations"))
        expected_range = f"O2:O{count + 1}"
        matched = False
        for validation in list(validations) if validations is not None else []:
            formula = validation.find(Q("formula1"))
            if validation.get("sqref") == expected_range and formula is not None:
                values = formula.text or ""
                matched = all(label in values for label in DECISION_LABELS)
        if not matched:
            raise WorkbookImportError(f"{name} Chinese decision dropdown drifted")
    readonly = sheets["只读排除347"]
    _require_pane(readonly, "只读排除347")
    if not set(range(11, 15)).issubset(_hidden_columns(readonly)):
        raise WorkbookImportError("只读排除347 hidden audit columns K:N drifted")
    for row in range(2, EXPECTED_COUNTS["excluded"] + 2):
        for column in "ABCDEFGHIJKLMN":
            ref = f"{column}{row}"
            if unlocked.get(readonly["styles"].get(ref, -1), False):
                raise WorkbookImportError(f"read-only exclusion cell is unlocked: {ref}")


def _literal_equal(actual: str, expected: str) -> bool:
    actual = actual.replace("\r\n", "\n").replace("\r", "\n").rstrip(" \t\n")
    expected = expected.replace("\r\n", "\n").replace("\r", "\n").rstrip(" \t\n")
    return actual == expected or (expected.startswith("=") and actual == "'" + expected)


def _integer_cell(value: str, label: str) -> int:
    if not re.fullmatch(r"\d+(?:\.0+)?", value):
        raise WorkbookImportError(f"numeric cell drift: {label}")
    return int(float(value))


def _validate_iso(value: str) -> None:
    if not ISO_8601.fullmatch(value):
        raise WorkbookImportError("review timestamp must be an ISO 8601 string with timezone")
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def _write_tsv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent) as stream:
        temp = Path(stream.name)
        writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def _review_explanation(row: dict[str, str]) -> str:
    verdict = row["parent_verdict"]
    if verdict == "approved":
        prefix = "DS审查认为当前译文可接受，但它仍是机器来源；只有人工选择“保留现译”后，才记录为人工已批准。"
    elif verdict == "correction":
        prefix = "DS审查发现当前译文可能有误，请重点核对建议中文和实际上下文。"
    elif verdict == "unresolved":
        prefix = "DS证据不足，请人工结合原文和实际使用位置判断。"
    else:
        prefix = "此前未完成DS审查，请人工直接判断中文语义。"
    rationale = row.get("parent_rationale", "")
    return prefix + (("\n\nDS原始理由：" + rationale) if rationale else "")


def _target_display(target: dict[str, Any]) -> tuple[str, str]:
    paths = target.get("product_target_paths") or target.get("declared_product_paths") or []
    contexts = target.get("context_snippets") or []
    return (
        "\n".join(str(value) for value in paths),
        "\n".join(str(value) for value in contexts).rstrip(" \r\n"),
    )


def _first(mapping: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key, "")
        if value:
            return value
    return ""


def _excluded_expected(
    item_id: str,
    sealed: dict[str, str],
    metadata: dict[str, str],
    category: str,
) -> tuple[dict[str, str], dict[str, object]]:
    if category == "authority-resolved":
        reason = "已有官方／Wiki／确认人工等高权威裁决"
        machine_candidate = sealed.get("old_cn", "") or sealed.get("current_cn", "")
        authority_value = metadata.get("final_value", "")
        authority_tier = metadata.get("authority_tier", "")
        evidence = metadata.get("evidence", "")
    else:
        reason = "机器候选已被更高权威值遮蔽"
        machine_candidate = _first(metadata, "machine_candidate", "low_tier_candidate", "candidate_cn") or sealed.get("old_cn", "")
        authority_value = _first(
            metadata, "authority_value", "selected_value", "effective_cn", "final_value", "protected_authority_text"
        ) or sealed.get("protected_authority_text", "") or sealed.get("current_cn", "")
        authority_tier = _first(metadata, "authority_tier", "selected_authority_tier", "highest_authority_tier")
        evidence = _first(metadata, "evidence", "authority_evidence", "selected_authority_evidence")
    payload = {"category": category, "sealed": sealed, "metadata": metadata}
    visible = {
        "B": item_id, "C": reason, "D": sealed.get("japanese_or_source_original", ""),
        "E": machine_candidate, "F": authority_value, "G": authority_tier, "H": evidence,
        "I": f"{sealed.get('source_path', '')}#{sealed.get('source_key', '')}", "J": "禁止机器候选回填",
        "K": json_digest(sealed), "L": json_digest(payload), "M": canonical_json(payload), "N": SCHEMA,
    }
    return visible, payload


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
    sequences: set[int] = set()
    for row_number in range(2, count + 2):
        item_id = cells.get(f"B{row_number}", "")
        if not item_id or item_id in row_by_id:
            raise WorkbookImportError(f"{label} has blank or duplicate stable ID")
        row_by_id[item_id] = row_number
        sequences.add(_integer_cell(cells.get(f"A{row_number}", ""), f"{label}!A{row_number}"))
    if sequences != set(range(1, count + 1)):
        raise WorkbookImportError(f"{label} display sequence drifted")
    return row_by_id


def import_workbook(
    xlsx: Path,
    source_path: Path,
    sealed_path: Path,
    decisions_path: Path,
    targets_path: Path,
    out_path: Path,
    *,
    priority_path: Path = DEFAULT_PRIORITY,
    inventory_path: Path = DEFAULT_INVENTORY,
    shadow_path: Path = DEFAULT_SHADOW,
    resolutions_path: Path = DEFAULT_RESOLUTIONS,
) -> dict[str, Any]:
    source_header, source_rows = load_tsv(source_path)
    _priority_header, priority_rows = load_tsv(priority_path)
    _inventory_header, inventory_rows = load_tsv(inventory_path)
    _shadow_header, shadow_rows = load_tsv(shadow_path)
    _resolution_header, resolution_rows = load_tsv(resolutions_path)
    sealed_header, sealed_rows = load_tsv(sealed_path)
    decision_header, decision_rows = load_tsv(decisions_path)
    source = unique_by_id(source_rows, "human queue")
    priority = unique_by_id(priority_rows, "priority queue")
    inventory = unique_by_id(inventory_rows, "machine inventory")
    shadow = unique_by_id(shadow_rows, "higher-authority shadow")
    resolutions = unique_by_id(resolution_rows, "authority resolutions")
    sealed = unique_by_id(sealed_rows, "sealed review")
    decisions = unique_by_id(decision_rows, "full decision TSV")
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
    if len(sealed_rows) != 1912 or len(decision_rows) != 1912 or set(decisions) != set(sealed):
        raise WorkbookImportError("sealed and decision TSVs must contain the same 1,912 unique items")
    if not set(decision_header).issubset(source_header):
        raise WorkbookImportError("human queue does not preserve all full decision TSV columns")
    if not set(SOURCE_FIELDS + ("source_text_sha256",)).issubset(sealed_header):
        raise WorkbookImportError("sealed source lacks immutable fields or source hash")
    if not set(SOURCE_FIELDS + DECISION_FIELDS).issubset(decision_header):
        raise WorkbookImportError("full decision TSV lacks immutable or decision fields")
    if [row["item_id"] for row in sealed_rows] != [row["item_id"] for row in decision_rows]:
        raise WorkbookImportError("full decision order differs from sealed source")
    for sealed_row, decision in zip(sealed_rows, decision_rows):
        item_id = sealed_row["item_id"]
        for field in SOURCE_FIELDS:
            if decision[field] != sealed_row[field]:
                raise WorkbookImportError(f"full decision immutable field drift {field}: {item_id}")
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

    target_raw = targets_path.read_bytes()
    target_payload = json.loads(target_raw.decode("utf-8"))
    if target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1" or target_payload.get("status") != "PASS":
        raise WorkbookImportError("product target manifest schema or status drifted")
    target_rows = target_payload.get("items", [])
    if not isinstance(target_rows, list):
        raise WorkbookImportError("product target manifest items are invalid")
    targets = unique_by_id(target_rows, "product target manifest")
    if set(targets) != set(source):
        raise WorkbookImportError("product target manifest differs from the 1,565-item human queue")
    target_indices = {str(row.get("item_id", "")): index for index, row in enumerate(target_rows)}
    if "" in target_indices or len(target_indices) != len(target_rows):
        raise WorkbookImportError("product target manifest external index is not unique")
    summary = target_payload.get("summary", {})
    if summary.get("items") != 1565 or summary.get("maintenance_rows_bound") != 1565:
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
        _require_workbook_ui(sheets, _styles_unlocked(package), {name: count for name, (_partition, count) in EDIT_SHEETS.items()})

    if sheets["说明"]["formulas"].intersection({"B18", "B19"}):
        raise WorkbookImportError("reviewer or timestamp cell contains a formula")
    reviewer = sheets["说明"]["cells"].get("B18", "").strip()
    timestamp = sheets["说明"]["cells"].get("B19", "").strip()

    expected_sheet_ids = {"①优先审核199": set(priority), "②DS已审1366": approved_ids}
    parsed_decisions: dict[str, dict[str, str]] = {}
    for sheet_name, (partition, count) in EDIT_SHEETS.items():
        sheet = sheets[sheet_name]
        row_by_id = _sheet_data_rows(sheet, HEADERS, count, sheet_name)
        if set(row_by_id) != expected_sheet_ids[sheet_name]:
            raise WorkbookImportError(f"{sheet_name} stable ID set drifted")
        for item_id, row_number in row_by_id.items():
            row = source[item_id]
            sealed_row = sealed[item_id]
            target = targets[item_id]
            paths_text, contexts = _target_display(target)
            visible = {
                "B": item_id, "C": row["japanese_or_source_original"], "D": row["current_cn"],
                "E": row["suggested_cn"], "F": VERDICT_LABELS[row["parent_verdict"]],
                "G": _review_explanation(row), "H": str(target.get("maintenance_layer_type", "")),
                "I": str(target.get("maintenance_table", "")), "J": row["source_key"],
                "K": str(target.get("path_prefix") or "（全局）"), "L": paths_text,
                "M": str(target.get("match_count", 0)),
                "N": (str(target.get("match_status", "")) + "\n" + contexts).rstrip(" \r\n"),
                "R": sealed_row["source_text_sha256"], "S": json_digest(row),
                "T": target_contract_hash, "U": json_digest(target),
                "V": row["stable_business_key"], "W": str(target_indices[item_id]), "X": SCHEMA, "Y": partition,
            }
            for column, expected in visible.items():
                actual = sheet["cells"].get(f"{column}{row_number}", "")
                if column in {"M", "W"}:
                    if _integer_cell(actual, f"{item_id}:{column}") != int(expected):
                        raise WorkbookImportError(f"visible source field drift {column}: {item_id}")
                elif not _literal_equal(actual, expected):
                    raise WorkbookImportError(f"visible source field drift {column}: {item_id}")
            label = sheet["cells"].get(f"O{row_number}", "").strip()
            final_value = sheet["cells"].get(f"P{row_number}", "")
            notes = sheet["cells"].get(f"Q{row_number}", "").strip()
            if not label:
                if final_value or notes:
                    raise WorkbookImportError(f"blank decision carries output: {item_id}")
                continue
            action = DECISION_LABELS.get(label)
            if action is None:
                raise WorkbookImportError(f"unknown decision label for {item_id}: {label!r}")
            if not reviewer or not timestamp:
                raise WorkbookImportError("reviewer and ISO timestamp are required for decided rows")
            _validate_iso(timestamp)
            if action == "approve-current":
                if final_value and final_value != row["current_cn"]:
                    raise WorkbookImportError(f"keep-current row has a changed final value: {item_id}")
                final_value = row["current_cn"]
                decision = "approve-current"
                human_revision = ""
                source_note = "机器来源、人工已批准"
                review_status = "human-reviewed-approved-current"
            elif action == "adopt-suggestion":
                suggestion = row["suggested_cn"]
                if not suggestion:
                    raise WorkbookImportError(f"adopt-suggestion row has no DS suggestion: {item_id}")
                if final_value and final_value != suggestion:
                    raise WorkbookImportError(f"adopt-suggestion row changed the suggestion: {item_id}")
                final_value = suggestion
                decision = "revise"
                human_revision = suggestion
                source_note = "人工采用DS建议"
                review_status = "human-reviewed-revised"
            elif action == "revise":
                if not final_value or final_value == row["current_cn"]:
                    raise WorkbookImportError(f"revision requires a changed final value: {item_id}")
                decision = "revise"
                human_revision = final_value
                source_note = "人工自行修订"
                review_status = "human-reviewed-revised"
            else:
                if final_value:
                    raise WorkbookImportError(f"unresolved row carries an applicable value: {item_id}")
                decision = "unresolved"
                human_revision = ""
                source_note = "暂时无法判断"
                review_status = "human-reviewed-unresolved"
            if final_value == "<DELETE>" and not (decision == "approve-current" and row["current_cn"] == "<DELETE>"):
                raise WorkbookImportError(f"reserved deletion token is forbidden as review text: {item_id}")
            combined_notes = source_note + (("；" + notes) if notes else "")
            parsed_decisions[item_id] = {
                "review_status": review_status,
                "human_decision": decision,
                "reviewer": reviewer,
                "timestamp": timestamp,
                "final_value": final_value,
                "human_revision": human_revision,
                "human_notes": combined_notes,
            }

    readonly = sheets["只读排除347"]
    readonly_rows = _sheet_data_rows(readonly, EXCLUDED_HEADERS, EXPECTED_COUNTS["excluded"], "只读排除347")
    expected_excluded = set(resolutions) | set(shadow)
    if set(readonly_rows) != expected_excluded:
        raise WorkbookImportError("只读排除347 stable ID set drifted")
    for item_id, row_number in readonly_rows.items():
        category = "authority-resolved" if item_id in resolutions else "higher-authority-shadowed"
        metadata = resolutions.get(item_id) or shadow[item_id]
        visible, _payload = _excluded_expected(item_id, sealed[item_id], metadata, category)
        for column, expected in visible.items():
            actual = readonly["cells"].get(f"{column}{row_number}", "")
            if not _literal_equal(actual, expected):
                raise WorkbookImportError(f"read-only exclusion field drift {column}: {item_id}")

    for item_id in expected_excluded:
        if any(decisions[item_id].get(field, "") for field in DECISION_FIELDS):
            raise WorkbookImportError(f"excluded item carries a human decision: {item_id}")
    changed = 0
    for item_id, update in parsed_decisions.items():
        row = decisions[item_id]
        if any(row[field] != value for field, value in update.items()):
            changed += 1
        row.update(update)
    ordered = [decisions[row["item_id"]] for row in decision_rows]
    if changed == 0:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(decisions_path.read_bytes())
    else:
        _write_tsv(out_path, decision_header, ordered)
    counts = {"approve-current": 0, "revise": 0, "unresolved": 0}
    for update in parsed_decisions.values():
        counts[update["human_decision"]] += 1
    return {
        "schema": "magireco-cn-v26-translation-xlsx-import/2",
        "status": "PASS",
        "workbook_rows": EXPECTED_COUNTS["human"],
        "priority_rows": EXPECTED_COUNTS["priority"],
        "approved_machine_rows": EXPECTED_COUNTS["approved"],
        "read_only_excluded_rows": EXPECTED_COUNTS["excluded"],
        "higher_authority_shadowed_rows": EXPECTED_COUNTS["shadowed"],
        "decisions_imported": len(parsed_decisions),
        "decision_rows_changed": changed,
        "pending_in_workbook": EXPECTED_COUNTS["human"] - len(parsed_decisions),
        "decision_counts": counts,
        "target_contract_sha256": target_contract_hash,
        "output": str(out_path),
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
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = import_workbook(
            args.xlsx, args.source, args.sealed, args.decisions, args.targets, args.out,
            priority_path=args.priority, inventory_path=args.inventory, shadow_path=args.shadow,
            resolutions_path=args.authority_resolutions,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (WorkbookImportError, OSError, UnicodeError, ValueError, zipfile.BadZipFile, ET.ParseError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
