#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("apply-v26-official-static-corrections.py")
spec = importlib.util.spec_from_file_location("official_static", TOOL)
MOD = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(MOD)


class OfficialStaticTests(unittest.TestCase):
    def fixture(self, root: Path, *, evidence: str = "a" * 64) -> tuple[Path, Path]:
        product = root / "magica/template/formation/FormationQuest.html"
        product.parent.mkdir(parents=True)
        product.write_text('<div class="deckDetailCongeniality"><p>属性相性</p></div>\n', encoding="utf-8", newline="\n")
        manifest = root / "manifest.tsv"
        columns = ["change_id","file","locator","before","after","source_tier","source_locator","source_sha256","match_method","machine_translated","confidence","review_status","evidence","expected_count","expected_after_count"]
        row = ["P19-1","magica/template/formation/FormationQuest.html","div.deckDetailCongeniality>p","属性相性","属性克制","official_cn_dump","D:/official.html#node",evidence,"exact-path-dom-match","false","exact","official-source-verified","fixture","1","1"]
        with manifest.open("w",encoding="utf-8",newline="") as h:
            w=csv.writer(h,delimiter="\t",lineterminator="\n"); w.writerow(columns); w.writerow(row)
        return product, manifest

    def test_apply_verify_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); product,manifest=self.fixture(root)
            self.assertEqual(MOD.run(root,manifest,True)["changed"],1)
            self.assertEqual(MOD.run(root,manifest,False)["status"],"PASS")
            self.assertIn("属性克制",product.read_text(encoding="utf-8"))

    def test_bad_official_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); _,manifest=self.fixture(root,evidence="")
            with self.assertRaises(ValueError): MOD.run(root,manifest,True)

    def test_preimage_drift_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); product,manifest=self.fixture(root)
            product.write_text("别的值\n",encoding="utf-8",newline="\n")
            with self.assertRaises(ValueError): MOD.run(root,manifest,True)


if __name__ == "__main__": unittest.main(verbosity=2)
