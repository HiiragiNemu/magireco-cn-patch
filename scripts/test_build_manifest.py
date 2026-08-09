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
    def run_manifest(self, package: str, entries: dict[str, bytes]):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            archive = root / "package.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, data in entries.items():
                    zf.writestr(name, data)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--zip",
                    str(archive),
                    "--package",
                    package,
                    "--version",
                    "1",
                    "--out",
                    str(root / "out"),
                    "--ledger-dir",
                    str(root / "ledger"),
                ],
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            manifest = root / "out" / (package + "_manifest.json")
            parsed = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None
            return proc, parsed

    def test_js_requires_engine_table_at_parallel_madomagi_root(self):
        proc, manifest = self.run_manifest(
            "cn_js_update",
            {"magica/js/app.js": b"ok", ENGINE: "原文\t译文\n".encode("utf-8")},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(ENGINE, manifest["files"])

    def test_js_without_engine_table_is_rejected_before_manifest_write(self):
        proc, manifest = self.run_manifest(
            "cn_js_update", {"magica/js/app.js": b"ok"}
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("缺少必需文件", proc.stderr)
        self.assertIsNone(manifest)

    def test_scenario_must_not_retain_migrated_engine_table(self):
        proc, manifest = self.run_manifest(
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
        proc, manifest = self.run_manifest(
            "cn_scenario_update",
            {"madomagi/resource/scenario/json/a.json": b"{}"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(ENGINE, manifest["files"])


if __name__ == "__main__":
    unittest.main()
