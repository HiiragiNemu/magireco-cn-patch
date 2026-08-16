#!/usr/bin/env python3
"""Validate the Pass20 review workbook and merge its decisions into the 1,912-row TSV."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
DEFAULT_XLSX = AUDIT / "pass20_human_review.xlsx"
DEFAULT_SOURCE = AUDIT / "pass20_remaining_manual_review.tsv"
DEFAULT_SEALED = AUDIT / "dsv4_terminal_handoff/full_review.tsv"
DEFAULT_DECISIONS = AUDIT / "dsv4_human_decisions.tsv"
DEFAULT_TARGETS = AUDIT / "pass20_product_targets.json"
TOTAL = 199
SCHEMA = "magireco-cn-pass20-human-review-workbook/1"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
Q = lambda tag: f"{{{NS}}}{tag}"

HEADERS = (
    "序号", "稳定ID", "原文（日文/源文）", "当前中文", "建议中文", "DS结论", "审查理由",
    "维护层类型", "维护表", "原文键", "路径前缀", "产品目标路径", "匹配次数", "上下文片段",
    "人工决定", "最终中文", "人工备注", "__source_text_sha256", "__source_row_json", "__schema_version",
)
DECISION_LABELS = {
    "保留现译": "approve-current",
    "修改译文": "revise",
    "暂时无法判断": "unresolved",
}
VERDICT_LABELS = {
    "correction": "DS发现错误／建议修正但尚未应用",
    "unresolved": "DS未确定／需人工判断",
    "manual-required": "尚未完成DS审查／需人工判断",
}
SOURCE_FIELDS = (
    "source_index", "batch_number", "item_id", "stable_business_key",
    "source_path", "source_key", "source_field", "review_kind", "allowed_action",
    "japanese_or_source_original", "old_cn", "current_cn", "parent_verdict",
    "suggested_cn", "parent_rationale", "role_verdicts", "role_details",
    "protected_authority_text", "product_write_allowed", "highest_authority_tier",
    "authority_status", "authority_evidence", "official_cn", "wiki_cn",
    "confirmed_human_cn",
)
DECISION_FIELDS = (
    "human_decision", "reviewer", "timestamp", "final_value", "human_revision", "human_notes",
)
ISO_8601 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


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
    targets = {
        rel.get("Id"): rel.get("Target", "")
        for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    result: dict[str, str] = {}
    for sheet in workbook.findall(f"./{Q('sheets')}/{Q('sheet')}"):
        name = sheet.get("name", "")
        rel_id = sheet.get(f"{{{REL_NS}}}id", "")
        target = targets.get(rel_id, "").lstrip("/")
        pure = PurePosixPath(target)
        if pure.is_absolute() or ".." in pure.parts or not target.startswith("xl/worksheets/"):
            raise WorkbookImportError(f"unsafe worksheet relationship for {name!r}")
        if name in result or target not in package.namelist():
            raise WorkbookImportError(f"missing or duplicate worksheet: {name!r}")
        result[name] = target
    return result


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
    result: dict[int, bool] = {}
    for index, xf in enumerate(cell_xfs):
        protection = xf.find(Q("protection"))
        result[index] = protection is not None and protection.get("locked") == "0"
    return result


def _require_workbook_ui(review: dict[str, Any], instruction: dict[str, Any], unlocked: dict[int, bool]) -> None:
    for payload, label in ((review, "审核"), (instruction, "说明")):
        if payload["root"].find(Q("sheetProtection")) is None:
            raise WorkbookImportError(f"{label} sheet protection is missing")
    pane1 = instruction["root"].find(f"./{Q('sheetViews')}/{Q('sheetView')}/{Q('pane')}")
    pane2 = review["root"].find(f"./{Q('sheetViews')}/{Q('sheetView')}/{Q('pane')}")
    if pane1 is None or pane1.get("ySplit") != "2" or pane1.get("state") != "frozen":
        raise WorkbookImportError("instruction freeze pane drifted")
    if (
        pane2 is None or pane2.get("xSplit") != "2" or pane2.get("ySplit") != "1"
        or pane2.get("state") != "frozen"
    ):
        raise WorkbookImportError("review freeze pane drifted")
    cols = review["root"].find(Q("cols"))
    hidden = set()
    for col in list(cols) if cols is not None else []:
        if col.get("hidden") == "1":
            hidden.update(range(int(col.get("min", "0")), int(col.get("max", "0")) + 1))
    if not {18, 19, 20}.issubset(hidden):
        raise WorkbookImportError("hidden audit columns R:T drifted")
    for ref in ("B13", "B14"):
        if not unlocked.get(instruction["styles"].get(ref, -1), False):
            raise WorkbookImportError(f"instruction input cell is locked: {ref}")
    for row in range(2, 201):
        for column in "OPQ":
            ref = f"{column}{row}"
            if not unlocked.get(review["styles"].get(ref, -1), False):
                raise WorkbookImportError(f"review input cell is locked: {ref}")
        for column in "ABCDEFGHIJKLMNRST":
            ref = f"{column}{row}"
            if unlocked.get(review["styles"].get(ref, -1), False):
                raise WorkbookImportError(f"immutable review cell is unlocked: {ref}")
    validations = review["root"].find(Q("dataValidations"))
    matched = False
    for validation in list(validations) if validations is not None else []:
        formula = validation.find(Q("formula1"))
        if validation.get("sqref") == "O2:O200" and formula is not None:
            values = formula.text or ""
            matched = all(label in values for label in DECISION_LABELS)
    if not matched:
        raise WorkbookImportError("Chinese decision dropdown drifted")


def _literal_equal(actual: str, expected: str) -> bool:
    actual = actual.replace("\r\n", "\n").replace("\r", "\n")
    expected = expected.replace("\r\n", "\n").replace("\r", "\n")
    return actual == expected or (expected.startswith("=") and actual == "'" + expected)


def _integer_cell(value: str, expected: int, label: str) -> None:
    if not re.fullmatch(r"\d+(?:\.0+)?", value) or int(float(value)) != expected:
        raise WorkbookImportError(f"numeric cell drift: {label}")


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


def import_workbook(
    xlsx: Path,
    source_path: Path,
    sealed_path: Path,
    decisions_path: Path,
    targets_path: Path,
    out_path: Path,
) -> dict[str, Any]:
    source_header, source_rows = load_tsv(source_path)
    sealed_header, sealed_rows = load_tsv(sealed_path)
    decision_header, decision_rows = load_tsv(decisions_path)
    if len(source_rows) != TOTAL or len({row["item_id"] for row in source_rows}) != TOTAL:
        raise WorkbookImportError(f"source review queue must contain {TOTAL} unique items")
    if len(sealed_rows) != 1912 or len(decision_rows) != 1912:
        raise WorkbookImportError("sealed and decision TSVs must each contain 1,912 rows")
    if decision_header != source_header:
        raise WorkbookImportError("queue and full decision TSV columns differ")
    if not set(SOURCE_FIELDS + ("source_text_sha256",)).issubset(sealed_header):
        raise WorkbookImportError("sealed source lacks immutable fields or source hash")
    if not set(SOURCE_FIELDS + DECISION_FIELDS).issubset(decision_header):
        raise WorkbookImportError("full decision TSV lacks immutable or decision fields")
    sealed_by_id = {row["item_id"]: row for row in sealed_rows}
    decisions_by_id = {row["item_id"]: row for row in decision_rows}
    if len(sealed_by_id) != 1912 or len(decisions_by_id) != 1912:
        raise WorkbookImportError("sealed or decision TSV has duplicate item_id")
    if [row["item_id"] for row in sealed_rows] != [row["item_id"] for row in decision_rows]:
        raise WorkbookImportError("full decision order differs from sealed source")
    for sealed, decision in zip(sealed_rows, decision_rows):
        item_id = sealed["item_id"]
        for field in SOURCE_FIELDS:
            if decision[field] != sealed[field]:
                raise WorkbookImportError(f"full decision immutable field drift {field}: {item_id}")
        expected_source_hash = sha256(
            sealed["japanese_or_source_original"].encode("utf-8")
        ).hexdigest()
        if sealed["source_text_sha256"] != expected_source_hash:
            raise WorkbookImportError(f"sealed source hash does not match source text: {item_id}")
    target_payload = json.loads(targets_path.read_text(encoding="utf-8"))
    if (
        target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1"
        or target_payload.get("status") != "PASS"
    ):
        raise WorkbookImportError("product target manifest schema or status drifted")
    target_rows = target_payload.get("items", [])
    if not isinstance(target_rows, list):
        raise WorkbookImportError("product target manifest items are invalid")
    target_by_id = {row.get("item_id"): row for row in target_rows if isinstance(row, dict)}
    if len(target_rows) != TOTAL or len(target_by_id) != TOTAL:
        raise WorkbookImportError(f"product target manifest must contain {TOTAL} unique items")
    summary = target_payload.get("summary", {})
    expected_summary = {
        "items": 199,
        "maintenance_rows_bound": 199,
        "exact_runtime_items": 180,
        "maintenance_only_items": 19,
        "runtime_occurrences": 246,
        "occurrence_collisions": 0,
        "unclassified_items": 0,
    }
    if any(summary.get(key) != value for key, value in expected_summary.items()):
        raise WorkbookImportError("product target manifest summary drifted")
    if set(target_by_id) != {row["item_id"] for row in source_rows}:
        raise WorkbookImportError(f"product target manifest differs from the {TOTAL}-item queue")

    if not xlsx.is_file() or xlsx.is_symlink():
        raise WorkbookImportError(f"workbook missing or unsafe: {xlsx}")
    with zipfile.ZipFile(xlsx) as package:
        if package.testzip() is not None:
            raise WorkbookImportError("workbook CRC failure")
        member_names = package.namelist()
        if len(member_names) != len(set(member_names)):
            raise WorkbookImportError("workbook contains duplicate ZIP members")
        for name in member_names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts:
                raise WorkbookImportError("unsafe workbook member path")
        paths = _sheet_paths(package)
        if set(paths) != {"说明", "审核"}:
            raise WorkbookImportError("workbook must contain exactly the 说明 and 审核 sheets")
        shared = _shared_strings(package)
        instruction = _parse_sheet(package, paths["说明"], shared)
        review = _parse_sheet(package, paths["审核"], shared)
        _require_workbook_ui(review, instruction, _styles_unlocked(package))

    cells = review["cells"]
    if review["formulas"].intersection({f"{column}{row}" for column in "ABCDEFGHIJKLMNOPQRST" for row in range(1, 201)}):
        raise WorkbookImportError("review data or audit cells contain a formula")
    if instruction["formulas"].intersection({"B13", "B14"}):
        raise WorkbookImportError("reviewer or timestamp cell contains a formula")
    actual_headers = tuple(cells.get(f"{chr(64 + index)}1", "") for index in range(1, 21))
    if actual_headers != HEADERS:
        raise WorkbookImportError("review workbook columns drifted")
    nonempty_extra = [
        ref for ref, value in cells.items()
        if value and (_row_number(ref) > 200 or _column_number(ref) > 20)
    ]
    if nonempty_extra:
        raise WorkbookImportError(f"review workbook has unexpected data cells: {nonempty_extra[:3]}")

    reviewer = instruction["cells"].get("B13", "").strip()
    timestamp = instruction["cells"].get("B14", "").strip()
    parsed_decisions: dict[str, dict[str, str]] = {}
    for sequence, source in enumerate(source_rows, 1):
        row_number = sequence + 1
        item_id = source["item_id"]
        sealed = sealed_by_id.get(item_id)
        full = decisions_by_id.get(item_id)
        target = target_by_id.get(item_id)
        if sealed is None or full is None or target is None:
            raise WorkbookImportError(f"item is absent from a bound source: {item_id}")
        for field in SOURCE_FIELDS:
            if full[field] != source[field] or sealed[field] != source[field]:
                raise WorkbookImportError(f"bound source drift {field}: {item_id}")
        expected_paths = target["product_target_paths"] or target["declared_product_paths"]
        expected_context = target["match_status"] + "\n" + "\n".join(target["context_snippets"])
        visible = {
            "A": str(sequence), "B": item_id,
            "C": source["japanese_or_source_original"], "D": source["current_cn"],
            "E": source["suggested_cn"], "F": VERDICT_LABELS[source["parent_verdict"]],
            "G": source["parent_rationale"], "H": target["maintenance_layer_type"],
            "I": target["maintenance_table"], "J": source["source_key"],
            "K": target["path_prefix"] or "（全局）", "L": "\n".join(expected_paths),
            "M": str(target["match_count"]), "N": expected_context,
        }
        for column, expected in visible.items():
            actual = cells.get(f"{column}{row_number}", "")
            if column in {"A", "M"}:
                _integer_cell(actual, int(expected), f"{item_id}:{column}")
            elif not _literal_equal(actual, expected):
                raise WorkbookImportError(f"visible source field drift {column}: {item_id}")
        expected_hash = sealed.get("source_text_sha256", "")
        recomputed_hash = sha256(
            source["japanese_or_source_original"].encode("utf-8")
        ).hexdigest()
        if expected_hash != recomputed_hash:
            raise WorkbookImportError(f"sealed source hash mismatch with source text: {item_id}")
        if cells.get(f"R{row_number}", "") != expected_hash:
            raise WorkbookImportError(f"sealed source hash mismatch: {item_id}")
        try:
            embedded = json.loads(cells.get(f"S{row_number}", ""))
        except json.JSONDecodeError as exc:
            raise WorkbookImportError(f"embedded source row is invalid: {item_id}") from exc
        if embedded != source:
            raise WorkbookImportError(f"embedded source row drift: {item_id}")
        if cells.get(f"T{row_number}", "") != SCHEMA:
            raise WorkbookImportError(f"workbook schema drift: {item_id}")

        label = cells.get(f"O{row_number}", "").strip()
        final_value = cells.get(f"P{row_number}", "")
        notes = cells.get(f"Q{row_number}", "").strip()
        if not label:
            if final_value or notes:
                raise WorkbookImportError(f"blank decision carries output: {item_id}")
            continue
        decision = DECISION_LABELS.get(label)
        if decision is None:
            raise WorkbookImportError(f"unknown decision label for {item_id}: {label!r}")
        if not reviewer or not timestamp:
            raise WorkbookImportError("reviewer and ISO timestamp are required for decided rows")
        _validate_iso(timestamp)
        if decision == "approve-current":
            if final_value and final_value != source["current_cn"]:
                raise WorkbookImportError(f"keep-current row has a changed final value: {item_id}")
            final_value = source["current_cn"]
            human_revision = ""
        elif decision == "revise":
            if not final_value or final_value == source["current_cn"]:
                raise WorkbookImportError(f"revision requires a changed final value: {item_id}")
            human_revision = final_value
        else:
            if final_value:
                raise WorkbookImportError(f"unresolved row carries an applicable value: {item_id}")
            human_revision = ""
        if final_value == "<DELETE>" and not (
            decision == "approve-current" and source["current_cn"] == "<DELETE>"
        ):
            raise WorkbookImportError(f"reserved deletion token is forbidden as review text: {item_id}")
        parsed_decisions[item_id] = {
            "human_decision": decision,
            "reviewer": reviewer,
            "timestamp": timestamp,
            "final_value": final_value,
            "human_revision": human_revision,
            "human_notes": notes,
        }

    changed = 0
    for item_id, update in parsed_decisions.items():
        row = decisions_by_id[item_id]
        if any(row[field] != value for field, value in update.items()):
            changed += 1
        row.update(update)
    ordered = [decisions_by_id[row["item_id"]] for row in decision_rows]
    if changed == 0:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(decisions_path.read_bytes())
    else:
        _write_tsv(out_path, decision_header, ordered)
    counts = {code: 0 for code in DECISION_LABELS.values()}
    for update in parsed_decisions.values():
        counts[update["human_decision"]] += 1
    return {
        "schema": "magireco-cn-pass20-xlsx-import/1",
        "status": "PASS",
        "workbook_rows": TOTAL,
        "decisions_imported": len(parsed_decisions),
        "decision_rows_changed": changed,
        "pending_in_workbook": TOTAL - len(parsed_decisions),
        "decision_counts": counts,
        "output": str(out_path),
        "product_tree_writes": False,
        "protected_text_changes": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--sealed", type=Path, default=DEFAULT_SEALED)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = import_workbook(
            args.xlsx, args.source, args.sealed, args.decisions, args.targets, args.out
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (WorkbookImportError, OSError, UnicodeError, ValueError, zipfile.BadZipFile, ET.ParseError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
