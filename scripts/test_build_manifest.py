#!/usr/bin/env python3
"""回归检查热更包清单的跨包文件所有权。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("build_manifest.py")
ENGINE = "madomagi/engine_i18n.tsv"


class BuildManifestOwnershipTest(unittest.TestCase):
    def run_manifest(
        self,
        package: str,
        entries: dict[str, bytes] | list[tuple[str, bytes]],
        manifest_name: str | None = None,
        ledger_mode: str = "update",
        seed_ledger: dict | None = None,
        version: int = 1,
    ):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "package.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
                source_entries = entries.items() if isinstance(entries, dict) else entries
                for name, data in source_entries:
                    zf.writestr(name, data)
            ledger_dir = root / "ledger"
            ledger_path = ledger_dir / f"{package}_ledger.json"
            if seed_ledger is not None:
                ledger_dir.mkdir(parents=True)
                ledger_path.write_text(
                    json.dumps(seed_ledger, ensure_ascii=False, indent=1),
                    encoding="utf-8",
                )
                ledger_before = ledger_path.read_bytes()
            else:
                ledger_before = None
            cmd = [
                    sys.executable,
                    str(SCRIPT),
                    "--zip",
                    str(archive),
                    "--package",
                    package,
                    "--version",
                    str(version),
                    "--out",
                    str(root / "out"),
                    "--ledger-dir",
                    str(ledger_dir),
                    "--ledger-mode",
                    ledger_mode,
                ]
            if manifest_name is not None:
                cmd.extend(["--manifest-name", manifest_name])
            proc = subprocess.run(
                cmd,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            manifest = root / "out" / (manifest_name or (package + "_manifest.json"))
            parsed = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None
            ledger_after = ledger_path.read_bytes() if ledger_path.exists() else None
            return proc, parsed, ledger_before, ledger_after

    def test_js_requires_engine_table_at_parallel_madomagi_root(self):
        proc, manifest, _, _ = self.run_manifest(
            "cn_js_update",
            {"magica/js/app.js": b"ok", ENGINE: "原文\t译文\n".encode("utf-8")},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(ENGINE, manifest["files"])

    def test_js_without_engine_table_is_rejected_before_manifest_write(self):
        proc, manifest, _, _ = self.run_manifest(
            "cn_js_update", {"magica/js/app.js": b"ok"}
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("缺少必需文件", proc.stderr)
        self.assertIsNone(manifest)

    def test_scenario_must_not_retain_migrated_engine_table(self):
        proc, manifest, _, _ = self.run_manifest(
            "cn_scenario_update",
            {
                "madomagi/resource/scenario/json/a.json": b"{}",
                ENGINE: b"old",
            },
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("仍含已迁出的文件", proc.stderr)
        self.assertIsNone(manifest)

    def test_scenario_without_engine_table_remains_valid(self):
        proc, manifest, _, _ = self.run_manifest(
            "cn_scenario_update",
            {"madomagi/resource/scenario/json/a.json": b"{}"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(ENGINE, manifest["files"])

    def test_preview_manifest_uses_new_name_without_formal_name(self):
        preview_name = "cn_js_update_manifest_new.json"
        proc, manifest, _, _ = self.run_manifest(
            "cn_js_update",
            {"magica/js/app.js": b"ok", ENGINE: b"source\ttarget\n"},
            preview_name,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNotNone(manifest)

    def test_duplicate_file_members_are_rejected_before_manifest_write(self):
        proc, manifest, _, _ = self.run_manifest(
            "cn_js_update",
            [
                ("magica/js/app.js", b"first"),
                ("magica/js/app.js", b"second"),
                (ENGINE, b"source\ttarget\n"),
            ],
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("重复文件路径", proc.stderr)
        self.assertIsNone(manifest)

    def test_preview_check_mode_reads_but_does_not_rewrite_ledger(self):
        seed = {
            "schema": 1,
            "package": "cn_js_update",
            "last_version": 25,
            "total_paths_ever": 3,
            "current_paths": 3,
            "paths": {
                "magica/js/app.js": {
                    "first_version": 25,
                    "last_version": 25,
                    "current": True,
                },
                "magica/js/removed.js": {
                    "first_version": 25,
                    "last_version": 25,
                    "current": True,
                },
                ENGINE: {
                    "first_version": 25,
                    "last_version": 25,
                    "current": True,
                },
            },
        }
        proc, manifest, before, after = self.run_manifest(
            "cn_js_update",
            {"magica/js/app.js": b"new", ENGINE: b"source\ttarget\n"},
            manifest_name="cn_js_update_manifest_new.json",
            ledger_mode="check",
            seed_ledger=seed,
            version=26,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNotNone(manifest)
        self.assertEqual(before, after)
        self.assertIn("账本未写回", proc.stdout)
        self.assertIn("这一版比上一版少了 1 个文件", proc.stdout)

    def test_publish_update_mode_advances_ledger(self):
        seed = {
            "schema": 1,
            "package": "cn_js_update",
            "last_version": 25,
            "total_paths_ever": 2,
            "current_paths": 2,
            "paths": {
                "magica/js/app.js": {
                    "first_version": 25,
                    "last_version": 25,
                    "current": True,
                },
                ENGINE: {
                    "first_version": 25,
                    "last_version": 25,
                    "current": True,
                },
            },
        }
        proc, _, before, after = self.run_manifest(
            "cn_js_update",
            {
                "magica/js/app.js": b"new",
                "magica/js/new.js": b"new",
                ENGINE: b"source\ttarget\n",
            },
            ledger_mode="update",
            seed_ledger=seed,
            version=26,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(before, after)
        parsed = json.loads(after.decode("utf-8"))
        self.assertEqual(parsed["last_version"], 26)
        self.assertTrue(parsed["paths"]["magica/js/new.js"]["current"])

    def test_ledger_version_regression_fails_without_rewrite(self):
        seed = {
            "schema": 1,
            "package": "cn_js_update",
            "last_version": 25,
            "paths": {},
        }
        proc, manifest, before, after = self.run_manifest(
            "cn_js_update",
            {"magica/js/app.js": b"new", ENGINE: b"source\ttarget\n"},
            ledger_mode="update",
            seed_ledger=seed,
            version=24,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("候选版本不得倒退", proc.stderr)
        self.assertIsNone(manifest)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
