#!/usr/bin/env python3
"""Regression tests for assemble-dsv4-v3-terminal.py."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("assemble-dsv4-v3-terminal.py")
SPEC = importlib.util.spec_from_file_location("assemble_dsv4_v3_terminal", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(mod.pretty_json_bytes(value))


def ledger_row(previous: str, sequence: int, event: dict) -> dict:
    row = {"sequence": sequence, "timestamp": f"2026-08-12T00:00:{sequence % 60:02d}.000Z", "previous_entry_sha256": previous, **event}
    row["entry_sha256"] = mod.sha256_bytes(mod.canonical_json_bytes(row))
    return row


def make_source_item(index: int) -> dict:
    protected = index == mod.TOTAL_ITEMS
    original = f"原文{index}"
    old = f"旧译{index}"
    current = f"现译{index}"
    return {
        "allowed_action": "review-history-only" if protected else "review-and-stage-low-tier-only",
        "authority_references": {
            "authority_status": "resolved-to-wiki" if protected else "no-authority",
            "confirmed_human_cn": "",
            "evidence": f"evidence/{index}" if protected else "",
            "highest_authority_tier": "wiki" if protected else "low-tier",
            "official_cn": "",
            "source_tier": "wiki" if protected else "legacy-unverified-ai-assisted",
            "wiki_cn": current if protected else "",
        },
        "current_cn": current,
        "item_id": f"ITEM-{index:04d}",
        "japanese_or_source_original": original,
        "old_cn": old,
        "old_cn_sha256": hashlib.sha256(old.encode()).hexdigest(),
        "origin_record_id": f"ORIGIN-{index:04d}",
        "previous_low_standard_ds_result": None,
        "product_write_allowed": False,
        "protected_authority_text": protected,
        "provenance": {
            "machine_translated": "historical-llm",
            "source_author": "fixture",
            "source_batch": "fixture",
            "source_bucket": "fixture",
            "source_stage": "fixture",
            "source_tier": "wiki" if protected else "legacy-unverified-ai-assisted",
        },
        "review_kind": "historical-review-only" if protected else "low-tier-review",
        "source_field": "value",
        "source_key": f"key-{index:04d}",
        "source_path": "i18n/fixture.tsv",
        "source_text_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "stable_business_key": f"i18n/fixture.tsv#key-{index:04d}/value",
    }


def make_roles(item: dict, index: int, imported: bool) -> tuple[dict, dict]:
    roles = {}
    expected = mod.expected_applicability(item)
    proposed = f"修订{index}"
    for role_index, name in enumerate(mod.ROLE_NAMES, 1):
        applicable = expected[name]
        verdict = "approved" if applicable else "N/A"
        if index == 1 and name in {mod.ROLE_NAMES[0], mod.ROLE_NAMES[4]}:
            verdict = "correction"
        if index == 2 and name == mod.ROLE_NAMES[0]:
            verdict = "unresolved"
        record = {
            "applicability": "applicable" if applicable else "N/A",
            "evidence": f"evidence {index}/{name}",
            "rationale": f"rationale {index}/{name}",
            "verdict": verdict,
        }
        if verdict == "correction":
            record["proposed_cn"] = proposed
        if imported:
            record["source_agent_id"] = f"import-agent-{role_index}"
        roles[name] = record
    role_verdicts = {name: roles[name]["verdict"] for name in mod.ROLE_NAMES}
    verdict = "correction" if index == 1 else "unresolved" if index == 2 else "approved"
    parent = {"verdict": verdict, "rationale": f"parent rationale {index}", "role_verdicts": role_verdicts}
    if verdict == "correction":
        parent["suggested_cn"] = proposed
    return roles, parent


def create_fixture(root: Path, session: str = "fixture-session") -> Path:
    stage = root / "staging_v3"
    for directory in ("queue", "accepted", "generated"):
        (stage / directory).mkdir(parents=True, exist_ok=True)
    lock_files = {
        "items.jsonl": {"bytes": 123, "sha256": "a" * 64},
        "protected_authority_reference_148_v2.tsv": {"bytes": 456, "sha256": "b" * 64},
    }
    source_lock = {
        "schema": f"{mod.SCHEMA_PREFIX}-source-lock/1",
        "source_v2_atomic_history": "failed",
        "source_v2_atomicity_claimed": False,
        "source_job_id": "fixture-import-job",
        "source_session_id": "fixture-import-session",
        "files": lock_files,
    }
    write_json(stage / "source_lock_v3.json", source_lock)
    items = [make_source_item(index) for index in range(1, mod.TOTAL_ITEMS + 1)]
    accepted_batches = []
    accepted_raw = {}
    for number in range(1, mod.TOTAL_BATCHES + 1):
        start, end = mod.batch_bounds(number)
        selected = items[start - 1:end]
        item_ids = [x["item_id"] for x in selected]
        queue = {
            "batch_number": number,
            "effort_required": mod.EFFORT,
            "input_items_sha256": "a" * 64,
            "item_ids": item_ids,
            "item_range": {"count": len(selected), "end": end, "start": start},
            "items": selected,
            "model_required": mod.MODEL,
            "roles_required": list(mod.ROLE_NAMES),
            "schema": f"{mod.SCHEMA_PREFIX}-queue-batch/1",
        }
        write_json(stage / "queue" / f"batch_{number:03d}.json", queue)
        imported = number <= mod.IMPORTED_BATCHES
        batch_agents = {name: f"agent-{number:03d}-{role_index}" for role_index, name in enumerate(mod.ROLE_NAMES, 1)}
        runtime = (
            {
                "effort": mod.EFFORT,
                "kind": "verified-v2-content-import",
                "model": mod.MODEL,
                "source_job_id": source_lock["source_job_id"],
                "source_parent_session_id": source_lock["source_session_id"],
                "source_v2_batches": [number],
            }
            if imported
            else {
                "agents": batch_agents,
                "effort": mod.EFFORT,
                "job_id": "fixture-durable-job",
                "kind": "deepseek-v4-cross-role-review",
                "model": mod.MODEL,
                "parent_session_id": session,
            }
        )
        pending_hash = hashlib.sha256(f"pending-{number}".encode()).hexdigest()
        accepted_items = []
        for offset, item in enumerate(selected):
            index = start + offset
            roles, parent = make_roles(item, index, imported)
            entry = {
                "item_id": item["item_id"],
                "origin_record_id": item["origin_record_id"],
                "parent": parent,
                "protection": {"product_tree_written": False, "authority_text_changed": False},
                "roles": roles,
                "source_index": index,
                "source_item": item,
                "stable_business_key": item["stable_business_key"],
            }
            if imported:
                entry["import_provenance"] = {
                    "source_v2_atomic_history": "failed",
                    "source_v2_atomicity_claimed": False,
                    "source_v2_job_id": source_lock["source_job_id"],
                    "source_v2_session_id": source_lock["source_session_id"],
                    "source_v2_model": mod.MODEL,
                    "source_v2_effort": mod.EFFORT,
                    "source_v2_role_agents": {name: f"import-agent-{i}" for i, name in enumerate(mod.ROLE_NAMES, 1)},
                    "source_v2_role_line_number": index,
                    "source_v2_review_line_number": index,
                    "source_v2_role_line_sha256": hashlib.sha256(f"role-{index}".encode()).hexdigest(),
                    "source_v2_review_line_sha256": hashlib.sha256(f"review-{index}".encode()).hexdigest(),
                }
            else:
                entry["review_provenance"] = {
                    "agents": batch_agents,
                    "effort": mod.EFFORT,
                    "job_id": runtime["job_id"],
                    "model": mod.MODEL,
                    "parent_session_id": session,
                    "pending_input_sha256": pending_hash,
                }
            accepted_items.append(entry)
        accepted = {
            "batch_number": number,
            "item_ids": item_ids,
            "item_range": queue["item_range"],
            "items": accepted_items,
            "protection_assertion": {
                "authority_text_changed": False,
                "product_tree_written": False,
                **({"locked_source_hashes": lock_files} if imported else {"protected_reference_sha256": "b" * 64}),
            },
            "review_runtime": runtime,
            "schema": f"{mod.SCHEMA_PREFIX}-accepted-batch/1",
        }
        if imported:
            accepted["import_notice"] = {
                "source_v2_atomic_history": "failed",
                "source_v2_atomicity_claimed": False,
                "source_v2_cancelled": True,
                "v3_batch_created_atomically": True,
            }
        else:
            accepted["pending_payload_sha256"] = pending_hash
        raw = mod.pretty_json_bytes(accepted)
        (stage / "accepted" / f"batch_{number:03d}.json").write_bytes(raw)
        accepted_raw[number] = raw
        accepted_batches.append(accepted)
    rows = []
    previous = "0" * 64
    first = ledger_row(previous, 1, {"type": "v3_import_start", "source_job_id": source_lock["source_job_id"], "source_session_id": source_lock["source_session_id"]})
    rows.append(first)
    previous = first["entry_sha256"]
    for number, batch in enumerate(accepted_batches, 1):
        event = {
            "type": "imported_batch_promoted" if number <= mod.IMPORTED_BATCHES else "pending_batch_promoted",
            "batch_number": number,
            "accepted_sha256": hashlib.sha256(accepted_raw[number]).hexdigest(),
            "item_range": batch["item_range"],
        }
        if number <= mod.IMPORTED_BATCHES:
            event.update({
                "item_ids_sha256": mod.sha256_bytes(mod.canonical_json_bytes(batch["item_ids"])),
                "v3_atomic_accept": True,
            })
        else:
            event.update({
                "pending_payload_sha256": batch["pending_payload_sha256"],
                "parent_session_id": session,
                "model": mod.MODEL,
                "effort": mod.EFFORT,
                "agents": batch["review_runtime"]["agents"],
                "protected_text_changes": 0,
            })
        row = ledger_row(previous, len(rows) + 1, event)
        rows.append(row)
        previous = row["entry_sha256"]
    ledger_data = b"".join(mod.canonical_json_bytes(x) for x in rows)
    (stage / "append_only_ledger.jsonl").write_bytes(ledger_data)
    accepted_hashes = {f"batch_{number:03d}.json": mod.file_record(accepted_raw[number]) for number in range(1, mod.TOTAL_BATCHES + 1)}
    ledger_status = {"valid": True, "entries": len(rows), "last_entry_sha256": rows[-1]["entry_sha256"]}
    generated = mod._derive_stage_generated(
        [entry for batch in accepted_batches for entry in batch["items"]],
        mod.TOTAL_BATCHES,
        ledger_status,
        accepted_hashes,
    )
    for name, data in generated.items():
        (stage / "generated" / name).write_bytes(data)
    checkpoint = {
        "schema": f"{mod.SCHEMA_PREFIX}-checkpoint/1",
        "state": "complete",
        "last_completed_batch": mod.TOTAL_BATCHES,
        "completed_items": mod.TOTAL_ITEMS,
        "total_batches": mod.TOTAL_BATCHES,
        "total_items": mod.TOTAL_ITEMS,
        "next_batch": None,
        "review_manifest_sha256": hashlib.sha256(generated["review_manifest.json"]).hexdigest(),
        "updated_at": "2026-08-12T00:00:00.000Z",
    }
    heartbeat = {
        "schema": f"{mod.SCHEMA_PREFIX}-heartbeat/1",
        "status": "complete",
        "last_completed_batch": mod.TOTAL_BATCHES,
        "completed_items": mod.TOTAL_ITEMS,
        "next_batch": None,
        "updated_at": "2026-08-12T00:00:00.000Z",
    }
    write_json(stage / "generated" / "checkpoint.json", checkpoint)
    write_json(stage / "generated" / "heartbeat.json", heartbeat)
    quarantine = stage / "rejected" / "batch_072_reboot_stale_fixture.json"
    quarantine.parent.mkdir(parents=True, exist_ok=True)
    quarantine.write_bytes(mod.pretty_json_bytes({"fixture": "stale-pending-batch72", "product_tree_writes": False}))
    accepted_72_sha = hashlib.sha256((stage / "accepted" / "batch_072.json").read_bytes()).hexdigest()
    stale_record = {
        "schema": f"{mod.SCHEMA_PREFIX}-stale-pending-quarantine/1",
        "recorded_at": "2026-08-13T08:40:26.782942Z",
        "reason": "fixture stale pending differs from accepted batch72",
        "source_path": "pending/batch_072.json",
        "quarantine_path": "rejected/batch_072_reboot_stale_fixture.json",
        "pending_sha256": hashlib.sha256(quarantine.read_bytes()).hexdigest(),
        "accepted_sha256": accepted_72_sha,
        "accepted_pending_payload_sha256": accepted_batches[71]["pending_payload_sha256"],
        "item_ids_equal": True,
        "checkpoint_before": {
            "schema": f"{mod.SCHEMA_PREFIX}-checkpoint/1",
            "state": "ready",
            "last_completed_batch": 74,
            "completed_items": 1472,
            "total_batches": mod.TOTAL_BATCHES,
            "total_items": mod.TOTAL_ITEMS,
            "next_batch": 75,
            "updated_at": "2026-08-12T16:47:44.392Z",
            "review_manifest_sha256": "c" * 64,
        },
        "product_tree_written": False,
        "authority_text_changed": False,
    }
    write_json(stage / "runtime" / "stale_pending_quarantine_fixture.json", stale_record)
    tool_events = [
        {"line": 790 + index, "result": "error" if index == 4 else "success", "timestamp": f"2026-08-11T22:4{index}:00.000Z", "tool": "Bash", "transcript": "fixture-transcript.jsonl"}
        for index in range(1, 5)
    ]
    write_json(stage / mod.TOOL_USAGE_AUDIT, {
        "schema": "magireco-cn-dsv4-tool-usage-audit/1",
        "session_id": session,
        "conclusions": {"bash_used": True, "mcp_used": False, "repository_or_host_path_boundary_violation": False, "web_used": False},
        "forbidden_tool_use_counts": {"Bash": 4},
        "forbidden_tool_uses": tool_events,
        "host_network_configuration_writes": 0,
    })
    return stage


class TerminalAssemblerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.base = create_fixture(cls.root / "base")
        cls.fake_repo = cls.root / "fake-repo"
        cls.fake_repo.mkdir()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def copy_stage(self, name: str) -> Path:
        destination = self.root / name / "staging_v3"
        if destination.parent.exists():
            shutil.rmtree(destination.parent)
        shutil.copytree(self.base, destination)
        return destination

    def test_terminal_build_is_complete_reproducible_and_reopened(self) -> None:
        output_a = self.root / "output-a"
        output_b = self.root / "output-b"
        report_a = mod.assemble(self.base, output_a, expected_parent_session="fixture-session", repo_root=self.fake_repo)
        report_b = mod.assemble(self.base, output_b, expected_parent_session="fixture-session", repo_root=self.fake_repo)
        self.assertTrue(report_a["double_build_byte_identical"])
        self.assertEqual(report_a["manifest_sha256"], report_b["manifest_sha256"])
        names_a = sorted(p.name for p in output_a.iterdir())
        names_b = sorted(p.name for p in output_b.iterdir())
        self.assertEqual(names_a, names_b)
        self.assertEqual(14, len(names_a))
        for name in names_a:
            self.assertEqual((output_a / name).read_bytes(), (output_b / name).read_bytes())
            self.assertNotIn(b"\r\n", (output_a / name).read_bytes())
        with (output_a / "full_review.tsv").open(encoding="utf-8", newline="") as stream:
            self.assertEqual(mod.TOTAL_ITEMS, sum(1 for _ in csv.DictReader(stream, delimiter="\t")))
        with (output_a / "human_review.tsv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual(mod.TOTAL_ITEMS, len(rows))
            self.assertTrue({"human_decision", "reviewer", "timestamp", "final_value"}.issubset(rows[0]))
            self.assertTrue(all(not row["human_decision"] and not row["reviewer"] and not row["timestamp"] and not row["final_value"] for row in rows))
        with (output_a / "nonapproved_review.tsv").open(encoding="utf-8", newline="") as stream:
            self.assertEqual(2, sum(1 for _ in csv.DictReader(stream, delimiter="\t")))
        with (output_a / "unresolved.tsv").open(encoding="utf-8", newline="") as stream:
            self.assertEqual(1, sum(1 for _ in csv.DictReader(stream, delimiter="\t")))
        manifest = json.loads((output_a / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual({"approved": 1910, "correction": 1, "unresolved": 1}, {k: manifest["counts"][k] for k in ("approved", "correction", "unresolved")})
        patch = json.loads((output_a / "correction_patch.json").read_text(encoding="utf-8"))
        rollback = json.loads((output_a / "rollback.json").read_text(encoding="utf-8"))
        self.assertEqual(1, len(patch["entries"]))
        self.assertEqual(patch["entries"][0]["before"], rollback["entries"][0]["after"])
        self.assertEqual(patch["entries"][0]["after"], rollback["entries"][0]["before"])
        self.assertEqual(patch["entries"][0]["locator_sha256"], rollback["entries"][0]["locator_sha256"])
        self.assertEqual("staging_patch_executor.py", rollback["executor"]["path"])
        self.assertEqual(4, manifest["exception_evidence"]["historical_tool_policy_exception"]["bash_use_count"])
        self.assertEqual("accepted/batch_072.json", manifest["exception_evidence"]["stale_batch72_quarantine"]["accepted_batch72"]["path"])
        sums = {}
        for line in (output_a / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
            digest, name = line.split("  ", 1)
            sums[name] = digest
        for name, digest in sums.items():
            self.assertEqual(digest, hashlib.sha256((output_a / name).read_bytes()).hexdigest())

    def test_machine_executable_patch_and_rollback_roundtrip_only_synthetic_low_tier_staging(self) -> None:
        output = self.root / "roundtrip-output"
        mod.assemble(self.base, output, expected_parent_session="fixture-session", repo_root=self.fake_repo)
        patch = json.loads((output / "correction_patch.json").read_text(encoding="utf-8"))
        entry = patch["entries"][0]
        stage = self.root / "synthetic-low-tier-staging"
        stage.mkdir(exist_ok=True)
        marker = {"schema": "magireco-cn-dsv4-v3-low-tier-staging-root/1", "staging_only": True, "product_tree_writes": False}
        (stage / ".dsv4-low-tier-staging.json").write_bytes(mod.pretty_json_bytes(marker))
        locator = entry["locator"]
        target_document = {
            "schema": "magireco-cn-dsv4-v3-low-tier-staging-values/1",
            "staging_only": True,
            "product_tree_writes": False,
            "records": [{
                "item_id": entry["item_id"],
                **locator,
                "value": entry["before"],
                "value_sha256": entry["before_sha256"],
                "product_write_allowed": False,
                "protected_authority_text": False,
            }],
        }
        target = stage / "low_tier_values.json"
        target.write_bytes(mod.pretty_json_bytes(target_document))
        baseline = target.read_bytes()
        executor = output / "staging_patch_executor.py"
        apply_result = subprocess.run(
            [sys.executable, str(executor), "--stage-root", str(stage), "--target", str(target), "--manifest", str(output / "correction_patch.json")],
            text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertEqual(0, apply_result.returncode, apply_result.stderr)
        applied = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(entry["after"], applied["records"][0]["value"])
        rollback_result = subprocess.run(
            [sys.executable, str(executor), "--stage-root", str(stage), "--target", str(target), "--manifest", str(output / "rollback.json")],
            text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertEqual(0, rollback_result.returncode, rollback_result.stderr)
        self.assertEqual(baseline, target.read_bytes())

    def test_patch_before_sha_gate_and_protected_record_fail_closed(self) -> None:
        output = self.root / "gate-output"
        mod.assemble(self.base, output, expected_parent_session="fixture-session", repo_root=self.fake_repo)
        patch = json.loads((output / "correction_patch.json").read_text(encoding="utf-8"))
        entry = patch["entries"][0]
        stage = self.root / "gate-low-tier-staging"
        stage.mkdir(exist_ok=True)
        (stage / ".dsv4-low-tier-staging.json").write_bytes(mod.pretty_json_bytes({
            "schema": "magireco-cn-dsv4-v3-low-tier-staging-root/1", "staging_only": True, "product_tree_writes": False,
        }))
        target = stage / "low_tier_values.json"
        target.write_bytes(mod.pretty_json_bytes({
            "schema": "magireco-cn-dsv4-v3-low-tier-staging-values/1", "staging_only": True, "product_tree_writes": False,
            "records": [{"item_id": entry["item_id"], **entry["locator"], "value": "drift", "value_sha256": hashlib.sha256("drift".encode()).hexdigest(), "product_write_allowed": False, "protected_authority_text": False}],
        }))
        executor = output / "staging_patch_executor.py"
        drift = subprocess.run(
            [sys.executable, str(executor), "--stage-root", str(stage), "--target", str(target), "--manifest", str(output / "correction_patch.json")],
            text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertEqual(2, drift.returncode)
        self.assertIn("before SHA gate failed", drift.stderr)
        protected_document = json.loads(target.read_text(encoding="utf-8"))
        protected_document["records"][0]["protected_authority_text"] = True
        target.write_bytes(mod.pretty_json_bytes(protected_document))
        protected = subprocess.run(
            [sys.executable, str(executor), "--stage-root", str(stage), "--target", str(target), "--manifest", str(output / "correction_patch.json")],
            text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertEqual(2, protected.returncode)
        self.assertIn("only unprotected non-product records are mutable", protected.stderr)

    def test_nonterminal_inventory_fails_closed_without_output(self) -> None:
        stage = self.copy_stage("nonterminal")
        (stage / "accepted" / "batch_096.json").unlink()
        output = self.root / "nonterminal-output"
        with self.assertRaisesRegex(mod.TerminalizationError, "terminal accepted inventory"):
            mod.assemble(stage, output, expected_parent_session="fixture-session", repo_root=self.fake_repo)
        self.assertFalse(output.exists())

    def test_queue_source_text_hash_drift_fails_closed(self) -> None:
        stage = self.copy_stage("queue-drift")
        path = stage / "queue" / "batch_096.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["items"][-1]["japanese_or_source_original"] += "漂移"
        write_json(path, value)
        with self.assertRaisesRegex(mod.TerminalizationError, "source text hash mismatch"):
            mod.validate_snapshot(mod.capture_snapshot(stage), "fixture-session")

    def test_parent_session_drift_fails_closed(self) -> None:
        stage = self.copy_stage("session-drift")
        path = stage / "accepted" / "batch_096.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["review_runtime"]["parent_session_id"] = "wrong-session"
        write_json(path, value)
        with self.assertRaisesRegex(mod.TerminalizationError, "parent session"):
            mod.validate_snapshot(mod.capture_snapshot(stage), "fixture-session")

    def test_five_agent_independence_fails_closed(self) -> None:
        stage = self.copy_stage("agent-drift")
        path = stage / "accepted" / "batch_096.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        agents = value["review_runtime"]["agents"]
        agents[mod.ROLE_NAMES[1]] = agents[mod.ROLE_NAMES[0]]
        write_json(path, value)
        with self.assertRaisesRegex(mod.TerminalizationError, "five independent IDs"):
            mod.validate_snapshot(mod.capture_snapshot(stage), "fixture-session")

    def test_ledger_chain_tamper_fails_closed(self) -> None:
        stage = self.copy_stage("ledger-drift")
        rows = [json.loads(x) for x in (stage / "append_only_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
        rows[-1]["accepted_sha256"] = "0" * 64
        (stage / "append_only_ledger.jsonl").write_bytes(b"".join(mod.canonical_json_bytes(x) for x in rows))
        with self.assertRaisesRegex(mod.TerminalizationError, "ledger entry hash"):
            mod.validate_snapshot(mod.capture_snapshot(stage), "fixture-session")

    def test_generated_aggregate_drift_fails_closed(self) -> None:
        stage = self.copy_stage("generated-drift")
        path = stage / "generated" / "summary.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["protected_text_changes"] = 1
        write_json(path, value)
        with self.assertRaisesRegex(mod.TerminalizationError, "generated aggregate"):
            mod.validate_snapshot(mod.capture_snapshot(stage), "fixture-session")

    def test_stale_batch72_quarantine_hash_drift_fails_closed(self) -> None:
        stage = self.copy_stage("stale-quarantine-drift")
        quarantined = next((stage / "rejected").glob("batch_072_reboot_stale_*.json"))
        quarantined.write_bytes(quarantined.read_bytes() + b"\n")
        with self.assertRaisesRegex(mod.TerminalizationError, "quarantined batch72 bytes"):
            mod.validate_snapshot(mod.capture_snapshot(stage), "fixture-session")

    def test_historical_bash_exception_count_drift_fails_closed(self) -> None:
        stage = self.copy_stage("bash-audit-drift")
        audit_path = stage / mod.TOOL_USAGE_AUDIT
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["forbidden_tool_uses"].pop()
        write_json(audit_path, audit)
        with self.assertRaisesRegex(mod.TerminalizationError, "exactly four historical Bash"):
            mod.validate_snapshot(mod.capture_snapshot(stage), "fixture-session")

    def test_protected_correction_is_rejected(self) -> None:
        item = make_source_item(mod.TOTAL_ITEMS)
        roles, parent = make_roles(item, mod.TOTAL_ITEMS, False)
        roles[mod.ROLE_NAMES[0]]["verdict"] = "correction"
        roles[mod.ROLE_NAMES[0]]["proposed_cn"] = "污染"
        parent["verdict"] = "correction"
        parent["suggested_cn"] = "污染"
        parent["role_verdicts"][mod.ROLE_NAMES[0]] = "correction"
        entry = {"roles": roles, "parent": parent}
        with self.assertRaisesRegex(mod.TerminalizationError, "protected authority proposal"):
            mod._validate_role_and_parent(entry=entry, source_item=item, imported=False, item_id=item["item_id"])

    def test_output_inside_repo_is_rejected(self) -> None:
        output = self.fake_repo / "forbidden-output"
        with self.assertRaisesRegex(mod.TerminalizationError, "outside staging_v3"):
            mod.assemble(self.base, output, expected_parent_session="fixture-session", repo_root=self.fake_repo)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
