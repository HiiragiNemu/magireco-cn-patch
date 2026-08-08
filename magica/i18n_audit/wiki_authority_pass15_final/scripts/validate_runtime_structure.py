#!/usr/bin/env python3
"""Read-only structural validator for the MagiaCN 23-dictionary runtime layer.

The validator deliberately never calls the builder's ``main`` function and never writes
inside the tree under test.  It validates the standalone JSON files, the embedded jQuery
payload, composite-key mapping, the Doppel three-way relation, JavaScript syntax, and
optionally compares the tree with a baseline without assuming array indices are stable IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


EXPECTED_DICT_NAMES = (
    "arenaClassList", "cardList", "cardMagiaMap", "cardSkillMap", "chapterList",
    "charaList", "charaMessageList", "doppelCardMagiaMap", "doppelList",
    "emotionSkillMap", "enemyList", "eventList", "eventStoryList",
    "formationSheetList", "giftList", "itemList", "live2dList", "patrolAreaList",
    "pieceList", "pieceSkillMap", "placeSkillMap", "sectionList", "shopItemList",
)

EXPECTED_LIST_NAMES = {
    "arenaClassList", "cardList", "chapterList", "charaList", "charaMessageList",
    "doppelList", "enemyList", "eventList", "eventStoryList", "formationSheetList",
    "giftList", "itemList", "live2dList", "patrolAreaList", "pieceList",
    "sectionList", "shopItemList",
}

SENSITIVE_CREDIT_FIELDS = {"illustrator", "designer", "voiceActor"}

PLACEHOLDER_PATTERNS = (
    re.compile(r"<%[=-]?[\s\S]*?%>"),
    re.compile(r"\{\{[\s\S]*?\}\}"),
    re.compile(r"\$\{[^{}]*\}"),
    re.compile(r"%(?:\d+\$)?[-+#0 ']*\d*(?:\.\d+)?[diouxXeEfFgGaAcspn%]"),
    re.compile(r"\{\d+(?::[^{}]+)?\}"),
    re.compile(r"\\(?:[nrtbfv\\\"']|u[0-9A-Fa-f]{4}|x[0-9A-Fa-f]{2})"),
)
HTML_TAG_PATTERN = re.compile(r"</?\s*([A-Za-z][A-Za-z0-9:-]*)\b[^>]*>")
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)*(?:%|％)?")
ROMAN_PATTERN = re.compile(r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+|\b[IVXLCDM]+\b")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_tree(path: Path) -> tuple[Path, Path, Path]:
    path = path.resolve()
    if (path / "magica" / "js" / "libs").is_dir():
        root = path
        libs = path / "magica" / "js" / "libs"
    elif path.name == "libs" and path.is_dir():
        libs = path
        root = path.parents[2]
    else:
        raise FileNotFoundError(f"tree does not contain magica/js/libs: {path}")
    builder = root / "Build_JS_Injector.py"
    if not builder.is_file():
        raise FileNotFoundError(f"builder missing: {builder}")
    return root, libs, builder


def load_builder(path: Path):
    name = "runtime_builder_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def extract_embedded_payload(jquery: Path) -> dict[str, Any]:
    text = jquery.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8-sig")
    start = text.rfind("(function(){")
    if start < 0:
        raise ValueError("audited injector start marker not found")
    marker = "var cn = "
    pos = text.find(marker, start)
    if pos < 0:
        raise ValueError("embedded dictionary marker not found")
    payload, _ = json.JSONDecoder().raw_decode(text[pos + len(marker):])
    if not isinstance(payload, dict):
        raise TypeError("embedded payload is not a JSON object")
    return payload


def walk_leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            yield from walk_leaves(child, f"{pointer}/{escaped}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_leaves(child, f"{pointer}/{index}")
    else:
        yield pointer or "/", value


def record_shapes(mapped: dict[str, Any]) -> dict[str, tuple[str, ...] | str]:
    result: dict[str, tuple[str, ...] | str] = {}
    for key, row in mapped.items():
        result[str(key)] = tuple(sorted(map(str, row.keys()))) if isinstance(row, dict) else type(row).__name__
    return result


def token_signature(value: str) -> dict[str, list[str]]:
    placeholders: list[str] = []
    for pattern in PLACEHOLDER_PATTERNS:
        placeholders.extend(match.group(0) for match in pattern.finditer(value))
    tags = [match.group(0) for match in HTML_TAG_PATTERN.finditer(value)]
    return {
        "placeholders": placeholders,
        "html_tags": tags,
        "numbers": NUMBER_PATTERN.findall(value),
        "roman": ROMAN_PATTERN.findall(value),
    }


def mapped_flatten(mapped: dict[str, Any]) -> dict[tuple[str, str], Any]:
    output: dict[tuple[str, str], Any] = {}
    for record_key, row in mapped.items():
        for pointer, value in walk_leaves(row):
            output[(str(record_key), pointer)] = value
    return output


def text_health(raw_by_name: dict[str, Any]) -> dict[str, Any]:
    replacement: list[dict[str, str]] = []
    nul_or_control: list[dict[str, str]] = []
    bidi_controls: list[dict[str, str]] = []
    string_count = 0
    for name, raw in raw_by_name.items():
        for pointer, value in walk_leaves(raw):
            if not isinstance(value, str):
                continue
            string_count += 1
            if "\ufffd" in value:
                replacement.append({"dictionary": name, "pointer": pointer, "value": value})
            bad = [f"U+{ord(ch):04X}" for ch in value if unicodedata.category(ch) == "Cc" and ch not in "\t\n\r"]
            if bad:
                nul_or_control.append({"dictionary": name, "pointer": pointer, "codepoints": ",".join(bad)})
            bidi = [f"U+{ord(ch):04X}" for ch in value if ord(ch) in {
                0x061C, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
                0x2066, 0x2067, 0x2068, 0x2069,
            }]
            if bidi:
                bidi_controls.append({"dictionary": name, "pointer": pointer, "codepoints": ",".join(bidi)})
    return {
        "string_leaf_count": string_count,
        "replacement_character_count": len(replacement),
        "control_character_count": len(nul_or_control),
        "bidi_control_count": len(bidi_controls),
        "replacement_character_samples": replacement[:20],
        "control_character_samples": nul_or_control[:20],
        "bidi_control_samples": bidi_controls[:20],
    }


def compare_baseline(
    current_raw: dict[str, Any],
    current_mapped: dict[str, dict[str, Any]],
    baseline_root: Path,
) -> dict[str, Any]:
    _, baseline_libs, baseline_builder_path = resolve_tree(baseline_root)
    baseline_builder = load_builder(baseline_builder_path)
    baseline_raw: dict[str, Any] = {}
    baseline_mapped: dict[str, dict[str, Any]] = {}
    missing_files: list[str] = []
    for name in EXPECTED_DICT_NAMES:
        path = baseline_libs / f"{name}.json"
        if not path.is_file():
            missing_files.append(path.name)
            continue
        raw = load_json(path)
        baseline_raw[name] = raw
        baseline_mapped[name] = baseline_builder.map_dictionary(name, raw)

    key_set_drift: list[dict[str, Any]] = []
    record_shape_drift: list[dict[str, Any]] = []
    non_string_drift: list[dict[str, Any]] = []
    placeholder_drift: list[dict[str, Any]] = []
    html_tag_drift: list[dict[str, Any]] = []
    numeric_signature_drift: list[dict[str, Any]] = []
    roman_signature_drift: list[dict[str, Any]] = []
    sensitive_credit_drift: list[dict[str, Any]] = []
    changed_string_fields = 0

    for name in EXPECTED_DICT_NAMES:
        if name not in baseline_mapped:
            continue
        old = baseline_mapped[name]
        new = current_mapped[name]
        old_keys, new_keys = set(old), set(new)
        if old_keys != new_keys:
            key_set_drift.append({
                "dictionary": name,
                "missing": sorted(old_keys - new_keys),
                "extra": sorted(new_keys - old_keys),
            })
        shared = sorted(old_keys & new_keys)
        old_shapes = record_shapes(old)
        new_shapes = record_shapes(new)
        for key in shared:
            if old_shapes[key] != new_shapes[key]:
                record_shape_drift.append({
                    "dictionary": name, "key": key,
                    "before": old_shapes[key], "after": new_shapes[key],
                })
        old_flat = mapped_flatten({key: old[key] for key in shared})
        new_flat = mapped_flatten({key: new[key] for key in shared})
        for leaf_key in sorted(set(old_flat) & set(new_flat)):
            before, after = old_flat[leaf_key], new_flat[leaf_key]
            if before == after:
                continue
            record_key, pointer = leaf_key
            entry = {"dictionary": name, "key": record_key, "pointer": pointer, "before": before, "after": after}
            if not isinstance(before, str) or not isinstance(after, str):
                non_string_drift.append(entry)
                continue
            changed_string_fields += 1
            field = pointer.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
            if field in SENSITIVE_CREDIT_FIELDS:
                sensitive_credit_drift.append(entry)
            bs, as_ = token_signature(before), token_signature(after)
            if bs["placeholders"] != as_["placeholders"]:
                placeholder_drift.append(entry | {"before_signature": bs["placeholders"], "after_signature": as_["placeholders"]})
            if bs["html_tags"] != as_["html_tags"]:
                html_tag_drift.append(entry | {"before_signature": bs["html_tags"], "after_signature": as_["html_tags"]})
            if bs["numbers"] != as_["numbers"]:
                numeric_signature_drift.append(entry | {"before_signature": bs["numbers"], "after_signature": as_["numbers"]})
            if bs["roman"] != as_["roman"]:
                roman_signature_drift.append(entry | {"before_signature": bs["roman"], "after_signature": as_["roman"]})

    return {
        "baseline_root": str(baseline_root.resolve()),
        "missing_dictionary_files": missing_files,
        "changed_string_field_count": changed_string_fields,
        "key_set_drift_count": len(key_set_drift),
        "record_shape_drift_count": len(record_shape_drift),
        "non_string_drift_count": len(non_string_drift),
        "placeholder_drift_count": len(placeholder_drift),
        "html_tag_drift_count": len(html_tag_drift),
        "numeric_signature_drift_count": len(numeric_signature_drift),
        "roman_signature_drift_count": len(roman_signature_drift),
        "sensitive_credit_drift_count": len(sensitive_credit_drift),
        "key_set_drift": key_set_drift,
        "record_shape_drift": record_shape_drift[:100],
        "non_string_drift": non_string_drift[:100],
        "placeholder_drift": placeholder_drift[:100],
        "html_tag_drift": html_tag_drift[:100],
        "numeric_signature_drift": numeric_signature_drift[:100],
        "roman_signature_drift": roman_signature_drift[:100],
        "sensitive_credit_drift": sensitive_credit_drift[:100],
    }


def audit(tree: Path, baseline: Path | None) -> dict[str, Any]:
    root, libs, builder_path = resolve_tree(tree)
    builder = load_builder(builder_path)
    declared_names = tuple(builder.DICT_NAMES)
    actual_names = tuple(sorted(p.stem for p in libs.glob("*.json")))
    expected_set = set(EXPECTED_DICT_NAMES)
    actual_set = set(actual_names)

    errors: list[str] = []
    warnings: list[str] = []
    if declared_names != EXPECTED_DICT_NAMES:
        errors.append("builder DICT_NAMES order/set differs from the pinned 23-name contract")
    if actual_set != expected_set:
        errors.append(f"dictionary set drift: missing={sorted(expected_set-actual_set)} extra={sorted(actual_set-expected_set)}")

    raw_by_name: dict[str, Any] = {}
    mapped_by_name: dict[str, dict[str, Any]] = {}
    dictionary_rows: dict[str, dict[str, Any]] = {}
    for name in EXPECTED_DICT_NAMES:
        path = libs / f"{name}.json"
        if not path.is_file():
            continue
        raw = load_json(path)
        expected_type = list if name in EXPECTED_LIST_NAMES else dict
        if not isinstance(raw, expected_type):
            errors.append(f"{name}: expected {expected_type.__name__}, found {type(raw).__name__}")
            continue
        raw_by_name[name] = raw
        try:
            mapped = builder.map_dictionary(name, raw)
        except Exception as exc:  # fail closed while still producing a report
            errors.append(f"{name}: map_dictionary failed: {type(exc).__name__}: {exc}")
            continue
        if not isinstance(mapped, dict):
            errors.append(f"{name}: mapped value is not an object")
            continue
        mapped_by_name[name] = mapped
        raw_count = len(raw)
        mapped_count = len(mapped)
        skipped = raw_count - mapped_count if isinstance(raw, list) else 0
        dictionary_rows[name] = {
            "raw_type": type(raw).__name__,
            "raw_rows": raw_count,
            "mapped_rows": mapped_count,
            "skipped_or_collided_rows": skipped,
            "sha256": sha256(path),
        }
        if isinstance(raw, list) and raw_count != mapped_count:
            errors.append(f"{name}: {raw_count} rows map to {mapped_count} keys")

    embedded_status: dict[str, Any]
    jquery = libs / "jquery-3.7.1.min.js"
    try:
        embedded = extract_embedded_payload(jquery)
        mismatch = [name for name in EXPECTED_DICT_NAMES if embedded.get(name) != mapped_by_name.get(name)]
        embedded_status = {
            "payload_dictionary_count": len(embedded),
            "set_matches": set(embedded) == expected_set,
            "mapped_dictionary_mismatch_count": len(mismatch),
            "mapped_dictionary_mismatches": mismatch,
            "jquery_sha256": sha256(jquery),
            "jquery_bytes": jquery.stat().st_size,
        }
        if set(embedded) != expected_set:
            errors.append("embedded dictionary set differs from standalone set")
        if mismatch:
            errors.append(f"embedded payload differs from mapped standalone dictionaries: {mismatch}")
    except Exception as exc:
        embedded_status = {"error": f"{type(exc).__name__}: {exc}"}
        errors.append(f"embedded payload parse failed: {type(exc).__name__}: {exc}")

    try:
        node = subprocess.run(
            ["node", "--check", str(jquery)], capture_output=True, text=True, timeout=120,
        )
        node_status = {"exit_code": node.returncode, "stdout": node.stdout, "stderr": node.stderr}
        if node.returncode != 0:
            errors.append("node --check failed")
    except Exception as exc:
        node_status = {"error": f"{type(exc).__name__}: {exc}"}
        errors.append(f"node --check could not run: {type(exc).__name__}: {exc}")

    doppel_status: dict[str, Any] = {}
    if all(name in raw_by_name for name in ("doppelList", "cardMagiaMap", "doppelCardMagiaMap")):
        missing_card_magia: list[dict[str, Any]] = []
        missing_doppel_magia: list[dict[str, Any]] = []
        name_mismatch: list[dict[str, Any]] = []
        rows = raw_by_name["doppelList"]
        card_magia = raw_by_name["cardMagiaMap"]
        doppel_magia = raw_by_name["doppelCardMagiaMap"]
        for row in rows:
            doppel_id = int(row["id"])
            chara_id = doppel_id // 100
            magia_id = str(chara_id * 10 + 8)
            cm = card_magia.get(magia_id)
            dm = doppel_magia.get(magia_id)
            if not isinstance(cm, dict):
                missing_card_magia.append({"doppelId": doppel_id, "magiaId": magia_id})
            if not isinstance(dm, dict):
                missing_doppel_magia.append({"doppelId": doppel_id, "magiaId": magia_id})
            names = {"doppelList": row.get("name"), "cardMagiaMap": cm.get("name") if isinstance(cm, dict) else None,
                     "doppelCardMagiaMap": dm.get("name") if isinstance(dm, dict) else None}
            if len(set(names.values())) != 1:
                name_mismatch.append({"doppelId": doppel_id, "magiaId": magia_id, "names": names})
        doppel_status = {
            "doppel_rows": len(rows),
            "card_magia_linked": len(rows) - len(missing_card_magia),
            "doppel_magia_linked": len(rows) - len(missing_doppel_magia),
            "three_way_name_matches": len(rows) - len(name_mismatch),
            "missing_card_magia": missing_card_magia,
            "missing_doppel_magia": missing_doppel_magia,
            "name_mismatch": name_mismatch,
        }
        if missing_card_magia or missing_doppel_magia or name_mismatch:
            errors.append("Doppel triad relation is incomplete or name-inconsistent")

    health = text_health(raw_by_name)
    if health["replacement_character_count"]:
        errors.append("U+FFFD replacement characters present")
    if health["control_character_count"]:
        errors.append("unexpected C0/C1 control characters present")
    if health["bidi_control_count"]:
        warnings.append("bidirectional control characters present; inspect samples")

    baseline_status = compare_baseline(raw_by_name, mapped_by_name, baseline) if baseline else None
    if baseline_status:
        for key in (
            "missing_dictionary_files", "key_set_drift_count", "record_shape_drift_count",
            "non_string_drift_count", "placeholder_drift_count", "html_tag_drift_count",
            "sensitive_credit_drift_count",
        ):
            value = baseline_status[key]
            if value:
                errors.append(f"baseline invariant failed: {key}={value}")
        if baseline_status["numeric_signature_drift_count"]:
            warnings.append(f"numeric signature drift requires semantic ledger: {baseline_status['numeric_signature_drift_count']}")
        if baseline_status["roman_signature_drift_count"]:
            warnings.append(f"Roman-numeral signature drift requires semantic ledger: {baseline_status['roman_signature_drift_count']}")

    return {
        "schema": "magireco-runtime-structure-audit/v1",
        "status": "PASS" if not errors else "FAIL",
        "tree": str(root),
        "dictionary_contract": {
            "expected_count": len(EXPECTED_DICT_NAMES),
            "actual_count": len(actual_set),
            "builder_declared_count": len(declared_names),
            "missing": sorted(expected_set - actual_set),
            "extra": sorted(actual_set - expected_set),
        },
        "dictionary_rows": dictionary_rows,
        "embedded_payload": embedded_status,
        "node_check": node_status,
        "doppel_triad": doppel_status,
        "text_health": health,
        "baseline_comparison": baseline_status,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.tree, args.baseline)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": report["status"],
        "errors": report["errors"],
        "warnings": report["warnings"],
        "output": str(args.out.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
