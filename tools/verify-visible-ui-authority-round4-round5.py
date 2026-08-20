#!/usr/bin/env python3
"""Read-only authority/runtime verifier for visible-text rounds 4 and 5."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
from typing import Any


RESEARCH = Path("magica/research/totentanz-full-localization-20260817")
ROUND4 = RESEARCH / "visible-ui-authority-round4-chara-kana"
ROUND5 = RESEARCH / "visible-ui-authority-round5-sisters"
CHARA = Path("magica/js/libs/charaList.json")
PIECE = Path("magica/js/libs/pieceList.json")
JQUERY = Path("magica/js/libs/jquery-3.7.1.min.js")
LATIN = re.compile(r"[A-Za-z]")


class VerificationError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def extract_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    start = text.rfind("(function(){")
    marker = "var cn = "
    payload_start = text.find(marker, start)
    if start < 0 or payload_start < 0:
        raise VerificationError("jQuery runtime dictionary marker is missing")
    value, _ = json.JSONDecoder().raw_decode(text[payload_start + len(marker):])
    if not isinstance(value, dict):
        raise VerificationError("jQuery runtime dictionary payload is not an object")
    return value


def index_unique(
    records: Any, key: str, label: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        errors.append(f"{label}: root is not a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(records):
        if not isinstance(row, dict) or key not in row:
            errors.append(f"{label}[{position}]: missing stable key {key}")
            continue
        stable = str(row[key])
        if stable in result:
            errors.append(f"{label}: duplicate stable key {stable}")
            continue
        result[stable] = row
    return result


def protected_record(row: dict[str, Any], allowed_field: str) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != allowed_field}


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    paths = {
        "r4_manifest": root / ROUND4 / "character_kana_apply_manifest.json",
        "r4_application": root / ROUND4 / "application_verification.json",
        "r4_rows": root / ROUND4 / "character_kana_visible_candidates.tsv",
        "r4_official": root / ROUND4 / "official_chara_kana_structural_sample.tsv",
        "r4_protected": root / ROUND4 / "protected_operation_siblings.json",
        "r5_manifest": root / ROUND5 / "remaining_explicit_visible_apply_manifest.json",
        "r5_application": root / ROUND5 / "application_verification.json",
        "r5_rows": root / ROUND5 / "remaining_explicit_visible_candidates.tsv",
        "r5_protected": root / ROUND5 / "protected_operation_siblings.json",
        "chara": root / CHARA,
        "piece": root / PIECE,
        "jquery": root / JQUERY,
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        return {"status": "FAIL", "errors": [f"missing inputs: {missing}"]}
    try:
        r4_manifest = load_json(paths["r4_manifest"])
        r4_application = load_json(paths["r4_application"])
        r4_rows = load_tsv(paths["r4_rows"])
        official_rows = load_tsv(paths["r4_official"])
        r4_protected = load_json(paths["r4_protected"])
        r5_manifest = load_json(paths["r5_manifest"])
        r5_application = load_json(paths["r5_application"])
        r5_rows = load_tsv(paths["r5_rows"])
        r5_protected = load_json(paths["r5_protected"])
        chara_records = load_json(paths["chara"])
        piece_records = load_json(paths["piece"])
        embedded = extract_payload(paths["jquery"])
    except (OSError, UnicodeError, json.JSONDecodeError, VerificationError) as exc:
        return {"status": "FAIL", "errors": [str(exc)]}

    chara_index = index_unique(chara_records, "id", "charaList", errors)
    piece_index = index_unique(piece_records, "pieceId", "pieceList", errors)
    r4_ops = r4_manifest.get("operations", [])
    r5_ops = r5_manifest.get("operations", [])
    if not isinstance(r4_ops, list) or len(r4_ops) != 139:
        errors.append("round4: operation count must be 139")
        r4_ops = []
    if not isinstance(r5_ops, list) or len(r5_ops) != 1:
        errors.append("round5: operation count must be 1")
        r5_ops = []

    r4_ids = [str(op.get("selector", {}).get("id")) for op in r4_ops]
    if len(set(r4_ids)) != len(r4_ids):
        errors.append("round4: operation stable IDs are not unique")
    source_counts = {
        "wiki-nameZh-literal-exact": 0,
        "stable-id-same-record-name-inheritance": 0,
    }
    r4_target_contract = r4_manifest.get("target_contract", {})
    if (
        r4_target_contract.get("allowed_field") != "kana"
        or r4_target_contract.get("forbidden_other_field_changes") is not True
        or r4_application.get("status") != "PASS"
        or r4_application.get("changed_fields") != ["kana"]
    ):
        errors.append("round4: application changed-field contract is not kana-only")
    protected4 = r4_protected.get("records", {})
    if set(protected4) != set(r4_ids):
        errors.append("round4: protected sibling IDs differ from manifest")
    for position, op in enumerate(r4_ops):
        stable = str(op.get("selector", {}).get("id"))
        row = chara_index.get(stable)
        if row is None:
            errors.append(f"round4[{position}]: missing chara {stable}")
            continue
        if op.get("field") != "kana":
            errors.append(f"round4[{position}]: only kana may change")
        if row.get("kana") != op.get("after"):
            errors.append(f"round4[{position}]: applied kana mismatch for {stable}")
        name = op.get("guard", {}).get("name_must_equal")
        if row.get("name") != name or op.get("after") != name:
            errors.append(f"round4[{position}]: same-record name guard failed for {stable}")
        if not LATIN.search(str(op.get("before", ""))) or LATIN.search(str(op.get("after", ""))):
            errors.append(f"round4[{position}]: Latin before/after contract failed for {stable}")
        if protected_record(row, "kana") != protected4.get(stable):
            errors.append(f"round4[{position}]: non-kana sibling field drift for {stable}")
        source_class = op.get("source_class")
        if source_class in source_counts:
            source_counts[source_class] += 1
        else:
            errors.append(f"round4[{position}]: unknown source class {source_class!r}")
        tier = (
            "wiki" if source_class == "wiki-nameZh-literal-exact"
            else "current-stable-id-name+wiki-component-evidence"
        )
        if op.get("source_tier") != tier:
            errors.append(f"round4[{position}]: source tier drift for {stable}")
        if "characters.json#" not in str(op.get("evidence", "")):
            errors.append(f"round4[{position}]: Wiki evidence missing for {stable}")

    expected_partition = {
        "wiki-nameZh-literal-exact": 118,
        "stable-id-same-record-name-inheritance": 21,
    }
    if source_counts != expected_partition:
        errors.append(f"round4: source partition drift: {source_counts}")
    if len(r4_rows) != 139 or len({row.get("chara_id") for row in r4_rows}) != 139:
        errors.append("round4 TSV: expected 139 unique chara IDs")
    elif {row.get("chara_id") for row in r4_rows} != set(r4_ids):
        errors.append("round4 TSV: stable IDs differ from manifest")
    if len(official_rows) != 65:
        errors.append("round4: official structural sample must contain 65 rows")
    for row in official_rows:
        if row.get("kana_equals_name") != "true" or row.get("official_name") != row.get("official_kana"):
            errors.append(f"round4: official convention failure for {row.get('chara_id')}")
    latin_ids = [stable for stable, row in chara_index.items() if LATIN.search(str(row.get("kana", "")))]
    if latin_ids:
        errors.append(f"charaList: Latin kana remains for IDs {latin_ids[:10]}")

    if r5_ops:
        op = r5_ops[0]
        expected = {
            "selector": {"pieceId": 1731}, "field": "pieceName",
            "before": "Sisters", "after": "姐妹", "source_tier": "wiki",
            "source_key": "memoria.number=1731",
        }
        for key, value in expected.items():
            if op.get(key) != value:
                errors.append(f"round5: {key} drift")
        row = piece_index.get("1731")
        if row is None or row.get("pieceName") != "姐妹":
            errors.append("round5: pieceId 1731 is not localized to 姐妹")
        elif protected_record(row, "pieceName") != r5_protected.get("records", {}).get("1731"):
            errors.append("round5: non-pieceName sibling field drift for 1731")
        if op.get("source_literal") != {"name_ja": "Sisters", "name_zh": "姐妹"}:
            errors.append("round5: Wiki source literal is incomplete")
        if "absent" not in str(op.get("official_cn_status", "")):
            errors.append("round5: official-CN absence evidence is unclear")
        if (
            r5_application.get("status") != "PASS"
            or r5_application.get("field") != "pieceName"
            or r5_application.get("before") != "Sisters"
            or r5_application.get("after") != "姐妹"
        ):
            errors.append("round5: application changed-field contract drift")
    if len(r5_rows) != 1 or r5_rows[0].get("stable_key") != "pieceId=1731":
        errors.append("round5 TSV: stable-key evidence drift")

    mapped_chara = {stable: row for stable, row in chara_index.items()}
    mapped_piece = {stable: row for stable, row in piece_index.items()}
    chara_equal = embedded.get("charaList") == mapped_chara
    piece_equal = embedded.get("pieceList") == mapped_piece
    if not chara_equal:
        errors.append("jQuery payload differs point-for-point from charaList.json")
    if not piece_equal:
        errors.append("jQuery payload differs point-for-point from pieceList.json")

    return {
        "schema": "visible-ui-authority-round4-round5-verification/v1",
        "status": "PASS" if not errors else "FAIL",
        "round4": {
            "records": len(chara_index), "operations": len(r4_ops),
            "unique_operation_ids": len(set(r4_ids)), "latin_kana": len(latin_ids),
            "source_partition": source_counts, "protected_sibling_records": len(protected4),
        },
        "round5": {
            "records": len(piece_index), "operations": len(r5_ops),
            "piece_1731": piece_index.get("1731", {}).get("pieceName"),
            "source_tier": r5_ops[0].get("source_tier") if r5_ops else None,
            "protected_sibling_records": len(r5_protected.get("records", {})),
        },
        "runtime": {
            "charaList_embedded_equals_standalone": chara_equal,
            "pieceList_embedded_equals_standalone": piece_equal,
        },
        "allowed_fields": {"round4": ["kana"], "round5": ["pieceName"]},
        "product_writes": 0,
        "errors": errors,
    }


def write_evidence(root: Path, result: dict[str, Any]) -> None:
    common = {
        "schema": result["schema"], "status": result["status"],
        "runtime": result["runtime"], "allowed_fields": result["allowed_fields"],
        "product_writes": 0, "errors": result["errors"],
    }
    for relative, key in ((ROUND4, "round4"), (ROUND5, "round5")):
        payload = dict(common); payload[key] = result[key]
        (root / relative / "reproducible_authority_runtime_verification.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()
    result = verify(args.repo_root)
    if args.write_evidence and result.get("status") == "PASS":
        write_evidence(args.repo_root.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
