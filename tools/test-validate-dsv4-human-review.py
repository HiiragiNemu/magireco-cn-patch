#!/usr/bin/env python3
"""Regression tests for the Pass20 final-value gate."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
HANDOFF = AUDIT / "dsv4_terminal_handoff"
FINAL_VALUES = AUDIT / "pass20_human_final_values.tsv"
RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
SHADOWS = AUDIT / "pass20_authority_shadowed_machine_items.json"
TARGETS = AUDIT / "pass20_product_targets.json"
ADOPTIONS = AUDIT / "pass21_user_directed_suggested_adoptions.tsv"

def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

MODULE = load("validate_dsv4_human_review", ROOT / "tools/validate-dsv4-human-review.py")
CONTRACT = load("pass20_final_values_contract_test", ROOT / "tools/pass20_final_values_contract.py")

def read_tsv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)

def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CONTRACT.FINAL_VALUE_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

def completed_rows() -> list[dict[str, str]]:
    _, queue = read_tsv(AUDIT / "pass20_remaining_manual_review.tsv")
    targets = {row["item_id"]: row for row in json.loads(TARGETS.read_text(encoding="utf-8"))["items"]}
    adoptions = MODULE.load_adoptions(ADOPTIONS)
    return [
        CONTRACT.expected_final_value_row(
            row, targets[row["item_id"]],
            CONTRACT.seed_for_source(row, adoptions.get(row["item_id"], ""))[0],
            adoptions.get(row["item_id"], ""),
        )
        for row in queue
    ]

class FinalValueValidationTests(unittest.TestCase):
    def validate(self, final_values: Path | None = FINAL_VALUES):
        return MODULE.validate(
            HANDOFF / "full_review.tsv", final_values, RESOLUTIONS, SHADOWS,
        )

    def test_01_header_only_template_keeps_release_closed(self):
        result = self.validate()
        self.assertFalse(result["release_gate_open"])
        self.assertEqual(result["states"]["pending"], 1565)
        self.assertEqual(result["final_values_received"], 0)
        header, rows = read_tsv(FINAL_VALUES)
        self.assertEqual(tuple(header), CONTRACT.FINAL_VALUE_FIELDS)
        self.assertEqual(rows, [])
        self.assertTrue({"reviewer", "timestamp", "human_decision", "human_notes"}.isdisjoint(header))

    def test_02_all_prefilled_final_values_open_gate_without_decision_metadata(self):
        rows = completed_rows()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "final.tsv"
            write_tsv(path, rows)
            result = self.validate(path)
        self.assertTrue(result["release_gate_open"])
        self.assertEqual(result["states"]["pending"], 0)
        self.assertEqual(result["states"]["machine_suggestion_adopted"], 29)
        self.assertEqual(result["states"]["machine_current_retained"], 1536)
        self.assertEqual(result["states"]["human_revised"], 0)

    def test_03_rows_may_be_sorted_by_stable_id(self):
        rows = list(reversed(completed_rows()))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sorted.tsv"
            write_tsv(path, rows)
            self.assertTrue(self.validate(path)["release_gate_open"])

    def test_04_changed_final_value_is_derived_as_human_revision(self):
        rows = completed_rows()
        row = next(row for row in rows if row["seed_origin"] == "current")
        item_id = row["item_id"]
        _, queue = read_tsv(AUDIT / "pass20_remaining_manual_review.tsv")
        source = next(entry for entry in queue if entry["item_id"] == item_id)
        target = next(entry for entry in json.loads(TARGETS.read_text(encoding="utf-8"))["items"] if entry["item_id"] == item_id)
        changed = CONTRACT.expected_final_value_row(source, target, "人工修订值")
        rows[rows.index(row)] = changed
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "human.tsv"
            write_tsv(path, rows)
            result = self.validate(path)
        self.assertEqual(result["states"]["human_revised"], 1)
        self.assertEqual(changed["machine_translated"], "false")
        self.assertEqual(changed["final_origin"], "human-revision")

    def test_05_machine_suggestion_keeps_machine_origin(self):
        row = next(row for row in completed_rows() if row["seed_origin"] == "adopted_suggestion")
        self.assertEqual(row["review_status"], "human-confirmed-machine-suggestion-adopted")
        self.assertEqual(row["final_origin"], "machine-suggestion")
        self.assertEqual(row["machine_translated"], "true")

    def test_06_binding_drift_fails_closed(self):
        rows = completed_rows()
        rows[0]["source_record_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.tsv"
            write_tsv(path, rows)
            with self.assertRaisesRegex(MODULE.HumanReviewError, "source_record_sha256"):
                self.validate(path)

    def test_07_release_cli_rejects_header_only_template(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = MODULE.main([
                "--source", str(HANDOFF / "full_review.tsv"),
                "--final-values", str(FINAL_VALUES),
                "--authority-resolutions", str(RESOLUTIONS),
                "--require-release-open",
            ])
        self.assertEqual(code, 3)
        self.assertFalse(json.loads(out.getvalue())["release_gate_open"])
        self.assertIn("1565 final values", err.getvalue())

if __name__ == "__main__":
    unittest.main(verbosity=2)
