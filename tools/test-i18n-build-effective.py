#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "i18n-build-effective.py"
UI_BUILDER = ROOT / "scripts" / "build_ui_text_source.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i18n_build_effective", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


MOD = load_tool()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


class EffectiveAuthorityTests(unittest.TestCase):
    def test_repository_snapshot_and_provenance(self):
        result = subprocess.run(
            [sys.executable, str(TOOL)],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads((ROOT / "i18n/generated/summary.json").read_text(encoding="utf-8"))
        tables = summary["input_tables"]
        self.assertEqual(
            (tables["frontend-strings.tsv"]["data_rows"],
             tables["frontend-strings.tsv"]["present_candidates"],
             tables["frontend-strings.tsv"]["absent_candidates"]),
            (1685, 1632, 53),
        )
        self.assertEqual(
            tables["frontend-strings.tsv"]["source_batch_counts"],
            {
                "legacy-claude-ai-assisted": 315,
                "legacy-kimi-ai-assisted": 1290,
                "pass21-user-directed-machine-suggestion": 27,
            },
        )
        self.assertEqual(tables["glossary.tsv"]["data_rows"], 955)
        self.assertEqual(
            tables["glossary.tsv"]["source_batch_counts"],
            {"wiki-canonical-lock": 3, "wiki-migrated-glossary": 952},
        )
        self.assertEqual(tables["overrides.tsv"]["present_candidates"], 9)
        self.assertEqual(tables["fragments.tsv"]["present_candidates"], 7)
        self.assertEqual(summary["human_reviewed_candidates"], 0)
        self.assertEqual(
            tables["reviewed-candidates.tsv"]["authority_counts"],
            {"new_proposal": 1565, "official_cn_dump": 62},
        )
        self.assertEqual(
            tables["reviewed-candidates.tsv"]["source_batch_counts"]
            ["official-cn-static-pass20-20260815"],
            58,
        )
        self.assertEqual(
            tables["reviewed-candidates.tsv"]["source_batch_counts"]
            ["pass20-rough-production-final-values-v1"],
            1565,
        )
        self.assertEqual(summary["fatal_equal_weight_conflicts"], 0)
        self.assertEqual(summary["resolved_conflicts"], 48)
        self.assertEqual(summary["product_tree_writes"], 0)
        self.assertFalse(summary["magica_consumed"])
        self.assertFalse(summary["runtime_consumed"])
        self.assertEqual(summary["producer"]["path"], "tools/i18n-build-effective.py")
        self.assertEqual(
            summary["producer"]["normalized_lf_sha256"],
            MOD.normalized_sha256(TOOL),
        )
        self.assertEqual(
            summary["input_contracts"]["authority-policy.json"]["normalized_lf_sha256"],
            MOD.normalized_sha256(ROOT / "i18n/authority-policy.json"),
        )
        self.assertEqual(
            summary["input_contracts"]["migration-source-summary.json"]["normalized_lf_sha256"],
            MOD.normalized_sha256(ROOT / "i18n/migration-source-summary.json"),
        )
        for output_name, expected_rows in (
            ("input-provenance.tsv", 4283),
            ("effective.tsv", 2583),
            ("conflicts.tsv", 48),
        ):
            record = summary["generated_outputs"][output_name]
            self.assertEqual(record["data_rows"], expected_rows)
            self.assertEqual(
                record["normalized_lf_sha256"],
                MOD.normalized_sha256(ROOT / "i18n/generated" / output_name),
            )

        provenance = read_tsv(ROOT / "i18n/generated/input-provenance.tsv")
        self.assertEqual(len(provenance), 4283)
        frontend_present = [
            row for row in provenance
            if row["source_file"] == "i18n/frontend-strings.tsv" and row["status"] == "present"
        ]
        self.assertEqual(len(frontend_present), 1632)
        self.assertEqual(
            {row["authority"] for row in frontend_present},
            {"legacy_unverified_ai_assisted"},
        )
        self.assertNotIn("human-reviewed", {row["status"] for row in provenance})
        rough_present = [
            row for row in provenance
            if row["source_file"] == "i18n/reviewed-candidates.tsv"
            and row["authority"] == "new_proposal"
            and row["status"] == "present"
        ]
        self.assertEqual(len(rough_present), 1565)
        self.assertEqual(
            {row["source_batch"] for row in rough_present},
            {"pass20-rough-production-final-values-v1"},
        )

        effective = read_tsv(ROOT / "i18n/generated/effective.tsv")
        canonical = {
            row["source_text"]: row for row in effective if row["scope"] == "global"
        }
        self.assertEqual((canonical["ヘルカ"]["selected_cn"], canonical["ヘルカ"]["authority"]),
                         ("赫露迦", "wiki"))
        self.assertEqual((canonical["トヨ"]["selected_cn"], canonical["トヨ"]["authority"]),
                         ("台与", "wiki"))
        self.assertEqual(
            (canonical["アマリュリス"]["selected_cn"], canonical["アマリュリス"]["authority"]),
            ("阿玛琉莉丝", "wiki"),
        )
        self.assertEqual((canonical["サポート"]["selected_cn"], canonical["サポート"]["authority"]),
                         ("辅助", "wiki"))
        self.assertEqual((canonical["HP回復"]["selected_cn"], canonical["HP回復"]["authority"]),
                         ("回复HP", "wiki"))
        self.assertEqual(
            (canonical["属性相性"]["selected_cn"], canonical["属性相性"]["authority"]),
            ("属性克制", "official_cn_dump"),
        )
        self.assertEqual(
            (canonical["キモチ戦"]["selected_cn"], canonical["キモチ戦"]["authority"]),
            ("心魔战", "official_cn_dump"),
        )
        self.assertEqual(
            (canonical["キモチ戦は"]["selected_cn"], canonical["キモチ戦は"]["authority"]),
            ("心魔战", "official_cn_dump"),
        )

    def test_ui_text_index_has_no_human_review_claim(self):
        result = subprocess.run(
            [sys.executable, str(UI_BUILDER)],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((ROOT / "i18n/uiTextList.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1632)
        self.assertEqual({entry["status"] for entry in data.values()},
                         {"legacy-unverified-ai-assisted"})
        batches = {}
        for entry in data.values():
            batches[entry["sourceBatch"]] = batches.get(entry["sourceBatch"], 0) + 1
            self.assertNotEqual(entry.get("authority"), "existing_human_reviewed")
        self.assertEqual(
            batches,
            {
                "legacy-claude-ai-assisted": 315,
                "legacy-kimi-ai-assisted": 1290,
                "pass21-user-directed-machine-suggestion": 27,
            },
        )
        proposals = [entry["proposal"] for entry in data.values() if "proposal" in entry]
        self.assertEqual(len(proposals), 3)
        self.assertTrue(all(item["authority"] == "new_proposal" for item in proposals))
        self.assertTrue(all(item["selected"] is False for item in proposals))

        runtime_build_text = (
            (ROOT / "Build_JS_Injector.py").read_text(encoding="utf-8-sig")
            + (ROOT / ".github/workflows/sync-and-upload.yml").read_text(encoding="utf-8-sig")
        )
        self.assertNotIn("uiTextList", runtime_build_text)
        self.assertNotIn("build_ui_text_source", runtime_build_text)

    def test_equal_weight_conflict_writes_report_and_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            i18n = root / "i18n"
            out = i18n / "generated"
            i18n.mkdir()
            (i18n / "frontend-strings.tsv").write_text(
                "# 原文\t译文\t风险\t出现次数\t出现于\n"
                "同一原文\t候选甲\t\t1\ta.js\n"
                "同一原文\t候选乙\t\t1\tb.js\n",
                encoding="utf-8",
                newline="\n",
            )
            (i18n / "glossary.tsv").write_text("# 日文\t中文\n", encoding="utf-8", newline="\n")
            (i18n / "overrides.tsv").write_text("# empty\n", encoding="utf-8", newline="\n")
            (i18n / "fragments.tsv").write_text("# empty\n", encoding="utf-8", newline="\n")
            lineage = {
                MOD.fingerprint("同一原文", "候选甲"): "legacy-test-batch",
                MOD.fingerprint("同一原文", "候选乙"): "legacy-test-batch",
            }
            source_tables = {}
            for name in ("frontend-strings.tsv", "glossary.tsv", "overrides.tsv", "fragments.tsv"):
                data_rows = len(MOD.read_data_rows(i18n / name))
                source_tables[name] = {
                    "data_rows": data_rows,
                    "normalized_lf_sha256": MOD.normalized_sha256(i18n / name),
                }
            source_tables["frontend-strings.tsv"].update(
                {"translated_candidate_lineage": lineage, "translation_batches": []}
            )
            source_tables["glossary.tsv"]["wiki_authority_locks"] = []
            migration = {"source_tables": source_tables}
            migration_path = i18n / "migration-source-summary.json"
            migration_path.write_text(
                json.dumps(migration, ensure_ascii=False), encoding="utf-8", newline="\n"
            )
            sentinel = root / "magica" / "sentinel.txt"
            sentinel.parent.mkdir()
            sentinel.write_text("unchanged", encoding="utf-8")
            summary, exit_code = MOD.run(
                i18n_dir=i18n,
                out_dir=out,
                policy_path=ROOT / "i18n/authority-policy.json",
                migration_path=migration_path,
            )
            self.assertEqual(exit_code, 2)
            self.assertEqual(summary["fatal_equal_weight_conflicts"], 1)
            self.assertEqual(summary["effective_rows"], 0)
            conflicts = read_tsv(out / "conflicts.tsv")
            self.assertEqual(conflicts[0]["resolution"], "fatal-equal-weight-conflict")
            self.assertEqual(conflicts[0]["fatal"], "true")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")

    def test_unknown_changed_frontend_candidate_is_rejected(self):
        migration = json.loads(
            (ROOT / "i18n/migration-source-summary.json").read_text(encoding="utf-8")
        )
        rows = {
            "frontend-strings.tsv": [(2, ["閉じる", "未登记的新译文", "", "1", "x.js"])],
            "glossary.tsv": [],
            "overrides.tsv": [],
            "fragments.tsv": [],
        }
        with self.assertRaises(MOD.AuditError):
            MOD.build_candidates(
                rows,
                migration,
                dict(MOD.EXPECTED_MAINTENANCE_ORDER),
            )

    def test_official_reviewed_candidate_requires_exact_evidence(self):
        migration = json.loads(
            (ROOT / "i18n/migration-source-summary.json").read_text(encoding="utf-8")
        )
        rows = {
            "frontend-strings.tsv": [], "glossary.tsv": [],
            "overrides.tsv": [], "fragments.tsv": [],
        }
        bad_reviewed = [(3, [
            "global", "", "属性相性", "属性克制", "present", "official_cn_dump",
            "official-test", "D:/official.html#node", "", "exact-path-dom-match",
            "false", "exact", "official-source-verified", "fixture",
        ])]
        with self.assertRaises(MOD.AuditError):
            MOD.build_candidates(
                rows, migration, dict(MOD.EXPECTED_MAINTENANCE_ORDER), bad_reviewed
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
