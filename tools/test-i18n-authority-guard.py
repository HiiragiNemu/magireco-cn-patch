#!/usr/bin/env python3
"""Regression tests for ``i18n-authority-guard.py``."""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "tools" / "i18n-authority-guard.py"
SPEC = importlib.util.spec_from_file_location("i18n_authority_guard", GUARD_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import machinery failure
    raise RuntimeError(f"cannot load {GUARD_PATH}")
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class AuthorityGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = guard.load_json(ROOT / "i18n" / "authority-policy.json")
        cls.rows, cls.read_errors = guard.read_provenance(
            ROOT / "i18n" / "authority-provenance.tsv"
        )

    def test_repository_contract_passes(self) -> None:
        report = guard.validate_repository(ROOT)
        self.assertTrue(report["ok"], "\n".join(report["errors"]))
        self.assertEqual(report["json_dictionaries"], 32)
        self.assertEqual(report["jquery_dictionaries"], 32)

    def test_authority_weights_are_fixed(self) -> None:
        self.assertEqual(guard.validate_policy(self.policy), [])
        altered = copy.deepcopy(self.policy)
        altered["authority_order"][-1]["weight"] = 301
        errors = guard.validate_policy(altered)
        self.assertTrue(any("authority weights changed" in error for error in errors))

    def test_official_absence_falls_through_to_wiki(self) -> None:
        self.assertEqual(self.read_errors, [])
        errors = guard.validate_provenance(self.policy, copy.deepcopy(self.rows))
        self.assertEqual(errors, [])

    def test_lower_weight_candidate_cannot_override_wiki(self) -> None:
        rows = copy.deepcopy(self.rows)
        for row in rows:
            if row["term_id"] != "chara_1051_name":
                continue
            if row["authority"] == "wiki":
                row["selected"] = "false"
            elif row["candidate_cn"] == "赫尔卡":
                row["status"] = "present"
                row["selected"] = "true"
        errors = guard.validate_provenance(self.policy, rows)
        self.assertTrue(any("lower-weight candidate selected" in error for error in errors))

    def test_equal_weight_conflict_fails_closed(self) -> None:
        rows = copy.deepcopy(self.rows)
        conflict = next(
            copy.deepcopy(row)
            for row in rows
            if row["term_id"] == "chara_1052_name" and row["authority"] == "wiki"
        )
        conflict["candidate_cn"] = "同权重冲突候选"
        conflict["selected"] = "false"
        rows.append(conflict)
        errors = guard.validate_provenance(self.policy, rows)
        self.assertTrue(any("equal-weight authority conflict" in error for error in errors))

    def test_known_bad_names_are_blocked_in_visible_fields(self) -> None:
        sample = {
            "itemList": [{"name": "东洋"}],
            "sectionList": [{"title": "丰的 Doppel"}],
        }
        errors = guard.find_forbidden(self.policy, sample, source="test")
        self.assertTrue(any("东洋" in error for error in errors))
        self.assertTrue(any("丰的 Doppel" in error for error in errors))

    def test_contextual_name_rule_does_not_block_unrelated_prose(self) -> None:
        sample = {"itemList": [{"description": "东洋文化是普通语境，不是角色名。"}]}
        errors = guard.find_forbidden(self.policy, sample, source="test")
        self.assertFalse(any("东洋" in error for error in errors))

    def test_glossary_contains_wiki_canonical_names(self) -> None:
        mapping, errors = guard.load_glossary(ROOT / "i18n" / "glossary.tsv")
        self.assertEqual(errors, [])
        self.assertEqual(guard.validate_glossary(self.policy, mapping), [])
        self.assertEqual(mapping["ヘルカ"], "赫露迦")
        self.assertEqual(mapping["トヨ"], "台与")
        self.assertEqual(mapping["アマリュリス"], "阿玛琉莉丝")


if __name__ == "__main__":
    unittest.main(verbosity=2)
