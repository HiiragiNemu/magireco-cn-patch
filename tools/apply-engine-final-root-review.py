#!/usr/bin/env python3
"""Fail-closed application and rollback for the 2026-08-19 engine review."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


PRODUCT = Path(__file__).resolve().parents[1]
ENGINE = PRODUCT / "madomagi" / "engine_i18n.tsv"
EVIDENCE = (
    PRODUCT
    / "magica"
    / "research"
    / "totentanz-full-localization-20260817"
    / "engine-i18n"
    / "final-root-review-20260819"
)
SIDECAR = EVIDENCE / "engine_unknown_212_root_review_sidecar.json"
ROLLBACK = EVIDENCE / "engine_unknown_212_rollback_manifest.json"
APPLICATION_VERIFICATION = EVIDENCE / "engine_unknown_212_application_verification.json"
ROUNDTRIP_VERIFICATION = EVIDENCE / "engine_unknown_212_roundtrip_verification.json"

OFFICIAL_TIER = "official-cn-native-sequence-exact-both-abis"
MANUAL_TIER = "manual-semantic-reviewed"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, value: object) -> None:
    atomic_write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def read_engine(path: Path) -> tuple[list[str], dict[int, tuple[str, str]]]:
    text = path.read_bytes().decode("utf-8-sig", errors="strict")
    if "\ufffd" in text:
        raise ValueError("engine table contains a replacement character")
    lines = text.splitlines()
    rules: dict[int, tuple[str, str]] = {}
    for number, line in enumerate(lines, 1):
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 2:
            raise ValueError(f"engine line {number} must contain exactly one TAB")
        rules[number] = (fields[0], fields[1])
    return lines, rules


def read_sidecar(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != 2 or payload.get("binding") != "current-engine-physical-line-exact":
        raise ValueError("unsupported sidecar schema or binding")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 212:
        raise ValueError("sidecar must contain exactly 212 rows")
    ids = [row.get("row_id") for row in rows]
    lines = [row.get("physical_line") for row in rows]
    if len(set(ids)) != 212 or None in ids:
        raise ValueError("sidecar row_id values must be unique and non-empty")
    if len(set(lines)) != 212 or any(not isinstance(line, int) for line in lines):
        raise ValueError("sidecar physical_line values must be unique integers")
    verdict_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}
    correction_tiers: dict[str, int] = {}
    for row in rows:
        verdict = row.get("semantic_verdict")
        tier = row.get("source_tier")
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        if verdict == "correction-proposed":
            correction_tiers[tier] = correction_tiers.get(tier, 0) + 1
        if row.get("product_write_allowed") is not False:
            raise ValueError(f'{row.get("row_id")}: review sidecar must remain audit-only')
        for field in ("source_key", "before_cn", "proposed_cn", "evidence"):
            if not isinstance(row.get(field), str):
                raise ValueError(f'{row.get("row_id")}: missing string field {field}')
    if verdict_counts != {"approved-current": 172, "correction-proposed": 40}:
        raise ValueError(f"sidecar verdict partition drifted: {verdict_counts}")
    if tier_counts != {OFFICIAL_TIER: 35, MANUAL_TIER: 177}:
        raise ValueError(f"sidecar source-tier partition drifted: {tier_counts}")
    if correction_tiers != {OFFICIAL_TIER: 35, MANUAL_TIER: 5}:
        raise ValueError(f"sidecar correction partition drifted: {correction_tiers}")
    return rows


def expected_target(row: dict, state: str) -> str:
    if state == "rolled-back":
        return row["before_cn"]
    if state == "applied":
        return row["proposed_cn"] if row["semantic_verdict"] == "correction-proposed" else row["before_cn"]
    raise ValueError(f"unsupported expected state: {state}")


def verify_state(engine_path: Path, sidecar_path: Path, state: str) -> dict:
    _, engine = read_engine(engine_path)
    rows = read_sidecar(sidecar_path)
    errors: list[str] = []
    for row in rows:
        row_id = row["row_id"]
        line = row["physical_line"]
        actual = engine.get(line)
        if actual is None:
            errors.append(f"{row_id}: physical line {line} missing")
            continue
        source, target = actual
        if source != row["source_key"]:
            errors.append(f"{row_id}: source drift at physical line {line}")
        expected = expected_target(row, state)
        if target != expected:
            errors.append(f"{row_id}: target drift at physical line {line}")
    return {
        "schema": 1,
        "state": state,
        "engine_rules": len(engine),
        "review_rows": len(rows),
        "correction_rows": sum(row["semantic_verdict"] == "correction-proposed" for row in rows),
        "exact_bindings": len(rows) - len({error.split(":", 1)[0] for error in errors}),
        "errors": errors,
        "status": "pass" if not errors else "fail",
    }


def apply_review(engine_path: Path, sidecar_path: Path, rollback_path: Path, verification_path: Path) -> dict:
    before_bytes = engine_path.read_bytes()
    lines, engine = read_engine(engine_path)
    rows = read_sidecar(sidecar_path)
    initial = verify_state(engine_path, sidecar_path, "rolled-back")
    if initial["status"] != "pass":
        raise ValueError("apply refused: current engine does not match all 212 exact before bindings")
    corrections = [row for row in rows if row["semantic_verdict"] == "correction-proposed"]
    manifest_rows = []
    for row in corrections:
        line = row["physical_line"]
        source, current = engine[line]
        lines[line - 1] = f'{source}\t{row["proposed_cn"]}'
        manifest_rows.append(
            {
                "row_id": row["row_id"],
                "physical_line": line,
                "source_key": source,
                "before_cn": current,
                "after_cn": row["proposed_cn"],
                "source_tier": row["source_tier"],
            }
        )
    rollback_payload = {"schema": 1, "binding": "exact-current-before-and-after", "rows": manifest_rows}
    new_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    atomic_write_json(rollback_path, rollback_payload)
    try:
        atomic_write_bytes(engine_path, new_bytes)
        result = verify_state(engine_path, sidecar_path, "applied")
        if result["status"] != "pass":
            raise ValueError("post-apply verification failed")
        result["official_exact_corrections_applied"] = sum(row["source_tier"] == OFFICIAL_TIER for row in corrections)
        result["manual_semantic_corrections_applied"] = sum(row["source_tier"] == MANUAL_TIER for row in corrections)
        atomic_write_json(verification_path, result)
        return result
    except Exception:
        atomic_write_bytes(engine_path, before_bytes)
        raise


def rollback_review(engine_path: Path, sidecar_path: Path, rollback_path: Path, verification_path: Path) -> dict:
    before_bytes = engine_path.read_bytes()
    lines, engine = read_engine(engine_path)
    side_rows = read_sidecar(sidecar_path)
    side_by_id = {row["row_id"]: row for row in side_rows}
    current = verify_state(engine_path, sidecar_path, "applied")
    if current["status"] != "pass":
        raise ValueError("rollback refused: current engine is not the exact applied state")
    manifest = json.loads(rollback_path.read_text(encoding="utf-8"))
    rows = manifest.get("rows", [])
    if manifest.get("schema") != 1 or len(rows) != 40 or len({row.get("row_id") for row in rows}) != 40:
        raise ValueError("rollback manifest contract drifted")
    for row in rows:
        side = side_by_id.get(row["row_id"])
        if side is None or side["semantic_verdict"] != "correction-proposed":
            raise ValueError(f'{row.get("row_id")}: rollback row is outside the correction set')
        required = (side["physical_line"], side["source_key"], side["before_cn"], side["proposed_cn"])
        actual_manifest = (row.get("physical_line"), row.get("source_key"), row.get("before_cn"), row.get("after_cn"))
        if actual_manifest != required:
            raise ValueError(f'{row.get("row_id")}: rollback manifest binding drifted')
        line = side["physical_line"]
        source, target = engine[line]
        if source != side["source_key"] or target != side["proposed_cn"]:
            raise ValueError(f'{row.get("row_id")}: exact applied value is absent')
        lines[line - 1] = f'{source}\t{side["before_cn"]}'
    try:
        atomic_write_bytes(engine_path, ("\n".join(lines) + "\n").encode("utf-8"))
        result = verify_state(engine_path, sidecar_path, "rolled-back")
        if result["status"] != "pass":
            raise ValueError("post-rollback verification failed")
        atomic_write_json(verification_path, result)
        return result
    except Exception:
        atomic_write_bytes(engine_path, before_bytes)
        raise


def roundtrip(engine_path: Path, sidecar_path: Path, rollback_path: Path, verification_path: Path, output_path: Path) -> dict:
    steps = []
    steps.append({"step": "apply", "result": apply_review(engine_path, sidecar_path, rollback_path, verification_path)})
    steps.append({"step": "verify-applied", "result": verify_state(engine_path, sidecar_path, "applied")})
    steps.append({"step": "rollback", "result": rollback_review(engine_path, sidecar_path, rollback_path, verification_path)})
    steps.append({"step": "verify-rolled-back", "result": verify_state(engine_path, sidecar_path, "rolled-back")})
    steps.append({"step": "reapply", "result": apply_review(engine_path, sidecar_path, rollback_path, verification_path)})
    final = verify_state(engine_path, sidecar_path, "applied")
    result = {"schema": 1, "steps": steps, "final": final, "status": "pass" if all(step["result"]["status"] == "pass" for step in steps) and final["status"] == "pass" else "fail"}
    atomic_write_json(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "verify", "rollback", "roundtrip"))
    parser.add_argument("--engine", type=Path, default=ENGINE)
    parser.add_argument("--sidecar", type=Path, default=SIDECAR)
    parser.add_argument("--rollback-manifest", type=Path, default=ROLLBACK)
    parser.add_argument("--verification", type=Path, default=APPLICATION_VERIFICATION)
    parser.add_argument("--roundtrip-output", type=Path, default=ROUNDTRIP_VERIFICATION)
    parser.add_argument("--expected-state", choices=("applied", "rolled-back"), default="applied")
    args = parser.parse_args()
    if args.action == "apply":
        result = apply_review(args.engine, args.sidecar, args.rollback_manifest, args.verification)
    elif args.action == "verify":
        result = verify_state(args.engine, args.sidecar, args.expected_state)
        atomic_write_json(args.verification, result)
    elif args.action == "rollback":
        result = rollback_review(args.engine, args.sidecar, args.rollback_manifest, args.verification)
    else:
        result = roundtrip(args.engine, args.sidecar, args.rollback_manifest, args.verification, args.roundtrip_output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
