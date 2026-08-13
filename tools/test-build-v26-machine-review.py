#!/usr/bin/env python3
"""Deterministic tests for the closed frontend empty-candidate partition."""

from __future__ import annotations

import csv
import importlib.util
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "build-v26-machine-review.py"
SPEC = importlib.util.spec_from_file_location("build_v26_machine_review", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FrontendEmptyClassificationTests(unittest.TestCase):
    def test_product_snapshot_excludes_self_referential_maintenance_files(self) -> None:
        before = MODULE.product_content_snapshot()
        # The regression target is a maintenance file under tools/.  It must
        # not make the product snapshot self-referential.
        probe = ROOT / "tools" / ".machine-review-snapshot-probe.txt"
        self.assertFalse(probe.exists())
        try:
            probe.write_text("maintenance-only\n", encoding="utf-8", newline="\n")
            self.assertEqual(before, MODULE.product_content_snapshot())
        finally:
            probe.unlink(missing_ok=True)

    def audited_sources(self) -> list[dict[str, str]]:
        path = ROOT / "i18n" / "generated" / "input-provenance.tsv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            frontend = [
                row
                for row in csv.DictReader(handle, delimiter="\t")
                if row["source_file"] == "i18n/frontend-strings.tsv"
            ]
        unknown_empty = [
            row
            for row in frontend
            if (row["status"] != "present" or not row["candidate_cn"])
            and row["key"] not in MODULE.FRONTEND_EMPTY_53_DECISIONS
        ]
        self.assertEqual(unknown_empty, [])
        return [row for row in frontend if row["key"] in MODULE.FRONTEND_EMPTY_53_DECISIONS]

    def test_partition_is_exact_and_complete(self) -> None:
        rows = self.audited_sources()
        decisions = {
            row["source_text"]: MODULE.classify_frontend_empty_candidate(row)
            for row in rows
        }
        self.assertEqual(len(rows), 53)
        self.assertEqual(set(MODULE.FRONTEND_EMPTY_53_DECISIONS), {r["key"] for r in rows})
        self.assertEqual(
            Counter(d["closure_status"] for d in decisions.values()),
            Counter(
                {
                    "runtime-absent/not-backlog": 18,
                    "visible-cn-compatible-identity": 33,
                    "identity-punctuation": 1,
                    "official-cn-exact-path-dom-match": 1,
                }
            ),
        )

        for source, decision in decisions.items():
            if decision["closure_status"] == "runtime-absent/not-backlog":
                self.assertEqual(decision["suggested_cn"], "")
            elif decision["closure_status"] in {
                "visible-cn-compatible-identity",
                "identity-punctuation",
            }:
                self.assertEqual(decision["suggested_cn"], source)

        self.assertEqual(decisions["・"]["closure_status"], "identity-punctuation")
        self.assertEqual(
            decisions["属性相性"]["closure_status"],
            "official-cn-exact-path-dom-match",
        )
        self.assertEqual(
            decisions["属性相性"]["suggested_cn"],
            "属性克制",
        )
        self.assertEqual(decisions["属性相性"]["is_machine_translation"].split(";", 1)[0], "false")
        self.assertEqual(decisions["属性相性"]["manual_review_status"], "official-source-verified")
        official_source = next(row for row in rows if row["source_text"] == "属性相性")
        populated_official = {
            **official_source,
            "candidate_id": "candidate-id-changes-when-target-changes",
            "candidate_cn": "属性克制",
            "status": "present",
        }
        populated_decision = MODULE.classify_frontend_empty_candidate(populated_official)
        self.assertEqual(populated_decision["current_cn"], "属性克制")
        self.assertEqual(populated_decision["suggested_cn"], "属性克制")
        self.assertEqual(populated_decision["authority_status"], "official-source-verified")
        self.assertNotEqual(
            {d["manual_review_status"] for d in decisions.values()},
            {"needs-review/root-translation-required"},
        )

    def test_generated_backlog_rows_preserve_partition(self) -> None:
        _, rows = MODULE.build_glossary_support_and_frontend_backlog()
        self.assertEqual(len(rows), 53)
        self.assertEqual(
            Counter(row["manual_review_status"] for row in rows),
            Counter(
                {
                    "runtime-absent/not-backlog": 18,
                    "visible-cn-compatible-identity": 33,
                    "identity-punctuation": 1,
                    "official-source-verified": 1,
                }
            ),
        )
        self.assertEqual(
            [row["japanese_or_source_original"] for row in rows if row["manual_review_status"] == "official-source-verified"],
            ["属性相性"],
        )

        master: list[dict[str, str]] = []
        MODULE.append_support_universe(master, [], rows)
        for row in master:
            MODULE.finalize_review_columns(row)
        self.assertEqual(
            Counter(row["review_status"] for row in master),
            Counter(
                {
                    "runtime-absent/not-backlog": 18,
                    "visible-cn-compatible-identity": 33,
                    "identity-punctuation": 1,
                    "official-source-verified": 1,
                }
            ),
        )
        self.assertFalse(
            any(
                row["review_status"] == "needs-review/root-translation-required"
                or row["suggested_cn"] == "needs-review/root-translation-required"
                for row in master
            )
        )
        official = next(row for row in master if row["original_text"] == "属性相性")
        self.assertEqual(official["suggested_cn"], "属性克制")
        self.assertEqual(official["source_bucket"], "official")
        self.assertEqual(official["machine_translated"], "false")
        self.assertEqual(official["authority_status"], "official-source-verified")

    def test_unknown_candidate_fails_closed(self) -> None:
        with self.assertRaisesRegex(AssertionError, "unclassified empty frontend candidate"):
            MODULE.classify_frontend_empty_candidate(
                {"key": "global:unknown", "source_text": "UNKNOWN", "candidate_cn": ""}
            )


if __name__ == "__main__":
    unittest.main()
