#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
APPLY = ROOT / "tools" / "i18n-apply.py"
BUILDER = ROOT / "tools" / "i18n-build-effective.py"


def normalized_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class CanonicalEffectiveApplyTests(unittest.TestCase):
    def make_bundle(self, root: Path) -> tuple[Path, Path, Path]:
        i18n = root / "i18n"
        generated = i18n / "generated"
        product = root / "magica"
        generated.mkdir(parents=True)
        (product / "js").mkdir(parents=True)

        (i18n / "frontend-strings.tsv").write_text(
            "# 原文\t译文\t风险\t出现次数\t出现于\n"
            "キモチ戦\t心情战\t\t1\tjs/sample.js\n"
            "キモチ戦は\t心情战\t\t1\tjs/sample.js\n",
            encoding="utf-8",
            newline="\n",
        )
        (i18n / "glossary.tsv").write_text("# 日文\t中文\n", encoding="utf-8", newline="\n")
        (i18n / "overrides.tsv").write_text("# empty\n", encoding="utf-8", newline="\n")
        (i18n / "fragments.tsv").write_text("# empty\n", encoding="utf-8", newline="\n")
        (i18n / "reviewed-candidates.tsv").write_text(
            "# fixture reviewed authority\nキモチ戦\t心魔战\nキモチ戦は\t心魔战\n",
            encoding="utf-8",
            newline="\n",
        )
        (i18n / "authority-policy.json").write_text(
            '{"fixture":"policy"}\n', encoding="utf-8", newline="\n"
        )
        (i18n / "migration-source-summary.json").write_text(
            '{"fixture":"migration"}\n', encoding="utf-8", newline="\n"
        )

        columns = (
            "key", "scope", "path_prefix", "source_text", "selected_cn", "authority",
            "weight", "source_file", "source_line", "source_batch", "evidence",
        )
        effective = generated / "effective.tsv"
        with effective.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            for ordinal, source in enumerate(("キモチ戦", "キモチ戦は"), 1):
                writer.writerow({
                    "key": "global:fixture%d" % ordinal,
                    "scope": "global",
                    "path_prefix": "",
                    "source_text": source,
                    "selected_cn": "心魔战",
                    "authority": "official_cn_dump",
                    "weight": "500",
                    "source_file": "i18n/reviewed-candidates.tsv",
                    "source_line": str(ordinal + 1),
                    "source_batch": "fixture-official",
                    "evidence": "fixture",
                })

        summary = {
            "schema_version": 1,
            "mode": "audit-only",
            "result": "pass",
            "fatal_equal_weight_conflicts": 0,
            "product_tree_writes": 0,
            "magica_consumed": False,
            "runtime_consumed": False,
            "effective_rows": 2,
            "producer": {
                "path": "tools/i18n-build-effective.py",
                "normalized_lf_sha256": normalized_sha256(BUILDER),
            },
            "input_tables": {
                name: {"normalized_lf_sha256": normalized_sha256(i18n / name)}
                for name in (
                    "frontend-strings.tsv", "glossary.tsv", "overrides.tsv",
                    "fragments.tsv", "reviewed-candidates.tsv",
                )
            },
            "input_contracts": {
                name: {"normalized_lf_sha256": normalized_sha256(i18n / name)}
                for name in ("authority-policy.json", "migration-source-summary.json")
            },
            "generated_outputs": {
                "effective.tsv": {
                    "data_rows": 2,
                    "normalized_lf_sha256": normalized_sha256(effective),
                }
            },
        }
        (generated / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        sample = product / "js" / "sample.js"
        sample.write_text(
            'const title = "キモチ戦"; const condition = "キモチ戦は";\n',
            encoding="utf-8",
            newline="\n",
        )
        return i18n, product, sample

    def run_apply(self, product: Path, table: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(APPLY), str(product), str(table), *extra],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            capture_output=True,
            check=False,
        )

    def test_canonical_apply_uses_verified_effective_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            i18n, product, sample = self.make_bundle(Path(tmp))
            result = self.run_apply(product, i18n / "frontend-strings.tsv")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("canonical effective 已验证", result.stdout)
            self.assertIn("权威覆盖 2 条", result.stdout)
            self.assertEqual(
                sample.read_text(encoding="utf-8"),
                'const title = "心魔战"; const condition = "心魔战";\n',
            )

    def test_missing_effective_fails_closed_before_product_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            i18n, product, sample = self.make_bundle(Path(tmp))
            before = sample.read_bytes()
            (i18n / "generated" / "effective.tsv").unlink()
            result = self.run_apply(product, i18n / "frontend-strings.tsv")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("缺少 canonical effective 表", result.stderr)
            self.assertEqual(sample.read_bytes(), before)

    def test_changed_authority_input_makes_effective_stale_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            i18n, product, sample = self.make_bundle(Path(tmp))
            before = sample.read_bytes()
            with (i18n / "reviewed-candidates.tsv").open("a", encoding="utf-8", newline="") as handle:
                handle.write("追加源\t追加译文\n")
            result = self.run_apply(product, i18n / "frontend-strings.tsv")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("effective 视图陈旧", result.stderr)
            self.assertEqual(sample.read_bytes(), before)

    def test_generated_bundle_is_byte_deterministic_across_two_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_a = Path(tmp) / "a"
            out_b = Path(tmp) / "b"
            for out in (out_a, out_b):
                result = subprocess.run(
                    [sys.executable, str(BUILDER), "--out-dir", str(out)],
                    cwd=ROOT,
                    text=True,
                    encoding="utf-8",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in ("effective.tsv", "conflicts.tsv", "input-provenance.tsv", "summary.json"):
                self.assertEqual((out_a / name).read_bytes(), (out_b / name).read_bytes(), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
