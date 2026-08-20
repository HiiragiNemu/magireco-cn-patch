#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("apply-missing-html-authority.py")
SPEC = importlib.util.spec_from_file_location("missing_html_authority", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class MissingHtmlAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="missing-html-authority-"))
        self.repo = self.temp / "repo"
        self.source = self.temp / "source"
        self.current_source = self.temp / "current-source"
        self.state = self.repo / MODULE.STATE_REL
        for spec in MODULE.SPECS:
            if spec.get("source_kind") == "current-upstream":
                source = MODULE.REPO_DEFAULT / MODULE.CURRENT_SOURCE_REL / spec["path"]
                target = self.current_source / spec["path"]
            else:
                source = MODULE.SOURCE_DEFAULT / spec["path"]
                target = self.source / spec["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def targets(self) -> list[Path]:
        return [self.repo / "magica" / spec["path"] for spec in MODULE.SPECS]

    def test_happy_prepare_apply_verify_rollback(self) -> None:
        manifest = MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        self.assertEqual(manifest["target_count"], 10)
        self.assertEqual(manifest["literal_record_count"], 30)
        self.assertEqual(manifest["source_tier_counts"], {"official-cn": 10, "root-reviewed": 20})
        self.assertEqual(len((self.state / "translations.tsv").read_text(encoding="utf-8").splitlines()), 31)
        MODULE.apply(self.repo, self.state)
        self.assertEqual(MODULE.verify(self.repo, self.state)["checked_files"], 10)
        MODULE.rollback(self.repo, self.state)
        self.assertFalse(any(path.exists() for path in self.targets()))

    def test_prepare_rejects_existing_target_without_writes(self) -> None:
        target = self.targets()[3]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("existing", encoding="utf-8")
        with self.assertRaises(ValueError):
            MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        self.assertEqual(target.read_text(encoding="utf-8"), "existing")

    def test_apply_failure_removes_every_created_file(self) -> None:
        MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        with self.assertRaises(RuntimeError):
            MODULE.apply(self.repo, self.state, fail_after=4)
        self.assertFalse(any(path.exists() for path in self.targets()))

    def test_prepared_drift_is_rejected_before_product_write(self) -> None:
        manifest = MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        prepared = self.repo / manifest["entries"][0]["prepared_state_path"]
        prepared.write_text(prepared.read_text(encoding="utf-8") + "drift", encoding="utf-8")
        with self.assertRaises(ValueError):
            MODULE.apply(self.repo, self.state)
        self.assertFalse(any(path.exists() for path in self.targets()))

    def test_product_drift_blocks_verify_and_rollback(self) -> None:
        MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        MODULE.apply(self.repo, self.state)
        target = self.targets()[0]
        target.write_text(target.read_text(encoding="utf-8") + "drift", encoding="utf-8")
        with self.assertRaises(ValueError):
            MODULE.verify(self.repo, self.state)
        with self.assertRaises(ValueError):
            MODULE.rollback(self.repo, self.state)
        self.assertTrue(all(path.exists() for path in self.targets()))

    def test_rollback_failure_restores_removed_files(self) -> None:
        MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        MODULE.apply(self.repo, self.state)
        before = {path: path.read_bytes() for path in self.targets()}
        with self.assertRaises(RuntimeError):
            MODULE.rollback(self.repo, self.state, fail_after=5)
        self.assertEqual({path: path.read_bytes() for path in self.targets()}, before)

    def test_structure_drift_is_rejected(self) -> None:
        broken = self.current_source / MODULE.SPECS[0]["path"]
        broken.write_text(broken.read_text(encoding="utf-8").replace('id="popupBp"', 'id="popupBpChanged"'), encoding="utf-8")
        with self.assertRaises(ValueError):
            MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        self.assertFalse(any(path.exists() for path in self.targets()))

    def install_round6_supersession(self) -> Path:
        missing_manifest = json.loads((self.state / "manifest.json").read_text(encoding="utf-8"))
        evidence = self.repo / MODULE.ROUND6_MANIFEST_REL.parent
        entries = []
        main_target = None
        for product_path, old in (
            ("magica/template/quest/MainQuest.html", '<span class="chapterNo">Ch.<span>'),
            ("magica/template/quest/SubQuest.html", '<span class="chapterNo">Ch <span>'),
        ):
            row = next(item for item in missing_manifest["entries"] if item["product_path"] == product_path)
            before = self.repo / row["prepared_state_path"]
            before_text = before.read_text(encoding="utf-8")
            new = '<span class="chapterNo"><span>'
            self.assertEqual(before_text.count(old), 1)
            after_text = before_text.replace(old, new, 1)
            suffix = product_path.removeprefix("magica/")
            before_path = evidence / "before" / suffix
            after_path = evidence / "after" / suffix
            before_path.parent.mkdir(parents=True, exist_ok=True)
            after_path.parent.mkdir(parents=True, exist_ok=True)
            before_path.write_text(before_text, encoding="utf-8", newline="")
            after_path.write_text(after_text, encoding="utf-8", newline="")
            entries.append({
                "product_path": product_path,
                "before_path": str(before_path.relative_to(self.repo)).replace("\\", "/"),
                "after_path": str(after_path.relative_to(self.repo)).replace("\\", "/"),
                "before_state": "present",
                "kind": "html",
                "after_bytes": len(after_text.encode("utf-8")),
                "operations": [{"before": old, "after": new, "source_tier": "official-cn-same-node-structure"}],
            })
            target = self.repo / product_path
            target.write_text(after_text, encoding="utf-8", newline="")
            if product_path.endswith("MainQuest.html"):
                main_target = target
        entries.extend({"product_path": f"unused-{index}"} for index in range(4))
        round6 = {
            "schema": 1,
            "scope": "visible-closure-round6",
            "target_count": 6,
            "literal_count": 15,
            "entries": entries,
        }
        (self.repo / MODULE.ROUND6_MANIFEST_REL).write_text(
            json.dumps(round6, ensure_ascii=False), encoding="utf-8"
        )
        assert main_target is not None
        return main_target

    def test_verify_accepts_only_declared_round6_supersession(self) -> None:
        MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        MODULE.apply(self.repo, self.state)
        self.install_round6_supersession()
        report = MODULE.verify(self.repo, self.state)
        self.assertEqual(report["approved_supersessions"], [
            "magica/template/quest/MainQuest.html",
            "magica/template/quest/SubQuest.html",
        ])

    def test_round6_supersession_still_rejects_extra_product_drift(self) -> None:
        MODULE.prepare(self.repo, self.source, self.current_source, self.state)
        MODULE.apply(self.repo, self.state)
        target = self.install_round6_supersession()
        target.write_text(target.read_text(encoding="utf-8") + "drift", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "product bytes differ"):
            MODULE.verify(self.repo, self.state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
