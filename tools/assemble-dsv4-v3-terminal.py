#!/usr/bin/env python3
"""Deterministically assemble the terminal DSV4 v3 review evidence.

This tool is deliberately read-only with respect to ``staging_v3``.  It reads
only the immutable queue/accepted records, generated checkpoint artifacts, the
source lock, and the append-only ledger.  It never reads or writes the product
tree and emits only review/staging artifacts into a new directory outside this
repository.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_PREFIX = "magireco-cn-dsv4-v3"
TOOL_SCHEMA = "magireco-cn-dsv4-v3-terminal-assembly/2"
TOOL_VERSION = "2"
TOTAL_ITEMS = 1912
TOTAL_BATCHES = 96
MANUAL_HANDOFF_BATCHES = 74
MANUAL_HANDOFF_ITEMS = 1472
MANUAL_REQUIRED_ITEMS = TOTAL_ITEMS - MANUAL_HANDOFF_ITEMS
MANUAL_CURRENT_LOW_TIER_ITEMS = 176
MANUAL_PROTECTED_HISTORICAL_ITEMS = 264
IMPORTED_BATCHES = 15
IMPORTED_ITEMS = 292
BATCH_SIZE = 20
MODEL = "deepseek-v4-flash"
EFFORT = "max"
DEFAULT_PARENT_SESSION = "7d338408-3137-4825-ba71-d00eb6aa335d"
ROLE_NAMES = (
    "japanese_semantics_context",
    "official_cn_comparison",
    "hiiraginemu_wiki_comparison",
    "confirmed_human_provenance_protection",
    "names_honorifics_terms_placeholders_format",
)
ROLE_CODES = dict(zip(ROLE_NAMES, ("R1", "object-storage", "R3", "R4", "R5")))
ROLE_VERDICTS = {"approved", "correction", "unresolved", "N/A"}
PARENT_VERDICTS = {"approved", "correction", "unresolved"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_GENERATED_FILES = {
    "candidate.patch",
    "checkpoint.json",
    "heartbeat.json",
    "manual_review.tsv",
    "review_manifest.json",
    "review_results.jsonl",
    "role_matrix.jsonl",
    "rollback.json",
    "summary.json",
}
MANUAL_HANDOFF_GENERATED_FILES = EXPECTED_GENERATED_FILES | {
    "manual_required.jsonl",
    "manual_required.tsv",
    "manual_handoff_manifest.json",
    "manual_handoff_state.json",
}
TOOL_USAGE_AUDIT = "dsv4_current_job_tool_usage_audit.json"
STALE_EVIDENCE_GLOB = "stale_pending_quarantine_*.json"
PATCH_EXECUTOR_NAME = "staging_patch_executor.py"
PATCH_EXECUTOR_SOURCE = Path(__file__).with_name("dsv4-v3-staging-patch.py")


class TerminalizationError(RuntimeError):
    """Fail-closed validation or assembly error."""


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_record(data: bytes) -> dict[str, Any]:
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    if data.startswith(b"\xef\xbb\xbf"):
        raise TerminalizationError(f"UTF-8 BOM forbidden: {label}")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TerminalizationError(f"invalid UTF-8 JSON: {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise TerminalizationError(f"JSON object required: {label}")
    return value


def parse_jsonl(data: bytes, label: str) -> list[dict[str, Any]]:
    if data.startswith(b"\xef\xbb\xbf"):
        raise TerminalizationError(f"UTF-8 BOM forbidden: {label}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TerminalizationError(f"invalid UTF-8 JSONL: {label}: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TerminalizationError(f"invalid JSONL {label}:{number}: {exc}") from exc
        if not isinstance(value, dict):
            raise TerminalizationError(f"JSONL object required {label}:{number}")
        rows.append(value)
    return rows


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def batch_bounds(number: int) -> tuple[int, int]:
    if not 1 <= number <= TOTAL_BATCHES:
        raise TerminalizationError(f"batch number out of range: {number}")
    if number <= 3:
        start, end = (number - 1) * BATCH_SIZE + 1, number * BATCH_SIZE
    elif number == 4:
        start, end = 61, 72
    else:
        start = 73 + (number - 5) * BATCH_SIZE
        end = start + BATCH_SIZE - 1
    return start, min(end, TOTAL_ITEMS)


def expected_applicability(item: dict[str, Any]) -> dict[str, bool]:
    refs = item.get("authority_references") or {}
    return {
        ROLE_NAMES[0]: True,
        ROLE_NAMES[1]: bool(str(refs.get("official_cn", "")).strip()),
        ROLE_NAMES[2]: bool(str(refs.get("wiki_cn", "")).strip()),
        ROLE_NAMES[3]: bool(str(refs.get("confirmed_human_cn", "")).strip()) or bool(item.get("protected_authority_text")),
        ROLE_NAMES[4]: True,
    }


def _require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise TerminalizationError(f"invalid SHA-256: {label}")
    return value


@dataclass(frozen=True)
class StageSnapshot:
    stage: Path
    raw: dict[str, bytes]
    hashes: dict[str, dict[str, Any]]
    digest: str


def _capture_common_paths(stage: Path, *, accepted_count: int, generated_files: set[str], include_terminal_documents: bool) -> StageSnapshot:
    """Capture an exact immutable view for either supported terminal mode."""
    stage = stage.resolve()
    if stage.name != "staging_v3" or not stage.is_dir():
        raise TerminalizationError(f"stage must be an existing staging_v3 directory: {stage}")
    paths: list[tuple[str, Path]] = [
        ("source_lock_v3.json", stage / "source_lock_v3.json"),
        ("append_only_ledger.jsonl", stage / "append_only_ledger.jsonl"),
        (TOOL_USAGE_AUDIT, stage / TOOL_USAGE_AUDIT),
    ]
    if include_terminal_documents:
        paths.extend([
            ("job_manifest_v3.json", stage / "job_manifest_v3.json"),
            ("pipeline_verification.json", stage / "pipeline_verification.json"),
        ])
    stale_files = sorted((stage / "runtime").glob(STALE_EVIDENCE_GLOB)) if (stage / "runtime").is_dir() else []
    if len(stale_files) != 1:
        raise TerminalizationError(f"exactly one stale batch quarantine record required, found {len(stale_files)}")
    if stale_files[0].is_symlink() or not stale_files[0].is_file():
        raise TerminalizationError("stale batch quarantine record must be a regular non-symlink file")
    stale_label = stale_files[0].relative_to(stage).as_posix()
    stale_record = parse_json(stale_files[0].read_bytes(), stale_label)
    quarantine_relative = stale_record.get("quarantine_path")
    if not isinstance(quarantine_relative, str) or not quarantine_relative.startswith("rejected/"):
        raise TerminalizationError("stale quarantine target path invalid")
    quarantine_path = stage / Path(quarantine_relative)
    if not _inside(quarantine_path, stage / "rejected"):
        raise TerminalizationError("stale quarantine target escapes rejected directory")
    paths.extend([(stale_label, stale_files[0]), (quarantine_relative, quarantine_path)])
    for directory, expected_count in (("queue", TOTAL_BATCHES), ("accepted", accepted_count)):
        root = stage / directory
        actual = sorted(p.name for p in root.iterdir() if p.is_file()) if root.is_dir() else []
        expected = [f"batch_{number:03d}.json" for number in range(1, expected_count + 1)]
        if actual != expected:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            raise TerminalizationError(
                f"terminal {directory} inventory required: expected {expected_count}, found {len(actual)}; "
                f"missing={missing[:5]} extra={extra[:5]}"
            )
        paths.extend((f"{directory}/{name}", root / name) for name in expected)
    generated = stage / "generated"
    actual_generated = {p.name for p in generated.iterdir() if p.is_file()} if generated.is_dir() else set()
    if actual_generated != generated_files:
        raise TerminalizationError(
            f"generated inventory mismatch: missing={sorted(generated_files-actual_generated)} "
            f"extra={sorted(actual_generated-generated_files)}"
        )
    paths.extend((f"generated/{name}", generated / name) for name in sorted(generated_files))
    raw: dict[str, bytes] = {}
    for relative, path in paths:
        if path.is_symlink() or not path.is_file():
            raise TerminalizationError(f"regular non-symlink input required: {relative}")
        raw[relative] = path.read_bytes()
    hashes = {name: file_record(data) for name, data in sorted(raw.items())}
    digest = sha256_bytes(canonical_json_bytes(hashes))
    return StageSnapshot(stage=stage, raw=raw, hashes=hashes, digest=digest)


def capture_snapshot(stage: Path) -> StageSnapshot:
    return _capture_common_paths(
        stage, accepted_count=TOTAL_BATCHES, generated_files=EXPECTED_GENERATED_FILES,
        include_terminal_documents=False,
    )


def capture_manual_handoff_snapshot(stage: Path) -> StageSnapshot:
    return _capture_common_paths(
        stage, accepted_count=MANUAL_HANDOFF_BATCHES, generated_files=MANUAL_HANDOFF_GENERATED_FILES,
        include_terminal_documents=True,
    )


@dataclass
class ValidatedStage:
    snapshot: StageSnapshot
    source_lock: dict[str, Any]
    queue_batches: list[dict[str, Any]]
    accepted_batches: list[dict[str, Any]]
    entries: list[dict[str, Any]]
    ledger: list[dict[str, Any]]
    ledger_status: dict[str, Any]
    verdict_counts: Counter[str]
    role_counts: dict[str, Counter[str]]
    imported_session_id: str
    parent_session_id: str
    corrections: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]
    generated_validation: dict[str, Any]
    exception_evidence: dict[str, Any]


def _validate_source_lock(snapshot: StageSnapshot) -> dict[str, Any]:
    lock = parse_json(snapshot.raw["source_lock_v3.json"], "source_lock_v3.json")
    if lock.get("schema") != f"{SCHEMA_PREFIX}-source-lock/1":
        raise TerminalizationError("source lock schema invalid")
    if lock.get("source_v2_atomic_history") != "failed" or lock.get("source_v2_atomicity_claimed") is not False:
        raise TerminalizationError("source v2 failed atomic history must remain explicit")
    if not isinstance(lock.get("source_job_id"), str) or not lock["source_job_id"].strip():
        raise TerminalizationError("source lock job ID missing")
    if not isinstance(lock.get("source_session_id"), str) or not lock["source_session_id"].strip():
        raise TerminalizationError("source lock session ID missing")
    files = lock.get("files")
    if not isinstance(files, dict) or "items.jsonl" not in files or "protected_authority_reference_148_v2.tsv" not in files:
        raise TerminalizationError("source lock required file bindings missing")
    for name, record in files.items():
        if not isinstance(name, str) or not name or not isinstance(record, dict):
            raise TerminalizationError("source lock file record invalid")
        if not isinstance(record.get("bytes"), int) or record["bytes"] < 0:
            raise TerminalizationError(f"source lock byte count invalid: {name}")
        _require_hash(record.get("sha256"), f"source lock {name}")
    return lock


def _validate_exception_evidence(snapshot: StageSnapshot, expected_parent_session: str) -> dict[str, Any]:
    stale_labels = sorted(name for name in snapshot.raw if name.startswith("runtime/stale_pending_quarantine_") and name.endswith(".json"))
    if len(stale_labels) != 1:
        raise TerminalizationError("snapshot must bind exactly one stale pending quarantine record")
    stale_label = stale_labels[0]
    stale = parse_json(snapshot.raw[stale_label], stale_label)
    if stale.get("schema") != f"{SCHEMA_PREFIX}-stale-pending-quarantine/1":
        raise TerminalizationError("stale pending quarantine schema invalid")
    quarantine_label = stale.get("quarantine_path")
    if not isinstance(quarantine_label, str) or quarantine_label not in snapshot.raw or not quarantine_label.startswith("rejected/batch_072_reboot_stale_"):
        raise TerminalizationError("stale batch72 quarantine file binding invalid")
    if stale.get("source_path") != "pending/batch_072.json" or stale.get("item_ids_equal") is not True:
        raise TerminalizationError("stale batch72 identity evidence invalid")
    pending_sha = _require_hash(stale.get("pending_sha256"), "stale pending batch72")
    accepted_sha = _require_hash(stale.get("accepted_sha256"), "accepted batch72")
    _require_hash(stale.get("accepted_pending_payload_sha256"), "accepted batch72 pending payload")
    if snapshot.hashes[quarantine_label]["sha256"] != pending_sha:
        raise TerminalizationError("quarantined batch72 bytes do not match recorded pending SHA-256")
    if snapshot.hashes["accepted/batch_072.json"]["sha256"] != accepted_sha:
        raise TerminalizationError("accepted batch72 bytes do not match quarantine record")
    checkpoint_before = stale.get("checkpoint_before")
    if not isinstance(checkpoint_before, dict) or checkpoint_before.get("last_completed_batch") != 74 or checkpoint_before.get("next_batch") != 75:
        raise TerminalizationError("stale batch72 checkpoint context invalid")
    if stale.get("product_tree_written") is not False or stale.get("authority_text_changed") is not False:
        raise TerminalizationError("stale batch72 quarantine protection assertion invalid")

    audit = parse_json(snapshot.raw[TOOL_USAGE_AUDIT], TOOL_USAGE_AUDIT)
    if audit.get("schema") != "magireco-cn-dsv4-tool-usage-audit/1" or audit.get("session_id") != expected_parent_session:
        raise TerminalizationError("historical tool-usage audit session/schema invalid")
    conclusions = audit.get("conclusions") or {}
    uses = audit.get("forbidden_tool_uses")
    counts = audit.get("forbidden_tool_use_counts") or {}
    if conclusions.get("bash_used") is not True or counts != {"Bash": 4} or not isinstance(uses, list) or len(uses) != 4:
        raise TerminalizationError("exactly four historical Bash policy exceptions must be disclosed")
    disclosed: list[dict[str, Any]] = []
    for index, event in enumerate(uses, 1):
        if not isinstance(event, dict) or event.get("tool") != "Bash" or event.get("result") not in {"success", "error"}:
            raise TerminalizationError(f"historical Bash event invalid: {index}")
        if not isinstance(event.get("line"), int) or not isinstance(event.get("timestamp"), str) or not event["timestamp"]:
            raise TerminalizationError(f"historical Bash event evidence incomplete: {index}")
        disclosed.append({"line": event["line"], "result": event["result"], "timestamp": event["timestamp"], "tool": "Bash"})
    if conclusions.get("repository_or_host_path_boundary_violation") is not False or audit.get("host_network_configuration_writes") != 0:
        raise TerminalizationError("historical tool audit reports a host/repository boundary or network write")
    return {
        "stale_batch72_quarantine": {
            "audit_record": {"path": stale_label, **snapshot.hashes[stale_label]},
            "quarantined_payload": {"path": quarantine_label, **snapshot.hashes[quarantine_label]},
            "accepted_batch72": {"path": "accepted/batch_072.json", **snapshot.hashes["accepted/batch_072.json"]},
            "pending_sha256": pending_sha,
            "accepted_sha256": accepted_sha,
            "checkpoint_before": checkpoint_before,
            "product_tree_written": False,
            "authority_text_changed": False,
        },
        "historical_tool_policy_exception": {
            "status": "disclosed-from-staging-evidence",
            "re_review_claimed": False,
            "affected_batches_claimed": False,
            "scope_note": "the captured audit identifies transcript line events but does not bind them to batch numbers",
            "audit_record": {"path": TOOL_USAGE_AUDIT, **snapshot.hashes[TOOL_USAGE_AUDIT]},
            "bash_use_count": 4,
            "result_counts": dict(sorted(Counter(event["result"] for event in disclosed).items())),
            "events": disclosed,
            "path_boundary_violations": 0,
            "host_network_configuration_writes": 0,
        },
    }


def _validate_queue(snapshot: StageSnapshot, source_lock: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    batches: list[dict[str, Any]] = []
    all_items: list[dict[str, Any]] = []
    expected_input_hash = source_lock["files"]["items.jsonl"]["sha256"]
    for number in range(1, TOTAL_BATCHES + 1):
        label = f"queue/batch_{number:03d}.json"
        batch = parse_json(snapshot.raw[label], label)
        start, end = batch_bounds(number)
        count = end - start + 1
        if batch.get("schema") != f"{SCHEMA_PREFIX}-queue-batch/1" or batch.get("batch_number") != number:
            raise TerminalizationError(f"queue batch identity invalid: {number}")
        if batch.get("item_range") != {"start": start, "end": end, "count": count}:
            raise TerminalizationError(f"queue item range invalid: {number}")
        if batch.get("model_required") != MODEL or batch.get("effort_required") != EFFORT:
            raise TerminalizationError(f"queue model/effort invalid: {number}")
        if batch.get("roles_required") != list(ROLE_NAMES):
            raise TerminalizationError(f"queue five-role contract invalid: {number}")
        if batch.get("input_items_sha256") != expected_input_hash:
            raise TerminalizationError(f"queue source-lock hash binding invalid: {number}")
        items = batch.get("items")
        ids = batch.get("item_ids")
        if not isinstance(items, list) or not isinstance(ids, list) or len(items) != count or ids != [x.get("item_id") for x in items]:
            raise TerminalizationError(f"queue items/IDs invalid: {number}")
        for offset, item in enumerate(items):
            index = start + offset
            if not isinstance(item, dict):
                raise TerminalizationError(f"queue item object required: {index}")
            item_id = item.get("item_id")
            stable_key = item.get("stable_business_key")
            if not isinstance(item_id, str) or not item_id or not isinstance(stable_key, str) or not stable_key:
                raise TerminalizationError(f"queue stable identity missing: {index}")
            original = str(item.get("japanese_or_source_original", ""))
            old_cn = str(item.get("old_cn", ""))
            if sha256_bytes(original.encode("utf-8")) != item.get("source_text_sha256"):
                raise TerminalizationError(f"queue source text hash mismatch: {item_id}")
            if sha256_bytes(old_cn.encode("utf-8")) != item.get("old_cn_sha256"):
                raise TerminalizationError(f"queue old CN hash mismatch: {item_id}")
            if item.get("product_write_allowed") is not False:
                raise TerminalizationError(f"product write permission detected: {item_id}")
            protected = bool(item.get("protected_authority_text"))
            expected_action = "review-history-only" if protected else "review-and-stage-low-tier-only"
            if item.get("allowed_action") != expected_action:
                raise TerminalizationError(f"allowed action/protection mismatch: {item_id}")
        batches.append(batch)
        all_items.extend(items)
    if len(all_items) != TOTAL_ITEMS:
        raise TerminalizationError(f"queue item count mismatch: {len(all_items)}")
    for field in ("item_id", "stable_business_key", "origin_record_id"):
        values = [x.get(field) for x in all_items]
        if any(not isinstance(x, str) or not x for x in values) or len(set(values)) != TOTAL_ITEMS:
            raise TerminalizationError(f"queue {field} must be non-empty and unique")
    return batches, all_items


def _validate_role_and_parent(
    *, entry: dict[str, Any], source_item: dict[str, Any], imported: bool, item_id: str
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    roles = entry.get("roles")
    if not isinstance(roles, dict) or set(roles) != set(ROLE_NAMES):
        raise TerminalizationError(f"exact five-role matrix required: {item_id}")
    expected_app = expected_applicability(source_item)
    applicable_verdicts: list[str] = []
    proposals: list[str] = []
    imported_agents: list[str] = []
    for name in ROLE_NAMES:
        role = roles[name]
        if not isinstance(role, dict) or role.get("verdict") not in ROLE_VERDICTS:
            raise TerminalizationError(f"role verdict invalid: {item_id}/{name}")
        expected_literal = "applicable" if expected_app[name] else "N/A"
        actual_literal = role.get("applicability")
        imported_r4_exception = imported and name == ROLE_NAMES[3] and not expected_app[name] and actual_literal == "applicable-by-source-role"
        if actual_literal != expected_literal and not imported_r4_exception:
            raise TerminalizationError(f"role applicability invalid: {item_id}/{name}")
        if actual_literal == "N/A" and role["verdict"] != "N/A":
            raise TerminalizationError(f"inapplicable role has verdict: {item_id}/{name}")
        if actual_literal != "N/A" and role["verdict"] == "N/A":
            raise TerminalizationError(f"applicable role marked N/A: {item_id}/{name}")
        for field in ("evidence", "rationale"):
            if not isinstance(role.get(field), str) or not role[field].strip():
                raise TerminalizationError(f"role {field} missing: {item_id}/{name}")
        if role["verdict"] != "N/A":
            applicable_verdicts.append(role["verdict"])
        if role["verdict"] == "correction":
            proposal = role.get("proposed_cn")
            if not isinstance(proposal, str) or not proposal:
                raise TerminalizationError(f"correction proposal missing: {item_id}/{name}")
            proposals.append(proposal)
        if imported:
            agent_id = role.get("source_agent_id")
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise TerminalizationError(f"imported role agent missing: {item_id}/{name}")
            imported_agents.append(agent_id)
    if imported and len(set(imported_agents)) != len(ROLE_NAMES):
        raise TerminalizationError(f"imported role agents not independent: {item_id}")
    parent = entry.get("parent")
    if not isinstance(parent, dict) or parent.get("verdict") not in PARENT_VERDICTS:
        raise TerminalizationError(f"parent verdict invalid: {item_id}")
    if not isinstance(parent.get("rationale"), str) or not parent["rationale"].strip():
        raise TerminalizationError(f"parent rationale missing: {item_id}")
    expected_role_verdicts = {name: roles[name]["verdict"] for name in ROLE_NAMES}
    if parent.get("role_verdicts") != expected_role_verdicts:
        raise TerminalizationError(f"parent role matrix mismatch: {item_id}")
    if parent["verdict"] == "approved" and any(x != "approved" for x in applicable_verdicts):
        raise TerminalizationError(f"parent approval conflicts with roles: {item_id}")
    if parent["verdict"] == "correction":
        if "unresolved" in applicable_verdicts or not proposals or len(set(proposals)) != 1:
            raise TerminalizationError(f"parent correction lacks role consensus: {item_id}")
        candidate = parent.get("suggested_cn") or parent.get("proposed_cn")
        if candidate != proposals[0] or candidate == source_item.get("current_cn"):
            raise TerminalizationError(f"parent correction value invalid: {item_id}")
    if source_item.get("protected_authority_text"):
        all_proposals = [r.get("proposed_cn") for r in roles.values() if r.get("proposed_cn")]
        all_proposals += [parent.get(k) for k in ("suggested_cn", "proposed_cn") if parent.get(k)]
        if parent["verdict"] == "correction" or all_proposals:
            raise TerminalizationError(f"protected authority proposal detected: {item_id}")
    return roles, parent, proposals


def _validate_accepted(
    snapshot: StageSnapshot,
    source_lock: dict[str, Any],
    queue_batches: list[dict[str, Any]],
    expected_parent_session: str,
    *,
    accepted_count: int = TOTAL_BATCHES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    batches: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    protected_hash = source_lock["files"]["protected_authority_reference_148_v2.tsv"]["sha256"]
    imported_session = source_lock["source_session_id"]
    if not IMPORTED_BATCHES <= accepted_count <= TOTAL_BATCHES:
        raise TerminalizationError(f"accepted batch count out of range: {accepted_count}")
    for number, queue in enumerate(queue_batches[:accepted_count], 1):
        label = f"accepted/batch_{number:03d}.json"
        batch = parse_json(snapshot.raw[label], label)
        imported = number <= IMPORTED_BATCHES
        if batch.get("schema") != f"{SCHEMA_PREFIX}-accepted-batch/1" or batch.get("batch_number") != number:
            raise TerminalizationError(f"accepted batch identity invalid: {number}")
        if batch.get("item_range") != queue["item_range"] or batch.get("item_ids") != queue["item_ids"]:
            raise TerminalizationError(f"accepted queue binding invalid: {number}")
        assertion = batch.get("protection_assertion") or {}
        if assertion.get("product_tree_written") is not False or assertion.get("authority_text_changed") is not False:
            raise TerminalizationError(f"accepted protection assertion invalid: {number}")
        if imported:
            if assertion.get("locked_source_hashes") != source_lock["files"]:
                raise TerminalizationError(f"imported source-lock binding invalid: {number}")
        elif assertion.get("protected_reference_sha256") != protected_hash:
            raise TerminalizationError(f"protected reference hash mismatch: {number}")
        runtime = batch.get("review_runtime") or {}
        if runtime.get("model") != MODEL or runtime.get("effort") != EFFORT:
            raise TerminalizationError(f"accepted model/effort invalid: {number}")
        if imported:
            if runtime.get("kind") != "verified-v2-content-import":
                raise TerminalizationError(f"imported runtime kind invalid: {number}")
            if runtime.get("source_parent_session_id") != imported_session or runtime.get("source_job_id") != source_lock["source_job_id"]:
                raise TerminalizationError(f"imported session/job binding invalid: {number}")
        else:
            agents = runtime.get("agents")
            if runtime.get("kind") != "deepseek-v4-cross-role-review" or runtime.get("parent_session_id") != expected_parent_session:
                raise TerminalizationError(f"review parent session/kind invalid: {number}")
            if not isinstance(agents, dict) or set(agents) != set(ROLE_NAMES):
                raise TerminalizationError(f"review agents matrix invalid: {number}")
            if any(not isinstance(x, str) or not x.strip() for x in agents.values()) or len(set(agents.values())) != len(ROLE_NAMES):
                raise TerminalizationError(f"review agents must be five independent IDs: {number}")
        batch_entries = batch.get("items")
        if not isinstance(batch_entries, list) or len(batch_entries) != len(queue["items"]):
            raise TerminalizationError(f"accepted item count invalid: {number}")
        for offset, (source_item, entry) in enumerate(zip(queue["items"], batch_entries)):
            source_index = queue["item_range"]["start"] + offset
            item_id = source_item["item_id"]
            if not isinstance(entry, dict):
                raise TerminalizationError(f"accepted item object required: {item_id}")
            identity = (entry.get("item_id"), entry.get("origin_record_id"), entry.get("stable_business_key"), entry.get("source_index"))
            expected_identity = (item_id, source_item.get("origin_record_id"), source_item.get("stable_business_key"), source_index)
            if identity != expected_identity or entry.get("source_item") != source_item:
                raise TerminalizationError(f"accepted source snapshot/order drift: {item_id}")
            _validate_role_and_parent(entry=entry, source_item=source_item, imported=imported, item_id=item_id)
            if imported:
                provenance = entry.get("import_provenance") or {}
                if provenance.get("source_v2_atomic_history") != "failed" or provenance.get("source_v2_atomicity_claimed") is not False:
                    raise TerminalizationError(f"imported atomic-history claim invalid: {item_id}")
                if provenance.get("source_v2_session_id") != imported_session or provenance.get("source_v2_job_id") != source_lock["source_job_id"]:
                    raise TerminalizationError(f"imported item session/job invalid: {item_id}")
                for key in ("source_v2_role_line_sha256", "source_v2_review_line_sha256"):
                    _require_hash(provenance.get(key), f"{item_id}/{key}")
            else:
                pending_hash = _require_hash(batch.get("pending_payload_sha256"), f"batch {number} pending payload")
                provenance = entry.get("review_provenance") or {}
                expected_provenance = {
                    "agents": runtime["agents"],
                    "effort": EFFORT,
                    "job_id": runtime.get("job_id"),
                    "model": MODEL,
                    "parent_session_id": expected_parent_session,
                    "pending_input_sha256": pending_hash,
                }
                if provenance != expected_provenance:
                    raise TerminalizationError(f"review provenance mismatch: {item_id}")
            entries.append(entry)
        batches.append(batch)
    expected_items = batch_bounds(accepted_count)[1]
    if len(entries) != expected_items or [x["source_index"] for x in entries] != list(range(1, expected_items + 1)):
        raise TerminalizationError("accepted item count/order invalid")
    if [x["item_id"] for x in entries] != [x for b in queue_batches[:accepted_count] for x in b["item_ids"]]:
        raise TerminalizationError("accepted item identity order differs from queue")
    return batches, entries


def _validate_ledger(
    snapshot: StageSnapshot,
    accepted_batches: list[dict[str, Any]],
    expected_parent_session: str,
    *,
    accepted_count: int = TOTAL_BATCHES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = parse_jsonl(snapshot.raw["append_only_ledger.jsonl"], "append_only_ledger.jsonl")
    previous = "0" * 64
    promotions: dict[int, dict[str, Any]] = {}
    for sequence, row in enumerate(rows, 1):
        if row.get("sequence") != sequence or row.get("previous_entry_sha256") != previous:
            raise TerminalizationError(f"ledger chain metadata invalid at line {sequence}")
        material = dict(row)
        digest = material.pop("entry_sha256", None)
        expected = sha256_bytes(canonical_json_bytes(material))
        if digest != expected:
            raise TerminalizationError(f"ledger entry hash invalid at line {sequence}")
        previous = digest
        if row.get("type") in {"imported_batch_promoted", "pending_batch_promoted"}:
            number = row.get("batch_number")
            if not isinstance(number, int) or number in promotions:
                raise TerminalizationError(f"duplicate/invalid ledger promotion at line {sequence}")
            promotions[number] = row
    if set(promotions) != set(range(1, accepted_count + 1)):
        raise TerminalizationError(f"ledger promotions do not cover exactly 1-{accepted_count}")
    for number, batch in enumerate(accepted_batches, 1):
        row = promotions[number]
        accepted_hash = snapshot.hashes[f"accepted/batch_{number:03d}.json"]["sha256"]
        expected_type = "imported_batch_promoted" if number <= IMPORTED_BATCHES else "pending_batch_promoted"
        if row.get("type") != expected_type or row.get("accepted_sha256") != accepted_hash or row.get("item_range") != batch["item_range"]:
            raise TerminalizationError(f"ledger accepted binding invalid: {number}")
        if number <= IMPORTED_BATCHES:
            item_ids_hash = sha256_bytes(canonical_json_bytes(batch["item_ids"]))
            if row.get("item_ids_sha256") != item_ids_hash or row.get("v3_atomic_accept") is not True:
                raise TerminalizationError(f"ledger imported binding invalid: {number}")
        else:
            runtime = batch["review_runtime"]
            if (
                row.get("pending_payload_sha256") != batch.get("pending_payload_sha256")
                or row.get("parent_session_id") != expected_parent_session
                or row.get("model") != MODEL
                or row.get("effort") != EFFORT
                or row.get("agents") != runtime.get("agents")
                or row.get("protected_text_changes") != 0
            ):
                raise TerminalizationError(f"ledger review/runtime binding invalid: {number}")
    return rows, {"valid": True, "entries": len(rows), "last_entry_sha256": previous}


def _aggregate_rows(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    roles: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    for entry in entries:
        roles.append({
            "item_id": entry["item_id"],
            "origin_record_id": entry.get("origin_record_id"),
            "stable_business_key": entry.get("stable_business_key"),
            "source_index": entry["source_index"],
            "roles": entry["roles"],
            "review_provenance": entry.get("import_provenance") or entry.get("review_provenance"),
        })
        parent = dict(entry["parent"])
        parent.update({
            "item_id": entry["item_id"],
            "origin_record_id": entry.get("origin_record_id"),
            "stable_business_key": entry.get("stable_business_key"),
            "source_index": entry["source_index"],
        })
        reviews.append(parent)
    return roles, reviews


def _tsv_bytes(fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter="\t", lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _patch_executor_bytes() -> bytes:
    if PATCH_EXECUTOR_SOURCE.is_symlink() or not PATCH_EXECUTOR_SOURCE.is_file():
        raise TerminalizationError(f"staging patch executor source missing: {PATCH_EXECUTOR_SOURCE}")
    data = PATCH_EXECUTOR_SOURCE.read_bytes()
    if data.startswith(b"\xef\xbb\xbf") or b"\r\n" in data:
        raise TerminalizationError("staging patch executor must be UTF-8/LF without BOM")
    return data


def _derive_stage_generated(entries: list[dict[str, Any]], accepted_count: int, ledger_status: dict[str, Any], accepted_hashes: dict[str, dict[str, Any]]) -> dict[str, bytes]:
    roles, reviews = _aggregate_rows(entries)
    role_data = b"".join(canonical_json_bytes(x) for x in roles)
    review_data = b"".join(canonical_json_bytes(x) for x in reviews)
    manual_fields = [
        "source_index", "batch_number", "item_id", "stable_business_key", "source_path", "source_field",
        "japanese_or_source_original", "old_cn", "current_cn", "parent_verdict", "parent_rationale",
        "role_verdicts", "proposed_candidates", "highest_authority_tier", "authority_evidence",
        "protected_authority_text", "source_job_id", "source_session_id", "review_status",
    ]
    manual_rows: list[dict[str, Any]] = []
    patch_entries: list[tuple[dict[str, Any], str, str]] = []
    rollback_entries: list[dict[str, Any]] = []
    for entry in entries:
        parent = entry["parent"]
        proposals = sorted({str(role.get("proposed_cn")) for role in entry["roles"].values() if isinstance(role.get("proposed_cn"), str) and role.get("proposed_cn")})
        candidate = str(parent.get("suggested_cn") or parent.get("proposed_cn") or "") if parent["verdict"] == "correction" else ""
        if parent["verdict"] != "approved":
            item = entry["source_item"]
            refs = item.get("authority_references") or {}
            provenance = entry.get("import_provenance") or entry.get("review_provenance") or {}
            manual_rows.append({
                "source_index": entry["source_index"],
                "batch_number": (entry["source_index"] - 1) // BATCH_SIZE + 1,
                "item_id": entry["item_id"],
                "stable_business_key": entry.get("stable_business_key", ""),
                "source_path": item.get("source_path", ""),
                "source_field": item.get("source_field", ""),
                "japanese_or_source_original": item.get("japanese_or_source_original", ""),
                "old_cn": item.get("old_cn", ""),
                "current_cn": item.get("current_cn", ""),
                "parent_verdict": parent["verdict"],
                "parent_rationale": parent.get("rationale", ""),
                "role_verdicts": json.dumps(parent.get("role_verdicts", {}), ensure_ascii=False, sort_keys=True),
                "proposed_candidates": json.dumps(proposals or ([candidate] if candidate else []), ensure_ascii=False),
                "highest_authority_tier": refs.get("highest_authority_tier", ""),
                "authority_evidence": refs.get("evidence", ""),
                "protected_authority_text": str(bool(item.get("protected_authority_text"))).lower(),
                "source_job_id": provenance.get("source_v2_job_id") or provenance.get("job_id", ""),
                "source_session_id": provenance.get("source_v2_session_id") or provenance.get("parent_session_id", ""),
                "review_status": "needs-human-review" if parent["verdict"] == "unresolved" else "staged-correction",
            })
        if candidate:
            item = entry["source_item"]
            before = str(item.get("current_cn", ""))
            patch_entries.append((entry, before, candidate))
            rollback_entries.append({
                "item_id": entry["item_id"],
                "stable_business_key": entry.get("stable_business_key"),
                "source_path": item.get("source_path"),
                "source_field": item.get("source_field"),
                "before": before,
                "after": candidate,
                "before_sha256": sha256_bytes(before.encode("utf-8")),
                "after_sha256": sha256_bytes(candidate.encode("utf-8")),
            })
    patch_lines = [
        "# magireco v26 DSV4 v3 low-tier staging patch",
        "# This is not applied to the product tree. Parent-approved corrections only.",
    ]
    for entry, before, after in patch_entries:
        item = entry["source_item"]
        locator = f"{item.get('source_path')}::{item.get('source_key')}::{item.get('source_field')}"
        patch_lines += [f"diff --magireco-key {entry['item_id']} {locator}", f"--- {locator}", f"+++ {locator}", "@@", f"-{before}", f"+{after}"]
    verdict_counts = Counter(x["verdict"] for x in reviews)
    role_counts = {name: dict(Counter(x["roles"][name]["verdict"] for x in roles)) for name in ROLE_NAMES}
    summary = {
        "schema": f"{SCHEMA_PREFIX}-summary/1",
        "accepted_batches": accepted_count,
        "completed_items": len(entries),
        "total_batches": TOTAL_BATCHES,
        "total_items": TOTAL_ITEMS,
        "next_batch": None if accepted_count == TOTAL_BATCHES else accepted_count + 1,
        "parent_verdicts": dict(verdict_counts),
        "role_verdicts": role_counts,
        "manual_review_rows": len(manual_rows),
        "patch_entries": len(patch_entries),
        "rollback_entries": len(rollback_entries),
        "protected_text_changes": 0,
        "source_v2_atomic_history": "failed",
        "source_v2_atomicity_claimed": False,
    }
    result = {
        "role_matrix.jsonl": role_data,
        "review_results.jsonl": review_data,
        "manual_review.tsv": _tsv_bytes(manual_fields, manual_rows),
        "candidate.patch": ("\n".join(patch_lines) + "\n").encode("utf-8"),
        "rollback.json": pretty_json_bytes({"schema": f"{SCHEMA_PREFIX}-rollback/1", "product_tree_writes": False, "entries": rollback_entries}),
        "summary.json": pretty_json_bytes(summary),
    }
    aggregate_hashes = {name: file_record(result[name]) for name in ("role_matrix.jsonl", "review_results.jsonl", "manual_review.tsv", "candidate.patch", "rollback.json", "summary.json")}
    manifest = {
        "schema": f"{SCHEMA_PREFIX}-review-manifest/1",
        "completed_batches": accepted_count,
        "completed_items": len(entries),
        "source_order_verified": True,
        "accepted_batches": accepted_hashes,
        "aggregates": aggregate_hashes,
        "append_only_ledger": ledger_status,
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "network_configuration_writes": False,
    }
    result["review_manifest.json"] = pretty_json_bytes(manifest)
    return result


def _validate_generated(
    snapshot: StageSnapshot,
    entries: list[dict[str, Any]],
    accepted_batches: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    ledger_status: dict[str, Any],
    *,
    accepted_count: int = TOTAL_BATCHES,
    manual_handoff: bool = False,
) -> dict[str, Any]:
    accepted_hashes = {f"batch_{number:03d}.json": snapshot.hashes[f"accepted/batch_{number:03d}.json"] for number in range(1, accepted_count + 1)}
    expected = _derive_stage_generated(entries, accepted_count, ledger_status, accepted_hashes)
    if manual_handoff:
        terminal_summary = parse_json(expected["summary.json"], "derived summary")
        terminal_summary.update({
            "next_batch": None,
            "ds_phase": "closed_manual_handoff",
            "ds_retry_disabled": True,
            "manual_required_items": MANUAL_REQUIRED_ITEMS,
        })
        expected["summary.json"] = pretty_json_bytes(terminal_summary)
    for name in ("role_matrix.jsonl", "review_results.jsonl", "manual_review.tsv", "candidate.patch", "rollback.json", "summary.json"):
        actual = snapshot.raw[f"generated/{name}"]
        if actual != expected[name]:
            raise TerminalizationError(f"generated aggregate differs from accepted source of truth: {name}")
    manifest = parse_json(snapshot.raw["generated/review_manifest.json"], "generated/review_manifest.json")
    expected_manifest = parse_json(expected["review_manifest.json"], "derived review manifest")
    if manual_handoff:
        expected_manifest["aggregates"]["summary.json"] = file_record(expected["summary.json"])
        expected_manifest["manual_handoff"] = {
            "ds_phase": "closed_manual_handoff",
            "ds_retry_disabled": True,
            "manual_required_items": MANUAL_REQUIRED_ITEMS,
            "manual_handoff_manifest_sha256": snapshot.hashes["generated/manual_handoff_manifest.json"]["sha256"],
        }
    # Supervisor lifecycle events can be appended after the aggregate commit.
    # The generated manifest must bind to a valid prefix of the current ledger.
    manifested_ledger = manifest.get("append_only_ledger") or {}
    prefix_count = manifested_ledger.get("entries")
    if not isinstance(prefix_count, int) or not 1 <= prefix_count <= len(ledger_rows):
        raise TerminalizationError("generated manifest ledger prefix invalid")
    if manifested_ledger != {
        "valid": True,
        "entries": prefix_count,
        "last_entry_sha256": ledger_rows[prefix_count - 1]["entry_sha256"],
    }:
        raise TerminalizationError("generated manifest ledger prefix hash invalid")
    expected_manifest["append_only_ledger"] = manifested_ledger
    if manifest != expected_manifest:
        raise TerminalizationError("generated review manifest invalid")
    checkpoint = parse_json(snapshot.raw["generated/checkpoint.json"], "generated/checkpoint.json")
    expected_checkpoint = {
        "schema": f"{SCHEMA_PREFIX}-checkpoint/1",
        "state": "closed-manual-handoff" if manual_handoff else "complete",
        "last_completed_batch": accepted_count,
        "completed_items": len(entries),
        "total_batches": TOTAL_BATCHES,
        "total_items": TOTAL_ITEMS,
        "next_batch": None,
        "review_manifest_sha256": snapshot.hashes["generated/review_manifest.json"]["sha256"],
    }
    if manual_handoff:
        reviewed_human_required = sum(entry["parent"]["verdict"] != "approved" for entry in entries)
        expected_checkpoint.update({
            "ds_phase": "closed_manual_handoff",
            "ds_retry_disabled": True,
            "manual_required_items": MANUAL_REQUIRED_ITEMS,
            "manual_required_batches": TOTAL_BATCHES - MANUAL_HANDOFF_BATCHES,
            "manual_required_unreviewed": MANUAL_REQUIRED_ITEMS,
            "reviewed_human_decision_required": reviewed_human_required,
            "human_decision_required": reviewed_human_required + MANUAL_REQUIRED_ITEMS,
            "manual_handoff_manifest_sha256": snapshot.hashes["generated/manual_handoff_manifest.json"]["sha256"],
        })
    for key, value in expected_checkpoint.items():
        if checkpoint.get(key) != value:
            raise TerminalizationError(f"terminal generated checkpoint invalid: {key}")
    if not isinstance(checkpoint.get("updated_at"), str) or not checkpoint["updated_at"]:
        raise TerminalizationError("generated checkpoint updated_at missing")
    if set(checkpoint) != set(expected_checkpoint) | {"updated_at"}:
        raise TerminalizationError("generated checkpoint has unexpected fields")
    heartbeat = parse_json(snapshot.raw["generated/heartbeat.json"], "generated/heartbeat.json")
    expected_heartbeat = {
        "schema": f"{SCHEMA_PREFIX}-heartbeat/1",
        "status": "closed-manual-handoff" if manual_handoff else "complete",
        "last_completed_batch": accepted_count,
        "completed_items": len(entries),
        "next_batch": None,
    }
    if manual_handoff:
        reviewed_human_required = sum(entry["parent"]["verdict"] != "approved" for entry in entries)
        expected_heartbeat.update({
            "ds_phase": "closed_manual_handoff",
            "manual_required_items": MANUAL_REQUIRED_ITEMS,
            "manual_required_unreviewed": MANUAL_REQUIRED_ITEMS,
            "human_decision_required": reviewed_human_required + MANUAL_REQUIRED_ITEMS,
            "ds_retry_disabled": True,
        })
    for key, value in expected_heartbeat.items():
        if heartbeat.get(key) != value:
            raise TerminalizationError(f"terminal generated heartbeat invalid: {key}")
    if not isinstance(heartbeat.get("updated_at"), str) or not heartbeat["updated_at"]:
        raise TerminalizationError("generated heartbeat updated_at missing")
    if set(heartbeat) != set(expected_heartbeat) | {"updated_at"}:
        raise TerminalizationError("generated heartbeat has unexpected fields")
    return {
        "terminal_checkpoint": True,
        "terminal_mode": "manual_handoff" if manual_handoff else "full_ds_review",
        "generated_aggregates_exact": True,
        "generated_manifest_ledger_prefix_entries": prefix_count,
        "current_ledger_entries": ledger_status["entries"],
    }


def validate_snapshot(snapshot: StageSnapshot, expected_parent_session: str = DEFAULT_PARENT_SESSION) -> ValidatedStage:
    source_lock = _validate_source_lock(snapshot)
    exception_evidence = _validate_exception_evidence(snapshot, expected_parent_session)
    queue_batches, _ = _validate_queue(snapshot, source_lock)
    accepted_batches, entries = _validate_accepted(snapshot, source_lock, queue_batches, expected_parent_session)
    ledger, ledger_status = _validate_ledger(snapshot, accepted_batches, expected_parent_session)
    generated_validation = _validate_generated(snapshot, entries, accepted_batches, ledger, ledger_status)
    verdict_counts: Counter[str] = Counter(entry["parent"]["verdict"] for entry in entries)
    role_counts = {name: Counter(entry["roles"][name]["verdict"] for entry in entries) for name in ROLE_NAMES}
    corrections = [entry for entry in entries if entry["parent"]["verdict"] == "correction"]
    unresolved = [entry for entry in entries if entry["parent"]["verdict"] == "unresolved"]
    if sum(verdict_counts.values()) != TOTAL_ITEMS:
        raise TerminalizationError("parent verdict counts do not close")
    if any(sum(role_counts[name].values()) != TOTAL_ITEMS for name in ROLE_NAMES):
        raise TerminalizationError("role verdict counts do not close")
    return ValidatedStage(
        snapshot=snapshot,
        source_lock=source_lock,
        queue_batches=queue_batches,
        accepted_batches=accepted_batches,
        entries=entries,
        ledger=ledger,
        ledger_status=ledger_status,
        verdict_counts=verdict_counts,
        role_counts=role_counts,
        imported_session_id=source_lock["source_session_id"],
        parent_session_id=expected_parent_session,
        corrections=corrections,
        unresolved=unresolved,
        generated_validation=generated_validation,
        exception_evidence=exception_evidence,
    )


MANUAL_REQUIRED_SOURCE_FIELDS = [
    "source_index", "batch_number", "item_id", "stable_business_key", "source_path", "source_key",
    "source_field", "review_kind", "allowed_action", "japanese_or_source_original", "old_cn", "current_cn",
    "protected_authority_text", "product_write_allowed", "highest_authority_tier", "authority_status",
    "authority_evidence", "official_cn", "wiki_cn", "confirmed_human_cn", "ds_review_status", "review_status",
    "allowed_human_decisions", "human_decision", "reviewer", "reviewed_at", "final_value", "human_notes",
    "source_text_sha256", "old_cn_sha256", "source_item_sha256",
]


def _expected_manual_source_rows(queue_batches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch in queue_batches[MANUAL_HANDOFF_BATCHES:]:
        number = batch["batch_number"]
        start = batch["item_range"]["start"]
        for offset, item in enumerate(batch["items"]):
            refs = item.get("authority_references") or {}
            protected = bool(item.get("protected_authority_text"))
            rows.append({
                "schema": f"{SCHEMA_PREFIX}-manual-required-item/1",
                "source_index": start + offset,
                "batch_number": number,
                "item_id": item["item_id"],
                "stable_business_key": item.get("stable_business_key", ""),
                "source_path": item.get("source_path", ""),
                "source_key": item.get("source_key", ""),
                "source_field": item.get("source_field", ""),
                "review_kind": item.get("review_kind", ""),
                "allowed_action": item.get("allowed_action", ""),
                "japanese_or_source_original": item.get("japanese_or_source_original", ""),
                "old_cn": item.get("old_cn", ""),
                "current_cn": item.get("current_cn", ""),
                "protected_authority_text": protected,
                "product_write_allowed": bool(item.get("product_write_allowed")),
                "highest_authority_tier": refs.get("highest_authority_tier", ""),
                "authority_status": refs.get("authority_status", ""),
                "authority_evidence": refs.get("evidence", ""),
                "official_cn": refs.get("official_cn", ""),
                "wiki_cn": refs.get("wiki_cn", ""),
                "confirmed_human_cn": refs.get("confirmed_human_cn", ""),
                "authority_references": refs,
                "ds_review_status": "not-reviewed-ds",
                "review_status": "manual-required",
                "human_decision": "",
                "reviewer": "",
                "reviewed_at": "",
                "timestamp": "",
                "final_value": "",
                "human_notes": "",
                "ds_retry_disabled": True,
                "source_item_sha256": sha256_bytes(canonical_json_bytes(item)),
                "source_item": item,
            })
    return rows


def _manual_source_tsv_bytes(rows: list[dict[str, Any]]) -> bytes:
    projected: list[dict[str, Any]] = []
    for row in rows:
        item = row.get("source_item") or {}
        protected = bool(row["protected_authority_text"])
        projected.append({
            **{key: row.get(key, "") for key in MANUAL_REQUIRED_SOURCE_FIELDS},
            "protected_authority_text": str(protected).lower(),
            "product_write_allowed": str(row["product_write_allowed"]).lower(),
            "allowed_human_decisions": json.dumps(
                ["keep-authority", "unresolved"] if protected else ["approve-current", "revise", "unresolved"],
                ensure_ascii=False, separators=(",", ":"),
            ),
            "source_text_sha256": item.get("source_text_sha256", ""),
            "old_cn_sha256": item.get("old_cn_sha256", ""),
        })
    return _tsv_bytes(MANUAL_REQUIRED_SOURCE_FIELDS, projected)


SEALED_MANUAL_REQUIRED_FIELDS = [
    "source_index", "batch_number", "item_id", "stable_business_key", "source_path", "source_key",
    "source_field", "japanese_or_source_original", "old_cn", "current_cn", "review_kind",
    "allowed_action", "protected_authority_text", "product_write_allowed", "authority_status",
    "highest_authority_tier", "authority_evidence", "official_cn", "wiki_cn", "confirmed_human_cn",
    "ds_review_status", "review_status", "human_decision", "reviewer", "reviewed_at", "timestamp",
    "final_value", "human_notes", "source_item_sha256",
]


def _sealed_manual_source_tsv_bytes(rows: list[dict[str, Any]]) -> bytes:
    return _tsv_bytes(SEALED_MANUAL_REQUIRED_FIELDS, ({key: row.get(key, "") for key in SEALED_MANUAL_REQUIRED_FIELDS} for row in rows))


def _validate_manual_source_documents(
    snapshot: StageSnapshot,
    queue_batches: list[dict[str, Any]],
    reviewed_human_required: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected = _expected_manual_source_rows(queue_batches)
    actual = parse_jsonl(snapshot.raw["generated/manual_required.jsonl"], "generated/manual_required.jsonl")
    if actual != expected:
        raise TerminalizationError("manual-required JSONL does not exactly derive from immutable queue batches 75-96")
    if snapshot.raw["generated/manual_required.tsv"] != _sealed_manual_source_tsv_bytes(expected):
        raise TerminalizationError("manual-required TSV does not exactly derive from immutable queue batches 75-96")
    all_ids = [item_id for batch in queue_batches for item_id in batch["item_ids"]]
    accepted_ids = all_ids[:MANUAL_HANDOFF_ITEMS]
    manual_ids = [row["item_id"] for row in expected]
    if (
        len(expected) != MANUAL_REQUIRED_ITEMS
        or [row["source_index"] for row in expected] != list(range(MANUAL_HANDOFF_ITEMS + 1, TOTAL_ITEMS + 1))
        or len(set(manual_ids)) != MANUAL_REQUIRED_ITEMS
        or set(accepted_ids).intersection(manual_ids)
        or set(accepted_ids).union(manual_ids) != set(all_ids)
    ):
        raise TerminalizationError("manual-required inventory has loss, duplication, overlap, or order drift")
    classification = Counter(
        "protected_historical_comparison_only" if row["protected_authority_text"] else "current_low_tier"
        for row in expected
    )
    if classification != Counter({
        "current_low_tier": MANUAL_CURRENT_LOW_TIER_ITEMS,
        "protected_historical_comparison_only": MANUAL_PROTECTED_HISTORICAL_ITEMS,
    }):
        raise TerminalizationError("manual-required current/history classification does not match the frozen 176/264 inventory")
    current_paths = Counter(row["source_path"] for row in expected if not row["protected_authority_text"])
    if current_paths != Counter({"i18n/frontend-strings.tsv": 167, "i18n/overrides.tsv": 9}):
        raise TerminalizationError("manual-required current-low-tier source split does not match frozen inventory")
    for row in expected:
        if row["product_write_allowed"] is not False:
            raise TerminalizationError(f"manual-required item unexpectedly permits product write: {row['item_id']}")
        if row["protected_authority_text"]:
            if row["review_kind"] != "historical-pass8-llm-comparison-only" or row["allowed_action"] != "review-history-only":
                raise TerminalizationError(f"protected manual item is not history-only: {row['item_id']}")
        elif row["review_kind"] != "current-low-tier-translation-review" or row["allowed_action"] != "review-and-stage-low-tier-only":
            raise TerminalizationError(f"current manual item has invalid low-tier action: {row['item_id']}")
    coverage = {
        "accepted_item_ids_sha256": sha256_bytes(canonical_json_bytes(accepted_ids)),
        "manual_item_ids_sha256": sha256_bytes(canonical_json_bytes(manual_ids)),
        "full_item_ids_sha256": sha256_bytes(canonical_json_bytes(all_ids)),
        "manual_first_item_id": manual_ids[0],
        "manual_last_item_id": manual_ids[-1],
        "manual_source_index_range": {"start": MANUAL_HANDOFF_ITEMS + 1, "end": TOTAL_ITEMS},
        "manual_batch_range": {"start": MANUAL_HANDOFF_BATCHES + 1, "end": TOTAL_BATCHES, "count": TOTAL_BATCHES - MANUAL_HANDOFF_BATCHES},
        "manual_required_unreviewed": MANUAL_REQUIRED_ITEMS,
        "manual_unreviewed_classes": {
            "current_low_tier": MANUAL_CURRENT_LOW_TIER_ITEMS,
            "current_low_tier_by_source_path": {"i18n/frontend-strings.tsv": 167, "i18n/overrides.tsv": 9},
            "historical_pass8_comparison_only": MANUAL_PROTECTED_HISTORICAL_ITEMS,
        },
        "accepted_manual_overlap": 0,
        "inventory_missing": 0,
    }
    manifest = parse_json(snapshot.raw["generated/manual_handoff_manifest.json"], "generated/manual_handoff_manifest.json")
    expected_manifest = {
        "schema": f"{SCHEMA_PREFIX}-manual-handoff-manifest/1",
        "terminal_mode": "manual_handoff",
        "ds_phase": "closed_manual_handoff",
        "accepted_batches": MANUAL_HANDOFF_BATCHES,
        "ds_reviewed_items": MANUAL_HANDOFF_ITEMS,
        "manual_required_items": MANUAL_REQUIRED_ITEMS,
        "manual_required_batches": TOTAL_BATCHES - MANUAL_HANDOFF_BATCHES,
        "manual_required_unreviewed": MANUAL_REQUIRED_ITEMS,
        "reviewed_human_decision_required": reviewed_human_required,
        "human_decision_required": reviewed_human_required + MANUAL_REQUIRED_ITEMS,
        "manual_batch_range": {"start": MANUAL_HANDOFF_BATCHES + 1, "end": TOTAL_BATCHES},
        "ds_retry_disabled": True,
        "queue_coverage": coverage,
        "files": {
            "manual_required.jsonl": snapshot.hashes["generated/manual_required.jsonl"],
            "manual_required.tsv": snapshot.hashes["generated/manual_required.tsv"],
        },
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "network_configuration_writes": False,
        "decision_contract": {
            "current_allowed": ["approve-current", "revise", "unresolved"],
            "history_protected_allowed": ["keep-authority", "unresolved"],
            "nonempty_decision_requires_reviewer_and_iso_timestamp": True,
            "unresolved_apply_allowed": False,
            "validation": {
                "blank": MANUAL_REQUIRED_ITEMS,
                "decided": 0,
                "rows": MANUAL_REQUIRED_ITEMS,
                "unresolved": 0,
                "unresolved_apply_allowed": False,
            },
        },
    }
    if manifest != expected_manifest:
        raise TerminalizationError("manual-handoff manifest is not the exact queue-derived contract")
    return expected, coverage


def _validate_manual_terminal_documents(
    snapshot: StageSnapshot,
    coverage: dict[str, Any],
    ledger_status: dict[str, Any],
    reviewed_human_required: int,
) -> None:
    handoff_hash = snapshot.hashes["generated/manual_handoff_manifest.json"]
    manual_jsonl_hash = snapshot.hashes["generated/manual_required.jsonl"]
    manual_tsv_hash = snapshot.hashes["generated/manual_required.tsv"]
    pipeline = parse_json(snapshot.raw["pipeline_verification.json"], "pipeline_verification.json")
    job = parse_json(snapshot.raw["job_manifest_v3.json"], "job_manifest_v3.json")
    required = {
        "terminal_mode": "manual_handoff",
        "ds_phase": "closed_manual_handoff",
        "ds_reviewed_items": MANUAL_HANDOFF_ITEMS,
        "manual_required_items": MANUAL_REQUIRED_ITEMS,
        "manual_required_unreviewed": MANUAL_REQUIRED_ITEMS,
        "human_decision_required": reviewed_human_required + MANUAL_REQUIRED_ITEMS,
        "next_batch": None,
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "network_configuration_writes": False,
    }
    for key, value in required.items():
        if pipeline.get(key) != value:
            raise TerminalizationError(f"pipeline manual-handoff field invalid: {key}")
    if pipeline.get("ledger") != ledger_status:
        raise TerminalizationError("pipeline does not bind the current terminal ledger")
    state_hash = snapshot.hashes["generated/manual_handoff_state.json"]
    for label, document in (("pipeline", pipeline), ("job", job)):
        pipeline_files = document.get("pipeline_files") or {}
        if pipeline_files.get("generated/manual_handoff_state.json") != state_hash:
            raise TerminalizationError(f"{label} does not bind manual-handoff state bytes")
        if pipeline_files.get("generated/manual_handoff_manifest.json") != handoff_hash:
            raise TerminalizationError(f"{label} does not bind current manual-handoff manifest bytes")
    terminal_gate = pipeline.get("terminal_gate") or {}
    if terminal_gate != {
        "required_accepted_batches": MANUAL_HANDOFF_BATCHES,
        "required_ds_reviewed_items": MANUAL_HANDOFF_ITEMS,
        "manual_required_items": MANUAL_REQUIRED_ITEMS,
        "accepted_batches": MANUAL_HANDOFF_BATCHES,
        "accepted_items": MANUAL_HANDOFF_ITEMS,
        "next_batch": None,
    }:
        raise TerminalizationError("pipeline manual-handoff terminal gate invalid")
    manual_contract = pipeline.get("manual_handoff") or {}
    if (
        manual_contract.get("accepted_batches") != MANUAL_HANDOFF_BATCHES
        or manual_contract.get("ds_reviewed_items") != MANUAL_HANDOFF_ITEMS
        or manual_contract.get("manual_required_items") != MANUAL_REQUIRED_ITEMS
        or manual_contract.get("manual_required_unreviewed") != MANUAL_REQUIRED_ITEMS
        or manual_contract.get("reviewed_human_decision_required") != reviewed_human_required
        or manual_contract.get("human_decision_required") != reviewed_human_required + MANUAL_REQUIRED_ITEMS
        or manual_contract.get("manual_required_batches") != {"start": 75, "end": 96, "count": 22}
        or manual_contract.get("manual_queue") != {"path": "generated/manual_required.jsonl", **manual_jsonl_hash}
        or manual_contract.get("manual_table") != {"path": "generated/manual_required.tsv", **manual_tsv_hash}
        or manual_contract.get("manifest") != {"path": "generated/manual_handoff_manifest.json", **handoff_hash}
        or manual_contract.get("queue_coverage") != coverage
        or any(manual_contract.get(key) != value for key, value in {
            "protected_text_changes": 0, "product_tree_writes": False, "network_configuration_writes": False,
        }.items())
    ):
        raise TerminalizationError("pipeline manual-handoff evidence binding invalid")
    if job.get("terminal_mode") != "manual_handoff" or job.get("ds_phase") != "closed_manual_handoff":
        raise TerminalizationError("job manifest manual-handoff mode invalid")
    progress = job.get("review_progress") or {}
    if progress != {"completed_items": MANUAL_HANDOFF_ITEMS, "completed_batches": MANUAL_HANDOFF_BATCHES, "next_batch": None}:
        raise TerminalizationError("job manifest review progress invalid")
    if job.get("manual_handoff") != manual_contract:
        raise TerminalizationError("job/pipeline manual-handoff contracts differ")
    if job.get("pipeline_verification") != snapshot.hashes["pipeline_verification.json"]:
        raise TerminalizationError("job manifest does not bind pipeline bytes")


def _validate_manual_handoff_state(
    snapshot: StageSnapshot,
    ledger: list[dict[str, Any]],
    reviewed_human_required: int,
) -> None:
    """Bind the current state bytes to the current manifest and final ledger revision."""
    state = parse_json(snapshot.raw["generated/manual_handoff_state.json"], "generated/manual_handoff_state.json")
    revision = ledger[-1]
    expected = {
        "schema": f"{SCHEMA_PREFIX}-manual-handoff-state/1",
        "terminal_mode": "manual_handoff",
        "ds_phase": "closed_manual_handoff",
        "accepted_batches": MANUAL_HANDOFF_BATCHES,
        "ds_reviewed_items": MANUAL_HANDOFF_ITEMS,
        "manual_required_items": MANUAL_REQUIRED_ITEMS,
        "reviewed_human_decision_required": reviewed_human_required,
        "human_decision_required": reviewed_human_required + MANUAL_REQUIRED_ITEMS,
        "ds_retry_disabled": True,
        "manual_handoff_manifest_sha256": snapshot.hashes["generated/manual_handoff_manifest.json"]["sha256"],
        "ledger_entry_sha256": revision["entry_sha256"],
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "network_configuration_writes": False,
        "closed_at": revision["timestamp"],
    }
    if state != expected:
        raise TerminalizationError("manual-handoff state is not the exact current manifest/ledger contract")


@dataclass
class ManualHandoffStage:
    validated: ValidatedStage
    manual_items: list[dict[str, Any]]
    queue_coverage: dict[str, Any]


def validate_manual_handoff_snapshot(snapshot: StageSnapshot, expected_parent_session: str = DEFAULT_PARENT_SESSION) -> ManualHandoffStage:
    source_lock = _validate_source_lock(snapshot)
    exception_evidence = _validate_exception_evidence(snapshot, expected_parent_session)
    queue_batches, _ = _validate_queue(snapshot, source_lock)
    accepted_batches, entries = _validate_accepted(
        snapshot, source_lock, queue_batches, expected_parent_session, accepted_count=MANUAL_HANDOFF_BATCHES,
    )
    ledger, ledger_status = _validate_ledger(
        snapshot, accepted_batches, expected_parent_session, accepted_count=MANUAL_HANDOFF_BATCHES,
    )
    reviewed_human_required = sum(entry["parent"]["verdict"] != "approved" for entry in entries)
    manual_items, coverage = _validate_manual_source_documents(snapshot, queue_batches, reviewed_human_required)
    handoff_events = [row for row in ledger if row.get("type") == "ds_phase_closed_manual_handoff"]
    revision_events = [row for row in ledger if row.get("type") == "manual_handoff_metadata_revision"]
    if (
        len(handoff_events) != 1
        or len(revision_events) != 1
        or handoff_events[0] != ledger[-2]
        or revision_events[0] != ledger[-1]
        or handoff_events[0].get("sequence") != 107
        or revision_events[0].get("sequence") != 108
    ):
        raise TerminalizationError("ledger must end with seq107 closure and seq108 metadata revision")
    closure, revision = handoff_events[0], revision_events[0]
    common_event = {
        "terminal_mode": "manual_handoff",
        "accepted_batches": MANUAL_HANDOFF_BATCHES,
        "ds_reviewed_items": MANUAL_HANDOFF_ITEMS,
        "manual_required_items": MANUAL_REQUIRED_ITEMS,
        "manual_required_unreviewed": MANUAL_REQUIRED_ITEMS,
        "reviewed_human_decision_required": reviewed_human_required,
        "human_decision_required": reviewed_human_required + MANUAL_REQUIRED_ITEMS,
        "manual_batch_range": {"start": 75, "end": 96},
        "ds_retry_disabled": True,
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "network_configuration_writes": False,
    }
    for label, event in (("closure", closure), ("revision", revision)):
        for key, value in common_event.items():
            if event.get(key) != value:
                raise TerminalizationError(f"manual-handoff {label} ledger event invalid: {key}")
    current_manifest_hash = snapshot.hashes["generated/manual_handoff_manifest.json"]["sha256"]
    superseded_hash = _require_hash(closure.get("manual_handoff_manifest_sha256"), "seq107 closure manifest")
    if revision.get("manual_handoff_manifest_sha256") != current_manifest_hash:
        raise TerminalizationError("manual-handoff metadata revision does not bind current manifest")
    if revision.get("supersedes_manual_handoff_manifest_sha256") != superseded_hash:
        raise TerminalizationError("manual-handoff metadata revision does not supersede seq107 manifest")
    _validate_manual_handoff_state(snapshot, ledger, reviewed_human_required)
    generated_validation = _validate_generated(
        snapshot, entries, accepted_batches, ledger, ledger_status,
        accepted_count=MANUAL_HANDOFF_BATCHES, manual_handoff=True,
    )
    _validate_manual_terminal_documents(snapshot, coverage, ledger_status, reviewed_human_required)
    verdict_counts: Counter[str] = Counter(entry["parent"]["verdict"] for entry in entries)
    role_counts = {name: Counter(entry["roles"][name]["verdict"] for entry in entries) for name in ROLE_NAMES}
    if sum(verdict_counts.values()) != MANUAL_HANDOFF_ITEMS:
        raise TerminalizationError("DS-reviewed parent verdict counts do not close")
    validated = ValidatedStage(
        snapshot=snapshot, source_lock=source_lock, queue_batches=queue_batches,
        accepted_batches=accepted_batches, entries=entries, ledger=ledger, ledger_status=ledger_status,
        verdict_counts=verdict_counts, role_counts=role_counts,
        imported_session_id=source_lock["source_session_id"], parent_session_id=expected_parent_session,
        corrections=[entry for entry in entries if entry["parent"]["verdict"] == "correction"],
        unresolved=[entry for entry in entries if entry["parent"]["verdict"] == "unresolved"],
        generated_validation=generated_validation, exception_evidence=exception_evidence,
    )
    return ManualHandoffStage(validated=validated, manual_items=manual_items, queue_coverage=coverage)


FULL_REVIEW_FIELDS = [
    "source_index", "batch_number", "item_id", "origin_record_id", "stable_business_key", "review_kind",
    "allowed_action", "source_path", "source_key", "source_field", "japanese_or_source_original", "old_cn",
    "current_cn", "parent_verdict", "suggested_cn", "parent_rationale", "role_verdicts", "role_details",
    "protected_authority_text", "product_write_allowed", "highest_authority_tier", "authority_status",
    "authority_evidence", "official_cn", "wiki_cn", "confirmed_human_cn", "model", "effort", "session_id",
    "job_id", "agents", "source_text_sha256", "old_cn_sha256", "previous_low_standard_ds_result",
]

PROVENANCE_FIELDS = [
    "source_index", "item_id", "origin_record_id", "stable_business_key", "source_path", "source_key", "source_field",
    "source_text_sha256", "old_cn_sha256", "source_tier", "source_author", "source_stage", "source_batch",
    "source_bucket", "machine_translated", "review_kind", "allowed_action", "protected_authority_text",
    "highest_authority_tier", "authority_status", "authority_evidence", "official_cn", "wiki_cn",
    "confirmed_human_cn", "parent_verdict", "model", "effort", "session_id", "job_id", "agents",
    "review_provenance", "previous_low_standard_ds_result",
]

HUMAN_FIELDS = [
    "source_index", "batch_number", "item_id", "stable_business_key", "source_path", "source_key", "source_field",
    "review_kind", "allowed_action", "japanese_or_source_original", "old_cn", "current_cn", "suggested_cn",
    "parent_verdict", "parent_rationale", "role_verdicts", "role_details", "highest_authority_tier",
    "authority_status", "authority_evidence", "official_cn", "wiki_cn", "confirmed_human_cn",
    "protected_authority_text", "product_write_allowed", "allowed_human_decisions", "review_status",
    "human_decision", "reviewer", "timestamp", "final_value", "human_revision", "human_notes",
]


def _entry_runtime(entry: dict[str, Any]) -> dict[str, Any]:
    provenance = entry.get("import_provenance") or entry.get("review_provenance") or {}
    return {
        "model": provenance.get("source_v2_model") or provenance.get("model") or MODEL,
        "effort": provenance.get("source_v2_effort") or provenance.get("effort") or EFFORT,
        "session_id": provenance.get("source_v2_session_id") or provenance.get("parent_session_id", ""),
        "job_id": provenance.get("source_v2_job_id") or provenance.get("job_id", ""),
        "agents": provenance.get("source_v2_role_agents") or provenance.get("agents") or {},
        "review_provenance": provenance,
    }


def _output_rows(validated: ValidatedStage) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    full: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    human: list[dict[str, Any]] = []
    nonapproved_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []
    for entry in validated.entries:
        item = entry["source_item"]
        parent = entry["parent"]
        refs = item.get("authority_references") or {}
        source_prov = item.get("provenance") or {}
        runtime = _entry_runtime(entry)
        suggested = str(parent.get("suggested_cn") or parent.get("proposed_cn") or "") if parent["verdict"] == "correction" else ""
        common = {
            "source_index": entry["source_index"],
            "batch_number": next(b["batch_number"] for b in validated.queue_batches if b["item_range"]["start"] <= entry["source_index"] <= b["item_range"]["end"]),
            "item_id": entry["item_id"],
            "origin_record_id": entry.get("origin_record_id", ""),
            "stable_business_key": entry.get("stable_business_key", ""),
            "review_kind": item.get("review_kind", ""),
            "allowed_action": item.get("allowed_action", ""),
            "source_path": item.get("source_path", ""),
            "source_key": item.get("source_key", ""),
            "source_field": item.get("source_field", ""),
            "japanese_or_source_original": item.get("japanese_or_source_original", ""),
            "old_cn": item.get("old_cn", ""),
            "current_cn": item.get("current_cn", ""),
            "parent_verdict": parent["verdict"],
            "suggested_cn": suggested,
            "parent_rationale": parent.get("rationale", ""),
            "role_verdicts": json.dumps(parent.get("role_verdicts", {}), ensure_ascii=False, sort_keys=True),
            "role_details": json.dumps(entry["roles"], ensure_ascii=False, sort_keys=True),
            "protected_authority_text": str(bool(item.get("protected_authority_text"))).lower(),
            "product_write_allowed": str(bool(item.get("product_write_allowed"))).lower(),
            "highest_authority_tier": refs.get("highest_authority_tier", ""),
            "authority_status": refs.get("authority_status", ""),
            "authority_evidence": refs.get("evidence", ""),
            "official_cn": refs.get("official_cn", ""),
            "wiki_cn": refs.get("wiki_cn", ""),
            "confirmed_human_cn": refs.get("confirmed_human_cn", ""),
            "model": runtime["model"],
            "effort": runtime["effort"],
            "session_id": runtime["session_id"],
            "job_id": runtime["job_id"],
            "agents": json.dumps(runtime["agents"], ensure_ascii=False, sort_keys=True),
            "source_text_sha256": item.get("source_text_sha256", ""),
            "old_cn_sha256": item.get("old_cn_sha256", ""),
            "previous_low_standard_ds_result": json.dumps(item.get("previous_low_standard_ds_result"), ensure_ascii=False, sort_keys=True),
        }
        full.append(common)
        provenance_rows.append({
            **common,
            "source_tier": source_prov.get("source_tier", ""),
            "source_author": source_prov.get("source_author", ""),
            "source_stage": source_prov.get("source_stage", ""),
            "source_batch": source_prov.get("source_batch", ""),
            "source_bucket": source_prov.get("source_bucket", ""),
            "machine_translated": source_prov.get("machine_translated", ""),
            "review_provenance": json.dumps(runtime["review_provenance"], ensure_ascii=False, sort_keys=True),
        })
        status = {
            "approved": "ds-approved-human-unreviewed",
            "correction": "staged-correction-needs-human-decision",
            "unresolved": "needs-human-review",
        }[parent["verdict"]]
        row = {
            **common,
            "allowed_human_decisions": json.dumps(
                ["keep-authority", "unresolved"]
                if item.get("protected_authority_text")
                else ["approve-current", "revise", "unresolved"],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "review_status": status,
            "human_decision": "",
            "reviewer": "",
            "timestamp": "",
            "final_value": "",
            "human_revision": "",
            "human_notes": "",
        }
        human.append(row)
        if parent["verdict"] != "approved":
            nonapproved_rows.append(row)
        if parent["verdict"] == "unresolved":
            unresolved_rows.append(row)
    return full, provenance_rows, human, nonapproved_rows, unresolved_rows


def _manual_output_rows(manual_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    full: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    human: list[dict[str, Any]] = []
    for record in manual_items:
        item = record["source_item"]
        refs = item.get("authority_references") or {}
        source_prov = item.get("provenance") or {}
        common = {
            "source_index": record["source_index"],
            "batch_number": record["batch_number"],
            "item_id": record["item_id"],
            "origin_record_id": item.get("origin_record_id", ""),
            "stable_business_key": item.get("stable_business_key", ""),
            "review_kind": item.get("review_kind", ""),
            "allowed_action": item.get("allowed_action", ""),
            "source_path": item.get("source_path", ""),
            "source_key": item.get("source_key", ""),
            "source_field": item.get("source_field", ""),
            "japanese_or_source_original": item.get("japanese_or_source_original", ""),
            "old_cn": item.get("old_cn", ""),
            "current_cn": item.get("current_cn", ""),
            "parent_verdict": "manual-required",
            "suggested_cn": "",
            "parent_rationale": "DeepSeek review closed after accepted batch 74; independent human translation/review is required.",
            "role_verdicts": "{}",
            "role_details": "{}",
            "protected_authority_text": str(bool(item.get("protected_authority_text"))).lower(),
            "product_write_allowed": str(bool(item.get("product_write_allowed"))).lower(),
            "highest_authority_tier": refs.get("highest_authority_tier", ""),
            "authority_status": refs.get("authority_status", ""),
            "authority_evidence": refs.get("evidence", ""),
            "official_cn": refs.get("official_cn", ""),
            "wiki_cn": refs.get("wiki_cn", ""),
            "confirmed_human_cn": refs.get("confirmed_human_cn", ""),
            "model": "",
            "effort": "",
            "session_id": "",
            "job_id": "",
            "agents": "{}",
            "source_text_sha256": item.get("source_text_sha256", ""),
            "old_cn_sha256": item.get("old_cn_sha256", ""),
            "previous_low_standard_ds_result": json.dumps(item.get("previous_low_standard_ds_result"), ensure_ascii=False, sort_keys=True),
        }
        full.append(common)
        provenance_rows.append({
            **common,
            "source_tier": source_prov.get("source_tier", ""),
            "source_author": source_prov.get("source_author", ""),
            "source_stage": source_prov.get("source_stage", ""),
            "source_batch": source_prov.get("source_batch", ""),
            "source_bucket": source_prov.get("source_bucket", ""),
            "machine_translated": source_prov.get("machine_translated", ""),
            "review_provenance": "{}",
        })
        human.append({
            **common,
            "allowed_human_decisions": json.dumps(
                ["keep-authority", "unresolved"]
                if item.get("protected_authority_text")
                else ["approve-current", "revise", "unresolved"],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "review_status": "manual-required",
            "human_decision": "",
            "reviewer": "",
            "timestamp": "",
            "final_value": "",
            "human_revision": "",
            "human_notes": "",
        })
    return full, provenance_rows, human


def render_artifacts(validated: ValidatedStage, *, reproducible: bool = True) -> dict[str, bytes]:
    full, provenance_rows, human_rows, nonapproved_rows, unresolved_rows = _output_rows(validated)
    roles, reviews = _aggregate_rows(validated.entries)
    corrections: list[dict[str, Any]] = []
    rollbacks: list[dict[str, Any]] = []
    patch_lines = [
        "# magireco v26 DSV4 v3 deterministic terminal correction patch",
        "# STAGING ONLY: product_tree_writes=false; human approval required before any later application.",
    ]
    for entry in validated.corrections:
        item = entry["source_item"]
        before = str(item.get("current_cn", ""))
        after = str(entry["parent"].get("suggested_cn") or entry["parent"].get("proposed_cn"))
        locator = {
            "source_path": item.get("source_path", ""),
            "source_key": item.get("source_key", ""),
            "source_field": item.get("source_field", ""),
            "stable_business_key": entry.get("stable_business_key", ""),
        }
        locator_sha256 = sha256_bytes(canonical_json_bytes(locator))
        record = {
            "source_index": entry["source_index"],
            "item_id": entry["item_id"],
            "locator": locator,
            "locator_sha256": locator_sha256,
            "before": before,
            "after": after,
            "before_sha256": sha256_bytes(before.encode("utf-8")),
            "after_sha256": sha256_bytes(after.encode("utf-8")),
            "parent_rationale": entry["parent"]["rationale"],
            "human_approval_required": True,
            "target_preconditions": {"product_write_allowed": False, "protected_authority_text": False},
        }
        corrections.append(record)
        rollbacks.append({**record, "before": after, "after": before, "before_sha256": record["after_sha256"], "after_sha256": record["before_sha256"]})
        label = f"{locator['source_path']}::{locator['source_key']}::{locator['source_field']}::{locator['stable_business_key']}"
        patch_lines += [
            f"diff --magireco-staging-key {entry['item_id']} {label}",
            f"--- {label}",
            f"+++ {label}",
            f"@@ before-sha256 {record['before_sha256']} after-sha256 {record['after_sha256']} @@",
            f"-{before}",
            f"+{after}",
        ]
    protected_items = sum(bool(entry["source_item"].get("protected_authority_text")) for entry in validated.entries)
    executor_bytes = _patch_executor_bytes()
    executor_record = {"path": PATCH_EXECUTOR_NAME, **file_record(executor_bytes)}
    verification = {
        "schema": f"{TOOL_SCHEMA}-verification",
        "status": "PASS",
        "tool_version": TOOL_VERSION,
        "terminal": {"batches": TOTAL_BATCHES, "items": TOTAL_ITEMS, "unique_item_ids": TOTAL_ITEMS, "source_order": True},
        "runtime": {
            "model": MODEL,
            "effort": EFFORT,
            "parent_session_id_batches_16_96": validated.parent_session_id,
            "imported_source_session_id_batches_1_15": validated.imported_session_id,
            "roles": list(ROLE_NAMES),
            "role_assignments": TOTAL_ITEMS * len(ROLE_NAMES),
        },
        "verdicts": {name: validated.verdict_counts.get(name, 0) for name in sorted(PARENT_VERDICTS)},
        "role_verdicts": {name: dict(sorted(validated.role_counts[name].items())) for name in ROLE_NAMES},
        "protection": {
            "protected_items": protected_items,
            "protected_proposals": 0,
            "protected_text_changes": 0,
            "product_write_allowed_items": 0,
            "product_tree_writes": False,
        },
        "ledger": validated.ledger_status,
        "source_lock": {
            "source_v2_atomic_history": "failed",
            "source_v2_atomicity_claimed": False,
            "items_jsonl": validated.source_lock["files"]["items.jsonl"],
            "declared_files": len(validated.source_lock["files"]),
        },
        "generated": validated.generated_validation,
        "exception_evidence": validated.exception_evidence,
        "reproducibility": {
            "independent_stage_reads": 2,
            "independent_renders": 2,
            "stage_snapshots_identical": reproducible,
            "artifact_bytes_identical": reproducible,
        },
        "input_snapshot_digest": validated.snapshot.digest,
        "human_decision_rows": len(human_rows),
        "nonapproved_review_rows": len(nonapproved_rows),
        "correction_patch_entries": len(corrections),
        "rollback_entries": len(rollbacks),
        "unresolved_entries": len(unresolved_rows),
        "network_configuration_writes": False,
        "staging_patch_executor": executor_record,
    }
    artifacts: dict[str, bytes] = {
        "full_review.tsv": _tsv_bytes(FULL_REVIEW_FIELDS, full),
        "provenance.tsv": _tsv_bytes(PROVENANCE_FIELDS, provenance_rows),
        "human_review.tsv": _tsv_bytes(HUMAN_FIELDS, human_rows),
        "nonapproved_review.tsv": _tsv_bytes(HUMAN_FIELDS, nonapproved_rows),
        "unresolved.tsv": _tsv_bytes(HUMAN_FIELDS, unresolved_rows),
        "review_results.jsonl": b"".join(canonical_json_bytes(x) for x in reviews),
        "role_matrix.jsonl": b"".join(canonical_json_bytes(x) for x in roles),
        "correction_patch.json": pretty_json_bytes({
            "schema": f"{TOOL_SCHEMA}-correction-patch",
            "staging_only": True,
            "product_tree_writes": False,
            "human_approval_required": True,
            "machine_executable": True,
            "executor_mode": "apply",
            "executor": executor_record,
            "target_contract": {
                "marker": ".dsv4-low-tier-staging.json",
                "target": "low_tier_values.json",
                "product_tree_writes": False,
                "protected_text_changes": 0,
            },
            "entries": corrections,
        }),
        "corrections.patch": ("\n".join(patch_lines) + "\n").encode("utf-8"),
        "rollback.json": pretty_json_bytes({
            "schema": f"{TOOL_SCHEMA}-rollback",
            "staging_only": True,
            "product_tree_writes": False,
            "machine_executable": True,
            "executor_mode": "rollback",
            "executor": executor_record,
            "command": "python staging_patch_executor.py --stage-root STAGING_ROOT --target STAGING_ROOT/low_tier_values.json --manifest rollback.json",
            "entries": rollbacks,
        }),
        PATCH_EXECUTOR_NAME: executor_bytes,
        "verification_record.json": pretty_json_bytes(verification),
    }
    core_hashes = {name: file_record(data) for name, data in sorted(artifacts.items())}
    manifest = {
        "schema": f"{TOOL_SCHEMA}-manifest",
        "tool_version": TOOL_VERSION,
        "status": "terminal-verified-staging-only",
        "counts": {
            "batches": TOTAL_BATCHES,
            "items": TOTAL_ITEMS,
            "approved": validated.verdict_counts.get("approved", 0),
            "correction": validated.verdict_counts.get("correction", 0),
            "unresolved": validated.verdict_counts.get("unresolved", 0),
        },
        "input_snapshot_digest": validated.snapshot.digest,
        "input_files": validated.snapshot.hashes,
        "source_lock_declared_files": validated.source_lock["files"],
        "exception_evidence": validated.exception_evidence,
        "outputs": core_hashes,
        "human_decision_contract": {
            "rows": TOTAL_ITEMS,
            "fields": ["human_decision", "reviewer", "timestamp", "final_value"],
            "nonapproved_rows": len(nonapproved_rows),
        },
        "staging_patch_executor": executor_record,
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "network_configuration_writes": False,
    }
    artifacts["manifest.json"] = pretty_json_bytes(manifest)
    sums = {name: sha256_bytes(data) for name, data in sorted(artifacts.items())}
    artifacts["SHA256SUMS.txt"] = "".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items())).encode("ascii")
    return artifacts


def render_manual_handoff_artifacts(stage: ManualHandoffStage, *, reproducible: bool = True) -> dict[str, bytes]:
    """Render a closed DS phase without inventing verdicts for the 440 remaining items."""
    validated = stage.validated
    full, provenance_rows, human_rows, nonapproved_rows, unresolved_rows = _output_rows(validated)
    manual_full, manual_provenance, manual_human = _manual_output_rows(stage.manual_items)
    full += manual_full
    provenance_rows += manual_provenance
    human_rows += manual_human
    nonapproved_rows += manual_human
    roles, reviews = _aggregate_rows(validated.entries)
    corrections: list[dict[str, Any]] = []
    rollbacks: list[dict[str, Any]] = []
    patch_lines = [
        "# magireco v26 DSV4 v3 deterministic manual-handoff correction patch",
        "# STAGING ONLY: only 74 accepted DS batches are represented; human approval is required.",
    ]
    for entry in validated.corrections:
        item = entry["source_item"]
        # A protected/history-only item never becomes writable even if a bad upstream record escaped validation.
        if item.get("protected_authority_text") or item.get("allowed_action") != "review-and-stage-low-tier-only":
            continue
        before = str(item.get("current_cn", ""))
        after = str(entry["parent"].get("suggested_cn") or entry["parent"].get("proposed_cn"))
        locator = {
            "source_path": item.get("source_path", ""), "source_key": item.get("source_key", ""),
            "source_field": item.get("source_field", ""), "stable_business_key": entry.get("stable_business_key", ""),
        }
        record = {
            "source_index": entry["source_index"], "item_id": entry["item_id"], "locator": locator,
            "locator_sha256": sha256_bytes(canonical_json_bytes(locator)), "before": before, "after": after,
            "before_sha256": sha256_bytes(before.encode("utf-8")), "after_sha256": sha256_bytes(after.encode("utf-8")),
            "parent_rationale": entry["parent"]["rationale"], "human_approval_required": True,
            "target_preconditions": {"product_write_allowed": False, "protected_authority_text": False},
        }
        corrections.append(record)
        rollbacks.append({**record, "before": after, "after": before, "before_sha256": record["after_sha256"], "after_sha256": record["before_sha256"]})
        label = f"{locator['source_path']}::{locator['source_key']}::{locator['source_field']}::{locator['stable_business_key']}"
        patch_lines += [
            f"diff --magireco-staging-key {entry['item_id']} {label}", f"--- {label}", f"+++ {label}",
            f"@@ before-sha256 {record['before_sha256']} after-sha256 {record['after_sha256']} @@", f"-{before}", f"+{after}",
        ]
    protected_manual = sum(bool(row["source_item"].get("protected_authority_text")) for row in stage.manual_items)
    writable_manual = sum(not row["source_item"].get("protected_authority_text") for row in stage.manual_items)
    if protected_manual != MANUAL_PROTECTED_HISTORICAL_ITEMS or writable_manual != MANUAL_CURRENT_LOW_TIER_ITEMS:
        raise TerminalizationError("manual-required protection classification does not close")
    executor_bytes = _patch_executor_bytes()
    executor_record = {"path": PATCH_EXECUTOR_NAME, **file_record(executor_bytes)}
    human_decision_required = len(nonapproved_rows)
    verification = {
        "schema": f"{TOOL_SCHEMA}-verification", "status": "PASS", "tool_version": TOOL_VERSION,
        "terminal_mode": "manual_handoff", "ds_phase": "closed_manual_handoff",
        "inventory": {
            "total_items": TOTAL_ITEMS, "ds_reviewed_items": MANUAL_HANDOFF_ITEMS,
            "manual_required_items": MANUAL_REQUIRED_ITEMS, "accepted_batches": MANUAL_HANDOFF_BATCHES,
            "manual_required_batches": TOTAL_BATCHES - MANUAL_HANDOFF_BATCHES,
            "unique_item_ids": TOTAL_ITEMS, "source_order": True, "queue_coverage": stage.queue_coverage,
        },
        "verdicts": {name: validated.verdict_counts.get(name, 0) for name in sorted(PARENT_VERDICTS)},
        "manual_required_classification": {"current_low_tier": writable_manual, "protected_historical_comparison_only": protected_manual},
        "human_decision_required": human_decision_required,
        "ds_nonapproved_human_decision_required": len(nonapproved_rows) - MANUAL_REQUIRED_ITEMS,
        "protection": {"protected_text_changes": 0, "product_tree_writes": False, "product_write_allowed_items": 0},
        "ledger": validated.ledger_status, "source_lock": validated.source_lock["files"],
        "generated": validated.generated_validation, "exception_evidence": validated.exception_evidence,
        "reproducibility": {"independent_stage_reads": 2, "independent_renders": 2, "stage_snapshots_identical": reproducible, "artifact_bytes_identical": reproducible},
        "input_snapshot_digest": validated.snapshot.digest, "network_configuration_writes": False,
        "staging_patch_executor": executor_record,
    }
    artifacts: dict[str, bytes] = {
        "full_review.tsv": _tsv_bytes(FULL_REVIEW_FIELDS, full),
        "provenance.tsv": _tsv_bytes(PROVENANCE_FIELDS, provenance_rows),
        "human_review.tsv": _tsv_bytes(HUMAN_FIELDS, human_rows),
        "manual_required.tsv": _manual_source_tsv_bytes(stage.manual_items),
        "nonapproved_review.tsv": _tsv_bytes(HUMAN_FIELDS, nonapproved_rows),
        "unresolved.tsv": _tsv_bytes(HUMAN_FIELDS, unresolved_rows),
        "review_results.jsonl": b"".join(canonical_json_bytes(x) for x in reviews),
        "role_matrix.jsonl": b"".join(canonical_json_bytes(x) for x in roles),
        "manual_required.jsonl": b"".join(canonical_json_bytes(x) for x in stage.manual_items),
        "correction_patch.json": pretty_json_bytes({
            "schema": f"{TOOL_SCHEMA}-correction-patch", "terminal_mode": "manual_handoff",
            "staging_only": True, "product_tree_writes": False, "human_approval_required": True,
            "machine_executable": True, "executor_mode": "apply", "executor": executor_record,
            "target_contract": {"marker": ".dsv4-low-tier-staging.json", "target": "low_tier_values.json", "product_tree_writes": False, "protected_text_changes": 0},
            "entries": corrections,
        }),
        "corrections.patch": ("\n".join(patch_lines) + "\n").encode("utf-8"),
        "rollback.json": pretty_json_bytes({
            "schema": f"{TOOL_SCHEMA}-rollback", "terminal_mode": "manual_handoff", "staging_only": True,
            "product_tree_writes": False, "machine_executable": True, "executor_mode": "rollback",
            "executor": executor_record,
            "command": "python staging_patch_executor.py --stage-root STAGING_ROOT --target STAGING_ROOT/low_tier_values.json --manifest rollback.json",
            "entries": rollbacks,
        }),
        PATCH_EXECUTOR_NAME: executor_bytes,
        "verification_record.json": pretty_json_bytes(verification),
    }
    core_hashes = {name: file_record(data) for name, data in sorted(artifacts.items())}
    manifest = {
        "schema": f"{TOOL_SCHEMA}-manifest", "tool_version": TOOL_VERSION,
        "status": "terminal-manual-handoff-verified-staging-only", "terminal_mode": "manual_handoff",
        "ds_phase": "closed_manual_handoff",
        "counts": {
            "total_items": TOTAL_ITEMS, "accepted_batches": MANUAL_HANDOFF_BATCHES,
            "ds_reviewed_items": MANUAL_HANDOFF_ITEMS, "manual_required_items": MANUAL_REQUIRED_ITEMS,
            "approved": validated.verdict_counts.get("approved", 0), "correction": validated.verdict_counts.get("correction", 0),
            "unresolved": validated.verdict_counts.get("unresolved", 0), "human_decision_required": human_decision_required,
            "manual_current_low_tier": writable_manual, "manual_protected_historical": protected_manual,
        },
        "input_snapshot_digest": validated.snapshot.digest, "input_files": validated.snapshot.hashes,
        "source_lock_declared_files": validated.source_lock["files"], "queue_coverage": stage.queue_coverage,
        "exception_evidence": validated.exception_evidence, "outputs": core_hashes,
        "human_decision_contract": {"rows": TOTAL_ITEMS, "fields": ["human_decision", "reviewer", "timestamp", "final_value"], "decision_required_rows": human_decision_required},
        "staging_patch_executor": executor_record, "protected_text_changes": 0, "product_tree_writes": False,
        "network_configuration_writes": False,
    }
    artifacts["manifest.json"] = pretty_json_bytes(manifest)
    sums = {name: sha256_bytes(data) for name, data in sorted(artifacts.items())}
    artifacts["SHA256SUMS.txt"] = "".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items())).encode("ascii")
    return artifacts


def _write_output_atomic(output: Path, artifacts: dict[str, bytes]) -> None:
    output = output.resolve()
    if output.exists():
        raise TerminalizationError(f"output must be a new path: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for name, data in sorted(artifacts.items()):
            path = temp / name
            with path.open("wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        for name, expected in artifacts.items():
            actual = (temp / name).read_bytes()
            if actual != expected:
                raise TerminalizationError(f"output reopen verification failed: {name}")
        os.replace(temp, output)
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def assemble(stage: Path, output: Path, *, expected_parent_session: str = DEFAULT_PARENT_SESSION, repo_root: Path | None = None) -> dict[str, Any]:
    stage = stage.resolve()
    output = output.resolve()
    effective_repo = (repo_root or Path(__file__).resolve().parent.parent).resolve()
    if _inside(output, stage) or _inside(output, effective_repo):
        raise TerminalizationError("output must be outside staging_v3 and outside the product repository")
    first = validate_snapshot(capture_snapshot(stage), expected_parent_session)
    first_artifacts = render_artifacts(first)
    second = validate_snapshot(capture_snapshot(stage), expected_parent_session)
    second_artifacts = render_artifacts(second)
    if first.snapshot.hashes != second.snapshot.hashes or first.snapshot.digest != second.snapshot.digest:
        raise TerminalizationError("stage changed between independent terminal reads")
    if first_artifacts != second_artifacts:
        raise TerminalizationError("independent deterministic builds are not byte-identical")
    _write_output_atomic(output, first_artifacts)
    for name, expected in first_artifacts.items():
        if (output / name).read_bytes() != expected:
            raise TerminalizationError(f"final output verification failed: {name}")
    return {
        "status": "PASS",
        "output": str(output),
        "input_snapshot_digest": first.snapshot.digest,
        "batches": TOTAL_BATCHES,
        "items": TOTAL_ITEMS,
        "verdicts": dict(sorted(first.verdict_counts.items())),
        "protected_text_changes": 0,
        "product_tree_writes": False,
        "double_build_byte_identical": True,
        "manifest_sha256": sha256_bytes(first_artifacts["manifest.json"]),
        "sha256sums_sha256": sha256_bytes(first_artifacts["SHA256SUMS.txt"]),
    }


def assemble_manual_handoff(
    stage: Path, output: Path, *, expected_parent_session: str = DEFAULT_PARENT_SESSION,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    stage = stage.resolve()
    output = output.resolve()
    effective_repo = (repo_root or Path(__file__).resolve().parent.parent).resolve()
    if _inside(output, stage) or _inside(output, effective_repo):
        raise TerminalizationError("output must be outside staging_v3 and outside the product repository")
    first = validate_manual_handoff_snapshot(capture_manual_handoff_snapshot(stage), expected_parent_session)
    first_artifacts = render_manual_handoff_artifacts(first)
    second = validate_manual_handoff_snapshot(capture_manual_handoff_snapshot(stage), expected_parent_session)
    second_artifacts = render_manual_handoff_artifacts(second)
    if first.validated.snapshot.hashes != second.validated.snapshot.hashes or first.validated.snapshot.digest != second.validated.snapshot.digest:
        raise TerminalizationError("stage changed between independent manual-handoff reads")
    if first_artifacts != second_artifacts:
        raise TerminalizationError("independent manual-handoff builds are not byte-identical")
    _write_output_atomic(output, first_artifacts)
    for name, expected in first_artifacts.items():
        if (output / name).read_bytes() != expected:
            raise TerminalizationError(f"final output verification failed: {name}")
    counts = first.validated.verdict_counts
    return {
        "status": "PASS", "terminal_mode": "manual_handoff", "ds_phase": "closed_manual_handoff",
        "output": str(output), "input_snapshot_digest": first.validated.snapshot.digest,
        "accepted_batches": MANUAL_HANDOFF_BATCHES, "ds_reviewed_items": MANUAL_HANDOFF_ITEMS,
        "manual_required_items": MANUAL_REQUIRED_ITEMS,
        "verdicts": dict(sorted(counts.items())),
        "human_decision_required": MANUAL_REQUIRED_ITEMS + counts.get("correction", 0) + counts.get("unresolved", 0),
        "protected_text_changes": 0, "product_tree_writes": False, "double_build_byte_identical": True,
        "manifest_sha256": sha256_bytes(first_artifacts["manifest.json"]),
        "sha256sums_sha256": sha256_bytes(first_artifacts["SHA256SUMS.txt"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New repository-external output directory")
    parser.add_argument("--expected-parent-session", default=DEFAULT_PARENT_SESSION)
    parser.add_argument("--terminal-mode", choices=("full_ds_review", "manual_handoff"), default="full_ds_review")
    args = parser.parse_args(argv)
    try:
        function = assemble_manual_handoff if args.terminal_mode == "manual_handoff" else assemble
        report = function(args.stage, args.output, expected_parent_session=args.expected_parent_session)
    except TerminalizationError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
