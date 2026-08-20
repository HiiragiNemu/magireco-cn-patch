#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import csv
from collections import Counter
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
    @staticmethod
    def adopted_verification_result():
        with TOOL.ADOPTIONS.open(encoding="utf-8", newline="") as stream:
            adoptions = {row["item_id"]: row for row in csv.DictReader(stream, delimiter="\t")}
        products = {}
        for item_id, row in adoptions.items():
            strategy = row["runtime_strategy"]
            products[item_id] = {
                "strategy": strategy,
                "adopted_cn": row["adopted_cn"],
                "product_match_count": 0 if strategy == "canonical-only" else 1,
                "application_allowed": "false" if strategy == "canonical-only" else "true",
            }
        counts = Counter({
            "target-manifest-exact": 22, "explicit-safe-paths": 2, "canonical-only": 5,
            "runtime_materialized_items": 24, "runtime_occurrences": 30, "runtime_files": 23,
        })
        return products, counts

    def test_37_corrections_are_partitioned_without_ds_product_writes(self):
        with mock.patch.object(
            TOOL, "verify_user_directed_adoptions", return_value=self.adopted_verification_result(),
        ):
            payload = TOOL.build()
        summary = payload["summary"]
        self.assertEqual(summary["ds_corrections"], 37)
        self.assertEqual(summary["official_cn_applied"], 7)
        self.assertEqual(summary["official_cn_existing_authority"], 1)
        self.assertEqual(summary["higher_authority_resolved"], 8)
        self.assertEqual(summary["user_directed_suggestion_adopted"], 29)
        self.assertEqual(summary["human_review_pending_not_applied"], 0)
        self.assertEqual(summary["ds_direct_product_writes"], 0)
        self.assertEqual(summary["ds_suggestion_equal_to_official"], 2)
        self.assertEqual(summary["adopted_target_status"], {
            "canonical-only": 5,
            "explicit-safe-paths": 2,
            "runtime_files": 23,
            "runtime_materialized_items": 24,
            "runtime_occurrences": 30,
            "target-manifest-exact": 22,
        })
        adopted_rows = [row for row in payload["items"] if row["final_status"] == "user-directed-suggestion-adopted"]
        self.assertEqual(len(adopted_rows), 29)
        self.assertTrue(all(row["machine_origin"] == "true" for row in adopted_rows))
        self.assertTrue(all(row["authority_tier"] == "legacy_unverified_ai_assisted" for row in adopted_rows))
        self.assertTrue(all(row["review_status"] == "user-directed-suggestion-adopted" for row in adopted_rows))
        preexisting = next(row for row in payload["items"] if row["item_id"] == "LOW-MT-01485")
        self.assertEqual(preexisting["final_status"], "official-cn-existing-authority")
        self.assertEqual(preexisting["official_final_cn"], "心魔战")
        self.assertEqual(preexisting["current_candidate_state"], "official-authority-preexisting-and-verified")
        official_equal = [row["item_id"] for row in payload["items"] if row["ds_suggestion_matches_official"] == "true"]
        self.assertEqual(official_equal, ["LOW-MT-01485", "LOW-MT-01540"])

        expected = {row["item_id"]: row for row in adopted_rows}
        with (ROOT / "magica/i18n_audit/release_v26_authority/pass21_user_directed_suggested_adoptions.tsv").open(
            encoding="utf-8", newline=""
        ) as stream:
            adopted = {row["item_id"]: row["adopted_cn"] for row in csv.DictReader(stream, delimiter="\t")}
        workbook = ROOT / "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1564.xlsx"
        with zipfile.ZipFile(workbook) as package:
            shared = IMPORTER._shared_strings(package)
            paths = IMPORTER._sheet_paths(package)
            review = IMPORTER._parse_sheet(package, paths["人工审核1564"], shared)["cells"]
        visible = {}
        all_ids = set()
        for row_number in range(2, IMPORTER.EXPECTED_COUNTS["human"] + 2):
            item_id = review[f"D{row_number}"]
            all_ids.add(item_id)
            if review[f"E{row_number}"] == "adopted_suggestion":
                visible[item_id] = review[f"C{row_number}"]
        self.assertEqual(set(visible), set(expected))
        self.assertEqual(len(visible), 29)
        self.assertEqual(set(adopted), set(expected))
        for item_id, suggestion in visible.items():
            self.assertEqual(suggestion, adopted[item_id])
        self.assertNotIn("LOW-MT-01485", all_ids)

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
                mock.patch.object(
                    TOOL, "verify_user_directed_adoptions", return_value=self.adopted_verification_result(),
                ),
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
