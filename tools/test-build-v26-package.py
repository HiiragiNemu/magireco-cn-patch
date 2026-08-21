#!/usr/bin/env python3
"""Contract tests for the deterministic v26 JS package builder."""

from __future__ import annotations

import hashlib
import importlib.util
import json
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
    def test_native_repair_tree_is_git_byte_exact(self):
        attributes = (MODULE.ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("madomagi/resource/image_native/** -text", attributes)

    def make_tree(self, root: Path) -> None:
        (root / "magica/js").mkdir(parents=True)
        (root / "magica/template").mkdir(parents=True)
        (root / "magica/resource/image_web/common").mkdir(parents=True)
        (root / "magica/research").mkdir(parents=True)
        (root / "magica/i18n_audit").mkdir(parents=True)
        (root / "madomagi").mkdir(parents=True)
        (root / "madomagi/resource/image_native/chara").mkdir(parents=True)
        (root / "magica/js/z.js").write_bytes(b"z\n")
        (root / "magica/js/a.js").write_bytes(b"a\n")
        (root / "magica/template/page.html").write_bytes(b"<p>ok</p>\n")
        image_member = "magica/resource/image_web/common/translated.png"
        image_bytes = b"localized-image"
        (root / image_member).write_bytes(image_bytes)
        image_manifest = root / MODULE.IMAGE_WEB_MANIFEST
        image_manifest.parent.mkdir(parents=True, exist_ok=True)
        image_manifest.write_text(
            json.dumps({
                "schema": "magireco-image-web-product-manifest/v1",
                "entry_count": 1,
                "entries": [{
                    "path": image_member,
                    "bytes": len(image_bytes),
                    "authority": "official-cn",
                    "evidence": "fixture",
                }],
            }),
            encoding="utf-8",
        )
        (root / "magica/research/private.tsv").write_bytes(b"excluded\n")
        (root / "magica/i18n_audit/report.json").write_bytes(b"{}\n")
        (root / MODULE.ENGINE_MEMBER).write_bytes("戻る\t返回\n".encode("utf-8"))
        repair_member = MODULE.REPAIR_PREFIX + "chara/sample.png"
        repair_bytes = b"repair-png"
        (root / repair_member).write_bytes(repair_bytes)
        (root / MODULE.REPAIR_MANIFEST).write_text(
            json.dumps({
                "schema": "magireco-cn-madomagi-repair/v1",
                "file_count": 1,
                "total_bytes": len(repair_bytes),
                "entries": [{"path": repair_member, "bytes": len(repair_bytes)}],
            }),
            encoding="utf-8",
        )

    def test_two_builds_are_identical_and_layout_is_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            first = root / "first.zip"
            second = root / "second.zip"
            report1 = MODULE.build_package(root, first)
            report2 = MODULE.build_package(root, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(report1["image_web_entries"], 1)
            self.assertEqual(report1["sha256"], report2["sha256"])
            self.assertEqual(
                report1["sha256"], hashlib.sha256(first.read_bytes()).hexdigest()
            )
            with zipfile.ZipFile(first) as archive:
                infos = archive.infolist()
                names = [info.filename for info in infos]
                self.assertEqual(names, sorted(names))
                self.assertEqual(names.count(MODULE.ENGINE_MEMBER), 1)
                self.assertEqual(names.count(MODULE.REPAIR_MANIFEST), 1)
                self.assertTrue(all(
                    name.startswith("magica/")
                    or name == MODULE.ENGINE_MEMBER
                    or name == MODULE.REPAIR_MANIFEST
                    or name.startswith(MODULE.REPAIR_PREFIX)
                    for name in names
                ))
                self.assertEqual(
                    sum(name.startswith(MODULE.REPAIR_PREFIX) for name in names), 1
                )
                self.assertFalse(any(
                    name.startswith(MODULE.FORBIDDEN_PREFIXES) for name in names
                ))
                self.assertEqual(
                    archive.read(MODULE.ENGINE_MEMBER),
                    (root / MODULE.ENGINE_MEMBER).read_bytes(),
                )
                self.assertEqual(
                    archive.read(MODULE.REPAIR_MANIFEST),
                    (root / MODULE.REPAIR_MANIFEST).read_bytes(),
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

    def test_missing_image_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            (root / MODULE.IMAGE_WEB_MANIFEST).unlink()
            with self.assertRaisesRegex(MODULE.PackageError, "image_web 产品清单"):
                MODULE.discover_inputs(root)

    def test_unmanifested_or_size_drift_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            extra = root / "magica/resource/image_web/common/unreviewed.png"
            extra.write_bytes(b"unreviewed")
            with self.assertRaisesRegex(MODULE.PackageError, "路径集合不一致"):
                MODULE.discover_inputs(root)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            image = root / "magica/resource/image_web/common/translated.png"
            image.write_bytes(b"drift")
            with self.assertRaisesRegex(MODULE.PackageError, "大小与清单不一致"):
                MODULE.discover_inputs(root)

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

    def test_missing_or_extra_repair_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            repair = next((root / MODULE.REPAIR_PREFIX).rglob("*.png"))
            repair.unlink()
            with self.assertRaisesRegex(MODULE.PackageError, "native 修复文件缺失"):
                MODULE.discover_inputs(root)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_tree(root)
            extra = root / MODULE.REPAIR_PREFIX / "extra.bin"
            extra.write_bytes(b"unexpected")
            with self.assertRaisesRegex(MODULE.PackageError, "路径集合不一致"):
                MODULE.discover_inputs(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
