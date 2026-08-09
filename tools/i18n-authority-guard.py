#!/usr/bin/env python3
"""Validate translation precedence and the committed MagiaCN runtime dictionaries.

This guard deliberately does not translate or rewrite product files.  It makes the
authority decision reproducible and fails closed when a lower-priority candidate is
selected, when a canonical name regresses, or when the 23 JSON dictionaries and the
embedded ``var cn`` payload in jQuery diverge.

Authority order (highest first): official CN dump, Wiki, existing human translation,
then a new human/LLM translation.  A documented *absence* at a higher layer permits the
next present layer to win; an absence is never treated as a translation.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator


EXPECTED_WEIGHTS = {
    "official_cn_dump": 400,
    "wiki": 300,
    "existing_human": 200,
    "new_human_or_llm": 100,
}
PROVENANCE_COLUMNS = (
    "term_id",
    "japanese",
    "candidate_cn",
    "authority",
    "weight",
    "status",
    "selected",
    "source_locator",
    "scanned_files",
    "hit_count",
    "evidence",
)
VALID_STATUSES = {"present", "absent", "rejected"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return json.load(handle)


def read_provenance(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != PROVENANCE_COLUMNS:
            errors.append(
                f"provenance header mismatch: expected {PROVENANCE_COLUMNS!r}, "
                f"got {tuple(reader.fieldnames or ())!r}"
            )
        rows = list(reader)
    return rows, errors


def _as_bool(value: str, *, context: str, errors: list[str]) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        errors.append(f"{context}: selected must be true or false, got {value!r}")
    return normalized == "true"


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("schema_version") != 1:
        errors.append("policy schema_version must be 1")
    levels = policy.get("authority_order")
    if not isinstance(levels, list):
        return errors + ["policy authority_order must be a list"]
    actual: dict[str, int] = {}
    for index, level in enumerate(levels):
        if not isinstance(level, dict):
            errors.append(f"authority_order[{index}] must be an object")
            continue
        try:
            actual[str(level["id"])] = int(level["weight"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"authority_order[{index}] has invalid id/weight")
    if actual != EXPECTED_WEIGHTS:
        errors.append(f"authority weights changed: expected {EXPECTED_WEIGHTS}, got {actual}")
    ordered_weights = [actual.get(str(level.get("id")), -1) for level in levels if isinstance(level, dict)]
    if ordered_weights != sorted(ordered_weights, reverse=True):
        errors.append("authority_order is not sorted from highest to lowest weight")
    return errors


def validate_provenance(
    policy: dict[str, Any], rows: list[dict[str, str]]
) -> list[str]:
    """Validate source evidence and ensure that the selected present row is strongest."""

    errors: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lineno, raw in enumerate(rows, 2):
        context = f"provenance line {lineno}"
        authority = raw.get("authority", "")
        if authority not in EXPECTED_WEIGHTS:
            errors.append(f"{context}: unknown authority {authority!r}")
            continue
        try:
            weight = int(raw.get("weight", ""))
        except ValueError:
            errors.append(f"{context}: invalid weight {raw.get('weight')!r}")
            continue
        if weight != EXPECTED_WEIGHTS[authority]:
            errors.append(
                f"{context}: {authority} must have weight {EXPECTED_WEIGHTS[authority]}, got {weight}"
            )
        status = raw.get("status", "")
        if status not in VALID_STATUSES:
            errors.append(f"{context}: invalid status {status!r}")
        selected = _as_bool(raw.get("selected", ""), context=context, errors=errors)
        candidate = raw.get("candidate_cn", "")
        if status == "absent":
            if candidate:
                errors.append(f"{context}: absent source must not contain candidate_cn")
            if selected:
                errors.append(f"{context}: absent source must not be selected")
        elif status == "present" and not candidate:
            errors.append(f"{context}: present source requires candidate_cn")
        elif status == "rejected" and selected:
            errors.append(f"{context}: rejected candidate must not be selected")
        enriched = dict(raw)
        enriched.update(_lineno=lineno, _weight=weight, _selected=selected)
        grouped[raw.get("term_id", "")].append(enriched)

    canonical_terms = policy.get("canonical_terms", [])
    expected_ids = {str(term.get("term_id")) for term in canonical_terms if isinstance(term, dict)}
    extra_ids = set(grouped) - expected_ids
    if extra_ids:
        errors.append(f"provenance contains terms absent from policy: {sorted(extra_ids)}")

    for term in canonical_terms:
        if not isinstance(term, dict):
            errors.append("canonical_terms contains a non-object entry")
            continue
        term_id = str(term.get("term_id", ""))
        term_rows = grouped.get(term_id, [])
        if not term_rows:
            errors.append(f"{term_id}: no provenance rows")
            continue

        official_expected = term.get("official_cn_dump", {})
        official_absent = [
            row
            for row in term_rows
            if row.get("authority") == "official_cn_dump" and row.get("status") == "absent"
        ]
        if len(official_absent) != 1:
            errors.append(f"{term_id}: expected exactly one official-cn absent evidence row")
        else:
            row = official_absent[0]
            try:
                scanned = int(row.get("scanned_files", ""))
                hits = int(row.get("hit_count", ""))
            except ValueError:
                errors.append(f"{term_id}: official absence scan counts must be integers")
            else:
                if scanned != int(official_expected.get("eligible_files_scanned", -1)):
                    errors.append(
                        f"{term_id}: official scan file count mismatch: {scanned}"
                    )
                if hits != 0 or hits != int(official_expected.get("hit_count", -1)):
                    errors.append(f"{term_id}: official absence evidence must have zero hits")
            if not row.get("source_locator") or not row.get("evidence"):
                errors.append(f"{term_id}: official absence row lacks source/evidence")

        present = [row for row in term_rows if row.get("status") == "present"]
        selected = [row for row in present if row.get("_selected")]
        if not present:
            errors.append(f"{term_id}: no present candidates")
            continue
        if len(selected) != 1:
            errors.append(f"{term_id}: expected exactly one selected present candidate")
            continue
        highest = max(int(row["_weight"]) for row in present)
        top_targets = {
            str(row.get("candidate_cn", ""))
            for row in present
            if int(row["_weight"]) == highest
        }
        if len(top_targets) != 1:
            errors.append(
                f"{term_id}: equal-weight authority conflict at {highest}: {sorted(top_targets)}"
            )
        winner = selected[0]
        if int(winner["_weight"]) != highest:
            errors.append(
                f"{term_id}: lower-weight candidate selected ({winner['_weight']} < {highest})"
            )
        if winner.get("candidate_cn") != term.get("chinese"):
            errors.append(
                f"{term_id}: selected target {winner.get('candidate_cn')!r} does not match "
                f"canonical {term.get('chinese')!r}"
            )
        if winner.get("authority") != term.get("authority"):
            errors.append(
                f"{term_id}: selected authority {winner.get('authority')!r} does not match "
                f"canonical {term.get('authority')!r}"
            )
        if winner.get("japanese") != term.get("japanese"):
            errors.append(f"{term_id}: source text does not match policy")

    return errors


def load_glossary(path: Path) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    errors: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip() or line.startswith("#"):
                continue
            columns = line.rstrip("\r\n").split("\t")
            if len(columns) < 2:
                errors.append(f"glossary line {lineno}: fewer than two columns")
                continue
            source, target = columns[:2]
            previous = mapping.get(source)
            if previous is not None and previous != target:
                errors.append(
                    f"glossary line {lineno}: conflicting targets for {source!r}: "
                    f"{previous!r} vs {target!r}"
                )
            mapping[source] = target
    return mapping, errors


def validate_glossary(policy: dict[str, Any], mapping: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for term in policy.get("canonical_terms", []):
        source = term["japanese"]
        target = term["chinese"]
        if mapping.get(source) != target:
            errors.append(
                f"glossary canonical mapping missing or wrong: {source!r} -> {target!r}"
            )
    return errors


def map_dictionary(name: str, data: Any, list_keys: dict[str, list[str]]) -> Any:
    if name not in list_keys:
        if not isinstance(data, dict):
            raise TypeError(f"{name} must be a JSON object")
        return data
    if not isinstance(data, list):
        raise TypeError(f"{name} must be a JSON array")
    mapped: dict[str, Any] = {}
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise TypeError(f"{name}[{index}] is not an object")
        if name == "charaMessageList":
            key = f"{item.get('charaNo', '')}_{item.get('messageId', '')}"
        elif name == "live2dList":
            key = f"{item.get('charaId', '')}_{item.get('live2dId', '')}"
        else:
            key = ""
            for field in list_keys[name]:
                if field in item:
                    key = str(item[field])
                    break
        if not key or key == "_":
            continue
        if key in mapped:
            raise ValueError(f"duplicate {name} key: {key}")
        mapped[key] = item
    return mapped


def extract_jquery_payload(path: Path) -> dict[str, Any]:
    text = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8-sig")
    runtime_start = text.rfind("(function(){")
    if runtime_start < 0:
        raise ValueError("audited injector start marker missing")
    marker = "var cn = "
    payload_start = text.find(marker, runtime_start)
    if payload_start < 0:
        raise ValueError("var cn payload marker missing")
    payload_start += len(marker)
    payload, consumed = json.JSONDecoder().raw_decode(text[payload_start:])
    if not isinstance(payload, dict):
        raise TypeError("jQuery var cn payload must be an object")
    if consumed <= 0:
        raise ValueError("empty jQuery var cn payload")
    return payload


def _iter_strings(value: Any, path: str = "$") -> Iterator[tuple[str, str, str]]:
    """Yield (path, leaf-field, value) for every string in a JSON-compatible tree."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if isinstance(child, str):
                yield child_path, str(key), child
            else:
                yield from _iter_strings(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_strings(child, f"{path}[{index}]")


def find_forbidden(
    policy: dict[str, Any], dictionaries: dict[str, Any], *, source: str
) -> list[str]:
    errors: list[str] = []
    for rule in policy.get("forbidden_regressions", []):
        needle = str(rule.get("text", ""))
        mode = rule.get("mode", "substring")
        allowed_dicts = set(rule.get("dictionaries", []))
        allowed_fields = set(rule.get("fields", []))
        for dictionary, data in dictionaries.items():
            if allowed_dicts and dictionary not in allowed_dicts:
                continue
            for path, field, value in _iter_strings(data, f"$.{dictionary}"):
                if allowed_fields and field not in allowed_fields:
                    continue
                hit = value == needle if mode == "exact" else needle in value
                if hit:
                    errors.append(
                        f"{source}: forbidden regression {needle!r} at {path}: {value!r}"
                    )
    return errors


def validate_assertions(policy: dict[str, Any], dictionaries: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for index, assertion in enumerate(policy.get("product_assertions", [])):
        dictionary = assertion["dictionary"]
        selector = assertion["selector"]
        data = dictionaries.get(dictionary)
        if not isinstance(data, list):
            errors.append(f"assertion[{index}]: {dictionary} is not a list")
            continue
        matches = [
            row
            for row in data
            if isinstance(row, dict)
            and all(row.get(field) == value for field, value in selector.items())
        ]
        if len(matches) != 1:
            errors.append(
                f"assertion[{index}]: selector {selector!r} matched {len(matches)} rows in {dictionary}"
            )
            continue
        row = matches[0]
        for field, expected in assertion.get("fields", {}).items():
            if row.get(field) != expected:
                errors.append(
                    f"assertion[{index}]: {dictionary} {selector!r} field {field!r} "
                    f"expected {expected!r}, got {row.get(field)!r}"
                )
        for field, expected_fragment in assertion.get("field_contains", {}).items():
            actual = row.get(field)
            if not isinstance(actual, str) or expected_fragment not in actual:
                errors.append(
                    f"assertion[{index}]: {dictionary} {selector!r} field {field!r} "
                    f"does not contain {expected_fragment!r}"
                )
    return errors


def validate_runtime(
    root: Path, policy: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    errors: list[str] = []
    libs = root / "magica" / "js" / "libs"
    contract = policy["dictionary_contract"]
    names = list(contract["names"])
    expected = set(names)
    actual = {path.stem for path in libs.glob("*.json")}
    if actual != expected:
        errors.append(
            f"dictionary set mismatch: missing={sorted(expected-actual)} extra={sorted(actual-expected)}"
        )
    dictionaries: dict[str, Any] = {}
    for name in names:
        path = libs / f"{name}.json"
        if not path.is_file():
            continue
        try:
            dictionaries[name] = load_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid JSON: {exc}")

    jquery_payload: dict[str, Any] = {}
    jquery_path = libs / "jquery-3.7.1.min.js"
    try:
        jquery_payload = extract_jquery_payload(jquery_path)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"{jquery_path}: invalid embedded dictionary payload: {exc}")

    if set(jquery_payload) != expected:
        errors.append(
            "jQuery dictionary set mismatch: "
            f"missing={sorted(expected-set(jquery_payload))} "
            f"extra={sorted(set(jquery_payload)-expected)}"
        )
    list_keys = contract["list_keys"]
    for name in names:
        if name not in dictionaries or name not in jquery_payload:
            continue
        try:
            expected_payload = map_dictionary(name, dictionaries[name], list_keys)
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if jquery_payload[name] != expected_payload:
            errors.append(f"jQuery payload differs from {name}.json")

    errors.extend(validate_assertions(policy, dictionaries))
    errors.extend(find_forbidden(policy, dictionaries, source="23 JSON"))
    errors.extend(find_forbidden(policy, jquery_payload, source="jQuery payload"))
    return dictionaries, jquery_payload, errors


def validate_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    policy_path = root / "i18n" / "authority-policy.json"
    provenance_path = root / "i18n" / "authority-provenance.tsv"
    glossary_path = root / "i18n" / "glossary.tsv"

    try:
        policy = load_json(policy_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"{policy_path}: {exc}"]}
    errors.extend(validate_policy(policy))

    try:
        rows, read_errors = read_provenance(provenance_path)
    except (OSError, UnicodeError, csv.Error) as exc:
        rows, read_errors = [], [f"{provenance_path}: {exc}"]
    errors.extend(read_errors)
    errors.extend(validate_provenance(policy, rows))

    try:
        glossary, glossary_errors = load_glossary(glossary_path)
    except (OSError, UnicodeError) as exc:
        glossary, glossary_errors = {}, [f"{glossary_path}: {exc}"]
    errors.extend(glossary_errors)
    errors.extend(validate_glossary(policy, glossary))

    dictionaries, jquery_payload, runtime_errors = validate_runtime(root, policy)
    errors.extend(runtime_errors)
    return {
        "ok": not errors,
        "policy_id": policy.get("policy_id"),
        "authority_weights": EXPECTED_WEIGHTS,
        "provenance_rows": len(rows),
        "canonical_terms": len(policy.get("canonical_terms", [])),
        "glossary_rows": len(glossary),
        "json_dictionaries": len(dictionaries),
        "jquery_dictionaries": len(jquery_payload),
        "product_assertions": len(policy.get("product_assertions", [])),
        "forbidden_rules": len(policy.get("forbidden_regressions", [])),
        "errors": errors,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = validate_repository(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["ok"]:
        print(
            "authority guard: PASS; "
            f"provenance={report['provenance_rows']} canonical={report['canonical_terms']} "
            f"JSON={report['json_dictionaries']} jQuery={report['jquery_dictionaries']} "
            f"assertions={report['product_assertions']} forbidden_hits=0"
        )
    else:
        print("authority guard: FAIL", file=sys.stderr)
        for error in report["errors"]:
            print(f"- {error}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
