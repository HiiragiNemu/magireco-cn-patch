#!/usr/bin/env python3
"""Stage, promote, or roll back the 29 user-directed Pass21 adoptions.

The tracked Pass21 manifest is bound to the exact non-empty ``suggested_cn``
subset of the frozen Pass20 queue.  It records the final, structure-checked
Chinese values selected by the user while deliberately preserving their
machine-origin/low-authority provenance.  Every item updates the canonical
i18n maintenance layer; only exact or explicitly allowlisted product targets
are materialized into ``magica/``.
"""

from __future__ import annotations

import argparse
import csv
import difflib
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
AUDIT_REL = Path("magica/i18n_audit/release_v26_authority")
QUEUE_REL = AUDIT_REL / "pass20_remaining_manual_review.tsv"
TARGETS_REL = AUDIT_REL / "pass20_product_targets.json"
PROTECTED_REL = AUDIT_REL / "protected_authority/protected_translation_fields.tsv"
PASS19_REL = AUDIT_REL / "pass19_official_static_corrections.tsv"
ADOPTION_REL = AUDIT_REL / "pass21_user_directed_suggested_adoptions.tsv"
CONTRACT_REL = AUDIT_REL / "pass20_review_contract.json"
FULL_REVIEW_REL = AUDIT_REL / "dsv4_terminal_handoff/full_review.tsv"
RESOLUTIONS_REL = AUDIT_REL / "pass20_authority_resolutions.tsv"
FRONTEND_REL = Path("i18n/frontend-strings.tsv")
MIGRATION_REL = Path("i18n/migration-source-summary.json")
GENERATED_RELS = (
    Path("i18n/generated/conflicts.tsv"),
    Path("i18n/generated/effective.tsv"),
    Path("i18n/generated/input-provenance.tsv"),
    Path("i18n/generated/summary.json"),
)
EXPECTED_SELECTED = 29
EXPECTED_TARGET_EXACT_ITEMS = 22
EXPECTED_EXPLICIT_ITEMS = 2
EXPECTED_CANONICAL_ONLY_ITEMS = 5
EXPECTED_TARGET_MAINTENANCE_ITEMS = 7
EXPECTED_TARGET_EXACT_OCCURRENCES = 26
EXPECTED_TARGET_EXACT_FILES = 20
EXPECTED_RUNTIME_MATERIALIZED_ITEMS = 24
EXPECTED_RUNTIME_PATCH_RECORDS = 28
EXPECTED_RUNTIME_OCCURRENCES = 30
EXPECTED_RUNTIME_FILES = 23
EXPECTED_UNCHANGED_ADOPTIONS = 2
ADOPTION_COLUMNS = (
    "item_id", "source_index", "stable_business_key", "source_key", "source_text",
    "current_cn", "ds_suggested_cn", "adopted_cn", "adoption_kind", "runtime_strategy",
    "explicit_rewrites_json", "machine_origin", "authority_tier", "review_status", "evidence",
)
KANA = re.compile(r"[\u3040-\u30ff]")


