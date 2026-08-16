#!/usr/bin/env python3
"""Build the closed 37-row DSV4 correction disposition audit."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from hashlib import sha256
import importlib.util
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
ADOPTIONS = AUDIT / "pass21_user_directed_suggested_adoptions.tsv"
OUT_TSV = AUDIT / "pass20_ds_correction_status.tsv"
OUT_JSON = AUDIT / "pass20_ds_correction_status.json"
FIELDS = (
    "item_id", "source_index", "current_cn_before_ds", "ds_suggested_cn",
    "final_status", "official_final_cn", "adopted_final_cn", "machine_origin",
    "authority_tier", "review_status", "ds_suggestion_matches_official",
    "current_candidate_state", "product_target_status", "product_match_count",
    "application_allowed", "evidence",
)
ADOPTION_FIELDS = (
    "item_id", "source_index", "stable_business_key", "source_key", "source_text",
    "current_cn", "ds_suggested_cn", "adopted_cn", "adoption_kind", "runtime_strategy",
    "explicit_rewrites_json", "machine_origin", "authority_tier", "review_status", "evidence",
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


def load_stage_helper():
    path = Path(__file__).resolve().parent / "stage-pass20-human-review-product.py"
    spec = importlib.util.spec_from_file_location("pass21_correction_status_helper", path)
    if spec is None or spec.loader is None:
        raise CorrectionStatusError(f"could not load product helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fingerprint(source_text: str, candidate_cn: str) -> str:
    return sha256((source_text + "\0" + candidate_cn).encode("utf-8")).hexdigest()


def read_frontend_candidates(root: Path) -> dict[str, str]:
    path = root / "i18n/frontend-strings.tsv"
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise CorrectionStatusError("frontend candidate byte contract drifted")
    lines = raw.decode("utf-8").splitlines()
    if not lines or lines[0] != "# 原文\t译文\t风险\t出现次数\t出现于":
        raise CorrectionStatusError("frontend candidate header drifted")
    result: dict[str, str] = {}
    for line in lines[1:]:
        columns = line.split("\t")
        if len(columns) != 5 or not columns[0] or columns[0] in result:
            raise CorrectionStatusError("frontend candidate key/row contract drifted")
        result[columns[0]] = columns[1]
    return result


def verify_user_directed_adoptions(
    entries_by_id: dict[str, dict[str, Any]],
    unresolved_ids: set[str],
    queue: dict[str, dict[str, str]],
    targets: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], Counter[str]]:
    header: list[str]
    with ADOPTIONS.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        adoption_rows = list(reader)
    if tuple(header) != ADOPTION_FIELDS:
        raise CorrectionStatusError("Pass21 adoption manifest header drifted")
    adoptions = index_unique(adoption_rows, "Pass21 adoption manifest")
    if set(adoptions) != unresolved_ids or len(adoptions) != 29:
        raise CorrectionStatusError("Pass21 adoption manifest must exactly cover the 29 non-authority corrections")

    frontend = read_frontend_candidates(ROOT)
    effective_rows = read_tsv(ROOT / "i18n/generated/effective.tsv")
    effective = {row["key"]: row for row in effective_rows}
    if len(effective) != len(effective_rows):
        raise CorrectionStatusError("effective authority table contains duplicate semantic keys")
    migration = json.loads((ROOT / "i18n/migration-source-summary.json").read_text(encoding="utf-8"))
    frontend_info = migration.get("source_tables", {}).get("frontend-strings.tsv", {})
    lineage = frontend_info.get("translated_candidate_lineage")
    post = migration.get("post_migration_adoptions", {}).get("pass21_user_directed_suggested_adoptions")
    if not isinstance(lineage, dict) or not isinstance(post, dict):
        raise CorrectionStatusError("Pass21 canonical migration metadata is missing")
    if (
        post.get("manifest") != "magica/i18n_audit/release_v26_authority/pass21_user_directed_suggested_adoptions.tsv"
        or post.get("items") != 29 or post.get("machine_origin") is not True
        or post.get("adoption_status") != "user-directed-suggestion-adopted"
        or post.get("new_lineage_fingerprints") != 27
        or post.get("preserved_existing_lineage_fingerprints") != 2
    ):
        raise CorrectionStatusError("Pass21 canonical migration summary drifted")

    helper = load_stage_helper()
    strategy_counts: Counter[str] = Counter()
    runtime_items: set[str] = set()
    runtime_occurrences = 0
    runtime_files: set[str] = set()
    results: dict[str, dict[str, Any]] = {}
    for item_id in sorted(adoptions):
        adoption = adoptions[item_id]
        entry = entries_by_id[item_id]
        queued = queue.get(item_id)
        target = targets.get(item_id)
        decision = decisions.get(item_id)
        if queued is None or target is None or decision is None:
            raise CorrectionStatusError(f"adopted correction lost its frozen source binding: {item_id}")
        if (
            adoption["source_index"] != str(entry["source_index"])
            or adoption["source_index"] != queued["source_index"]
            or adoption["source_text"] != queued["japanese_or_source_original"]
            or adoption["current_cn"] != entry["before"]
            or adoption["current_cn"] != queued["current_cn"]
            or adoption["ds_suggested_cn"] != entry["after"]
            or adoption["ds_suggested_cn"] != queued["suggested_cn"]
            or adoption["machine_origin"] != "true"
            or adoption["authority_tier"] != "legacy_unverified_ai_assisted"
            or adoption["review_status"] != "user-directed-suggestion-adopted"
            or queued["parent_verdict"] != "correction"
        ):
            raise CorrectionStatusError(f"Pass21 adoption source/provenance binding drifted: {item_id}")
        for field, value in queued.items():
            if field not in HUMAN_FIELDS | QUEUE_CONTRACT_FIELDS and decision.get(field) != value:
                raise CorrectionStatusError(f"Pass21 adoption decision source binding drifted {field}: {item_id}")
        if any(decision.get(field, "") for field in HUMAN_FIELDS):
            raise CorrectionStatusError(f"Pass21 machine-origin adoption was falsely marked human-reviewed: {item_id}")
        if frontend.get(adoption["source_text"]) != adoption["adopted_cn"]:
            raise CorrectionStatusError(f"Pass21 canonical frontend value was not adopted: {item_id}")
        lineage_entry = lineage.get(fingerprint(adoption["source_text"], adoption["adopted_cn"]))
        if not isinstance(lineage_entry, dict):
            raise CorrectionStatusError(f"Pass21 adoption lineage is missing: {item_id}")
        if adoption["adopted_cn"] != adoption["current_cn"] and lineage_entry != {
            "batch": "pass21-user-directed-machine-suggestion", "commit": "",
        }:
            raise CorrectionStatusError(f"Pass21 changed adoption lineage drifted: {item_id}")
        if adoption["adopted_cn"] == adoption["current_cn"] and lineage_entry.get("batch") == "pass21-user-directed-machine-suggestion":
            raise CorrectionStatusError(f"Pass21 unchanged adoption overwrote historical lineage: {item_id}")
        winner = effective.get(target["semantic_key"])
        if (
            winner is None or winner.get("selected_cn") != adoption["adopted_cn"]
            or winner.get("authority") != "legacy_unverified_ai_assisted"
            or winner.get("source_file") != "i18n/frontend-strings.tsv"
        ):
            raise CorrectionStatusError(f"Pass21 effective winner/provenance drifted: {item_id}")

        strategy = adoption["runtime_strategy"]
        strategy_counts[strategy] += 1
        rewrites: list[dict[str, Any]] = []
        if strategy == "target-manifest-exact":
            if target.get("application_allowed") is not True:
                raise CorrectionStatusError(f"Pass21 exact runtime target is no longer exact: {item_id}")
            expected_by_path: dict[str, int] = {}
            for occurrence in target.get("occurrences", []):
                rel = str(occurrence["path"])
                expected_by_path[rel] = expected_by_path.get(rel, 0) + 1
            rewrites = [{
                "path": rel, "before": decode_cell(adoption["current_cn"]),
                "after": decode_cell(adoption["adopted_cn"]), "expected_count": count,
            } for rel, count in sorted(expected_by_path.items())]
        elif strategy == "explicit-safe-paths":
            try:
                rewrites = json.loads(adoption["explicit_rewrites_json"])
            except json.JSONDecodeError as exc:
                raise CorrectionStatusError(f"Pass21 explicit rewrite JSON drifted: {item_id}") from exc
            allowed_paths = set(target.get("product_target_paths") or [])
            if not rewrites or any(rewrite.get("path") not in allowed_paths for rewrite in rewrites):
                raise CorrectionStatusError(f"Pass21 explicit runtime allowlist drifted: {item_id}")
        elif strategy == "canonical-only":
            if target.get("application_allowed") is True or adoption["explicit_rewrites_json"] != "[]":
                raise CorrectionStatusError(f"Pass21 canonical-only boundary drifted: {item_id}")
        else:
            raise CorrectionStatusError(f"Pass21 runtime strategy drifted: {item_id}")

        item_occurrences = 0
        for rewrite in rewrites:
            rel = str(rewrite["path"])
            expected_count = int(rewrite["expected_count"])
            path = ROOT / "magica" / Path(*PurePosixPath(rel).parts)
            if not path.is_file() or path.is_symlink():
                raise CorrectionStatusError(f"Pass21 runtime product path is missing or unsafe: {item_id}")
            text = path.read_bytes().decode("utf-8")
            old_count = len(helper.semantic_spans(text, rewrite["before"], rel, "global"))
            new_count = len(helper.semantic_spans(text, rewrite["after"], rel, "global"))
            if old_count != 0 or new_count < expected_count:
                raise CorrectionStatusError(
                    f"Pass21 runtime product value was not adopted: {item_id} {rel} old={old_count} new={new_count}"
                )
            item_occurrences += expected_count
            runtime_occurrences += expected_count
            runtime_files.add(rel)
        if rewrites:
            runtime_items.add(item_id)
        results[item_id] = {
            "strategy": strategy,
            "adopted_cn": adoption["adopted_cn"],
            "product_match_count": item_occurrences,
            "application_allowed": "true" if rewrites else "false",
        }

    if (
        strategy_counts != {"target-manifest-exact": 22, "explicit-safe-paths": 2, "canonical-only": 5}
        or len(runtime_items) != 24 or runtime_occurrences != 30 or len(runtime_files) != 23
    ):
        raise CorrectionStatusError(
            f"Pass21 adopted runtime summary drifted: strategies={dict(strategy_counts)} "
            f"items={len(runtime_items)} occurrences={runtime_occurrences} files={len(runtime_files)}"
        )
    strategy_counts["runtime_materialized_items"] = len(runtime_items)
    strategy_counts["runtime_occurrences"] = runtime_occurrences
    strategy_counts["runtime_files"] = len(runtime_files)
    return results, strategy_counts


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
    adopted_ids = set(entries_by_id) - resolved_correction_ids
    adopted_products, adopted_counts = verify_user_directed_adoptions(
        entries_by_id, adopted_ids, queue, targets, decisions,
    )
    rows: list[dict[str, Any]] = []
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
                "adopted_final_cn": resolution["final_value"],
                "machine_origin": "false",
                "authority_tier": "official_cn_dump",
                "review_status": "official-source-verified",
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
                raise CorrectionStatusError(f"adopted correction is absent from its frozen queue/target: {item_id}")
            if (
                str(entry["source_index"]) != queued["source_index"]
                or queued["parent_verdict"] != "correction"
                or queued["current_cn"] != entry["before"]
                or queued["suggested_cn"] != entry["after"]
            ):
                raise CorrectionStatusError(f"adopted correction queue binding drifted: {item_id}")
            product = adopted_products[item_id]
            row = {
                "item_id": item_id,
                "source_index": entry["source_index"],
                "current_cn_before_ds": entry["before"],
                "ds_suggested_cn": entry["after"],
                "final_status": "user-directed-suggestion-adopted",
                "official_final_cn": "",
                "adopted_final_cn": product["adopted_cn"],
                "machine_origin": "true",
                "authority_tier": "legacy_unverified_ai_assisted",
                "review_status": "user-directed-suggestion-adopted",
                "ds_suggestion_matches_official": "",
                "current_candidate_state": (
                    "machine-origin-adopted-in-canonical-and-product"
                    if product["application_allowed"] == "true"
                    else "machine-origin-adopted-in-canonical-maintenance-only"
                ),
                "product_target_status": product["strategy"],
                "product_match_count": product["product_match_count"],
                "application_allowed": product["application_allowed"],
                "evidence": (
                    "Pass21 tracked adoption manifest; canonical effective winner and allowlisted runtime "
                    "materialization verified; machine origin and legacy authority retained"
                ),
            }
        rows.append(row)

    status_counts = Counter(row["final_status"] for row in rows)
    official_matches = sum(row["ds_suggestion_matches_official"] == "true" for row in rows)
    if status_counts != {
        "official-cn-applied": 7,
        "user-directed-suggestion-adopted": 29,
        "official-cn-existing-authority": 1,
    }:
        raise CorrectionStatusError(f"correction disposition count drifted: {dict(status_counts)}")
    if official_matches != 2:
        raise CorrectionStatusError("exactly two higher-authority values must equal the DS suggestion")
    return {
        "schema": "magireco-cn-pass20-ds-correction-disposition/2",
        "status": "PASS",
        "summary": {
            "ds_corrections": 37,
            "official_cn_applied": 7,
            "official_cn_existing_authority": 1,
            "higher_authority_resolved": 8,
            "user_directed_suggestion_adopted": 29,
            "human_review_pending_not_applied": 0,
            "ds_direct_product_writes": 0,
            "ds_suggestion_equal_to_official": 2,
            "adopted_target_status": dict(sorted(adopted_counts.items())),
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
