#!/usr/bin/env python3
"""Bind the 199 unresolved Pass20 items to maintenance rows and current product literals."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
QUEUE = AUDIT / "pass20_remaining_manual_review.tsv"
PROVENANCE = ROOT / "i18n/generated/input-provenance.tsv"
EFFECTIVE = ROOT / "i18n/generated/effective.tsv"
UI_TEXT = ROOT / "i18n/uiTextList.json"
PRODUCT = ROOT / "magica"
OUT_JSON = AUDIT / "pass20_product_targets.json"
OUT_TSV = AUDIT / "pass20_product_targets.tsv"
TOTAL = 199
JS_LIT = re.compile(r'(["\'])((?:(?!\1)[^\\]|\\.)*)\1')
HTML_TEXT = re.compile(r'>([^<>{}]*)<')
HTML_ATTR = re.compile(r'((?:placeholder|title|alt|value)=")([^"]*)(")')

TSV_COLUMNS = (
    "item_id", "maintenance_layer_type", "maintenance_table", "source_key",
    "source_line", "source_text", "current_cn", "path_prefix",
    "declared_product_paths", "product_target_paths", "match_count",
    "match_status", "context_snippets", "application_allowed",
)
LAYER_LABELS = {
    "global": "全局原文映射",
    "override": "路径限定覆盖",
    "fragment": "指定文件代码片段",
}


class TargetError(RuntimeError):
    pass


def load_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise TargetError(f"TSV must be UTF-8-no-BOM with LF endings: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if not header or any(None in row for row in rows):
        raise TargetError(f"invalid TSV structure: {path}")
    return header, rows


def decode_cell(value: str) -> str:
    return value.replace("\\t", "\t").replace("\\n", "\n").replace("\\\\", "\\")


def safe_product_path(root: Path, rel: str) -> Path:
    posix = PurePosixPath(rel)
    if posix.is_absolute() or ".." in posix.parts or not rel:
        raise TargetError(f"unsafe product path: {rel!r}")
    path = root.joinpath(*posix.parts)
    if path.suffix.lower() not in {".js", ".html", ".json"}:
        raise TargetError(f"unsupported product target: {rel}")
    return path


def contexts(text: str, needle: str, rel: str, scope: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    if scope == "fragment":
        spans = [match.span() for match in re.finditer(re.escape(needle), text)]
    elif rel.endswith(".js"):
        spans = [match.span(2) for match in JS_LIT.finditer(text) if match.group(2) == needle]
    elif rel.endswith(".html"):
        for match in HTML_TEXT.finditer(text):
            body = match.group(1)
            if body.strip() == needle:
                offset = body.index(needle)
                spans.append((match.start(1) + offset, match.start(1) + offset + len(needle)))
        spans.extend(match.span(2) for match in HTML_ATTR.finditer(text) if match.group(2) == needle)
        spans.sort()
    for ordinal, (start, end) in enumerate(spans, 1):
        line = text.count("\n", 0, start) + 1
        line_start = text.rfind("\n", 0, start) + 1
        column = start - line_start + 1
        before = text[max(0, start - 90):start]
        after = text[end:min(len(text), end + 90)]
        result.append({
            "path": rel,
            "ordinal_in_file": ordinal,
            "start": start,
            "end": end,
            "line": line,
            "column": column,
            "context": (before + "⟦" + needle + "⟧" + after).replace("\r", "").replace("\n", "↵"),
        })
    return result


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=TSV_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in TSV_COLUMNS})


def build(
    queue_path: Path,
    provenance_path: Path,
    effective_path: Path,
    ui_text_path: Path,
    product_root: Path,
) -> dict[str, Any]:
    _, queue = load_tsv(queue_path)
    _, provenance_rows = load_tsv(provenance_path)
    _, effective_rows = load_tsv(effective_path)
    if len(queue) != TOTAL or len({row["item_id"] for row in queue}) != TOTAL:
        raise TargetError(f"Pass20 queue must contain {TOTAL} unique items")
    provenance: dict[str, dict[str, str]] = {}
    for row in provenance_rows:
        candidate_id = row.get("candidate_id", "")
        if not candidate_id or candidate_id in provenance:
            raise TargetError("effective provenance has an empty or duplicate candidate_id")
        provenance[candidate_id] = row
    effective = {row["key"]: row for row in effective_rows}
    if len(effective) != len(effective_rows):
        raise TargetError("effective table has an empty or duplicate semantic key")

    physical_rows: dict[tuple[str, int], list[str]] = {}
    for rel in ("i18n/frontend-strings.tsv", "i18n/overrides.tsv", "i18n/fragments.tsv"):
        with (ROOT / rel).open("r", encoding="utf-8-sig", newline="") as stream:
            for line_no, row in enumerate(csv.reader(stream, delimiter="\t"), 1):
                if row and not row[0].startswith("#"):
                    physical_rows[(rel, line_no)] = row

    ui_payload = json.loads(ui_text_path.read_text(encoding="utf-8"))
    ui_by_source: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for record in ui_payload.values():
        if not isinstance(record, dict) or record.get("source") != "i18n/frontend-strings.tsv":
            continue
        try:
            line = int(record.get("sourceLine"))
        except (TypeError, ValueError):
            continue
        ui_by_source[(line, record.get("ja", ""))].append(record)

    items: list[dict[str, Any]] = []
    claimed: dict[tuple[str, int, int], list[str]] = defaultdict(list)
    product_files: dict[str, str] = {}
    for path in product_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".js", ".html", ".json"}:
            continue
        rel = path.relative_to(product_root).as_posix()
        if rel.startswith("i18n_audit/") or rel.startswith("research/"):
            continue
        product_files[rel] = path.read_text(encoding="utf-8")
    for queue_row in queue:
        item_id = queue_row["item_id"]
        source_key = queue_row["source_key"]
        source = provenance.get(source_key)
        if source is None:
            raise TargetError(f"candidate absent from effective provenance: {item_id}")
        if source["source_file"] != queue_row["source_path"]:
            raise TargetError(f"maintenance table drift: {item_id}")
        source_text = decode_cell(source["source_text"])
        current_cn = decode_cell(source["candidate_cn"])
        if source_text != decode_cell(queue_row["japanese_or_source_original"]):
            raise TargetError(f"source text drift: {item_id}")
        if current_cn != decode_cell(queue_row["current_cn"]):
            raise TargetError(f"current translation drift: {item_id}")
        scope = source["scope"]
        if scope not in LAYER_LABELS:
            raise TargetError(f"unsupported maintenance scope for {item_id}: {scope}")
        path_prefix = source["path_prefix"]
        semantic_key = source["key"]
        effective_row = effective.get(semantic_key)
        if effective_row is None:
            raise TargetError(f"semantic key absent from effective table: {item_id}")
        shadowed = (
            effective_row["selected_cn"] != source["candidate_cn"]
            or effective_row["authority"] != source["authority"]
            or effective_row["source_file"] != source["source_file"]
            or effective_row["source_line"] != source["source_line"]
        )
        physical = physical_rows.get((source["source_file"], int(source["source_line"])))
        if physical is None:
            raise TargetError(f"physical maintenance row missing: {item_id}")
        expected_occurrences: int | None = None
        truncated_target_count: int | None = None
        if scope == "global":
            records = ui_by_source.get((int(source["source_line"]), source_text), [])
            if len(records) != 1:
                raise TargetError(f"uiTextList source binding is not unique: {item_id}")
            if len(physical) != 5 or decode_cell(physical[0]) != source_text:
                raise TargetError(f"frontend physical row drift: {item_id}")
            try:
                expected_occurrences = int(physical[3])
            except ValueError as exc:
                raise TargetError(f"frontend occurrence count is invalid: {item_id}") from exc
            raw_declared = list(records[0].get("usedBy") or [])
            markers = [re.fullmatch(r"…共(\d+)处", value) for value in raw_declared]
            marker_values = [int(match.group(1)) for match in markers if match]
            if len(marker_values) > 1:
                raise TargetError(f"multiple truncated target markers: {item_id}")
            truncated_target_count = marker_values[0] if marker_values else None
            declared_paths = [value for value, match in zip(raw_declared, markers) if not match]
        else:
            declared_paths = [path_prefix]
        if not declared_paths or len(set(declared_paths)) != len(declared_paths):
            raise TargetError(f"invalid declared target list: {item_id}")

        observed_occurrences: list[dict[str, Any]] = []
        existing_paths: list[str] = []
        missing_paths: list[str] = []
        if current_cn == "<DELETE>":
            literal = ""
        else:
            literal = current_cn
        scan_paths = declared_paths
        if scope == "global" and truncated_target_count is not None:
            scan_paths = sorted(product_files)
        for rel in scan_paths:
            target = safe_product_path(product_root, rel)
            text = product_files.get(rel)
            if text is None:
                if rel in declared_paths:
                    missing_paths.append(rel)
                continue
            if rel in declared_paths:
                existing_paths.append(rel)
            if literal:
                observed_occurrences.extend(contexts(text, literal, rel, scope))

        observed_paths = list(dict.fromkeys(entry["path"] for entry in observed_occurrences))
        exact_binding = False
        if shadowed:
            status = "protected-higher-authority-selected"
            application_allowed = False
            note = (
                f"effective 已选择 {effective_row['authority']} 的“{effective_row['selected_cn']}”；"
                "低权重候选保持只读，不生成产品写入。"
            )
        elif scope == "global" and truncated_target_count is not None:
            exact_binding = (
                literal != ""
                and len(observed_occurrences) == expected_occurrences
                and len(observed_paths) == truncated_target_count
                and set(declared_paths).issubset(observed_paths)
            )
            if exact_binding:
                status = "exact-current-runtime-literal"
                application_allowed = True
                note = "截断出现路径已用总路径数和总命中数闭合，人工修订只可作用于这些位置。"
            else:
                status = "maintenance-only-truncated-target-ambiguous"
                application_allowed = False
                note = "出现路径为截断摘要，当前值扫描未同时满足路径总数与命中总数；运行时写入保持关闭。"
        elif scope == "global":
            per_declared = Counter(entry["path"] for entry in observed_occurrences)
            exact_binding = (
                literal != ""
                and not missing_paths
                and all(per_declared[path] > 0 for path in declared_paths)
                and len(observed_occurrences) == expected_occurrences
            )
            if exact_binding:
                status = "exact-current-runtime-literal"
                application_allowed = True
                note = "当前译文已按完整出现路径和原始命中总数闭合；人工修订只可作用于这些位置。"
            elif observed_occurrences:
                status = "maintenance-only-count-or-path-drift"
                application_allowed = False
                note = "当前值虽有命中，但路径覆盖或命中总数与维护表不一致；运行时写入保持关闭。"
            elif not existing_paths:
                status = "maintenance-only-declared-path-absent"
                application_allowed = False
                note = "声明路径在当前 magica 中不存在；仅保留未来重建所需的维护层决定。"
            else:
                status = "maintenance-only-current-literal-absent"
                application_allowed = False
                note = "声明路径存在，但当前运行时已不使用这条现译；仅保留未来重建所需的维护层决定。"
        elif observed_occurrences:
            exact_binding = True
            status = "exact-current-runtime-literal"
            application_allowed = True
            note = "当前译文已按维护层声明路径精确定位；人工修订只可作用于这些位置。"
        elif current_cn == "<DELETE>":
            status = "maintenance-only-deletion-already-applied"
            application_allowed = False
            note = "删除型覆盖在当前运行时没有可替换字面值；维护层可复核，运行时写入保持关闭。"
        elif not existing_paths:
            status = "maintenance-only-declared-path-absent"
            application_allowed = False
            note = "声明路径在当前 magica 中不存在；仅保留未来重建所需的维护层决定。"
        else:
            status = "maintenance-only-current-literal-absent"
            application_allowed = False
            note = "声明路径存在，但当前运行时已不使用这条现译；仅保留未来重建所需的维护层决定。"

        exact_occurrences = observed_occurrences if exact_binding and application_allowed else []
        for occurrence in exact_occurrences:
            claimed[(occurrence["path"], occurrence["start"], occurrence["end"])].append(item_id)
        snippets = [
            f"{entry['path']}:{entry['line']}:{entry['column']} {entry['context']}"
            for entry in observed_occurrences[:3]
        ]
        if not snippets:
            snippets = [note]
        actual_paths = observed_paths
        item = {
            "item_id": item_id,
            "stable_business_key": queue_row["stable_business_key"],
            "maintenance_layer_type": LAYER_LABELS[scope],
            "maintenance_scope": scope,
            "semantic_key": semantic_key,
            "maintenance_table": source["source_file"],
            "source_key": source_key,
            "source_line": int(source["source_line"]),
            "source_text": source_text,
            "current_cn": current_cn,
            "path_prefix": path_prefix,
            "declared_product_paths": declared_paths,
            "existing_declared_paths": existing_paths,
            "missing_declared_paths": missing_paths,
            "product_target_paths": actual_paths,
            "expected_occurrence_count": expected_occurrences,
            "truncated_target_count": truncated_target_count,
            "match_count": len(observed_occurrences),
            "match_status": status,
            "context_snippets": snippets,
            "application_allowed": application_allowed,
            "product_write_allowed_from_review_queue": queue_row["product_write_allowed"],
            "effective_before": {
                "selected_cn": effective_row["selected_cn"],
                "authority": effective_row["authority"],
                "source_file": effective_row["source_file"],
                "source_line": int(effective_row["source_line"]),
            },
            "shadowed_by_higher_authority": shadowed,
            "occurrences": exact_occurrences,
            "observed_occurrences": observed_occurrences,
            "note": note,
        }
        items.append(item)

    collisions = [
        {"path": key[0], "start": key[1], "end": key[2], "item_ids": ids}
        for key, ids in sorted(claimed.items()) if len(ids) != 1
    ]
    if collisions:
        raise TargetError(f"product occurrence claimed by multiple review items: {collisions[:3]}")
    status_counts = Counter(item["match_status"] for item in items)
    exact_items = sum(bool(item["application_allowed"]) for item in items)
    result = {
        "schema": "magireco-cn-pass20-product-target-manifest/1",
        "status": "PASS",
        "items": items,
        "summary": {
            "items": len(items),
            "maintenance_rows_bound": len(items),
            "exact_runtime_items": exact_items,
            "maintenance_only_items": len(items) - exact_items,
            "runtime_occurrences": sum(len(item["occurrences"]) for item in items),
            "occurrence_collisions": len(collisions),
            "unclassified_items": 0,
            "status_counts": dict(sorted(status_counts.items())),
            "xlsx_writes_product_tree": False,
            "runtime_application_requires_human_gate": True,
        },
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--provenance", type=Path, default=PROVENANCE)
    parser.add_argument("--effective", type=Path, default=EFFECTIVE)
    parser.add_argument("--ui-text", type=Path, default=UI_TEXT)
    parser.add_argument("--product-root", type=Path, default=PRODUCT)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-tsv", type=Path, default=OUT_TSV)
    args = parser.parse_args(argv)
    try:
        result = build(args.queue, args.provenance, args.effective, args.ui_text, args.product_root)
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        rows = []
        for item in result["items"]:
            rows.append({
                "item_id": item["item_id"],
                "maintenance_layer_type": item["maintenance_layer_type"],
                "maintenance_table": item["maintenance_table"],
                "source_key": item["source_key"],
                "source_line": item["source_line"],
                "source_text": item["source_text"],
                "current_cn": item["current_cn"],
                "path_prefix": item["path_prefix"],
                "declared_product_paths": "\n".join(item["declared_product_paths"]),
                "product_target_paths": "\n".join(item["product_target_paths"]),
                "match_count": item["match_count"],
                "match_status": item["match_status"],
                "context_snippets": "\n".join(item["context_snippets"]),
                "application_allowed": str(item["application_allowed"]).lower(),
            })
        write_tsv(args.out_tsv, rows)
        print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
        return 0
    except (TargetError, OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
