#!/usr/bin/env python3
"""Contract tests for the deterministic v26 JS package builder."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile


SCRIPT = Path(__file__).with_name("build-v26-package.py")
SPEC = importlib.util.spec_from_file_location("build_v26_package", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DeterministicV26PackageTest(unittest.TestCase):
    def make_tree(self, root: Path) -> None:
        (root / "magica/js").mkdir(parents=True)
        (root / "magica/template").mkdir(parents=True)
        (root / "magica/research").mkdir(parents=True)
        (root / "magica/i18n_audit").mkdir(parents=True)
        (root / "madomagi").mkdir(parents=True)
        (root / "magica/js/z.js").write_bytes(b"z\n")
        (root / "magica/js/a.js").write_bytes(b"a\n")
        (root / "magica/template/page.html").write_bytes(b"<p>ok</p>\n")
        (root / "magica/research/private.tsv").write_bytes(b"excluded\n")
        (root / "magica/i18n_audit/report.json").write_bytes(b"{}\n")
        (root / MODULE.ENGINE_MEMBER).write_bytes("戻る\t返回\n".encode("utf-8"))

    def test_two_builds_are_identical_and_layout_is_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            first = root / "first.zip"
            second = root / "second.zip"
            report1 = MODULE.build_package(root, first)
            report2 = MODULE.build_package(root, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(report1["sha256"], report2["sha256"])
            self.assertEqual(
                report1["sha256"], hashlib.sha256(first.read_bytes()).hexdigest()
            )
            with zipfile.ZipFile(first) as archive:
                infos = archive.infolist()
                names = [info.filename for info in infos]
                self.assertEqual(names, sorted(names))
                self.assertEqual(names.count(MODULE.ENGINE_MEMBER), 1)
                self.assertTrue(all(
                    name.startswith("magica/") or name == MODULE.ENGINE_MEMBER
                    for name in names
                ))
                self.assertFalse(any(
                    name.startswith(MODULE.FORBIDDEN_PREFIXES) for name in names
                ))
                self.assertEqual(
                    archive.read(MODULE.ENGINE_MEMBER),
                    (root / MODULE.ENGINE_MEMBER).read_bytes(),
                )
                for info in infos:
                    self.assertEqual(info.date_time, MODULE.FIXED_DOS_TIME)
                    self.assertEqual(info.create_system, 3)
                    self.assertEqual(
                        info.external_attr >> 16, stat.S_IFREG | 0o644
                    )
                    self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)
                    self.assertEqual(info.comment, b"")
                    self.assertEqual(info.extra, b"")

    def test_missing_engine_is_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "magica/js").mkdir(parents=True)
            (root / "magica/js/a.js").write_bytes(b"a")
            output = root / "result.zip"
            with self.assertRaisesRegex(MODULE.PackageError, "engine_i18n.tsv"):
                MODULE.build_package(root, output)
            self.assertFalse(output.exists())

    def test_validator_rejects_duplicate_and_forbidden_members(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            inputs = MODULE.discover_inputs(root)
            duplicate = root / "duplicate.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate, "w") as archive:
                    archive.writestr("magica/js/a.js", b"a")
                    archive.writestr("magica/js/a.js", b"b")
            with self.assertRaisesRegex(MODULE.PackageError, "重复路径"):
                MODULE.verify_archive(duplicate, inputs)

            polluted = root / "polluted.zip"
            with zipfile.ZipFile(polluted, "w") as archive:
                archive.writestr(
                    "madomagi/resource/scenario/json/1001.json", b"{}"
                )
            with self.assertRaises(MODULE.PackageError):
                MODULE.verify_archive(polluted, inputs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
