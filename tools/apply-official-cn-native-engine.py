#!/usr/bin/env python3
"""Apply or roll back audited official-CN native engine mappings."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_engine(path: Path) -> tuple[str, list[tuple[str, str]]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r\n" in raw:
        raise AssertionError("engine input must be UTF-8 without BOM and LF-only")
    lines = raw.decode("utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise AssertionError("engine header is missing")
    pairs: list[tuple[str, str]] = []
    for physical_line, line in enumerate(lines[1:], 2):
        parts = line.split("\t")
        if len(parts) != 2:
            raise AssertionError(f"malformed engine line {physical_line}")
        source, target = parts
        if not source or any(ch in source + target for ch in "\r\n"):
            raise AssertionError(f"invalid engine value at line {physical_line}")
        pairs.append((source, target))
    if len({source for source, _ in pairs}) != len(pairs):
        raise AssertionError("duplicate engine source key")
    return lines[0], pairs


def load_contract(path: Path) -> tuple[dict, list[dict]]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema") != "official-cn-native-localization-exhaustion/v1":
        raise AssertionError("unexpected native localization contract schema")
    mapping = contract.get("mapping_counts", {})
    expected = contract.get("expected_post_application", {})
    records = [record for record in contract.get("records", []) if record.get("product_write_allowed")]
    if mapping.get("all_stable_mapping_records") != 189 or len(records) != 182:
        raise AssertionError("native localization mapping count drift")
    if expected.get("engine_logical_rules") != 621 or expected.get("engine_physical_lines") != 622:
        raise AssertionError("native localization output count drift")
    if len({record["source"] for record in records}) != len(records):
        raise AssertionError("duplicate accepted native source key")
    if any(not record.get("selected_cn") for record in records):
        raise AssertionError("accepted native mapping has an empty selected value")
    return contract, records


def render(header: str, pairs: list[tuple[str, str]]) -> bytes:
    return (header + "\n" + "".join(f"{source}\t{target}\n" for source, target in pairs)).encode("utf-8")


def transform(engine: Path, evidence: Path, mode: str) -> tuple[bytes, dict]:
    before_bytes = engine.read_bytes()
    header, pairs = load_engine(engine)
    contract, records = load_contract(evidence)
    order = [source for source, _ in pairs]
    values = dict(pairs)
    changed: list[dict] = []

    added_records = [record for record in records if not record["current_cn"]]
    added_sources = [record["source"] for record in added_records]
    present_added = [source for source in added_sources if source in values]
    if present_added and len(present_added) != len(added_sources):
        raise AssertionError("partial official-CN added-source set")

    official_post_rows = contract["expected_post_application"]["engine_logical_rules"]
    official_baseline_rows = official_post_rows - len(added_sources)
    official_core_rows = official_post_rows if present_added else official_baseline_rows
    if len(pairs) < official_core_rows:
        raise AssertionError("native engine is shorter than the official-CN core")

    accepted_sources = {record["source"] for record in records}
    expected_core_sources = accepted_sources - (set(added_sources) if not present_added else set())
    core_sources = set(order[:official_core_rows])
    extension_sources = set(order[official_core_rows:])
    if not expected_core_sources.issubset(core_sources):
        raise AssertionError("official-CN source escaped the native engine core")
    if accepted_sources & extension_sources:
        raise AssertionError("official-CN source collided with an extension rule")
    extension_logical_rules = len(pairs) - official_core_rows
    insertion_index = official_core_rows

    if mode == "apply":
        for record in records:
            source = record["source"]
            baseline = record["current_cn"]
            selected = record["selected_cn"]
            current = values.get(source)
            if baseline:
                if current not in {baseline, selected}:
                    raise AssertionError(f"before-value drift for {source!r}")
                if current != selected:
                    values[source] = selected
                    changed.append({"source": source, "before": current, "after": selected, "operation": "replace"})
            else:
                if current is None:
                    values[source] = selected
                    order.insert(insertion_index, source)
                    insertion_index += 1
                    changed.append({"source": source, "before": "", "after": selected, "operation": "add"})
                elif current != selected:
                    raise AssertionError(f"new-source collision for {source!r}")
        expected_rows = len(pairs) + len(added_sources) - len(present_added)
    elif mode == "rollback":
        for record in reversed(records):
            source = record["source"]
            baseline = record["current_cn"]
            selected = record["selected_cn"]
            current = values.get(source)
            if baseline:
                if current not in {baseline, selected}:
                    raise AssertionError(f"modified-value drift for {source!r}")
                if current != baseline:
                    values[source] = baseline
                    changed.append({"source": source, "before": current, "after": baseline, "operation": "restore"})
            else:
                if current is None:
                    continue
                if current != selected:
                    raise AssertionError(f"added-source drift for {source!r}")
                del values[source]
                order.remove(source)
                changed.append({"source": source, "before": current, "after": "", "operation": "remove"})
        expected_rows = len(pairs) - len(present_added)
    else:
        raise AssertionError(f"unsupported mode: {mode}")

    output_pairs = [(source, values[source]) for source in order]
    if len(output_pairs) != expected_rows or len({source for source, _ in output_pairs}) != expected_rows:
        raise AssertionError("transformed engine row count or uniqueness drift")
    output_bytes = render(header, output_pairs)
    verification = {
        "schema": "official-cn-native-engine-transform-verification/v1",
        "mode": mode,
        "input": str(engine),
        "evidence": str(evidence),
        "input_bytes": len(before_bytes),
        "output_bytes": len(output_bytes),
        "input_logical_rules": len(pairs),
        "output_logical_rules": len(output_pairs),
        "official_core_logical_rules": official_core_rows,
        "protected_extension_logical_rules": extension_logical_rules,
        "changed_records": len(changed),
        "changes": changed,
        "protected_debug_source_writes": 0,
        "ok": True,
    }
    return output_bytes, verification


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--mode", choices=("apply", "rollback"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.engine.resolve():
        raise SystemExit("output must differ from input")
    output, verification = transform(args.engine, args.evidence, args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.verification.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    args.verification.write_text(
        json.dumps(verification, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({key: verification[key] for key in (
        "mode", "input_logical_rules", "output_logical_rules", "changed_records",
        "input_bytes", "output_bytes", "ok",
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
