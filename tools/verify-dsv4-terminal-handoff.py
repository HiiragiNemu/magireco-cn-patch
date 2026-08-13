#!/usr/bin/env python3
"""Verify the committed, staging-only DSV4 terminal handoff byte for byte."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "magica/i18n_audit/release_v26_authority/dsv4_terminal_handoff"
)
HASH_RE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$")
EXPECTED_COUNTS = {
    "total_items": 1912,
    "accepted_batches": 74,
    "ds_reviewed_items": 1472,
    "approved": 1390,
    "correction": 37,
    "unresolved": 45,
    "manual_required_items": 440,
    "manual_current_low_tier": 176,
    "manual_protected_historical": 264,
    "human_decision_required": 522,
}
HASHED_FILES = {
    "correction_patch.json",
    "corrections.patch",
    "full_review.tsv",
    "human_review.tsv",
    "manifest.json",
    "manual_required.jsonl",
    "manual_required.tsv",
    "nonapproved_review.tsv",
    "provenance.tsv",
    "review_results.jsonl",
    "role_matrix.jsonl",
    "rollback.json",
    "staging_patch_executor.py",
    "unresolved.tsv",
    "verification_record.json",
}
EXPECTED_FILES = HASHED_FILES | {"README.md", "SHA256SUMS.txt"}


class HandoffError(RuntimeError):
    """A terminal-handoff invariant failed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"invalid JSON {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise HandoffError(f"JSON root must be an object: {path.name}")
    return value