class AdoptionError(RuntimeError):
    pass


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AdoptionError(f"could not load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise AdoptionError(f"TSV byte contract drifted: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        rows = list(reader)
    if not reader.fieldnames or any(None in row for row in rows):
        raise AdoptionError(f"TSV structure drifted: {path}")
    return list(reader.fieldnames), rows


def write_tsv(path: Path, columns: tuple[str, ...] | list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def read_adoption_manifest(path: Path) -> dict[str, dict[str, Any]]:
    header, rows = read_tsv(path)
    if tuple(header) != ADOPTION_COLUMNS:
        raise AdoptionError("adoption manifest header drifted")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row["item_id"]
        if (
            not item_id or item_id in result or not row["adopted_cn"]
            or row["runtime_strategy"] not in {"target-manifest-exact", "canonical-only", "explicit-safe-paths"}
            or row["machine_origin"] != "true"
            or row["authority_tier"] != "legacy_unverified_ai_assisted"
            or row["review_status"] != "user-directed-suggestion-adopted"
            or not row["evidence"].strip()
        ):
            raise AdoptionError(f"invalid adoption manifest row: {item_id!r}")
        try:
            rewrites = json.loads(row["explicit_rewrites_json"] or "[]")
        except json.JSONDecodeError as exc:
            raise AdoptionError(f"invalid runtime_rewrites JSON: {item_id}") from exc
        if not isinstance(rewrites, list):
            raise AdoptionError(f"runtime_rewrites must be a JSON list: {item_id}")
        cooked: list[dict[str, Any]] = []
        for rewrite in rewrites:
            if (
                not isinstance(rewrite, dict)
                or set(rewrite) != {"path", "before", "after", "expected_count"}
                or not all(isinstance(rewrite.get(key), str) and rewrite[key] for key in ("path", "before", "after"))
                or not isinstance(rewrite.get("expected_count"), int)
                or isinstance(rewrite.get("expected_count"), bool)
                or rewrite["expected_count"] < 1
            ):
                raise AdoptionError(f"invalid explicit runtime rewrite: {item_id}")
            cooked.append(rewrite)
        if row["runtime_strategy"] == "explicit-safe-paths" and not cooked:
            raise AdoptionError(f"explicit-safe-paths has no rewrites: {item_id}")
        if row["runtime_strategy"] != "explicit-safe-paths" and cooked:
            raise AdoptionError(f"non-explicit strategy carries runtime rewrites: {item_id}")
        result[item_id] = {**row, "runtime_rewrites_parsed": cooked}
    if len(result) != EXPECTED_SELECTED:
        raise AdoptionError(f"adoption manifest must contain {EXPECTED_SELECTED} rows, found {len(result)}")
    return result


def unique(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result = {str(row.get("item_id", "")): row for row in rows}
    if "" in result or len(result) != len(rows):
        raise AdoptionError(f"{label} contains an empty or duplicate item_id")
    return result


def build_selection(
    queue_path: Path, targets_path: Path, manifest_path: Path, helper: Any,
) -> list[dict[str, Any]]:
    _, queue_rows = read_tsv(queue_path)
    queue = unique(queue_rows, "Pass20 queue")
    target_payload = json.loads(targets_path.read_text(encoding="utf-8"))
    if (
        target_payload.get("schema") != "magireco-cn-pass20-product-target-manifest/1"
        or target_payload.get("status") != "PASS"
        or not isinstance(target_payload.get("items"), list)
    ):
        raise AdoptionError("Pass20 target manifest schema/status drifted")
    targets = unique(target_payload["items"], "Pass20 target manifest")
    if set(targets) != set(queue):
        raise AdoptionError("Pass20 queue and target manifest stable IDs differ")
    adoptions = read_adoption_manifest(manifest_path)
    selected_rows = [row for row in queue_rows if row.get("suggested_cn", "")]
    if len(selected_rows) != EXPECTED_SELECTED:
        raise AdoptionError(f"expected {EXPECTED_SELECTED} non-empty suggestions, found {len(selected_rows)}")
    if set(adoptions) != {row["item_id"] for row in selected_rows}:
        raise AdoptionError("adoption manifest is not the exact non-empty-suggestion stable-ID set")

    selected: list[dict[str, Any]] = []
    runtime_files: set[str] = set()
    runtime_occurrences = 0
    for source in selected_rows:
        item_id = source["item_id"]
        target = targets[item_id]
        if (
            source.get("highest_authority_tier") != "legacy_unverified_ai_assisted"
            or source.get("review_scope_status") != "current-effective-low-authority"
            or source.get("product_write_forbidden") != "false"
            or source.get("canonical_write_allowed_after_human_gate") != "true"
            or target.get("shadowed_by_higher_authority") is True
            or target.get("product_write_forbidden") is True
            or target.get("maintenance_scope") != "global"
            or target.get("current_cn") != helper.decode_cell(source.get("current_cn", ""))
        ):
            raise AdoptionError(f"authority/write contract drifted: {item_id}")
        adoption = adoptions[item_id]
        if (
            adoption["source_index"] != source["source_index"]
            or adoption["stable_business_key"] != source["stable_business_key"]
            or adoption["source_key"] != source["source_key"]
            or adoption["source_text"] != source["japanese_or_source_original"]
            or adoption["current_cn"] != source["current_cn"]
            or adoption["ds_suggested_cn"] != source["suggested_cn"]
        ):
            raise AdoptionError(f"adoption source/current/suggestion binding drifted: {item_id}")
        final_cn = adoption["adopted_cn"]
        if KANA.search(final_cn):
            raise AdoptionError(f"final Chinese still contains Japanese kana: {item_id}")
        before_literal = helper.decode_cell(source["current_cn"])
        after_literal = helper.decode_cell(final_cn)
        try:
            helper.validate_translation_structure(item_id, before_literal, after_literal)
        except Exception as exc:
            if adoption["runtime_strategy"] != "explicit-safe-paths":
                raise AdoptionError(f"translation structure gate failed: {item_id}: {exc}") from exc

        application_allowed = target.get("application_allowed") is True
        occurrences = target.get("occurrences")
        if not isinstance(occurrences, list):
            raise AdoptionError(f"target occurrence list drifted: {item_id}")
        if application_allowed:
            if adoption["runtime_strategy"] != "target-manifest-exact":
                raise AdoptionError(f"exact target must use target-manifest-exact: {item_id}")
            if target.get("match_status") != "exact-current-runtime-literal" or not occurrences:
                raise AdoptionError(f"runtime target is not exact: {item_id}")
            paths = sorted({str(row.get("path", "")) for row in occurrences})
            if any(not path for path in paths) or paths != sorted(target.get("product_target_paths") or []):
                raise AdoptionError(f"runtime target path binding drifted: {item_id}")
            runtime_files.update(paths)
            runtime_occurrences += len(occurrences)
        else:
            if occurrences:
                raise AdoptionError(f"maintenance-only item claims safe target-manifest occurrences: {item_id}")
            if adoption["runtime_strategy"] not in {"canonical-only", "explicit-safe-paths"}:
                raise AdoptionError(f"maintenance-only strategy drifted: {item_id}")

        selected.append({
            "item_id": item_id,
            "source": source,
            "target": target,
            "final_cn": final_cn,
            "before_literal": before_literal,
            "after_literal": after_literal,
            "strategy": adoption["runtime_strategy"],
            "runtime_rewrites": adoption["runtime_rewrites_parsed"],
            "reason": adoption["evidence"],
        })

    target_exact_items = sum(item["target"]["application_allowed"] is True for item in selected)
    target_maintenance_items = len(selected) - target_exact_items
    explicit_items = sum(item["strategy"] == "explicit-safe-paths" for item in selected)
    canonical_only_items = sum(item["strategy"] == "canonical-only" for item in selected)
    if (
        target_exact_items != EXPECTED_TARGET_EXACT_ITEMS
        or target_maintenance_items != EXPECTED_TARGET_MAINTENANCE_ITEMS
        or explicit_items != EXPECTED_EXPLICIT_ITEMS
        or canonical_only_items != EXPECTED_CANONICAL_ONLY_ITEMS
        or runtime_occurrences != EXPECTED_TARGET_EXACT_OCCURRENCES
        or len(runtime_files) != EXPECTED_TARGET_EXACT_FILES
    ):
        raise AdoptionError(
            "suggestion target contract drifted: "
            f"target_exact={target_exact_items} target_maintenance={target_maintenance_items} "
            f"explicit={explicit_items} canonical_only={canonical_only_items} "
            f"occurrences={runtime_occurrences} files={len(runtime_files)}"
        )
    return selected


def normalized_lf_sha256(path: Path) -> str:
    return digest(path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def update_frontend_and_lineage(candidate_root: Path, selected: list[dict[str, Any]]) -> None:
    path = candidate_root / FRONTEND_REL
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise AdoptionError("frontend-strings.tsv byte contract drifted")
    lines = raw.decode("utf-8").splitlines()
    if not lines or lines[0] != "# 原文\t译文\t风险\t出现次数\t出现于":
        raise AdoptionError("frontend-strings.tsv header drifted")
    by_source = {item["source"]["japanese_or_source_original"]: item for item in selected}
    if len(by_source) != len(selected):
        raise AdoptionError("selected source texts are not unique")
    changed: set[str] = set()
    output = [lines[0]]
    for line in lines[1:]:
        columns = line.split("\t")
        if len(columns) != 5:
            raise AdoptionError("frontend-strings.tsv row width drifted")
        item = by_source.get(columns[0])
        if item is not None:
            if columns[1] != item["source"]["current_cn"]:
                raise AdoptionError(f"frontend preimage drifted: {item['item_id']}")
            columns[1] = item["final_cn"]
            changed.add(item["item_id"])
        output.append("\t".join(columns))
    if changed != {item["item_id"] for item in selected}:
        raise AdoptionError("not every selected source was updated in frontend-strings.tsv")
    path.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")

    migration_path = candidate_root / MIGRATION_REL
    migration = json.loads(migration_path.read_text(encoding="utf-8"))
    info = migration.get("source_tables", {}).get("frontend-strings.tsv")
    if not isinstance(info, dict) or not isinstance(info.get("translated_candidate_lineage"), dict):
        raise AdoptionError("frontend migration lineage contract drifted")
    lineage = info["translated_candidate_lineage"]
    preserved_lineage = 0
    added_lineage = 0
    for item in selected:
        source_text = item["source"]["japanese_or_source_original"]
        fp = digest((source_text + "\0" + item["final_cn"]).encode("utf-8"))
        existing = lineage.get(fp)
        expected = {"batch": "pass21-user-directed-machine-suggestion", "commit": ""}
        if item["final_cn"] == item["source"]["current_cn"]:
            if existing is None:
                raise AdoptionError(f"unchanged adoption lost its existing lineage: {item['item_id']}")
            preserved_lineage += 1
        else:
            if existing is not None and existing != expected:
                raise AdoptionError(f"new frontend lineage fingerprint collides: {item['item_id']}")
            lineage[fp] = expected
            added_lineage += 1
    if preserved_lineage != EXPECTED_UNCHANGED_ADOPTIONS or added_lineage != EXPECTED_SELECTED - EXPECTED_UNCHANGED_ADOPTIONS:
        raise AdoptionError(
            f"Pass21 lineage partition drifted: preserved={preserved_lineage} added={added_lineage}"
        )
    info["normalized_lf_sha256"] = normalized_lf_sha256(path)
    post = migration.setdefault("post_migration_adoptions", {})
    post["pass21_user_directed_suggested_adoptions"] = {
        "manifest": ADOPTION_REL.as_posix(),
        "items": EXPECTED_SELECTED,
        "machine_origin": True,
        "adoption_status": "user-directed-suggestion-adopted",
        "new_lineage_fingerprints": added_lineage,
        "preserved_existing_lineage_fingerprints": preserved_lineage,
    }
    migration_path.write_text(json.dumps(migration, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def update_review_contract(candidate_root: Path, repo_root: Path) -> None:
    path = candidate_root / CONTRACT_REL
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema") != "magireco-cn-pass20-review-contract/2" or contract.get("status") != "PASS":
        raise AdoptionError("Pass20 review contract schema/status drifted")
    sources = contract.get("source_sha256")
    before_sources = {
        "full_review": digest((repo_root / FULL_REVIEW_REL).read_bytes()),
        "authority_resolutions": digest((repo_root / RESOLUTIONS_REL).read_bytes()),
        "input_provenance": digest((repo_root / "i18n/generated/input-provenance.tsv").read_bytes()),
        "effective": digest((repo_root / "i18n/generated/effective.tsv").read_bytes()),
    }
    if sources != before_sources:
        raise AdoptionError("Pass20 frozen review contract preimage drifted")
    contract["source_sha256"] = {
        "full_review": before_sources["full_review"],
        "authority_resolutions": before_sources["authority_resolutions"],
        "input_provenance": digest((candidate_root / "i18n/generated/input-provenance.tsv").read_bytes()),
        "effective": digest((candidate_root / "i18n/generated/effective.tsv").read_bytes()),
    }
    contract["post_pass21_adoption"] = {
        "manifest": ADOPTION_REL.as_posix(),
        "items": EXPECTED_SELECTED,
        "queue_and_targets_frozen": True,
        "machine_origin": True,
        "authority_tier": "legacy_unverified_ai_assisted",
    }
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def safe_repo_path(root: Path, rel: str) -> Path:
    if "\\" in rel or ":" in rel:
        raise AdoptionError(f"unsafe repository path: {rel!r}")
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise AdoptionError(f"unsafe repository path: {rel!r}")
    allowed = {"magica", "i18n"}
    if pure.parts[0] not in allowed:
        raise AdoptionError(f"repository path role is not allowed: {rel!r}")
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to((root / pure.parts[0]).resolve())
    except ValueError as exc:
        raise AdoptionError(f"repository path escapes its role root: {rel!r}") from exc
    return candidate


def copy_candidate_tree(repo_root: Path, candidate_root: Path, helper: Any) -> None:
    helper.copy_tree(repo_root / "i18n", candidate_root / "i18n")
    helper.copy_tree(repo_root / "magica", candidate_root / "magica", product=True)
    # Authority protection also covers the JS-package sibling engine table.
    # It is copied only as a read-only verification input and is never part of
    # the Pass21 promotion allowlist.
    helper.copy_tree(repo_root / "madomagi", candidate_root / "madomagi")
    contract_target = candidate_root / CONTRACT_REL
    contract_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_root / CONTRACT_REL, contract_target)
    pass19_target = candidate_root / PASS19_REL
    pass19_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_root / PASS19_REL, pass19_target)


def apply_runtime_changes(
    candidate_root: Path, selected: list[dict[str, Any]], helper: Any, *,
    enforce_release_contract: bool = True,
) -> tuple[list[str], list[dict[str, Any]], dict[str, bytes]]:
    changed_before: dict[str, bytes] = {}
    patch_records: list[dict[str, Any]] = []
    for item in selected:
        target = item["target"]
        rewrites: list[dict[str, Any]] = []
        if target["application_allowed"] is True:
            expected_by_path: dict[str, int] = {}
            for occurrence in target["occurrences"]:
                rel = str(occurrence["path"])
                expected_by_path[rel] = expected_by_path.get(rel, 0) + 1
            rewrites = [
                {"path": rel, "before": item["before_literal"], "after": item["after_literal"], "expected_count": expected}
                for rel, expected in sorted(expected_by_path.items())
            ]
        elif item["strategy"] == "explicit-safe-paths":
            allowed_paths = set(target.get("product_target_paths") or [])
            if any(rewrite["path"] not in allowed_paths for rewrite in item["runtime_rewrites"]):
                raise AdoptionError(f"explicit rewrite leaves the target path allowlist: {item['item_id']}")
            rewrites = item["runtime_rewrites"]
        else:
            continue
        for rewrite in rewrites:
            rel = rewrite["path"]
            expected = rewrite["expected_count"]
            before_literal = rewrite["before"]
            after_literal = rewrite["after"]
            path = candidate_root / "magica" / rel
            key = f"magica/{rel}"
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf") or b"\r\n" in raw:
                raise AdoptionError(f"runtime product is not UTF-8/LF: {rel}")
            text = raw.decode("utf-8")
            spans = helper.semantic_spans(text, before_literal, rel, "global")
            if len(spans) != expected:
                raise AdoptionError(
                    f"runtime preimage count drifted: {item['item_id']} {rel} expected={expected} got={len(spans)}"
                )
            before_after_count = len(helper.semantic_spans(text, after_literal, rel, "global"))
            updated = text
            for start, end in reversed(spans):
                updated = updated[:start] + after_literal + updated[end:]
            if len(helper.semantic_spans(updated, before_literal, rel, "global")) != 0:
                raise AdoptionError(f"runtime old literal remains after staging: {item['item_id']} {rel}")
            after_after_count = len(helper.semantic_spans(updated, after_literal, rel, "global"))
            if after_after_count - before_after_count != expected:
                raise AdoptionError(f"runtime new literal delta drifted: {item['item_id']} {rel}")
            changed_before.setdefault(key, raw)
            path.write_text(updated, encoding="utf-8", newline="\n")
            patch_records.append({
                "item_id": item["item_id"], "path": rel, "before": before_literal,
                "after": after_literal, "expected_count": expected, "strategy": item["strategy"],
            })
    changed = sorted(changed_before)
    materialized_items = {record["item_id"] for record in patch_records}
    occurrence_count = sum(int(record["expected_count"]) for record in patch_records)
    if enforce_release_contract and (
        len(materialized_items) != EXPECTED_RUNTIME_MATERIALIZED_ITEMS
        or len(patch_records) != EXPECTED_RUNTIME_PATCH_RECORDS
        or occurrence_count != EXPECTED_RUNTIME_OCCURRENCES
        or len(changed) != EXPECTED_RUNTIME_FILES
    ):
        raise AdoptionError(
            "runtime materialization contract drifted: "
            f"items={len(materialized_items)} records={len(patch_records)} "
            f"occurrences={occurrence_count} files={len(changed)}"
        )
    return changed, patch_records, changed_before


def run(command: list[str], cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="strict", env=env)
    record = {"argv": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode:
        raise AdoptionError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return record


def make_records(
    repo_root: Path, candidate_root: Path, rels: list[str], rollback_root: Path,
) -> list[dict[str, Any]]:
    records = []
    for rel in sorted(set(rels)):
        before_path = safe_repo_path(repo_root, rel)
        after_path = safe_repo_path(candidate_root, rel)
        if not after_path.is_file() or after_path.is_symlink():
            raise AdoptionError(f"staged after file is missing or unsafe: {rel}")
        before_exists = before_path.is_file() and not before_path.is_symlink()
        if before_path.exists() and not before_exists:
            raise AdoptionError(f"repository preimage is not a regular file: {rel}")
        before = before_path.read_bytes() if before_exists else b""
        after = after_path.read_bytes()
        before_snapshot = rollback_root / "before" / rel
        after_snapshot = rollback_root / "after" / rel
        before_snapshot.parent.mkdir(parents=True, exist_ok=True)
        after_snapshot.parent.mkdir(parents=True, exist_ok=True)
        before_snapshot.write_bytes(before)
        after_snapshot.write_bytes(after)
        records.append({
            "path": rel, "before_exists": before_exists,
            "before_snapshot": before_snapshot.relative_to(rollback_root.parent).as_posix(),
            "after_snapshot": after_snapshot.relative_to(rollback_root.parent).as_posix(),
            "before_sha256": digest(before), "after_sha256": digest(after),
            "before_size": len(before), "after_size": len(after),
        })
    return records


def stage(repo_root: Path, manifest_path: Path, stage_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    manifest_path = manifest_path.resolve()
    stage_root = stage_root.resolve()
    if manifest_path != (repo_root / ADOPTION_REL).resolve():
        raise AdoptionError("stage input must be the tracked Pass21 adoption manifest")
    if stage_root == repo_root or repo_root in stage_root.parents:
        raise AdoptionError("stage root must remain outside the repository")
    if stage_root.exists() and any(stage_root.iterdir()):
        raise AdoptionError(f"stage root must be absent or empty: {stage_root}")
    stage_root.mkdir(parents=True, exist_ok=True)
    helper = load_module("pass20_adoption_stage_helper", repo_root / "tools/stage-pass20-human-review-product.py")
    protection = load_module("pass20_adoption_protection", repo_root / "tools/v26_authority_protection.py")
    selected = build_selection(repo_root / QUEUE_REL, repo_root / TARGETS_REL, manifest_path, helper)
    protected_rows = protection.read_tsv(repo_root / PROTECTED_REL)
    protection.validate_row_hashes(protected_rows)
    protection.verify_current_product_values(repo_root, protected_rows)

    candidate_root = stage_root / "candidate"
    copy_candidate_tree(repo_root, candidate_root, helper)
    adoption_path = candidate_root / ADOPTION_REL
    adoption_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_path, adoption_path)
    update_frontend_and_lineage(candidate_root, selected)
    commands = [run([
        sys.executable, str(repo_root / "tools/i18n-build-effective.py"),
        "--i18n-dir", str(candidate_root / "i18n"),
        "--out-dir", str(candidate_root / "i18n/generated"),
        "--policy", str(candidate_root / "i18n/authority-policy.json"),
        "--migration-summary", str(candidate_root / "i18n/migration-source-summary.json"),
    ], repo_root)]
    update_review_contract(candidate_root, repo_root)
    _, effective_rows = read_tsv(candidate_root / "i18n/generated/effective.tsv")
    effective = {row["key"]: row for row in effective_rows}
    for item in selected:
        winner = effective.get(item["target"]["semantic_key"])
        if (
            winner is None or winner.get("authority") != "legacy_unverified_ai_assisted"
            or winner.get("selected_cn") != item["final_cn"]
            or winner.get("source_file") != "i18n/frontend-strings.tsv"
        ):
            raise AdoptionError(f"canonical effective winner drifted: {item['item_id']}")

    changed_runtime, patch_records, runtime_before = apply_runtime_changes(candidate_root, selected, helper)
    for rel in changed_runtime:
        before_text = runtime_before[rel].decode("utf-8")
        after_text = (candidate_root / rel).read_text(encoding="utf-8")
        if rel.endswith(".html") and helper.html_sensitive_signature(before_text) != helper.html_sensitive_signature(after_text):
            raise AdoptionError(f"HTML sensitive attribute drifted: {rel}")
    node = shutil.which("node")
    if not node:
        raise AdoptionError("Node.js is required for staged JS syntax validation")
    js_files = [rel for rel in changed_runtime if rel.endswith(".js")]
    for rel in js_files:
        commands.append(run([node, "--check", str(candidate_root / rel)], repo_root))
    protection.verify_current_product_values(candidate_root, protected_rows)

    canonical_rels = [
        FRONTEND_REL.as_posix(), MIGRATION_REL.as_posix(), CONTRACT_REL.as_posix(),
        *(rel.as_posix() for rel in GENERATED_RELS),
    ]
    promotion_rels = sorted(changed_runtime + canonical_rels)
    rollback_root = stage_root / "rollback"
    records = make_records(repo_root, candidate_root, promotion_rels, rollback_root)
    manifest = {
        "schema": "magireco-cn-pass20-suggested-adoption-rollback/1",
        "selection": {
            "items": EXPECTED_SELECTED,
            "target_manifest_exact_items": EXPECTED_TARGET_EXACT_ITEMS,
            "explicit_safe_path_items": EXPECTED_EXPLICIT_ITEMS,
            "canonical_only_items": EXPECTED_CANONICAL_ONLY_ITEMS,
            "runtime_materialized_items": EXPECTED_RUNTIME_MATERIALIZED_ITEMS,
            "runtime_occurrences": EXPECTED_RUNTIME_OCCURRENCES,
        },
        "files": records,
    }
    (rollback_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (stage_root / "product_patch.json").write_text(
        json.dumps({"schema": "magireco-cn-pass20-suggested-adoption-patch/1", "items": patch_records}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    diff_parts: list[str] = []
    for rel in changed_runtime:
        before = runtime_before[rel].decode("utf-8").splitlines(True)
        after = (candidate_root / rel).read_text(encoding="utf-8").splitlines(True)
        # Zero-context keeps the checked-in audit diff machine-applicable while
        # avoiding false `git diff --check` findings from context lines whose
        # source indentation legitimately begins with tabs.
        diff_parts.extend(
            difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                lineterm="\n",
                n=0,
            )
        )
    (stage_root / "product.diff").write_text("".join(diff_parts), encoding="utf-8", newline="\n")
    report = {
        "schema": "magireco-cn-pass20-suggested-adoption-stage/1", "status": "PASS",
        "selected_items": EXPECTED_SELECTED, "canonical_adoptions": EXPECTED_SELECTED,
        "target_manifest_exact_items": EXPECTED_TARGET_EXACT_ITEMS,
        "explicit_safe_path_items": sum(item["strategy"] == "explicit-safe-paths" for item in selected),
        "canonical_only_items": sum(item["strategy"] == "canonical-only" for item in selected),
        "runtime_materialized_items": EXPECTED_RUNTIME_MATERIALIZED_ITEMS,
        "target_manifest_exact_occurrences": EXPECTED_TARGET_EXACT_OCCURRENCES,
        "explicit_safe_path_occurrences": EXPECTED_RUNTIME_OCCURRENCES - EXPECTED_TARGET_EXACT_OCCURRENCES,
        "runtime_occurrences": EXPECTED_RUNTIME_OCCURRENCES,
        "runtime_patch_records": len(patch_records), "runtime_files": changed_runtime,
        "promotion_files": promotion_rels, "protected_fields_checked": len(protected_rows),
        "protected_text_changes": 0, "machine_origin": True,
        "authority_tier": "legacy_unverified_ai_assisted",
        "review_status": "user-directed-suggestion-adopted", "repository_writes": 0,
        "machine_review_and_snapshot_refresh_required_after_promotion": True,
        "pass20_queue_and_targets_frozen_after_promotion": True,
        "pass20_queue_and_targets_refresh_required_after_promotion": False,
        "queue_sha256": digest((repo_root / QUEUE_REL).read_bytes()),
        "targets_sha256": digest((repo_root / TARGETS_REL).read_bytes()),
        "adoption_manifest": ADOPTION_REL.as_posix(),
        "adoption_manifest_sha256": digest(manifest_path.read_bytes()), "commands": commands,
    }
    (stage_root / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


def load_transaction(stage_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report = json.loads((stage_root / "verification.json").read_text(encoding="utf-8"))
    manifest = json.loads((stage_root / "rollback/manifest.json").read_text(encoding="utf-8"))
    runtime_files = report.get("runtime_files")
    promotion_files = report.get("promotion_files")
    if (
        report.get("schema") != "magireco-cn-pass20-suggested-adoption-stage/1"
        or report.get("status") != "PASS" or report.get("repository_writes") != 0
        or report.get("selected_items") != EXPECTED_SELECTED
        or report.get("target_manifest_exact_items") != EXPECTED_TARGET_EXACT_ITEMS
        or report.get("explicit_safe_path_items") != EXPECTED_EXPLICIT_ITEMS
        or report.get("canonical_only_items") != EXPECTED_CANONICAL_ONLY_ITEMS
        or report.get("runtime_materialized_items") != EXPECTED_RUNTIME_MATERIALIZED_ITEMS
        or report.get("runtime_occurrences") != EXPECTED_RUNTIME_OCCURRENCES
        or report.get("runtime_patch_records") != EXPECTED_RUNTIME_PATCH_RECORDS
        or not isinstance(runtime_files, list) or len(runtime_files) != EXPECTED_RUNTIME_FILES
        or not isinstance(promotion_files, list)
        or report.get("protected_text_changes") != 0
        or manifest.get("schema") != "magireco-cn-pass20-suggested-adoption-rollback/1"
        or not isinstance(manifest.get("files"), list)
    ):
        raise AdoptionError("staged suggestion adoption contract drifted")
    expected_selection = {
        "items": EXPECTED_SELECTED,
        "target_manifest_exact_items": EXPECTED_TARGET_EXACT_ITEMS,
        "explicit_safe_path_items": EXPECTED_EXPLICIT_ITEMS,
        "canonical_only_items": EXPECTED_CANONICAL_ONLY_ITEMS,
        "runtime_materialized_items": EXPECTED_RUNTIME_MATERIALIZED_ITEMS,
        "runtime_occurrences": EXPECTED_RUNTIME_OCCURRENCES,
    }
    if manifest.get("selection") != expected_selection:
        raise AdoptionError("staged rollback selection contract drifted")
    records = manifest["files"]
    if sorted(record.get("path", "") for record in records) != sorted(promotion_files):
        raise AdoptionError("staged promotion/rollback file sets differ")
    return report, records


def snapshot_bytes(stage_root: Path, record: dict[str, Any], kind: str) -> bytes:
    rel = str(record.get(f"{kind}_snapshot", ""))
    expected = f"rollback/{kind}/{record['path']}"
    if rel != expected:
        raise AdoptionError(f"rollback snapshot path drifted: {record.get('path')}")
    path = stage_root.joinpath(*PurePosixPath(rel).parts)
    data = path.read_bytes()
    if len(data) != record.get(f"{kind}_size") or digest(data) != record.get(f"{kind}_sha256"):
        raise AdoptionError(f"rollback snapshot bytes drifted: {record.get('path')}")
    return data


def atomic_replace(source: Path, target: Path) -> None:
    source.replace(target)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent) as stream:
        temp = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        atomic_replace(temp, path)
    except Exception:
        if temp.exists():
            temp.unlink()
        raise


def verify_promotion_sources(repo_root: Path, report: dict[str, Any]) -> None:
    if report.get("adoption_manifest") != ADOPTION_REL.as_posix():
        raise AdoptionError("staged adoption manifest path drifted")
    sources = (
        (QUEUE_REL, "queue_sha256"),
        (TARGETS_REL, "targets_sha256"),
        (ADOPTION_REL, "adoption_manifest_sha256"),
    )
    for rel, field in sources:
        path = repo_root / rel
        if not path.is_file() or path.is_symlink():
            raise AdoptionError(f"promotion source is missing or unsafe: {rel.as_posix()}")
        if digest(path.read_bytes()) != report.get(field):
            raise AdoptionError(f"promotion source hash drifted: {rel.as_posix()}")


def _transaction(
    stage_root: Path, repo_root: Path, *, rollback: bool,
    replace: Callable[[Path, Path], None] = atomic_replace,
    report_writer: Callable[[Path, bytes], None] = atomic_write_bytes,
) -> dict[str, Any]:
    report, records = load_transaction(stage_root)
    if not rollback:
        verify_promotion_sources(repo_root, report)
    runtime_files = report.get("runtime_files", [])
    if (
        not isinstance(runtime_files, list)
        or len(runtime_files) != len(set(runtime_files))
        or any(not isinstance(rel, str) or not rel.startswith("magica/") for rel in runtime_files)
    ):
        raise AdoptionError("staged runtime file allowlist drifted")
    canonical_files = {
        FRONTEND_REL.as_posix(), MIGRATION_REL.as_posix(), CONTRACT_REL.as_posix(),
        *(rel.as_posix() for rel in GENERATED_RELS),
    }
    # A pre-contract Pass21 stage may be consumed once for rollback only.  New
    # promotions must always carry the post-adoption review contract.
    if rollback and CONTRACT_REL.as_posix() not in report.get("promotion_files", []):
        canonical_files.remove(CONTRACT_REL.as_posix())
    if set(report.get("promotion_files", [])) != canonical_files | set(runtime_files):
        raise AdoptionError("staged promotion file role contract drifted")

    name = "rollback_verification.json" if rollback else "promotion_verification.json"
    verification_path = stage_root / name
    if verification_path.exists() and (not verification_path.is_file() or verification_path.is_symlink()):
        raise AdoptionError(f"transaction report path is unsafe: {verification_path}")
    verification_before_exists = verification_path.is_file()
    verification_before = verification_path.read_bytes() if verification_before_exists else b""

    prepared = []
    for record in records:
        rel = str(record["path"])
        target = safe_repo_path(repo_root, rel)
        before = snapshot_bytes(stage_root, record, "before")
        after = snapshot_bytes(stage_root, record, "after")
        expected = after if rollback else before
        expected_exists = True if rollback else bool(record["before_exists"])
        if target.exists() != expected_exists:
            raise AdoptionError(f"repository existence gate failed: {rel}")
        if expected_exists and (not target.is_file() or target.is_symlink() or target.read_bytes() != expected):
            raise AdoptionError(f"repository byte gate failed: {rel}")
        desired = before if rollback else after
        desired_exists = bool(record["before_exists"]) if rollback else True
        prepared.append({"record": record, "target": target, "original": expected,
                         "original_exists": expected_exists, "desired": desired,
                         "desired_exists": desired_exists, "temp": None})

    result = {
        "schema": "magireco-cn-pass20-suggested-adoption-transaction/1", "status": "PASS",
        "mode": "rollback" if rollback else "promote", "files": [item["record"]["path"] for item in prepared],
        "atomic_per_file": True, "failure_compensation": True,
        "protected_text_changes": report["protected_text_changes"],
    }
    result_bytes = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    changed: list[dict[str, Any]] = []
    try:
        for item in prepared:
            if item["desired_exists"]:
                item["target"].parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile("wb", delete=False, dir=item["target"].parent) as stream:
                    item["temp"] = Path(stream.name)
                    stream.write(item["desired"])
                    stream.flush()
                    os.fsync(stream.fileno())
        for item in prepared:
            if item["desired_exists"]:
                replace(item["temp"], item["target"])
                item["temp"] = None
            else:
                item["target"].unlink()
            changed.append(item)
        for item in prepared:
            if item["target"].exists() != item["desired_exists"]:
                raise AdoptionError(f"repository post-write existence gate failed: {item['record']['path']}")
            if item["desired_exists"] and item["target"].read_bytes() != item["desired"]:
                raise AdoptionError(f"repository post-write byte gate failed: {item['record']['path']}")
        report_writer(verification_path, result_bytes)
        if not verification_path.is_file() or verification_path.is_symlink() or verification_path.read_bytes() != result_bytes:
            raise AdoptionError("transaction verification report byte gate failed")
    except Exception as exc:
        for item in prepared:
            temp = item.get("temp")
            if isinstance(temp, Path) and temp.exists():
                temp.unlink()
        for item in reversed(changed):
            if item["original_exists"]:
                with tempfile.NamedTemporaryFile("wb", delete=False, dir=item["target"].parent) as stream:
                    recovery = Path(stream.name)
                    stream.write(item["original"])
                    stream.flush()
                    os.fsync(stream.fileno())
                atomic_replace(recovery, item["target"])
            elif item["target"].exists():
                item["target"].unlink()
        if verification_before_exists:
            atomic_write_bytes(verification_path, verification_before)
        elif verification_path.exists():
            if not verification_path.is_file() or verification_path.is_symlink():
                raise AdoptionError(
                    f"transaction failed and report cleanup was unsafe: {verification_path}: {exc}"
                ) from exc
            verification_path.unlink()
        raise AdoptionError(f"transaction failed; all changed files restored: {exc}") from exc
    return result


def promote(
    stage_root: Path, repo_root: Path, *, replace: Callable[[Path, Path], None] = atomic_replace,
    report_writer: Callable[[Path, bytes], None] = atomic_write_bytes,
) -> dict[str, Any]:
    return _transaction(
        stage_root.resolve(), repo_root.resolve(), rollback=False,
        replace=replace, report_writer=report_writer,
    )


def rollback(
    stage_root: Path, repo_root: Path, *, replace: Callable[[Path, Path], None] = atomic_replace,
    report_writer: Callable[[Path, bytes], None] = atomic_write_bytes,
) -> dict[str, Any]:
    return _transaction(
        stage_root.resolve(), repo_root.resolve(), rollback=True,
        replace=replace, report_writer=report_writer,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--manifest", type=Path,
        help="tracked Pass21 adoption manifest (defaults under --repo-root)",
    )
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--allow-repository-write", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.rollback:
            if not args.allow_repository_write:
                raise AdoptionError("--rollback requires --allow-repository-write")
            result = rollback(args.stage_root, args.repo_root)
        elif args.allow_repository_write and (args.stage_root / "verification.json").is_file():
            result = promote(args.stage_root, args.repo_root)
        else:
            manifest = args.manifest or (args.repo_root / ADOPTION_REL)
            result = stage(args.repo_root, manifest, args.stage_root)
            if args.allow_repository_write:
                result = {"stage": result, "promotion": promote(args.stage_root, args.repo_root)}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (AdoptionError, OSError, UnicodeError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
