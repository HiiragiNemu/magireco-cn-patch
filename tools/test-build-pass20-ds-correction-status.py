#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import csv
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def load_tool():
    path = ROOT / "tools/build-pass20-ds-correction-status.py"
    spec = importlib.util.spec_from_file_location("pass20_corrections_tested", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


def load_importer():
    path = ROOT / "tools/import-pass20-human-review-xlsx.py"
    spec = importlib.util.spec_from_file_location("pass20_workbook_tested", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IMPORTER = load_importer()


def rewrite_tsv(source: Path, target: Path, mutate) -> None:
    with source.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)
    mutate(rows)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class Pass20CorrectionDispositionTests(unittest.TestCase):
    def test_37_corrections_are_partitioned_without_ds_product_writes(self):
        payload = TOOL.build()
        summary = payload["summary"]
        self.assertEqual(summary["ds_corrections"], 37)
        self.assertEqual(summary["official_cn_applied"], 7)
        self.assertEqual(summary["official_cn_existing_authority"], 1)
        self.assertEqual(summary["higher_authority_resolved"], 8)
        self.assertEqual(summary["human_review_pending_not_applied"], 29)
        self.assertEqual(summary["ds_direct_product_writes"], 0)
        self.assertEqual(summary["ds_suggestion_equal_to_official"], 2)
        self.assertEqual(summary["pending_target_status"], {
            "exact-current-runtime-literal": 22,
            "maintenance-only-count-or-path-drift": 3,
            "maintenance-only-current-literal-absent": 2,
            "maintenance-only-declared-path-absent": 2,
        })
        pending = [row for row in payload["items"] if row["final_status"].startswith("human-review-pending-")]
        self.assertEqual(len(pending), 29)
        self.assertTrue(all(row["current_candidate_state"] == "old-candidate-retained" for row in pending))
        preexisting = next(row for row in payload["items"] if row["item_id"] == "LOW-MT-01485")
        self.assertEqual(preexisting["final_status"], "official-cn-existing-authority")
        self.assertEqual(preexisting["official_final_cn"], "心魔战")
        self.assertEqual(preexisting["current_candidate_state"], "official-authority-preexisting-and-verified")
        official_equal = [row["item_id"] for row in payload["items"] if row["ds_suggestion_matches_official"] == "true"]
        self.assertEqual(official_equal, ["LOW-MT-01485", "LOW-MT-01540"])

        expected = {row["item_id"]: row for row in pending}
        workbook = ROOT / "magica/i18n_audit/release_v26_authority/pass20_human_review.xlsx"
        with zipfile.ZipFile(workbook) as package:
            shared = IMPORTER._shared_strings(package)
            paths = IMPORTER._sheet_paths(package)
            review = IMPORTER._parse_sheet(package, paths["审核"], shared)["cells"]
        visible = {}
        for row_number in range(2, 201):
            item_id = review[f"B{row_number}"]
            if review[f"F{row_number}"] == "DS发现错误／建议修正但尚未应用":
                visible[item_id] = review[f"E{row_number}"]
        self.assertEqual(set(visible), set(expected))
        self.assertEqual(len(visible), 29)
        for item_id, suggestion in visible.items():
            self.assertEqual(suggestion, expected[item_id]["ds_suggested_cn"])
        self.assertNotIn("LOW-MT-01485", {review[f"B{row}"] for row in range(2, 201)})

    def test_queue_binding_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            queue = Path(temp) / "queue.tsv"
            rewrite_tsv(
                TOOL.QUEUE,
                queue,
                lambda rows: next(row for row in rows if row["item_id"] == "LOW-MT-00601").update(
                    {"suggested_cn": "伪造建议", "parent_verdict": "manual-required"}
                ),
            )
            with (
                mock.patch.object(TOOL, "QUEUE", queue),
                self.assertRaisesRegex(TOOL.CorrectionStatusError, "queue binding drifted"),
            ):
                TOOL.build()

    def test_duplicate_decision_item_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            decisions = Path(temp) / "decisions.tsv"
            rewrite_tsv(TOOL.DECISIONS, decisions, lambda rows: rows.append(dict(rows[0])))
            with (
                mock.patch.object(TOOL, "DECISIONS", decisions),
                self.assertRaisesRegex(TOOL.CorrectionStatusError, "duplicate item_id"),
            ):
                TOOL.build()

    def test_official_product_byte_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            products = Path(temp) / "products.tsv"
            def drift(rows):
                next(row for row in rows if row["item_id"] == "LOW-MT-00700")["after"] = "不存在的官方值"
            rewrite_tsv(TOOL.OFFICIAL_PRODUCTS, products, drift)
            with (
                mock.patch.object(TOOL, "OFFICIAL_PRODUCTS", products),
                self.assertRaisesRegex(TOOL.CorrectionStatusError, "product bytes drifted"),
            ):
                TOOL.build()


if __name__ == "__main__":
    unittest.main(verbosity=2)
