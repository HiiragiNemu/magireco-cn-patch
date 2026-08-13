#!/usr/bin/env python3
"""Regression tests for the v26 authority protection gate."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from v26_authority_protection import (
    EXPECTED_BUCKETS,
    EXPECTED_BUCKETS_WITH_PASS19,
    EXPECTED_CANDIDATE_ONLY_METADATA,
    EXPECTED_MASTER_BUCKETS,
    EXPECTED_MASTER_TOTAL,
    EXPECTED_PASS16_ADDITIONS,
    EXPECTED_PASS16_PROTECTED_FIELDS,
    EXPECTED_PASS19_APPLIED_CHANGES,
    EXPECTED_PASS19_CONTRACTS,
    EXPECTED_PASS19_FINAL_OCCURRENCES,
    EXPECTED_TOTAL,
    EXPECTED_TOTAL_WITH_PASS19,
    GLOSSARY_REL,
    MANIFEST_REL,
    MASTER_REL,
    PASS19_APPLIED_OCCURRENCE_ORDINALS,
    PROTECTED_TSV_REL,
    ProtectionError,
    aggregate_sha256,
    build_snapshot,
    candidate_only_metadata,
    combined_protected_rows,
    compare_baseline_to_master,
    counts_by,
    current_values_for_file,
    protected_rows_from_pass16,
    protected_rows_from_pass19,
    protected_rows_from_master,
    pass19_literal_occurrences,
    read_tsv,
    select_protected_master_rows,
    sha256_file,
    validate_row_hashes,
    verify_current_product_values,
    verify_pass19_applied_rows,
    verify_pass19_authority_evidence,
    verify_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]


class AuthorityProtectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.master = read_tsv(ROOT / MASTER_REL)
        cls.baseline = read_tsv(ROOT / PROTECTED_TSV_REL)

    def test_selection_contract_is_exact(self) -> None:
        selected, held = select_protected_master_rows(self.master)
        self.assertEqual(EXPECTED_MASTER_TOTAL, len(selected))
        self.assertEqual(EXPECTED_MASTER_BUCKETS, counts_by(selected, "source_bucket"))
        self.assertEqual(3, len(held))
        candidates = [row for row in self.master if candidate_only_metadata(row)]
        self.assertEqual(EXPECTED_CANDIDATE_ONLY_METADATA, len(candidates))
        self.assertNotIn(candidates[0], selected)
        self.assertEqual("MT-01965", candidates[0]["record_id"])

    def test_pass16_all_occurrences_are_merged_by_stable_identity(self) -> None:
        pass16 = protected_rows_from_pass16(ROOT)
        combined, merge = combined_protected_rows(self.master, root=ROOT)
        self.assertEqual(EXPECTED_PASS16_PROTECTED_FIELDS, len(pass16))
        self.assertEqual(EXPECTED_TOTAL_WITH_PASS19, len(combined))
        self.assertEqual(EXPECTED_BUCKETS_WITH_PASS19, counts_by(combined, "source_bucket"))
        self.assertEqual(EXPECTED_PASS16_ADDITIONS, merge["pass16_added"])
        self.assertEqual(
            EXPECTED_PASS16_PROTECTED_FIELDS - EXPECTED_PASS16_ADDITIONS,
            merge["pass16_overlap"],
        )
        combined_ids = {row["identity_sha256"] for row in combined}
        self.assertTrue({row["identity_sha256"] for row in pass16} <= combined_ids)
        pass19 = protected_rows_from_pass19(ROOT)
        self.assertEqual(EXPECTED_PASS19_APPLIED_CHANGES, len(pass19))
        self.assertEqual(EXPECTED_PASS19_APPLIED_CHANGES, sum(int(row["expected_count"]) for row in pass19))
        self.assertEqual(len(pass19), len({row["locator_sha256"] for row in pass19}))
        self.assertTrue(all(row["business_key_type"] == "pass19-applied-occurrence" for row in pass19))
        self.assertEqual(
            EXPECTED_PASS19_APPLIED_CHANGES,
            merge["pass19_applied_changes"],
        )
        self.assertEqual(EXPECTED_PASS19_CONTRACTS, merge["pass19_contracts"])
        self.assertEqual(EXPECTED_PASS19_APPLIED_CHANGES, merge["pass19_protected_occurrences"])
        self.assertEqual(EXPECTED_PASS19_FINAL_OCCURRENCES, merge["pass19_final_occurrences"])

    def test_pass19_applied_ordinals_and_external_evidence_are_exact(self) -> None:
        source_rows = read_tsv(
            ROOT / "magica/i18n_audit/release_v26_authority/pass19_official_static_corrections.tsv"
        )
        evidence = verify_pass19_authority_evidence(source_rows, require_available=True)
        self.assertEqual(EXPECTED_PASS19_CONTRACTS, evidence["checked_rows"])
        self.assertEqual(0, evidence["unavailable_rows"])
        protected = protected_rows_from_pass19(ROOT)
        actual: dict[str, list[int]] = {}
        for row in protected:
            ordinal = int(row["business_key"].rsplit("-", 1)[1])
            actual.setdefault(row["master_record_id"], []).append(ordinal)
        self.assertEqual(
            {key: list(value) for key, value in PASS19_APPLIED_OCCURRENCE_ORDINALS.items()},
            {key: sorted(value) for key, value in sorted(actual.items())},
        )

    def test_pass19_context_anchor_is_value_independent_and_unique(self) -> None:
        source = next(
            row
            for row in read_tsv(
                ROOT / "magica/i18n_audit/release_v26_authority/pass19_official_static_corrections.tsv"
            )
            if row["change_id"] == "P19-00005"
        )
        text = (ROOT / source["file"]).read_text(encoding="utf-8")
        occurrences = pass19_literal_occurrences(text, source["after"])
        self.assertEqual(int(source["expected_after_count"]), len(occurrences))
        self.assertEqual(len(occurrences), len({row["anchor_sha256"] for row in occurrences}))

    def test_two_wiki_equivalences_and_confirmed_human_fields_are_protected(self) -> None:
        expected = {
            ("magica/js/libs/pieceList.json", "1561", "description"),
            ("magica/js/libs/pieceList.json", "1973", "description"),
            ("magica/js/libs/charaMessageList.json", "1040|70", "message"),
            ("magica/js/libs/charaMessageList.json", "3058|61", "message"),
            ("magica/js/libs/itemList.json", "EVENT_DAILYTOWER_1218_EXCHANGE_2", "description"),
            ("magica/js/libs/itemList.json", "EVENT_DAILYTOWER_1218_EXCHANGE_2", "shortDescription"),
            ("magica/js/libs/sectionList.json", "102704", "areaDetailName"),
            ("magica/js/libs/sectionList.json", "102921", "areaDetailName"),
            ("magica/js/libs/shopItemList.json", "10620", "name"),
            ("magica/js/libs/shopItemList.json", "11003", "name"),
            ("magica/js/libs/shopItemList.json", "15980", "name"),
            ("magica/js/libs/shopItemList.json", "22134", "name"),
            ("magica/js/libs/shopItemList.json", "28596", "name"),
        }
        actual = {
            (row["file"], row["business_key"], row["field"])
            for row in self.baseline
        }
        self.assertTrue(expected <= actual)
        self.assertNotIn(
            ("magica/js/libs/emotionSkillMap.json", "2203113", "name"),
            actual,
        )

    def test_committed_snapshot_verifies_without_freshness_side_effects(self) -> None:
        report = verify_snapshot(ROOT, require_freshness=False)
        self.assertEqual("PASS", report["status"])
        self.assertEqual(EXPECTED_TOTAL_WITH_PASS19, report["protected_fields"])

    def test_value_hash_tamper_fails(self) -> None:
        rows = copy.deepcopy(self.baseline)
        rows[0]["protected_value"] += "篡改"
        with self.assertRaisesRegex(ProtectionError, "value hash mismatch"):
            validate_row_hashes(rows)

    def test_lower_tier_cannot_overwrite_official_value(self) -> None:
        master = copy.deepcopy(self.master)
        target = next(row for row in master if row["source_bucket"] == "official")
        target["current_cn"] += "低权重覆盖"
        with self.assertRaisesRegex(ProtectionError, "protected field/provenance drift"):
            compare_baseline_to_master(self.baseline, master, root=ROOT)

    def test_authority_demotion_fails(self) -> None:
        master = copy.deepcopy(self.master)
        target = next(row for row in master if row["source_bucket"] == "official")
        target["source_bucket"] = "unknown"
        with self.assertRaisesRegex(ProtectionError, "protected selection count drift"):
            compare_baseline_to_master(self.baseline, master, root=ROOT)

    def test_builder_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_dir = Path(first)
            second_dir = Path(second)
            first_tsv = first_dir / "protected.tsv"
            first_manifest = first_dir / "manifest.json"
            second_tsv = second_dir / "protected.tsv"
            second_manifest = second_dir / "manifest.json"
            build_snapshot(ROOT, output_tsv=first_tsv, output_manifest=first_manifest)
            build_snapshot(ROOT, output_tsv=second_tsv, output_manifest=second_manifest)
            self.assertEqual(sha256_file(first_tsv), sha256_file(second_tsv))
            # Absolute temporary paths are intentionally represented in an
            # out-of-tree manifest.  Compare semantic content after removing it.
            a = json.loads(first_manifest.read_text(encoding="utf-8"))
            b = json.loads(second_manifest.read_text(encoding="utf-8"))
            a["baseline"]["protected_fields_tsv"] = "OUTSIDE"
            b["baseline"]["protected_fields_tsv"] = "OUTSIDE"
            self.assertEqual(a, b)

    def test_mixed_runtime_file_allows_unprotected_change(self) -> None:
        rows = [row for row in self.baseline if row["file"] == "magica/js/libs/itemList.json"]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / rows[0]["file"]
            target.parent.mkdir(parents=True)
            data = json.loads((ROOT / rows[0]["file"]).read_text(encoding="utf-8-sig"))
            protected_keys = {row["business_key"] for row in rows}
            unprotected = next(item for item in data if str(item["itemCode"]) not in protected_keys)
            unprotected["name"] = "允许修改的低权重字段"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            actual = current_values_for_file(root, rows)
            self.assertEqual(len(rows), len(actual))

    def test_direct_protected_runtime_mutation_fails_release_gate(self) -> None:
        rows = [row for row in self.baseline if row["file"] == "magica/js/libs/itemList.json"]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / rows[0]["file"]
            target.parent.mkdir(parents=True)
            data = json.loads((ROOT / rows[0]["file"]).read_text(encoding="utf-8-sig"))
            victim = rows[0]
            item = next(item for item in data if str(item["itemCode"]) == victim["business_key"])
            item[victim["field"]] += "篡改"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ProtectionError, "protected product value drift"):
                verify_current_product_values(root, rows)

    def test_pass16_only_field_mutation_fails_release_gate(self) -> None:
        victim = next(
            row
            for row in self.baseline
            if row["file"] == "magica/js/libs/pieceList.json"
            and row["business_key"] == "1561"
            and row["field"] == "description"
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / victim["file"]
            target.parent.mkdir(parents=True)
            data = json.loads((ROOT / victim["file"]).read_text(encoding="utf-8-sig"))
            item = next(item for item in data if str(item["pieceId"]) == victim["business_key"])
            item[victim["field"]] += "篡改"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ProtectionError, "protected product value drift"):
                verify_current_product_values(root, [victim])

    def test_glossary_whole_file_digest_is_locked(self) -> None:
        manifest = json.loads((ROOT / MANIFEST_REL).read_text(encoding="utf-8"))
        expected = manifest["whole_file_protections"][GLOSSARY_REL.as_posix()]["sha256"]
        self.assertEqual(expected, sha256_file(ROOT / GLOSSARY_REL))

    def test_aggregate_is_stable_after_readback(self) -> None:
        generated, _merge = combined_protected_rows(self.master, root=ROOT)
        self.assertEqual(aggregate_sha256(self.baseline), aggregate_sha256(generated))

    def test_pass19_literal_or_occurrence_drift_fails(self) -> None:
        source = next(row for row in read_tsv(ROOT / "magica/i18n_audit/release_v26_authority/pass19_official_static_corrections.tsv") if row["change_id"] == "P19-00002")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / source["file"]
            target.parent.mkdir(parents=True)
            text = (ROOT / source["file"]).read_text(encoding="utf-8")
            target.write_text(text.replace(source["after"], source["before"], 1), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ProtectionError, "Pass19 applied value/count drift"):
                verify_pass19_applied_rows(root, [source])


if __name__ == "__main__":
    unittest.main(verbosity=2)
