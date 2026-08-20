#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("apply-visible-residue-closure-round4.py")
SPEC = importlib.util.spec_from_file_location("round4_apply", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC); assert SPEC.loader; SPEC.loader.exec_module(MODULE)


class Round4TransformTests(unittest.TestCase):
    def test_css_exact_translation(self):
        row = {"item_id": "x", "before": "必要GP", "after": "所需GP"}
        self.assertEqual(MODULE.transform("css", 'a{content:"必要GP"}'.encode(), [row], "before", "after").decode(), 'a{content:"所需GP"}')

    def test_css_drift_rejected(self):
        row = {"item_id": "x", "before": "必要GP", "after": "所需GP"}
        with self.assertRaises(MODULE.ClosureError): MODULE.transform("css", b'a{content:"GP"}', [row], "before", "after")

    def test_card_stable_key(self):
        row = {"item_id": "x", "file": "card", "key": "10424", "field": "cardName", "before": "Kyubert", "after": "小丘比"}
        result = json.loads(MODULE.transform("card", json.dumps([{"cardId": 10424, "cardName": "Kyubert"}]).encode(), [row], "before", "after"))
        self.assertEqual(result[0]["cardName"], "小丘比")

    def test_duplicate_stable_key_rejected(self):
        data = [{"sectionId": 1, "title": "x"}, {"sectionId": 1, "title": "x"}]
        row = {"item_id": "x", "file": "section", "key": "1", "field": "title", "before": "x", "after": "y"}
        with self.assertRaises(MODULE.ClosureError): MODULE.transform("section", json.dumps(data).encode(), [row], "before", "after")

    def test_manifest_allowlist_and_count(self):
        manifest = MODULE.read_manifest(MODULE.DEFAULT_MANIFEST)
        self.assertEqual(len(manifest["changes"]), 39)
        self.assertEqual(len(manifest["protected_retained"]), 0)

    def test_read_only_verification_state_can_relocate_but_writes_cannot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "clean-checkout"
            root.mkdir()
            manifest = root / "closure_manifest.json"
            manifest.write_bytes(MODULE.DEFAULT_MANIFEST.read_bytes())
            state = root / "runtime"
            shutil.copytree(MODULE.DEFAULT_STATE, state)

            with self.assertRaisesRegex(MODULE.ClosureError, "repository root drift"):
                MODULE.load_state(root, manifest, state)

            saved, loaded = MODULE.load_state(
                root, manifest, state, allow_relocated_root=True
            )
            self.assertEqual(len(saved["entries"]), 6)
            self.assertEqual(len(loaded["changes"]), 39)

    def test_json_verification_allows_unrelated_later_authority_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rel = "magica/js/libs/cardList.json"
            path = root / rel
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps([
                    {"cardId": 10424, "cardName": "小丘比", "laterAuthority": "权威新值"},
                    {"cardId": 99999, "cardName": "后续新增"},
                ], ensure_ascii=False),
                encoding="utf-8",
            )
            row = {
                "item_id": "x", "file": rel, "key": "10424",
                "field": "cardName", "before": "Kyubert", "after": "小丘比",
            }
            entry = {"target": rel, "kind": "card"}
            MODULE.verify_entry_fields(root, root / "unused", entry, [row], "after")

    def test_json_verification_rejects_target_field_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rel = "magica/js/libs/cardList.json"
            path = root / rel
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps([{"cardId": 10424, "cardName": "Kyubert"}]), encoding="utf-8")
            row = {
                "item_id": "x", "file": rel, "key": "10424",
                "field": "cardName", "before": "Kyubert", "after": "小丘比",
            }
            with self.assertRaises(MODULE.ClosureError):
                MODULE.verify_entry_fields(root, root / "unused", {"target": rel, "kind": "card"}, [row], "after")

    def test_json_verification_accepts_manifest_bound_later_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rel = "magica/js/libs/eventStoryList.json"
            path = root / rel
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps([{"storyIds": "1", "pointTitle": "剧情"}], ensure_ascii=False), encoding="utf-8")
            row = {
                "item_id": "x", "file": rel, "key": "1",
                "field": "pointTitle", "before": "Story", "after": "故事",
            }
            approved = {(rel, "0/pointTitle"): {
                "local": "故事", "after": "剧情", "source_commit": "origin/main@abc",
            }}
            count = MODULE.verify_entry_fields(
                root, root / "unused", {"target": rel, "kind": "story"},
                [row], "after", approved,
            )
            self.assertEqual(count, 1)

    def test_rollback_preserves_manifest_bound_later_authority(self):
        rel = "magica/js/libs/eventStoryList.json"
        rows = [{
            "item_id": "x", "file": rel, "key": "1",
            "field": "pointTitle", "before": "Story", "after": "故事",
        }]
        approved = {(rel, "0/pointTitle"): {
            "local": "故事", "after": "剧情", "source_commit": "origin/main@abc",
        }}
        source = json.dumps([{"storyIds": "1", "pointTitle": "剧情"}], ensure_ascii=False).encode()
        result = json.loads(MODULE.rollback_json_fields(rel, "story", source, rows, approved))
        self.assertEqual(result[0]["pointTitle"], "剧情")


if __name__ == "__main__":
    unittest.main(verbosity=2)
