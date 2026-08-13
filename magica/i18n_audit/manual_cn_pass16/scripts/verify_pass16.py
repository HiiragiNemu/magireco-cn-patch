#!/usr/bin/env python3
"""Portable, read-only validation for the Pass16 manual-CN overlay.

The validator deliberately compares the candidate worktree with the immutable
Pass15 Git commit rather than trusting a previously generated report.  It never
writes below the repository tree; ``--out`` is the only optional output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


BASE_COMMIT = "4db6698623311ee5ab1dce9ebce940e0eb2748f0"
EXPECTED_JS_COUNT = 197  # product JS, excluding derived jQuery and research evidence
EXPECTED_HTML_COUNT = 182
DICT_NAMES = (
    "arenaClassList", "cardList", "cardMagiaMap", "cardSkillMap", "chapterList",
    "charaList", "charaMessageList", "doppelCardMagiaMap", "doppelList",
    "emotionSkillMap", "enemyList", "eventList", "eventStoryList",
    "formationSheetList", "giftList", "itemList", "live2dList", "patrolAreaList",
    "pieceList", "pieceSkillMap", "placeSkillMap", "sectionList", "shopItemList",
)
LIST_KEYS = {
    "arenaClassList": ("arenaBattleFreeRankClass",),
    "cardList": ("cardId", "id"),
    "chapterList": ("chapterId", "id"),
    "charaList": ("id", "charaNo"),
    "charaMessageList": ("charaNo_messageId",),
    "doppelList": ("id",),
    "enemyList": ("enemyId", "id"),
    "eventList": ("eventId", "id"),
    "eventStoryList": ("storyIds",),
    "formationSheetList": ("formationSheetId", "id"),
    "giftList": ("id", "giftId"),
    "itemList": ("itemCode", "id", "itemId"),
    "live2dList": ("charaId_live2dId",),
    "patrolAreaList": ("patrolAreaId", "id"),
    "pieceList": ("pieceId", "id"),
    "sectionList": ("sectionId", "id"),
    "shopItemList": ("shopItemId", "id"),
}
GACHA_PATHS = (
    "magica/js/campaign/box_gacha/CampaignBoxGachaTop.js",
    "magica/template/campaign/box_gacha/CampaignBoxGachaTop.html",
    "magica/template/gacha/GachaTop.html",
)
SENSITIVE_EXACT = {"id", "class", "href", "src", "name"}
CHECKLIST_COLUMNS = (
    "status", "risk", "file", "key_or_line", "field", "original_text",
    "final_cn", "category", "source_tier", "source_path", "reviewer_check", "notes",
)
TEXT_EXTENSIONS = {".js", ".html", ".json", ".css"}
BIDI_CODEPOINTS = {
    *range(0x202A, 0x202F),  # embeddings, overrides and PDF
    *range(0x2066, 0x206A),  # isolates
    0x200E, 0x200F, 0x061C,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def git_lines(tree: Path, *args: str) -> list[str]:
    cp = run(["git", "-C", str(tree), *args])
    if cp.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {cp.stderr.strip()}")
    return [line for line in cp.stdout.splitlines() if line]


def git_blob(tree: Path, commit: str, rel: str) -> bytes:
    cp = subprocess.run(
        ["git", "-C", str(tree), "show", f"{commit}:{rel}"],
        capture_output=True,
    )
    if cp.returncode:
        message = cp.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"cannot read {commit}:{rel}: {message}")
    return cp.stdout


def product_files(tree: Path, suffix: str) -> list[str]:
    root = tree / "magica"
    result = []
    for path in root.rglob(f"*{suffix}"):
        if not path.is_file():
            continue
        rel = path.relative_to(tree).as_posix()
        if rel.startswith("magica/research/") or rel.startswith("magica/i18n_audit/"):
            continue
        result.append(rel)
    return sorted(result)


def map_dictionary(name: str, data: Any) -> dict[str, Any]:
    if name not in LIST_KEYS:
        if not isinstance(data, dict):
            raise TypeError(f"{name} must be a JSON object")
        return data
    if not isinstance(data, list):
        raise TypeError(f"{name} must be a JSON array")
    mapped: dict[str, Any] = {}
    for row_index, item in enumerate(data):
        if not isinstance(item, dict):
            raise TypeError(f"{name}[{row_index}] is not an object")
        if name == "charaMessageList":
            key = f"{item.get('charaNo', '')}_{item.get('messageId', '')}"
        elif name == "live2dList":
            key = f"{item.get('charaId', '')}_{item.get('live2dId', '')}"
        else:
            key = ""
            for field in LIST_KEYS[name]:
                if field in item:
                    key = str(item[field])
                    break
        if not key or key == "_":
            continue
        if key in mapped:
            raise ValueError(f"duplicate {name} runtime key: {key}")
        mapped[key] = item
    return mapped


def compare_json_structure(base: Any, current: Any, pointer: str, errors: list[str], limit: int = 100) -> None:
    """Allow string-value edits only; preserve every container/key/non-string scalar."""
    if len(errors) >= limit:
        return
    if type(base) is not type(current):
        errors.append(f"{pointer}: type drift {type(base).__name__} -> {type(current).__name__}")
        return
    if isinstance(base, dict):
        base_keys = set(base)
        current_keys = set(current)
        if base_keys != current_keys:
            missing = sorted(base_keys - current_keys)[:10]
            extra = sorted(current_keys - base_keys)[:10]
            errors.append(f"{pointer}: object-key drift missing={missing} extra={extra}")
        for key in sorted(base_keys & current_keys):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            compare_json_structure(base[key], current[key], f"{pointer}/{escaped}", errors, limit)
            if len(errors) >= limit:
                return
    elif isinstance(base, list):
        if len(base) != len(current):
            errors.append(f"{pointer}: array-length drift {len(base)} -> {len(current)}")
        for index, (left, right) in enumerate(zip(base, current)):
            compare_json_structure(left, right, f"{pointer}/{index}", errors, limit)
            if len(errors) >= limit:
                return
    elif isinstance(base, str):
        # Text may change, but its rendering structure may not.  In
        # particular, converting a real line break into the two visible
        # characters ``\\n`` passes JSON parsing yet breaks the client UI.
        if base.count("\n") != current.count("\n"):
            errors.append(
                f"{pointer}: newline-layout drift "
                f"{base.count(chr(10))} -> {current.count(chr(10))}"
            )
        return
    elif base != current:
        errors.append(f"{pointer}: non-string scalar drift {base!r} -> {current!r}")


def sensitive_html(text: str) -> list[dict[str, Any]]:
    """Extract sensitive attributes, including tags inside text/template scripts.

    ``html.parser`` deliberately treats the contents of ``<script>`` as raw
    text, while this client stores most Underscore templates there.  This small
    quote-aware scanner therefore recognizes start tags without interpreting
    JavaScript or Underscore delimiters.
    """
    records: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    index = 0
    length = len(text)
    while index < length:
        start = text.find("<", index)
        if start < 0:
            break
        if text.startswith("<!--", start):
            end_comment = text.find("-->", start + 4)
            index = length if end_comment < 0 else end_comment + 3
            continue
        if start + 1 >= length or not text[start + 1].isascii() or not text[start + 1].isalpha():
            index = start + 1
            continue
        cursor = start + 1
        while cursor < length and (text[cursor].isalnum() or text[cursor] in "_:-"):
            cursor += 1
        tag = text[start + 1:cursor].lower()
        quote: str | None = None
        end = cursor
        while end < length:
            char = text[end]
            if quote:
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == ">":
                break
            end += 1
        if end >= length:
            break
        body = text[cursor:end]
        body_index = 0
        while body_index < len(body):
            while body_index < len(body) and body[body_index].isspace():
                body_index += 1
            if body_index >= len(body) or body[body_index] == "/":
                break
            name_start = body_index
            while body_index < len(body) and not body[body_index].isspace() and body[body_index] not in "=/>":
                body_index += 1
            name = body[name_start:body_index].lower()
            if not name:
                body_index += 1
                continue
            while body_index < len(body) and body[body_index].isspace():
                body_index += 1
            value: str | None = None
            if body_index < len(body) and body[body_index] == "=":
                body_index += 1
                while body_index < len(body) and body[body_index].isspace():
                    body_index += 1
                if body_index < len(body) and body[body_index] in "\"'":
                    delimiter = body[body_index]
                    body_index += 1
                    value_start = body_index
                    while body_index < len(body) and body[body_index] != delimiter:
                        body_index += 1
                    value = body[value_start:body_index]
                    if body_index < len(body):
                        body_index += 1
                else:
                    value_start = body_index
                    while body_index < len(body) and not body[body_index].isspace() and body[body_index] not in "/>":
                        body_index += 1
                    value = body[value_start:body_index]
            if name in SENSITIVE_EXACT or name.startswith("data-"):
                occurrence = counts[name]
                counts[name] += 1
                records.append({
                    "tag": tag,
                    "attribute": name,
                    "attribute_occurrence": occurrence,
                    "value": value,
                    "line": text.count("\n", 0, start) + 1,
                })
        index = end + 1
    return records


def load_allowed_changes(path: Path) -> dict[tuple[str, str, int], dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    allowed: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in rows:
        key = (row["path"], row["attribute"].lower(), int(row["attribute_occurrence"]))
        if key in allowed:
            raise ValueError(f"duplicate allowed-sensitive-change key: {key}")
        allowed[key] = row
    return allowed


def inspect_forbidden_unicode(rel: str, data: bytes) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        return [{"path": rel, "kind": "invalid_utf8", "offset": exc.start}]
    line = 1
    column = 0
    for index, char in enumerate(text):
        if char == "\n":
            line += 1
            column = 0
            continue
        column += 1
        code = ord(char)
        kind = None
        if code == 0xFFFD:
            kind = "replacement_character"
        elif code in BIDI_CODEPOINTS:
            kind = "bidi_control"
        elif (code < 0x20 and char not in "\t\r") or 0x7F <= code <= 0x9F:
            kind = "control_character"
        if kind:
            findings.append({
                "path": rel,
                "kind": kind,
                "codepoint": f"U+{code:04X}",
                "index": index,
                "line": line,
                "column": column,
            })
            if len(findings) >= 100:
                break
    return findings


def read_checklist(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        actual = tuple(reader.fieldnames or ())
        if actual != CHECKLIST_COLUMNS:
            errors.append(f"checklist header mismatch: expected={CHECKLIST_COLUMNS!r} actual={actual!r}")
        rows = list(reader)
    for index, row in enumerate(rows, 2):
        for column in CHECKLIST_COLUMNS:
            if not (row.get(column) or "").strip():
                errors.append(f"checklist line {index}: blank required cell {column}")
                if len(errors) >= 100:
                    return rows, errors
    identities = [
        tuple(row.get(column, "") for column in (
            "file", "key_or_line", "field", "original_text", "final_cn"
        ))
        for row in rows
    ]
    duplicates = [identity for identity, count in Counter(identities).items() if count > 1]
    if duplicates:
        errors.append(f"checklist duplicate identities: {len(duplicates)}")
    return rows, errors


def counted(rows: Iterable[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row[field] for row in rows).items()))


def verify_checklist(checklist: Path, summary_path: Path, tree: Path, base: str) -> dict[str, Any]:
    errors: list[str] = []
    if not checklist.is_file():
        return {"status": "FAIL", "errors": [f"checklist missing: {checklist}"]}
    if not summary_path.is_file():
        return {"status": "FAIL", "errors": [f"checklist summary missing: {summary_path}"]}
    rows, row_errors = read_checklist(checklist)
    errors.extend(row_errors)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    actual = {
        "schema": "magireco-cn-pass16-manual-review/v1",
        "checklist_path": checklist.relative_to(tree).as_posix() if checklist.is_relative_to(tree) else str(checklist),
        "checklist_sha256": sha256(checklist.read_bytes()),
        "row_count": len(rows),
        "status_counts": counted(rows, "status"),
        "risk_counts": counted(rows, "risk"),
        "category_counts": counted(rows, "category"),
        "source_tier_counts": counted(rows, "source_tier"),
    }
    for key, value in actual.items():
        if summary.get(key) != value:
            errors.append(f"checklist summary mismatch for {key}: expected={value!r} actual={summary.get(key)!r}")

    changed = set(git_lines(tree, "diff", "--name-only", base, "--", "magica"))
    product_changed = {
        rel for rel in changed
        if Path(rel).suffix.lower() in {".js", ".html", ".json"}
        and not rel.startswith("magica/research/")
        and not rel.startswith("magica/i18n_audit/")
        and rel != "magica/js/libs/jquery-3.7.1.min.js"
    }
    listed = {row["file"].replace("\\", "/") for row in rows}
    missing_files = sorted(product_changed - listed)
    stale_files = sorted(
        rel for rel in listed
        if rel.startswith("magica/") and rel not in product_changed and rel != "magica/js/libs/jquery-3.7.1.min.js"
    )
    if missing_files:
        errors.append(f"changed product files absent from checklist: {missing_files}")
    if stale_files:
        errors.append(f"checklist references unchanged product files: {stale_files}")
    return {
        "status": "PASS" if not errors else "FAIL",
        **actual,
        "changed_product_files": len(product_changed),
        "listed_product_files": len(listed),
        "missing_changed_files": missing_files,
        "unchanged_listed_files": stale_files,
        "errors": errors,
    }


def node_check(path: Path) -> dict[str, Any]:
    cp = run(["node", "--check", str(path)])
    return {
        "path": str(path),
        "exit_code": cp.returncode,
        "stdout": cp.stdout.strip(),
        "stderr": cp.stderr.strip(),
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    default_tree = here.parent / "pass15_final_integration"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, default=default_tree)
    parser.add_argument("--base", default=BASE_COMMIT)
    parser.add_argument("--allowed-sensitive-changes", type=Path, default=here / "allowed_sensitive_changes.json")
    parser.add_argument(
        "--checklist", type=Path,
        help="default: TREE/magica/i18n_audit/manual_cn_pass16/manual_translation_review_checklist.tsv",
    )
    parser.add_argument(
        "--checklist-summary", type=Path,
        help="default: checklist sibling manual_translation_review_checklist.summary.json",
    )
    parser.add_argument("--skip-checklist", action="store_true", help="preflight only; final validation must omit this")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    tree = args.tree.resolve()
    base = args.base
    checklist = (args.checklist or tree / "magica/i18n_audit/manual_cn_pass16/manual_translation_review_checklist.tsv").resolve()
    checklist_summary = (
        args.checklist_summary
        or checklist.with_name("manual_translation_review_checklist.summary.json")
    ).resolve()
    errors: list[str] = []
    checks: dict[str, Any] = {}

    head_probe = run(["git", "-C", str(tree), "cat-file", "-e", f"{base}^{{commit}}"])
    if head_probe.returncode:
        print(json.dumps({"status": "FAIL", "errors": [f"baseline commit unavailable: {base}"]}, ensure_ascii=False, indent=2))
        return 1

    # 23 standalone runtime dictionaries: parse, identity-key parity, and full structure parity.
    libs = tree / "magica/js/libs"
    actual_dict_files = sorted(path.stem for path in libs.glob("*.json"))
    dict_errors: list[str] = []
    dictionaries: dict[str, Any] = {}
    baseline_dictionaries: dict[str, Any] = {}
    dictionary_rows: list[dict[str, Any]] = []
    if actual_dict_files != sorted(DICT_NAMES):
        dict_errors.append(
            f"dictionary set drift missing={sorted(set(DICT_NAMES)-set(actual_dict_files))} "
            f"extra={sorted(set(actual_dict_files)-set(DICT_NAMES))}"
        )
    for name in DICT_NAMES:
        rel = f"magica/js/libs/{name}.json"
        try:
            current_raw = json.loads((tree / rel).read_text(encoding="utf-8-sig"))
            baseline_raw = json.loads(git_blob(tree, base, rel).decode("utf-8-sig"))
            structure_errors: list[str] = []
            compare_json_structure(baseline_raw, current_raw, "", structure_errors)
            current_mapped = map_dictionary(name, current_raw)
            baseline_mapped = map_dictionary(name, baseline_raw)
            key_match = set(current_mapped) == set(baseline_mapped)
            if not key_match:
                structure_errors.append(
                    f"runtime identity-key drift missing={sorted(set(baseline_mapped)-set(current_mapped))[:10]} "
                    f"extra={sorted(set(current_mapped)-set(baseline_mapped))[:10]}"
                )
            dictionaries[name] = current_mapped
            baseline_dictionaries[name] = baseline_mapped
            dictionary_rows.append({
                "name": name,
                "root_type": type(current_raw).__name__,
                "runtime_keys": len(current_mapped),
                "runtime_keys_match": key_match,
                "structure_match": not structure_errors,
                "errors": structure_errors,
            })
            dict_errors.extend(f"{name}{message}" for message in structure_errors)
        except Exception as exc:  # report all dictionaries rather than fail fast
            message = f"{name}: {type(exc).__name__}: {exc}"
            dict_errors.append(message)
            dictionary_rows.append({"name": name, "errors": [message]})
    checks["standalone_json"] = {
        "status": "PASS" if not dict_errors else "FAIL",
        "expected_count": len(DICT_NAMES),
        "actual_count": len(actual_dict_files),
        "files": dictionary_rows,
        "errors": dict_errors,
    }
    errors.extend(f"standalone_json: {item}" for item in dict_errors)

    # Committed jQuery must contain precisely the mapped standalone dictionaries.
    jquery = libs / "jquery-3.7.1.min.js"
    embedded_errors: list[str] = []
    embedded_count = 0
    try:
        jquery_text = jquery.read_text(encoding="utf-8-sig")
        marker = "var cn = "
        position = jquery_text.rfind(marker)
        if position < 0:
            raise ValueError("var cn marker missing")
        embedded, consumed = json.JSONDecoder().raw_decode(jquery_text[position + len(marker):])
        embedded_count = len(embedded) if isinstance(embedded, dict) else 0
        if embedded != dictionaries:
            embedded_errors.append("embedded dictionary payload differs from 23 mapped standalone JSON files")
        if set(embedded) != set(DICT_NAMES):
            embedded_errors.append(
                f"embedded dictionary set drift missing={sorted(set(DICT_NAMES)-set(embedded))} "
                f"extra={sorted(set(embedded)-set(DICT_NAMES))}"
            )
        if consumed <= 2:
            embedded_errors.append("embedded payload is unexpectedly empty")
    except Exception as exc:
        embedded_errors.append(f"{type(exc).__name__}: {exc}")
    checks["jquery_embedded"] = {
        "status": "PASS" if not embedded_errors else "FAIL",
        "jquery": str(jquery),
        "jquery_sha256": sha256(jquery.read_bytes()) if jquery.is_file() else None,
        "embedded_count": embedded_count,
        "standalone_count": len(dictionaries),
        "errors": embedded_errors,
    }
    errors.extend(f"jquery_embedded: {item}" for item in embedded_errors)

    # All 197 product scripts; the generated jQuery is checked by payload parsing above.
    js_paths = [rel for rel in product_files(tree, ".js") if rel != "magica/js/libs/jquery-3.7.1.min.js"]
    with ThreadPoolExecutor(max_workers=min(12, max(1, os.cpu_count() or 1))) as pool:
        node_rows = list(pool.map(lambda rel: node_check(tree / rel), js_paths))
    node_failures = [row for row in node_rows if row["exit_code"] != 0]
    if len(js_paths) != EXPECTED_JS_COUNT:
        errors.append(f"node_check: JS count drift expected={EXPECTED_JS_COUNT} actual={len(js_paths)}")
    if node_failures:
        errors.extend(f"node_check: {row['path']}: {row['stderr']}" for row in node_failures)
    checks["node_check"] = {
        "status": "PASS" if len(js_paths) == EXPECTED_JS_COUNT and not node_failures else "FAIL",
        "expected_count": EXPECTED_JS_COUNT,
        "actual_count": len(js_paths),
        "passed": len(js_paths) - len(node_failures),
        "failed": len(node_failures),
        "failures": node_failures,
    }

    # Sensitive HTML attribute parity with five explicit, value-only exceptions.
    allowed = load_allowed_changes(args.allowed_sensitive_changes.resolve())
    html_paths = product_files(tree, ".html")
    baseline_html_paths = sorted(git_lines(tree, "ls-tree", "-r", "--name-only", base, "--", "magica") )
    baseline_html_paths = [rel for rel in baseline_html_paths if rel.endswith(".html") and not rel.startswith("magica/research/")]
    html_errors: list[str] = []
    allowed_seen: set[tuple[str, str, int]] = set()
    html_rows: list[dict[str, Any]] = []
    if html_paths != baseline_html_paths:
        html_errors.append(
            f"HTML path-set drift missing={sorted(set(baseline_html_paths)-set(html_paths))} "
            f"extra={sorted(set(html_paths)-set(baseline_html_paths))}"
        )
    for rel in sorted(set(html_paths) & set(baseline_html_paths)):
        baseline_records = sensitive_html(git_blob(tree, base, rel).decode("utf-8-sig"))
        current_records = sensitive_html((tree / rel).read_text(encoding="utf-8-sig"))
        file_errors: list[str] = []
        if len(baseline_records) != len(current_records):
            file_errors.append(f"sensitive attribute count {len(baseline_records)} -> {len(current_records)}")
        for index, (before, after) in enumerate(zip(baseline_records, current_records)):
            identity_before = (before["tag"], before["attribute"], before["attribute_occurrence"])
            identity_after = (after["tag"], after["attribute"], after["attribute_occurrence"])
            if identity_before != identity_after:
                file_errors.append(f"record {index}: identity drift {identity_before!r} -> {identity_after!r}")
                continue
            if before["value"] == after["value"]:
                continue
            key = (rel, before["attribute"], before["attribute_occurrence"])
            exception = allowed.get(key)
            if (
                exception
                and before["value"] == exception["baseline_value"]
                and after["value"] == exception["expected_value"]
            ):
                allowed_seen.add(key)
                continue
            file_errors.append(
                f"record {index} {before['attribute']}[{before['attribute_occurrence']}]: "
                f"{before['value']!r} -> {after['value']!r}"
            )
        if file_errors:
            html_errors.extend(f"{rel}: {message}" for message in file_errors)
        html_rows.append({
            "path": rel,
            "sensitive_attributes": len(current_records),
            "match": not file_errors,
            "errors": file_errors,
        })
    missing_allowed = sorted(set(allowed) - allowed_seen)
    # During a final Pass16 verification all five promised translations must exist.
    # A baseline infrastructure preflight may intentionally precede those edits.
    if missing_allowed and not args.skip_checklist:
        html_errors.append(f"declared sensitive-attribute translations not observed: {missing_allowed}")
    if len(html_paths) != EXPECTED_HTML_COUNT:
        html_errors.append(f"HTML count drift expected={EXPECTED_HTML_COUNT} actual={len(html_paths)}")
    checks["html_sensitive_attributes"] = {
        "status": "PASS" if not html_errors else "FAIL",
        "expected_html_count": EXPECTED_HTML_COUNT,
        "actual_html_count": len(html_paths),
        "allowed_changes_declared": len(allowed),
        "allowed_changes_observed": len(allowed_seen),
        "allowed_changes_pending_preflight": missing_allowed if args.skip_checklist else [],
        "files": html_rows,
        "errors": html_errors,
    }
    errors.extend(f"html_sensitive_attributes: {item}" for item in html_errors)

    # Protected CSS and the three already completed gacha files: exact normalized bytes.
    baseline_css_paths = [
        rel for rel in git_lines(tree, "ls-tree", "-r", "--name-only", base, "--", "magica/css")
        if rel.endswith(".css")
    ]
    current_css_paths = [
        rel for rel in product_files(tree, ".css")
        if rel.startswith("magica/css/")
    ]
    protected_errors: list[str] = []
    if baseline_css_paths != current_css_paths:
        protected_errors.append(
            f"CSS path-set drift missing={sorted(set(baseline_css_paths)-set(current_css_paths))} "
            f"extra={sorted(set(current_css_paths)-set(baseline_css_paths))}"
        )
    protected_rows: list[dict[str, Any]] = []
    for rel in sorted(set(baseline_css_paths) | set(GACHA_PATHS)):
        try:
            baseline_bytes = normalized_lf(git_blob(tree, base, rel))
            current_bytes = normalized_lf((tree / rel).read_bytes())
            same = baseline_bytes == current_bytes
            protected_rows.append({
                "path": rel,
                "baseline_sha256_lf": sha256(baseline_bytes),
                "current_sha256_lf": sha256(current_bytes),
                "identical": same,
            })
            if not same:
                protected_errors.append(f"protected file drift: {rel}")
        except Exception as exc:
            protected_errors.append(f"protected file error {rel}: {type(exc).__name__}: {exc}")
    checks["protected_paths"] = {
        "status": "PASS" if not protected_errors else "FAIL",
        "css_count": len(baseline_css_paths),
        "gacha_count": len(GACHA_PATHS),
        "files": protected_rows,
        "errors": protected_errors,
    }
    errors.extend(f"protected_paths: {item}" for item in protected_errors)

    # Unicode hygiene in all product JS/HTML/JSON/CSS and in the review checklist.
    hygiene_paths = sorted(set(
        product_files(tree, ".js")
        + product_files(tree, ".html")
        + product_files(tree, ".json")
        + product_files(tree, ".css")
    ))
    unicode_findings: list[dict[str, Any]] = []
    for rel in hygiene_paths:
        unicode_findings.extend(inspect_forbidden_unicode(rel, (tree / rel).read_bytes()))
        if len(unicode_findings) >= 100:
            break
    if not args.skip_checklist and checklist.is_file():
        unicode_findings.extend(inspect_forbidden_unicode(str(checklist), checklist.read_bytes()))
    if unicode_findings:
        errors.extend(f"unicode_hygiene: {row}" for row in unicode_findings)
    checks["unicode_hygiene"] = {
        "status": "PASS" if not unicode_findings else "FAIL",
        "files_scanned": len(hygiene_paths) + (int(checklist.is_file()) if not args.skip_checklist else 0),
        "findings": unicode_findings,
    }

    diff_check = run(["git", "-C", str(tree), "diff", "--check", base, "--", "magica"])
    if diff_check.returncode:
        errors.append(f"git_diff_check: {diff_check.stdout.strip()} {diff_check.stderr.strip()}".strip())
    checks["git_diff_check"] = {
        "status": "PASS" if diff_check.returncode == 0 else "FAIL",
        "command": f"git -C {tree} diff --check {base} -- magica",
        "exit_code": diff_check.returncode,
        "stdout": diff_check.stdout,
        "stderr": diff_check.stderr,
    }

    if args.skip_checklist:
        checks["manual_review_checklist"] = {"status": "SKIPPED", "final_validation_eligible": False}
    else:
        checklist_result = verify_checklist(checklist, checklist_summary, tree, base)
        checks["manual_review_checklist"] = checklist_result
        errors.extend(f"manual_review_checklist: {item}" for item in checklist_result.get("errors", []))

    result = {
        "schema": "magireco-cn-pass16-verification/v1",
        "status": "PASS" if not errors and not args.skip_checklist else ("PREFLIGHT_PASS" if not errors else "FAIL"),
        "final_validation_eligible": not args.skip_checklist,
        "tree": str(tree),
        "baseline_commit": base,
        "checks": checks,
        "error_count": len(errors),
        "errors": errors,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8", newline="\n")
    sys.stdout.write(rendered)
    return 0 if result["status"] in {"PASS", "PREFLIGHT_PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
