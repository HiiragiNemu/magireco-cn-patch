#!/usr/bin/env python3
"""Build the closed 37-row DSV4 correction disposition audit."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
PATCH = AUDIT / "dsv4_terminal_handoff/correction_patch.json"
DECISIONS = AUDIT / "dsv4_human_decisions.tsv"
RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
TARGETS = AUDIT / "pass20_product_targets.json"
QUEUE = AUDIT / "pass20_remaining_manual_review.tsv"
OFFICIAL_PRODUCTS = AUDIT / "pass20_official_static_product_corrections.tsv"
OUT_TSV = AUDIT / "pass20_ds_correction_status.tsv"
OUT_JSON = AUDIT / "pass20_ds_correction_status.json"
FIELDS = (
    "item_id", "source_index", "current_cn_before_ds", "ds_suggested_cn",
    "final_status", "official_final_cn", "ds_suggestion_matches_official",
    "current_candidate_state", "product_target_status", "product_match_count",
    "application_allowed", "evidence",
)


class CorrectionStatusError(RuntimeError):
    pass


HUMAN_FIELDS = {
    "human_decision", "reviewer", "timestamp", "final_value", "human_revision", "human_notes",
}
QUEUE_CONTRACT_FIELDS = {
    "review_scope_status", "application_policy", "effective_cn", "effective_tier",
    "effective_source_file", "effective_source_line", "shadowed_by_higher_authority",
    "product_write_forbidden", "canonical_write_allowed_after_human_gate",
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def decode_cell(value: str) -> str:
    """Decode the maintenance TSV escaping used by the product target manifest."""
    return value.replace("\\t", "\t").replace("\\n", "\n").replace("\\\\", "\\")


def index_unique(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in result:
            raise CorrectionStatusError(f"{label} contains a missing or duplicate item_id: {item_id!r}")
        result[item_id] = row
    return result


def verify_official_product_rows(resolution_ids: set[str]) -> None:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in read_tsv(OFFICIAL_PRODUCTS):
        for item_id in row["item_id"].split("+"):
            if item_id in resolution_ids:
                grouped.setdefault(item_id, []).append(row)
    if set(grouped) != resolution_ids:
        raise CorrectionStatusError("official correction products do not exactly cover the resolved correction IDs")
    magica = (ROOT / "magica").resolve()
    for item_id, rows in grouped.items():
        for row in rows:
            rel = PurePosixPath(row["target_path"])
            if rel.is_absolute() or ".." in rel.parts:
                raise CorrectionStatusError(f"unsafe official correction product path: {item_id}")
            path = (ROOT / Path(*rel.parts)).resolve()
            if magica not in path.parents or not path.is_file() or path.is_symlink():
                raise CorrectionStatusError(f"official correction product path is missing or unsafe: {item_id}")
            text = path.read_bytes().decode("utf-8")
            before_count = int(row["before_count"])
            expected_after = int(row["baseline_after_count"]) + before_count
            if text.count(row["before"]) != 0 or text.count(row["after"]) != expected_after:
                raise CorrectionStatusError(f"official correction product bytes drifted: {item_id}")


def verify_existing_official_authority(resolution: dict[str, str]) -> None:
    if (
        resolution["item_id"] != "LOW-MT-01485"
        or resolution["final_value"] != "心魔战"
        or resolution["product_write_status"] != "equivalent-already-present"
    ):
        raise CorrectionStatusError("preexisting official correction resolution drifted")
    candidate_lines = (ROOT / "i18n/reviewed-candidates.tsv").read_text(encoding="utf-8").splitlines()
    if len(candidate_lines) < 3 or not candidate_lines[1].startswith("# "):
        raise CorrectionStatusError("reviewed authority candidate table header drifted")
    reader = csv.DictReader(
        [candidate_lines[1][2:]] + candidate_lines[2:], delimiter="\t"
    )
    candidates = [
        row for row in reader
        if row["source_text"] == "キモチ戦は"
        and row["candidate_cn"] == "心魔战"
        and row["authority"] == "official_cn_dump"
        and row["review_status"] == "official-source-verified"
    ]
    effective = [
        row for row in read_tsv(ROOT / "i18n/generated/effective.tsv")
        if row["source_text"] == "キモチ戦は"
        and row["selected_cn"] == "心魔战"
        and row["authority"] == "official_cn_dump"
    ]
    if len(candidates) != 1 or len(effective) != 1:
        raise CorrectionStatusError("preexisting official authority row is missing or ambiguous")
    runtime_paths = (
        ROOT / "magica/js/regularEvent/RegularEventTop.js",
        ROOT / "magica/js/regularEvent/groupBattle/RegularEventGroupBattleTop.js",
    )
    texts = [path.read_text(encoding="utf-8") for path in runtime_paths]
    if sum(text.count("心情战") for text in texts) != 0 or sum(text.count("心魔战") for text in texts) != 8:
        raise CorrectionStatusError("preexisting official runtime value drifted")


def build() -> dict[str, Any]:
    patch = json.loads(PATCH.read_text(encoding="utf-8"))
    if (
        patch.get("staging_only") is not True
        or patch.get("product_tree_writes") is not False
        or patch.get("human_approval_required") is not True
    ):
        raise CorrectionStatusError("DS correction patch write boundary drifted")
    entries = patch.get("entries")
    if not isinstance(entries, list) or len(entries) != 37:
        raise CorrectionStatusError("DS correction patch must contain 37 entries")
    entries_by_id = index_unique(entries, "DS correction patch")
    if len(entries_by_id) != 37:
        raise CorrectionStatusError("DS correction patch must contain 37 unique item IDs")
    decisions = index_unique(read_tsv(DECISIONS), "decision table")
    resolutions = index_unique(read_tsv(RESOLUTIONS), "authority resolution table")
    queue = index_unique(read_tsv(QUEUE), "final human queue")
    target_payload = json.loads(TARGETS.read_text(encoding="utf-8"))
    targets = index_unique(target_payload["items"], "product target manifest")
    resolved_correction_ids = set(entries_by_id).intersection(resolutions)
    applied_ids = {
        item_id for item_id in resolved_correction_ids
        if resolutions[item_id]["product_write_status"] == "applied-and-verified"
    }
    equivalent_ids = resolved_correction_ids - applied_ids
    verify_official_product_rows(applied_ids)
    if equivalent_ids != {"LOW-MT-01485"}:
        raise CorrectionStatusError("preexisting official correction set drifted")
    verify_existing_official_authority(resolutions["LOW-MT-01485"])
    rows: list[dict[str, Any]] = []
    pending_target_status = Counter()
    for entry in entries:
        item_id = entry["item_id"]
        decision = decisions.get(item_id)
        if decision is None:
            raise CorrectionStatusError(f"correction item is absent from decisions: {item_id}")
        if decision["current_cn"] != entry["before"] or decision["suggested_cn"] != entry["after"]:
            raise CorrectionStatusError(f"DS correction before/after drifted: {item_id}")
        resolution = resolutions.get(item_id)
        if resolution:
            if (
                resolution["resolution_kind"] != "official-cn-applied"
                or resolution["authority_tier"] != "official_cn_dump"
                or resolution["product_write_status"] not in {
                    "applied-and-verified", "equivalent-already-present",
                }
            ):
                raise CorrectionStatusError(f"official correction resolution drifted: {item_id}")
            if item_id in queue or item_id in targets:
                raise CorrectionStatusError(f"authority-resolved correction leaked into human queue: {item_id}")
            preexisting = resolution["product_write_status"] == "equivalent-already-present"
            row = {
                "item_id": item_id,
                "source_index": entry["source_index"],
                "current_cn_before_ds": entry["before"],
                "ds_suggested_cn": entry["after"],
                "final_status": (
                    "official-cn-existing-authority" if preexisting else "official-cn-applied"
                ),
                "official_final_cn": resolution["final_value"],
                "ds_suggestion_matches_official": str(entry["after"] == resolution["final_value"]).lower(),
                "current_candidate_state": (
                    "official-authority-preexisting-and-verified"
                    if preexisting else "official-authority-applied-and-verified"
                ),
                "product_target_status": "authority-resolved-before-final-queue",
                "product_match_count": "",
                "application_allowed": "false",
                "evidence": resolution["evidence"],
            }
        else:
            target = targets.get(item_id)
            queued = queue.get(item_id)
            if target is None or queued is None:
                raise CorrectionStatusError(f"pending correction is absent from final human queue: {item_id}")
            if (
                str(entry["source_index"]) != queued["source_index"]
                or queued["parent_verdict"] != "correction"
                or queued["current_cn"] != entry["before"]
                or queued["suggested_cn"] != entry["after"]
            ):
                raise CorrectionStatusError(f"pending correction queue binding drifted: {item_id}")
            for field, value in queued.items():
                if field not in HUMAN_FIELDS | QUEUE_CONTRACT_FIELDS and decision.get(field) != value:
                    raise CorrectionStatusError(f"pending correction decision binding drifted {field}: {item_id}")
            if any(decision[field] for field in ("human_decision", "reviewer", "timestamp", "final_value", "human_revision")):
                raise CorrectionStatusError(f"pending correction already carries a human decision: {item_id}")
            if target["current_cn"] != decode_cell(entry["before"]):
                raise CorrectionStatusError(f"pending correction no longer retains the old candidate: {item_id}")
            pending_target_status[target["match_status"]] += 1
            row = {
                "item_id": item_id,
                "source_index": entry["source_index"],
                "current_cn_before_ds": entry["before"],
                "ds_suggested_cn": entry["after"],
                "final_status": "human-review-pending-not-applied",
                "official_final_cn": "",
                "ds_suggestion_matches_official": "",
                "current_candidate_state": "old-candidate-retained",
                "product_target_status": target["match_status"],
                "product_match_count": target["match_count"],
                "application_allowed": str(target["application_allowed"]).lower(),
                "evidence": (
                    "magireco_v26_translation_review_1565.xlsx; DS suggestion is visible but remains unapplied "
                    "until a human decision opens staging"
                ),
            }
        rows.append(row)

    status_counts = Counter(row["final_status"] for row in rows)
    official_matches = sum(row["ds_suggestion_matches_official"] == "true" for row in rows)
    if status_counts != {
        "official-cn-applied": 7,
        "human-review-pending-not-applied": 29,
        "official-cn-existing-authority": 1,
    }:
        raise CorrectionStatusError(f"correction disposition count drifted: {dict(status_counts)}")
    if official_matches != 2:
        raise CorrectionStatusError("exactly two higher-authority values must equal the DS suggestion")
    expected_targets = {
        "exact-current-runtime-literal": 22,
        "maintenance-only-count-or-path-drift": 3,
        "maintenance-only-declared-path-absent": 2,
        "maintenance-only-current-literal-absent": 2,
    }
    if dict(pending_target_status) != expected_targets:
        raise CorrectionStatusError(f"pending correction target classes drifted: {dict(pending_target_status)}")
    return {
        "schema": "magireco-cn-pass20-ds-correction-disposition/1",
        "status": "PASS",
        "summary": {
            "ds_corrections": 37,
            "official_cn_applied": 7,
            "official_cn_existing_authority": 1,
            "higher_authority_resolved": 8,
            "human_review_pending_not_applied": 29,
            "ds_direct_product_writes": 0,
            "ds_suggestion_equal_to_official": 2,
            "pending_target_status": dict(sorted(pending_target_status.items())),
        },
        "items": rows,
    }


def write(payload: dict[str, Any], out_tsv: Path, out_json: Path) -> None:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(payload["items"])
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-tsv", type=Path, default=OUT_TSV)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    args = parser.parse_args(argv)
    try:
        payload = build()
        write(payload, args.out_tsv, args.out_json)
        print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
        return 0
    except (CorrectionStatusError, OSError, UnicodeError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