def load_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise HandoffError(f"TSV must be UTF-8-no-BOM with LF endings: {path.name}")
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            header = list(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise HandoffError(f"invalid TSV {path.name}: {exc}") from exc
    if not header or any(None in row for row in rows):
        raise HandoffError(f"malformed TSV rows: {path.name}")
    return header, rows


def verify(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise HandoffError(f"handoff directory missing or unsafe: {root}")
    actual_files = {
        item.name for item in root.iterdir() if item.is_file() and not item.is_symlink()
    }
    if actual_files != EXPECTED_FILES:
        raise HandoffError(
            f"handoff file set mismatch: missing={sorted(EXPECTED_FILES-actual_files)}, "
            f"extra={sorted(actual_files-EXPECTED_FILES)}"
        )

    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        match = HASH_RE.fullmatch(line)
        if not match or match.group(2) in sums:
            raise HandoffError("SHA256SUMS.txt is malformed or contains duplicates")
        sums[match.group(2)] = match.group(1)
    if set(sums) != HASHED_FILES:
        raise HandoffError("SHA256SUMS.txt does not bind the exact assembly file set")
    drift = [name for name, expected in sums.items() if sha256(root / name) != expected]
    if drift:
        raise HandoffError(f"handoff hash drift: {sorted(drift)}")

    manifest = load_json(root / "manifest.json")
    verification = load_json(root / "verification_record.json")
    if manifest.get("schema") != "magireco-cn-dsv4-v3-terminal-assembly/2-manifest":
        raise HandoffError("unexpected manifest schema")
    if manifest.get("status") != "terminal-manual-handoff-verified-staging-only":
        raise HandoffError("manifest is not the verified manual-handoff terminal state")
    if verification.get("status") != "PASS":
        raise HandoffError("terminal verification record is not PASS")
    for document in (manifest, verification):
        if document.get("terminal_mode") != "manual_handoff":
            raise HandoffError("terminal mode is not manual_handoff")
        if document.get("ds_phase") != "closed_manual_handoff":
            raise HandoffError("DS phase is not closed_manual_handoff")
        if document.get("network_configuration_writes") is not False:
            raise HandoffError("network configuration write invariant failed")
    if manifest.get("counts") != EXPECTED_COUNTS:
        raise HandoffError("manifest counts differ from the sealed inventory")
    if manifest.get("product_tree_writes") is not False:
        raise HandoffError("terminal assembly claims product-tree writes")
    if manifest.get("protected_text_changes") != 0:
        raise HandoffError("terminal assembly claims protected text changes")
    protection = verification.get("protection", {})
    if protection != {
        "product_tree_writes": False,
        "product_write_allowed_items": 0,
        "protected_text_changes": 0,
    }:
        raise HandoffError("verification protection contract drifted")

    outputs = manifest.get("outputs", {})
    if set(outputs) != HASHED_FILES - {"manifest.json"}:
        raise HandoffError("manifest output set is incomplete")
    for name, record in outputs.items():
        path = root / name
        if record.get("bytes") != path.stat().st_size or record.get("sha256") != sha256(path):
            raise HandoffError(f"manifest output binding drifted: {name}")

    human_header, human = load_tsv(root / "human_review.tsv")
    _manual_header, manual = load_tsv(root / "manual_required.tsv")
    nonapproved_header, nonapproved = load_tsv(root / "nonapproved_review.tsv")
    _unresolved_header, unresolved = load_tsv(root / "unresolved.tsv")
    required_columns = {
        "item_id", "stable_business_key", "source_path", "source_key", "source_field",
        "review_kind", "allowed_action", "japanese_or_source_original", "old_cn",
        "current_cn", "suggested_cn", "parent_verdict", "highest_authority_tier",
        "authority_status", "authority_evidence", "official_cn", "wiki_cn",
        "confirmed_human_cn", "protected_authority_text", "product_write_allowed",
        "allowed_human_decisions", "human_decision", "reviewer", "timestamp",
        "final_value", "human_notes",
    }
    if not required_columns.issubset(human_header) or not required_columns.issubset(nonapproved_header):
        raise HandoffError("human review tables lack required decision/provenance columns")
    if len(human) != 1912 or len(manual) != 440 or len(nonapproved) != 522 or len(unresolved) != 45:
        raise HandoffError("human/manual/unresolved row counts drifted")
    human_ids = [row["item_id"] for row in human]
    nonapproved_ids = [row["item_id"] for row in nonapproved]
    manual_ids = [row["item_id"] for row in manual]
    if len(set(human_ids)) != 1912 or len(set(nonapproved_ids)) != 522 or len(set(manual_ids)) != 440:
        raise HandoffError("review item ids are not unique")
    if not set(nonapproved_ids).issubset(human_ids) or not set(manual_ids).issubset(nonapproved_ids):
        raise HandoffError("manual/nonapproved tables are not exact inventory subsets")
    if Counter(row["parent_verdict"] for row in nonapproved) != Counter(
        {"manual-required": 440, "correction": 37, "unresolved": 45}
    ):
        raise HandoffError("nonapproved verdict partition drifted")
    if Counter(row["review_kind"] for row in nonapproved) != Counter(
        {"current-low-tier-translation-review": 258, "historical-pass8-llm-comparison-only": 264}
    ):
        raise HandoffError("human decision review-kind partition drifted")
    if any(row["product_write_allowed"] != "false" for row in nonapproved):
        raise HandoffError("human queue contains an implicitly product-writable row")
    if any(row["human_decision"] or row["reviewer"] or row["timestamp"] or row["final_value"] for row in nonapproved):
        raise HandoffError("unreviewed human decision fields are not blank")
    for row in nonapproved:
        expected = (
            '["approve-current","revise","unresolved"]'
            if row["review_kind"] == "current-low-tier-translation-review"
            else '["keep-authority","unresolved"]'
        )
        if row["allowed_human_decisions"] != expected:
            raise HandoffError(f"invalid decision enum for {row['item_id']}")

    patch = load_json(root / "correction_patch.json")
    rollback = load_json(root / "rollback.json")
    patch_ids = [entry.get("item_id") for entry in patch.get("entries", [])]
    rollback_ids = [entry.get("item_id") for entry in rollback.get("entries", [])]
    if len(patch_ids) != 37 or patch_ids != rollback_ids or len(set(patch_ids)) != 37:
        raise HandoffError("correction patch and rollback are not a 37-item bijection")
    if patch.get("product_tree_writes") is not False or rollback.get("product_tree_writes") is not False:
        raise HandoffError("patch or rollback escaped staging-only scope")
    if patch.get("human_approval_required") is not True:
        raise HandoffError("correction patch does not require human approval")

    return {
        "schema": "magireco-cn-dsv4-terminal-handoff-verification/v1",
        "status": "PASS",
        "root": str(root),
        "files": len(actual_files),
        "bytes": sum((root / name).stat().st_size for name in actual_files),
        "manifest_sha256": sha256(root / "manifest.json"),
        "sha256sums_sha256": sha256(root / "SHA256SUMS.txt"),
        "readme_sha256": sha256(root / "README.md"),
        "counts": EXPECTED_COUNTS,
        "decision_queue": {
            "all_rows": 1912,
            "human_required": 522,
            "current_product_low_tier": 258,
            "historical_protected_comparison_only": 264,
            "blank_decisions": 522,
        },
        "patch_entries": 37,
        "rollback_entries": 37,
        "product_tree_writes": False,
        "protected_text_changes": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify(args.root), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (HandoffError, OSError, UnicodeDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
