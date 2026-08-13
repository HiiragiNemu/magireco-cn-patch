#!/usr/bin/env python3
"""Regression tests for full DSV4 human-decision validation."""

from __future__ import annotations

import csv
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/validate-dsv4-human-review.py"
SPEC = importlib.util.spec_from_file_location("validate_dsv4_human_review", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
HANDOFF = ROOT / "magica/i18n_audit/release_v26_authority/dsv4_terminal_handoff"


def read_rows() -> tuple[list[str], list[dict[str, str]]]:
    with (HANDOFF / "human_review.tsv").open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=header, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8", newline="\n")


class FullHumanReviewValidationTests(unittest.TestCase):
    def test_blank_committed_template_is_valid_and_closed(self) -> None:
        result = MODULE.validate(HANDOFF / "full_review.tsv", HANDOFF / "human_review.tsv")
        self.assertEqual(result["states"]["pending"], 522)
        self.assertEqual(result["states"]["not_required"], 1390)
        self.assertFalse(result["all_decided"])
        self.assertFalse(result["release_gate_open"])

    def test_allowed_current_and_historical_decisions(self) -> None:
        header, rows = read_rows()
        current = next(row for row in rows if row["parent_verdict"] != "approved" and row["review_kind"].startswith("current"))
        history = next(row for row in rows if row["parent_verdict"] != "approved" and row["review_kind"].startswith("historical"))
        stamp = "2026-08-13T12:00:00Z"
        current.update(human_decision="approve-current", reviewer="Fixture Reviewer", timestamp=stamp, final_value=current["current_cn"])
        final = history["wiki_cn"] or history["current_cn"]
        history.update(human_decision="keep-authority", reviewer="Fixture Reviewer", timestamp=stamp, final_value=final)
        with tempfile.TemporaryDirectory(prefix="dsv4-human-decisions-") as td:
            decisions = Path(td) / "decisions.tsv"
            write_rows(decisions, header, rows)
            result = MODULE.validate(HANDOFF / "full_review.tsv", decisions)
        self.assertEqual(result["states"]["approved_current"], 1)
        self.assertEqual(result["states"]["kept_authority"], 1)
        self.assertEqual(result["states"]["pending"], 520)

    def test_protected_historical_revision_is_rejected(self) -> None:
        header, rows = read_rows()
        history = next(row for row in rows if row["parent_verdict"] != "approved" and row["review_kind"].startswith("historical"))
        history.update(human_decision="revise", reviewer="Fixture Reviewer", timestamp="2026-08-13T12:00:00Z", final_value="污染")
        with tempfile.TemporaryDirectory(prefix="dsv4-human-invalid-") as td:
            decisions = Path(td) / "decisions.tsv"
            write_rows(decisions, header, rows)
            with self.assertRaises(MODULE.HumanReviewError):
                MODULE.validate(HANDOFF / "full_review.tsv", decisions)


    def test_release_gate_mode_fails_closed_while_decisions_are_pending(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dsv4-human-gate-") as td:
            report = Path(td) / "report.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = MODULE.main([
                    "--source", str(HANDOFF / "full_review.tsv"),
                    "--decisions", str(HANDOFF / "human_review.tsv"),
                    "--report", str(report),
                    "--require-release-gate",
                ])
            payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 3)
        self.assertEqual(payload["states"]["pending"], 522)
        self.assertFalse(payload["release_gate_open"])
        self.assertIn("human decision release gate is closed", stderr.getvalue())

    def test_release_gate_mode_accepts_a_complete_resolved_fixture(self) -> None:
        header, rows = read_rows()
        stamp = "2026-08-13T12:00:00Z"
        for row in rows:
            if row["parent_verdict"] == "approved":
                continue
            if row["review_kind"] == "current-low-tier-translation-review":
                row.update(
                    human_decision="approve-current",
                    reviewer="Fixture Reviewer",
                    timestamp=stamp,
                    final_value=row["current_cn"],
                )
            else:
                row.update(
                    human_decision="keep-authority",
                    reviewer="Fixture Reviewer",
                    timestamp=stamp,
                    final_value=row["wiki_cn"] or row["current_cn"],
                )
        with tempfile.TemporaryDirectory(prefix="dsv4-human-open-gate-") as td:
            decisions = Path(td) / "decisions.tsv"
            report = Path(td) / "report.json"
            write_rows(decisions, header, rows)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                exit_code = MODULE.main([
                    "--source", str(HANDOFF / "full_review.tsv"),
                    "--decisions", str(decisions),
                    "--report", str(report),
                    "--require-release-gate",
                ])
            payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["release_gate_open"])
        self.assertEqual(payload["states"]["pending"], 0)
        self.assertEqual(payload["states"]["unresolved"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
