#!/usr/bin/env python3
"""Regression tests for the complete Pass20 human-decision gate."""

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
TOOL = ROOT / "tools/validate-dsv4-human-review.py"
SPEC = importlib.util.spec_from_file_location("validate_dsv4_human_review", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
HANDOFF = AUDIT / "dsv4_terminal_handoff"
DECISIONS = AUDIT / "dsv4_human_decisions.tsv"
RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
SHADOWS = AUDIT / "pass20_authority_shadowed_machine_items.json"


def read_rows() -> tuple[list[str], list[dict[str, str]]]:
    with DECISIONS.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=header, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8", newline="\n")


def resolution_ids() -> set[str]:
    with RESOLUTIONS.open("r", encoding="utf-8", newline="") as stream:
        return {row["item_id"] for row in csv.DictReader(stream, delimiter="\t")}


def shadow_ids() -> set[str]:
    payload = json.loads(SHADOWS.read_text(encoding="utf-8"))
    return {row["item_id"] for row in payload["items"]}


class FullHumanReviewValidationTests(unittest.TestCase):
    def validate(self, decisions: Path = DECISIONS, shadows: Path = SHADOWS):
        return MODULE.validate(HANDOFF / "full_review.tsv", decisions, RESOLUTIONS, shadows)

    def test_blank_template_has_1565_pending_and_347_authority_excluded(self):
        result = self.validate()
        self.assertEqual(result["decision_required"], 1565)
        self.assertEqual(result["states"]["pending"], 1565)
        self.assertEqual(result["authority_resolved"], 323)
        self.assertEqual(result["higher_authority_shadowed"], 24)
        self.assertEqual(result["authority_excluded_total"], 347)
        self.assertFalse(result["release_gate_open"])

    def test_decision_rows_may_be_sorted_because_item_id_is_authoritative(self):
        header, rows = read_rows()
        rows.reverse()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sorted.tsv"
            write_rows(path, header, rows)
            result = self.validate(path)
        self.assertEqual(result["states"]["pending"], 1565)

    def test_shadowed_row_cannot_carry_human_decision(self):
        header, rows = read_rows()
        item_id = next(iter(shadow_ids()))
        row = next(row for row in rows if row["item_id"] == item_id)
        row.update(
            human_decision="approve-current", reviewer="Fixture Reviewer",
            timestamp="2026-08-16T12:00:00Z", final_value=row["current_cn"],
            review_status="human-reviewed-approved-current",
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "shadow-write.tsv"
            write_rows(path, header, rows)
            with self.assertRaisesRegex(MODULE.HumanReviewError, "authority-shadowed"):
                self.validate(path)

    def test_shadow_manifest_cannot_swap_in_a_human_queue_item(self):
        payload = json.loads(SHADOWS.read_text(encoding="utf-8"))
        payload["items"][0]["item_id"] = "LOW-MT-00312"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "swapped-shadow.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8", newline="\n",
            )
            with self.assertRaises(MODULE.HumanReviewError):
                self.validate(shadows=path)

    def test_release_enforcement_accepts_all_1565_human_approved(self):
        header, rows = read_rows()
        excluded = resolution_ids() | shadow_ids()
        stamp = "2026-08-16T12:00:00Z"
        for row in rows:
            if row["item_id"] in excluded:
                continue
            row.update(
                human_decision="approve-current", reviewer="Fixture Reviewer",
                timestamp=stamp, final_value=row["current_cn"], human_revision="",
                review_status="human-reviewed-approved-current",
            )
        with tempfile.TemporaryDirectory() as temp:
            decisions = Path(temp) / "decisions.tsv"
            report = Path(temp) / "report.json"
            write_rows(decisions, header, rows)
            out = io.StringIO()
            with redirect_stdout(out):
                code = MODULE.main([
                    "--source", str(HANDOFF / "full_review.tsv"),
                    "--decisions", str(decisions),
                    "--authority-resolutions", str(RESOLUTIONS),
                    "--authority-shadows", str(SHADOWS),
                    "--report", str(report),
                    "--require-release-open",
                ])
            result = json.loads(out.getvalue())
            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), result)
        self.assertEqual(code, 0)
        self.assertTrue(result["release_gate_open"])
        self.assertEqual(result["states"]["approved_current"], 1565)
        self.assertEqual(result["states"]["unresolved"], 0)

    def test_release_enforcement_rejects_pending_template(self):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = MODULE.main([
                "--source", str(HANDOFF / "full_review.tsv"),
                "--decisions", str(DECISIONS),
                "--authority-resolutions", str(RESOLUTIONS),
                "--authority-shadows", str(SHADOWS),
                "--require-release-open",
            ])
        self.assertEqual(code, 3)
        self.assertFalse(json.loads(out.getvalue())["release_gate_open"])
        self.assertIn("all 1565", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
