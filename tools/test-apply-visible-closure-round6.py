#!/usr/bin/env python3
"""Independent transactional tests for visible closure round 6."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).with_name("apply-visible-closure-round6.py")
SPEC = importlib.util.spec_from_file_location("visible_closure_round6", TOOL)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class VisibleClosureRound6Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "magica/js/libs").mkdir(parents=True)
        card = {str(i): {"shortDescription": f"技能{i} 与角色Connect后效果"} for i in mod.OFFICIAL_CONNECT_IDS}
        (self.repo / "magica/js/libs/cardSkillMap.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        (self.repo / "magica/js/libs/jquery-3.7.1.min.js").write_text("/".join(v["shortDescription"] for v in card.values()), encoding="utf-8")
        for spec in mod.SPECS:
            target = self.repo / "magica" / spec["path"]
            if spec["before_state"] == "present":
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("\n".join(op["before"] for op in spec["operations"]) + "\n", encoding="utf-8")
        self.router = self.repo / "source/Router.js"
        self.router.parent.mkdir(parents=True)
        self.router.write_text('(function(){var a={};a.battleTitle="LAST BATTLE";})();\n', encoding="utf-8")
        self.state = self.repo / "state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def prepare(self) -> dict:
        return mod.prepare(self.repo, self.router, self.state)

    def snapshot(self) -> dict[str, bytes | None]:
        return {spec["path"]: ((self.repo / "magica" / spec["path"]).read_bytes()
                if (self.repo / "magica" / spec["path"]).exists() else None) for spec in mod.SPECS}

    def test_01_full_apply_verify_rollback_reapply(self) -> None:
        self.prepare()
        before = self.snapshot()
        mod.apply(self.repo, self.state)
        self.assertEqual(mod.verify(self.repo, self.state)["literal_changes"], 15)
        after = self.snapshot()
        mod.rollback(self.repo, self.state)
        self.assertEqual(before, self.snapshot())
        mod.apply(self.repo, self.state)
        self.assertEqual(after, self.snapshot())
        mod.verify(self.repo, self.state)

    def test_02_before_drift_is_zero_write(self) -> None:
        self.prepare()
        first = self.repo / "magica" / mod.SPECS[0]["path"]
        first.write_text(first.read_text(encoding="utf-8") + "drift", encoding="utf-8")
        snapshot = self.snapshot()
        with self.assertRaisesRegex(ValueError, "before gate drift"):
            mod.apply(self.repo, self.state)
        self.assertEqual(snapshot, self.snapshot())

    def test_03_staged_after_drift_is_zero_write(self) -> None:
        manifest = self.prepare()
        staged = self.repo / manifest["entries"][0]["after_path"]
        staged.write_text(staged.read_text(encoding="utf-8") + "drift", encoding="utf-8")
        snapshot = self.snapshot()
        with self.assertRaisesRegex(ValueError, "staging byte-count drift"):
            mod.apply(self.repo, self.state)
        self.assertEqual(snapshot, self.snapshot())

    def test_04_manifest_path_or_role_tamper_rejected(self) -> None:
        self.prepare()
        path = self.state / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["entries"][0]["product_path"] = "magica/unknown/file.html"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fixed path/order mismatch"):
            mod.apply(self.repo, self.state)
        self.prepare()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["entries"][0]["operations"][0]["after"] = "篡改"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "operation mismatch"):
            mod.apply(self.repo, self.state)
        self.prepare()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["entries"][0]["before_path"] = manifest["entries"][1]["before_path"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "state path mismatch"):
            mod.apply(self.repo, self.state)

    def test_05_mid_apply_failure_restores_every_file(self) -> None:
        self.prepare()
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "synthetic apply failure"):
            mod.apply(self.repo, self.state, fail_after=3)
        self.assertEqual(before, self.snapshot())

    def test_06_mid_rollback_failure_restores_modified_state(self) -> None:
        self.prepare()
        mod.apply(self.repo, self.state)
        after = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "synthetic rollback failure"):
            mod.rollback(self.repo, self.state, fail_after=4)
        self.assertEqual(after, self.snapshot())


if __name__ == "__main__":
    unittest.main(verbosity=2)
