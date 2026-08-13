#!/usr/bin/env python3
"""Regression tests for the closed human-decision staging patch builder."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/build-dsv4-human-decision-patch.py"
EXECUTOR = ROOT / "tools/dsv4-v3-staging-patch.py"
HANDOFF = ROOT / "magica/i18n_audit/release_v26_authority/dsv4_terminal_handoff"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load(TOOL, "build_dsv4_human_decision_patch_test")
STAGING = load(EXECUTOR, "dsv4_staging_executor_test")


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_table(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=header, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8", newline="\n")


def close_decisions(rows: list[dict[str, str]], *, revised: int = 1) -> list[str]:
    revised_ids: list[str] = []
    for row in rows:
        if row["parent_verdict"] == "approved":
            continue
        row["reviewer"] = "Human Fixture"
        row["timestamp"] = "2026-08-13T12:00:00Z"
        if row["review_kind"] == "historical-pass8-llm-comparison-only":
            row["human_decision"] = "keep-authority"
            row["final_value"] = row["wiki_cn"] or row["current_cn"]
            continue
        if len(revised_ids) < revised:
            row["human_decision"] = "revise"
            row["final_value"] = row["current_cn"] + "（人工修订）"
            row["human_revision"] = row["final_value"]
            revised_ids.append(row["item_id"])
        else:
            row["human_decision"] = "approve-current"
            row["final_value"] = row["current_cn"]
    return revised_ids


def inventory(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class HumanDecisionPatchTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("DSV4_TEST_TMP")
        self.temp = tempfile.TemporaryDirectory(
            prefix="dsv4-human-patch-tests-",
            dir=parent if parent else None,
        )
        self.base = Path(self.temp.name)
        self.source_header, self.source_rows = read_table(HANDOFF / "full_review.tsv")
        self.decision_header, self.decision_rows = read_table(HANDOFF / "human_review.tsv")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fixture(self, *, revised: int = 1) -> tuple[Path, Path, list[str]]:
        source = self.base / "source.tsv"
        decisions = self.base / "decisions.tsv"
        revised_ids = close_decisions(self.decision_rows, revised=revised)
        write_table(source, self.source_header, self.source_rows)
        write_table(decisions, self.decision_header, self.decision_rows)
        return source, decisions, revised_ids

    def test_build_is_byte_deterministic_and_apply_rollback_exact(self) -> None:
        source, decisions, revised_ids = self.fixture(revised=2)
        out_a = self.base / "out-a"
        out_b = self.base / "out-b"
        report_a = BUILDER.build(source, decisions, out_a)
        report_b = BUILDER.build(source, decisions, out_b)
        self.assertEqual(report_a["selected_revisions"], 2)
        self.assertEqual(report_b["selected_revisions"], 2)
        self.assertEqual(inventory(out_a), inventory(out_b))
        patch = json.loads((out_a / "correction_patch.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["item_id"] for entry in patch["entries"]], revised_ids)
        self.assertTrue(all(entry["target_preconditions"]["protected_authority_text"] is False for entry in patch["entries"]))
        target = out_a / "baseline_staging/low_tier_values.json"
        baseline = target.read_bytes()
        applied = STAGING.execute(out_a / "baseline_staging", target, out_a / "correction_patch.json")
        self.assertEqual(applied["entries"], 2)
        self.assertNotEqual(target.read_bytes(), baseline)
        rolled = STAGING.execute(out_a / "baseline_staging", target, out_a / "rollback.json")
        self.assertEqual(rolled["entries"], 2)
        self.assertEqual(target.read_bytes(), baseline)

    def test_unresolved_gate_is_closed(self) -> None:
        source, decisions, _ = self.fixture()
        header, rows = read_table(decisions)
        row = next(row for row in rows if row["review_kind"].startswith("current") and row["parent_verdict"] != "approved")
        row.update(human_decision="unresolved", final_value="", human_revision="")
        write_table(decisions, header, rows)
        with self.assertRaises((BUILDER.BuildError, RuntimeError)):
            BUILDER.build(source, decisions, self.base / "out")

    def test_protected_current_revision_is_rejected(self) -> None:
        source, decisions, revised_ids = self.fixture()
        item_id = revised_ids[0]
        source_header, source_rows = read_table(source)
        decision_header, decision_rows = read_table(decisions)
        next(row for row in source_rows if row["item_id"] == item_id)["protected_authority_text"] = "true"
        next(row for row in decision_rows if row["item_id"] == item_id)["protected_authority_text"] = "true"
        write_table(source, source_header, source_rows)
        write_table(decisions, decision_header, decision_rows)
        with self.assertRaises(BUILDER.BuildError):
            BUILDER.build(source, decisions, self.base / "out")

    def test_duplicate_stable_locator_is_rejected(self) -> None:
        source, decisions, _ = self.fixture(revised=2)
        source_header, source_rows = read_table(source)
        decision_header, decision_rows = read_table(decisions)
        selected = [row for row in decision_rows if row["human_decision"] == "revise"]
        first, second = selected[:2]
        for field in BUILDER.LOCATOR_FIELDS:
            next(row for row in source_rows if row["item_id"] == second["item_id"])[field] = first[field]
            second[field] = first[field]
        write_table(source, source_header, source_rows)
        write_table(decisions, decision_header, decision_rows)
        with self.assertRaises(BUILDER.BuildError):
            BUILDER.build(source, decisions, self.base / "out")

    def test_path_traversal_is_rejected(self) -> None:
        source, decisions, revised_ids = self.fixture()
        item_id = revised_ids[0]
        source_header, source_rows = read_table(source)
        decision_header, decision_rows = read_table(decisions)
        next(row for row in source_rows if row["item_id"] == item_id)["source_path"] = "../product.tsv"
        next(row for row in decision_rows if row["item_id"] == item_id)["source_path"] = "../product.tsv"
        write_table(source, source_header, source_rows)
        write_table(decisions, decision_header, decision_rows)
        with self.assertRaises(BUILDER.BuildError):
            BUILDER.build(source, decisions, self.base / "out")

    def test_manifest_tamper_fails_before_sha_gate(self) -> None:
        source, decisions, _ = self.fixture()
        out = self.base / "out"
        BUILDER.build(source, decisions, out)
        document = json.loads((out / "correction_patch.json").read_text(encoding="utf-8"))
        document["entries"][0]["after"] += "污染"
        tampered = self.base / "tampered.json"
        tampered.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True), encoding="utf-8", newline="\n")
        with self.assertRaises(STAGING.PatchError):
            STAGING.execute(out / "baseline_staging", out / "baseline_staging/low_tier_values.json", tampered)

    def test_output_inside_repo_and_preexisting_output_are_rejected(self) -> None:
        source, decisions, _ = self.fixture()
        with self.assertRaises(BUILDER.BuildError):
            BUILDER.build(source, decisions, ROOT / "forbidden-output")
        existing = self.base / "existing"
        existing.mkdir()
        with self.assertRaises(BUILDER.BuildError):
            BUILDER.build(source, decisions, existing)


if __name__ == "__main__":
    unittest.main(verbosity=2)
