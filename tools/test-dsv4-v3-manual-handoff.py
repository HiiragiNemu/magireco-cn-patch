#!/usr/bin/env python3
"""Synthetic manual-handoff and human-decision regressions."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mod = load("assemble_dsv4_v3_terminal_manual_test", "assemble-dsv4-v3-terminal.py")
fixtures = load("assemble_dsv4_v3_terminal_fixture", "test-assemble-dsv4-v3-terminal.py")
decisions = load("validate_dsv4_manual_decisions", "validate-dsv4-manual-decisions.py")


def write_json(path: Path, value: object) -> None:
    path.write_bytes(mod.pretty_json_bytes(value))


def make_manual_handoff(stage: Path) -> None:
    # Freeze the actual 176 current-low-tier / 264 protected-history shape.
    manual_offset = 0
    for number in range(75, 97):
        path = stage / "queue" / f"batch_{number:03d}.json"
        batch = json.loads(path.read_text(encoding="utf-8"))
        for item in batch["items"]:
            current = manual_offset < mod.MANUAL_CURRENT_LOW_TIER_ITEMS
            if current:
                item.update({
                    "protected_authority_text": False,
                    "allowed_action": "review-and-stage-low-tier-only",
                    "review_kind": "current-low-tier-translation-review",
                    "source_path": "i18n/frontend-strings.tsv" if manual_offset < 167 else "i18n/overrides.tsv",
                })
                item["authority_references"].update({
                    "highest_authority_tier": "legacy_unverified_ai_assisted", "source_tier": "legacy_unverified_ai_assisted",
                    "authority_status": "no_per_entry_official_or_wiki_pair", "official_cn": "", "wiki_cn": "",
                })
            else:
                item.update({
                    "protected_authority_text": True,
                    "allowed_action": "review-history-only",
                    "review_kind": "historical-pass8-llm-comparison-only",
                    "source_path": "magica/js/libs/fixture.json",
                })
                item["authority_references"].update({
                    "highest_authority_tier": "official-or-wiki", "source_tier": "official-or-wiki",
                    "authority_status": "resolved-to-wiki", "wiki_cn": item["current_cn"],
                })
            manual_offset += 1
        write_json(path, batch)
    assert manual_offset == mod.MANUAL_REQUIRED_ITEMS

    for number in range(75, 97):
        (stage / "accepted" / f"batch_{number:03d}.json").unlink()
    ledger_rows = [json.loads(line) for line in (stage / "append_only_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    ledger_rows = ledger_rows[: mod.MANUAL_HANDOFF_BATCHES + 1]

    accepted = [json.loads((stage / "accepted" / f"batch_{number:03d}.json").read_text(encoding="utf-8")) for number in range(1, 75)]
    entries = [entry for batch in accepted for entry in batch["items"]]
    accepted_hashes = {
        f"batch_{number:03d}.json": mod.file_record((stage / "accepted" / f"batch_{number:03d}.json").read_bytes())
        for number in range(1, 75)
    }
    queue_batches = [json.loads((stage / "queue" / f"batch_{number:03d}.json").read_text(encoding="utf-8")) for number in range(1, 97)]
    manual_rows = mod._expected_manual_source_rows(queue_batches)
    manual_jsonl = b"".join(mod.canonical_json_bytes(row) for row in manual_rows)
    manual_tsv = mod._sealed_manual_source_tsv_bytes(manual_rows)
    (stage / "generated" / "manual_required.jsonl").write_bytes(manual_jsonl)
    (stage / "generated" / "manual_required.tsv").write_bytes(manual_tsv)
    all_ids = [item_id for batch in queue_batches for item_id in batch["item_ids"]]
    manual_ids = [row["item_id"] for row in manual_rows]
    coverage = {
        "accepted_item_ids_sha256": mod.sha256_bytes(mod.canonical_json_bytes(all_ids[:1472])),
        "manual_item_ids_sha256": mod.sha256_bytes(mod.canonical_json_bytes(manual_ids)),
        "full_item_ids_sha256": mod.sha256_bytes(mod.canonical_json_bytes(all_ids)),
        "manual_first_item_id": manual_ids[0], "manual_last_item_id": manual_ids[-1],
        "manual_source_index_range": {"start": 1473, "end": 1912},
        "manual_batch_range": {"start": 75, "end": 96, "count": 22},
        "manual_required_unreviewed": 440,
        "manual_unreviewed_classes": {
            "current_low_tier": 176,
            "current_low_tier_by_source_path": {"i18n/frontend-strings.tsv": 167, "i18n/overrides.tsv": 9},
            "historical_pass8_comparison_only": 264,
        },
        "accepted_manual_overlap": 0, "inventory_missing": 0,
    }
    reviewed_human_required = sum(entry["parent"]["verdict"] != "approved" for entry in entries)
    handoff_manifest = {
        "schema": f"{mod.SCHEMA_PREFIX}-manual-handoff-manifest/1", "terminal_mode": "manual_handoff",
        "ds_phase": "closed_manual_handoff", "accepted_batches": 74, "ds_reviewed_items": 1472,
        "manual_required_items": 440, "manual_required_batches": 22,
        "manual_required_unreviewed": 440, "reviewed_human_decision_required": reviewed_human_required,
        "human_decision_required": reviewed_human_required + 440,
        "manual_batch_range": {"start": 75, "end": 96}, "ds_retry_disabled": True,
        "queue_coverage": coverage,
        "files": {"manual_required.jsonl": mod.file_record(manual_jsonl), "manual_required.tsv": mod.file_record(manual_tsv)},
        "protected_text_changes": 0, "product_tree_writes": False, "network_configuration_writes": False,
        "decision_contract": {
            "current_allowed": ["approve-current", "revise", "unresolved"],
            "history_protected_allowed": ["keep-authority", "unresolved"],
            "nonempty_decision_requires_reviewer_and_iso_timestamp": True,
            "unresolved_apply_allowed": False,
            "validation": {"blank": 440, "decided": 0, "rows": 440, "unresolved": 0, "unresolved_apply_allowed": False},
        },
    }
    write_json(stage / "generated" / "manual_handoff_manifest.json", handoff_manifest)
    handoff_hash = hashlib.sha256((stage / "generated" / "manual_handoff_manifest.json").read_bytes()).hexdigest()
    # Mirror the real terminal contract: seq107 is the original closure and
    # seq108 atomically revises its metadata to the current manifest.
    while len(ledger_rows) < 106:
        ledger_rows.append(fixtures.ledger_row(ledger_rows[-1]["entry_sha256"], len(ledger_rows) + 1, {
            "type": "supervisor_lifecycle_checkpoint", "pid": 4242,
        }))
    superseded_hash = hashlib.sha256(b"fixture-superseded-manual-handoff-manifest").hexdigest()
    common_event = {
        "terminal_mode": "manual_handoff", "accepted_batches": 74,
        "ds_reviewed_items": 1472, "manual_required_items": 440,
        "manual_required_unreviewed": 440, "reviewed_human_decision_required": reviewed_human_required,
        "human_decision_required": reviewed_human_required + 440,
        "manual_batch_range": {"start": 75, "end": 96}, "ds_retry_disabled": True,
        "protected_text_changes": 0, "product_tree_writes": False, "network_configuration_writes": False,
    }
    closure = fixtures.ledger_row(ledger_rows[-1]["entry_sha256"], 107, {
        "type": "ds_phase_closed_manual_handoff", "terminal_mode": "manual_handoff", "accepted_batches": 74,
        **common_event, "manual_handoff_manifest_sha256": superseded_hash,
    })
    ledger_rows.append(closure)
    revision = fixtures.ledger_row(ledger_rows[-1]["entry_sha256"], 108, {
        "type": "manual_handoff_metadata_revision", **common_event,
        "manual_handoff_manifest_sha256": handoff_hash,
        "supersedes_manual_handoff_manifest_sha256": superseded_hash,
    })
    ledger_rows.append(revision)
    (stage / "append_only_ledger.jsonl").write_bytes(b"".join(mod.canonical_json_bytes(row) for row in ledger_rows))
    ledger_status = {"valid": True, "entries": 108, "last_entry_sha256": revision["entry_sha256"]}
    generated = mod._derive_stage_generated(entries, 74, ledger_status, accepted_hashes)
    terminal_summary = json.loads(generated["summary.json"])
    terminal_summary.update({"next_batch": None, "ds_phase": "closed_manual_handoff", "ds_retry_disabled": True, "manual_required_items": 440})
    generated["summary.json"] = mod.pretty_json_bytes(terminal_summary)
    review_manifest = json.loads(generated["review_manifest.json"])
    review_manifest["aggregates"]["summary.json"] = mod.file_record(generated["summary.json"])
    review_manifest["manual_handoff"] = {
        "ds_phase": "closed_manual_handoff", "ds_retry_disabled": True, "manual_required_items": 440,
        "manual_handoff_manifest_sha256": handoff_hash,
    }
    generated["review_manifest.json"] = mod.pretty_json_bytes(review_manifest)
    for name, data in generated.items():
        (stage / "generated" / name).write_bytes(data)
    review_manifest_hash = hashlib.sha256((stage / "generated" / "review_manifest.json").read_bytes()).hexdigest()
    write_json(stage / "generated" / "checkpoint.json", {
        "schema": f"{mod.SCHEMA_PREFIX}-checkpoint/1", "state": "closed-manual-handoff",
        "ds_phase": "closed_manual_handoff", "last_completed_batch": 74, "completed_items": 1472,
        "total_batches": 96, "total_items": 1912, "next_batch": None, "ds_retry_disabled": True,
        "manual_required_items": 440, "manual_required_batches": 22,
        "manual_required_unreviewed": 440, "reviewed_human_decision_required": reviewed_human_required,
        "human_decision_required": reviewed_human_required + 440,
        "manual_handoff_manifest_sha256": handoff_hash, "review_manifest_sha256": review_manifest_hash,
        "updated_at": revision["timestamp"],
    })
    write_json(stage / "generated" / "heartbeat.json", {
        "schema": f"{mod.SCHEMA_PREFIX}-heartbeat/1", "status": "closed-manual-handoff",
        "ds_phase": "closed_manual_handoff", "last_completed_batch": 74, "completed_items": 1472,
        "next_batch": None, "manual_required_items": 440, "manual_required_unreviewed": 440,
        "human_decision_required": reviewed_human_required + 440, "ds_retry_disabled": True,
        "updated_at": revision["timestamp"],
    })
    write_json(stage / "generated" / "manual_handoff_state.json", {
        "schema": f"{mod.SCHEMA_PREFIX}-manual-handoff-state/1", "terminal_mode": "manual_handoff",
        "ds_phase": "closed_manual_handoff", "accepted_batches": 74, "ds_reviewed_items": 1472,
        "manual_required_items": 440, "reviewed_human_decision_required": reviewed_human_required,
        "human_decision_required": reviewed_human_required + 440, "ds_retry_disabled": True,
        "manual_handoff_manifest_sha256": handoff_hash, "ledger_entry_sha256": revision["entry_sha256"],
        "protected_text_changes": 0, "product_tree_writes": False, "network_configuration_writes": False,
        "closed_at": revision["timestamp"],
    })
    manual_contract = {
        "accepted_batches": 74, "ds_reviewed_items": 1472, "manual_required_items": 440,
        "manual_required_unreviewed": 440, "reviewed_human_decision_required": reviewed_human_required,
        "human_decision_required": reviewed_human_required + 440,
        "manual_required_batches": {"start": 75, "end": 96, "count": 22},
        "manual_queue": {"path": "generated/manual_required.jsonl", **mod.file_record(manual_jsonl)},
        "manual_table": {"path": "generated/manual_required.tsv", **mod.file_record(manual_tsv)},
        "manifest": {"path": "generated/manual_handoff_manifest.json", **mod.file_record((stage / "generated" / "manual_handoff_manifest.json").read_bytes())},
        "queue_coverage": coverage, "protected_text_changes": 0, "product_tree_writes": False,
        "network_configuration_writes": False,
    }
    pipeline = {
        "schema": f"{mod.SCHEMA_PREFIX}-pipeline-verification/2", "result": "PASS", "terminal_seal": True,
        "terminal_mode": "manual_handoff", "ds_phase": "closed_manual_handoff", "ds_reviewed_items": 1472,
        "manual_required_items": 440, "manual_required_unreviewed": 440,
        "human_decision_required": reviewed_human_required + 440, "next_batch": None, "protected_text_changes": 0,
        "product_tree_writes": False, "network_configuration_writes": False,
        "ledger": ledger_status,
        "terminal_gate": {"required_accepted_batches": 74, "required_ds_reviewed_items": 1472,
                          "manual_required_items": 440, "accepted_batches": 74, "accepted_items": 1472, "next_batch": None},
        "manual_handoff": manual_contract,
        "pipeline_files": {
            "generated/manual_handoff_state.json": mod.file_record((stage / "generated" / "manual_handoff_state.json").read_bytes()),
            "generated/manual_handoff_manifest.json": mod.file_record((stage / "generated" / "manual_handoff_manifest.json").read_bytes()),
        },
    }
    write_json(stage / "pipeline_verification.json", pipeline)
    write_json(stage / "job_manifest_v3.json", {
        "schema": f"{mod.SCHEMA_PREFIX}-job-manifest/1", "terminal_mode": "manual_handoff",
        "ds_phase": "closed_manual_handoff", "review_progress": {"completed_items": 1472, "completed_batches": 74, "next_batch": None},
        "manual_handoff": manual_contract,
        "pipeline_files": pipeline["pipeline_files"],
        "pipeline_verification": mod.file_record((stage / "pipeline_verification.json").read_bytes()),
    })


class ManualHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.stage = fixtures.create_fixture(cls.root / "fixture", session="fixture-session")
        make_manual_handoff(cls.stage)
        cls.repo = cls.root / "repo"
        cls.repo.mkdir()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_manual_handoff_assembles_without_fabricating_440_ds_verdicts(self) -> None:
        out_a, out_b = self.root / "out-a", self.root / "out-b"
        a = mod.assemble_manual_handoff(self.stage, out_a, expected_parent_session="fixture-session", repo_root=self.repo)
        b = mod.assemble_manual_handoff(self.stage, out_b, expected_parent_session="fixture-session", repo_root=self.repo)
        self.assertEqual(a["manifest_sha256"], b["manifest_sha256"])
        self.assertEqual((74, 1472, 440, 442), (a["accepted_batches"], a["ds_reviewed_items"], a["manual_required_items"], a["human_decision_required"]))
        with (out_a / "full_review.tsv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(1912, len(rows))
        self.assertEqual(440, sum(row["parent_verdict"] == "manual-required" for row in rows))
        with (out_a / "human_review.tsv").open(encoding="utf-8", newline="") as stream:
            human = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(1912, len(human))
        self.assertEqual(442, sum(row["review_status"] != "ds-approved-human-unreviewed" for row in human))
        manifest = json.loads((out_a / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(176, manifest["counts"]["manual_current_low_tier"])
        self.assertEqual(264, manifest["counts"]["manual_protected_historical"])
        self.assertFalse(manifest["product_tree_writes"])
        self.assertEqual(0, manifest["protected_text_changes"])

    def test_ready_checkpoint_after_top_level_seal_is_rejected_as_race(self) -> None:
        stage = self.root / "race" / "staging_v3"
        shutil.copytree(self.stage, stage)
        checkpoint = json.loads((stage / "generated" / "checkpoint.json").read_text(encoding="utf-8"))
        checkpoint.update({"state": "ready", "next_batch": 75})
        write_json(stage / "generated" / "checkpoint.json", checkpoint)
        with self.assertRaisesRegex(mod.TerminalizationError, "checkpoint"):
            mod.validate_manual_handoff_snapshot(mod.capture_manual_handoff_snapshot(stage), "fixture-session")

    def test_manual_handoff_state_tamper_is_rejected(self) -> None:
        stage = self.root / "state-tamper" / "staging_v3"
        shutil.copytree(self.stage, stage)
        state = json.loads((stage / "generated" / "manual_handoff_state.json").read_text(encoding="utf-8"))
        state["human_decision_required"] += 1
        write_json(stage / "generated" / "manual_handoff_state.json", state)
        with self.assertRaisesRegex(mod.TerminalizationError, "manual-handoff state"):
            mod.validate_manual_handoff_snapshot(mod.capture_manual_handoff_snapshot(stage), "fixture-session")

    def test_terminal_ledger_metadata_revision_tamper_is_rejected(self) -> None:
        stage = self.root / "ledger-revision-tamper" / "staging_v3"
        shutil.copytree(self.stage, stage)
        rows = [json.loads(line) for line in (stage / "append_only_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
        revision = rows[-1]
        revision["manual_handoff_manifest_sha256"] = "f" * 64
        material = dict(revision)
        material.pop("entry_sha256")
        revision["entry_sha256"] = mod.sha256_bytes(mod.canonical_json_bytes(material))
        (stage / "append_only_ledger.jsonl").write_bytes(b"".join(mod.canonical_json_bytes(row) for row in rows))
        with self.assertRaisesRegex(mod.TerminalizationError, "metadata revision"):
            mod.validate_manual_handoff_snapshot(mod.capture_manual_handoff_snapshot(stage), "fixture-session")

    def test_manual_decision_enums_and_protected_value_gate(self) -> None:
        out = self.root / "decisions-out"
        mod.assemble_manual_handoff(self.stage, out, expected_parent_session="fixture-session", repo_root=self.repo)
        source = out / "manual_required.jsonl"
        table = out / "manual_required.tsv"
        report = decisions.validate(source, table)
        self.assertEqual(440, report["states"]["pending"])
        rows = list(csv.DictReader(table.read_text(encoding="utf-8").splitlines(), delimiter="\t"))
        rows[0].update({"human_decision": "approve-current", "reviewer": "Fixture", "reviewed_at": "2026-08-13T12:00:00Z", "final_value": rows[0]["current_cn"]})
        protected_index = next(i for i, row in enumerate(rows) if row["protected_authority_text"] == "true")
        rows[protected_index].update({"human_decision": "keep-authority", "reviewer": "Fixture", "reviewed_at": "2026-08-13T12:01:00+00:00", "final_value": rows[protected_index]["wiki_cn"] or rows[protected_index]["current_cn"]})
        with table.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), delimiter="\t", lineterminator="\n")
            writer.writeheader(); writer.writerows(rows)
        report = decisions.validate(source, table)
        self.assertEqual(1, report["states"]["approved_current"])
        self.assertEqual(1, report["states"]["kept_authority"])
        rows[protected_index]["final_value"] = "污染"
        with table.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), delimiter="\t", lineterminator="\n")
            writer.writeheader(); writer.writerows(rows)
        with self.assertRaisesRegex(decisions.DecisionError, "wiki_cn or current_cn"):
            decisions.validate(source, table)


if __name__ == "__main__":
    unittest.main(verbosity=2)
