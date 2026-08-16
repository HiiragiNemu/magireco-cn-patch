#!/usr/bin/env python3

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"


def load_tool():
    path = ROOT / "tools/build-pass20-product-targets.py"
    spec = importlib.util.spec_from_file_location("pass20_product_targets", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()

MAINTENANCE_ONLY_IDS = {
    "LOW-MT-00317",
    "LOW-MT-00423",
    "LOW-MT-00460",
    "LOW-MT-00581",
    "LOW-MT-00601",
    "LOW-MT-00852",
    "LOW-MT-01015",
    "LOW-MT-01200",
    "LOW-MT-01248",
    "LOW-MT-01584",
    "LOW-MT-01685",
    "LOW-MT-01852",
    "LOW-MT-01885",
    "LOW-MT-01891",
    "LOW-MT-01902",
    "LOW-MT-01913",
    "LOW-MT-01926",
    "LOW-MT-02958",
    "LOW-MT-02961",
}


def build(product_root: Path = ROOT / "magica"):
    return TOOL.build(
        AUDIT / "pass20_remaining_manual_review.tsv",
        ROOT / "i18n/generated/input-provenance.tsv",
        ROOT / "i18n/generated/effective.tsv",
        ROOT / "i18n/uiTextList.json",
        product_root,
    )


def copy_product(source: Path, target: Path) -> None:
    """Copy only files that the target generator is permitted to inspect."""
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".js", ".html", ".json"}:
            continue
        relative = path.relative_to(source)
        if relative.parts[0] in {"i18n_audit", "research"}:
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


class Pass20ProductTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build()
        cls.items = {item["item_id"]: item for item in cls.result["items"]}

    def test_01_fixed_baseline_counts(self):
        self.assertEqual(
            self.result["summary"],
            {
                "items": 199,
                "maintenance_rows_bound": 199,
                "exact_runtime_items": 180,
                "maintenance_only_items": 19,
                "runtime_occurrences": 246,
                "occurrence_collisions": 0,
                "unclassified_items": 0,
                "status_counts": {
                    "exact-current-runtime-literal": 180,
                    "maintenance-only-count-or-path-drift": 3,
                    "maintenance-only-current-literal-absent": 10,
                    "maintenance-only-declared-path-absent": 2,
                    "maintenance-only-deletion-already-applied": 1,
                    "maintenance-only-truncated-target-ambiguous": 3,
                },
                "xlsx_writes_product_tree": False,
                "runtime_application_requires_human_gate": True,
            },
        )

    def test_02_exact_maintenance_only_item_ids(self):
        actual = {
            item["item_id"]
            for item in self.result["items"]
            if not item["application_allowed"]
        }
        self.assertEqual(actual, MAINTENANCE_ONLY_IDS)

    def test_03_low_mt_01485_is_authority_resolved_not_a_human_item(self):
        self.assertNotIn("LOW-MT-01485", self.items)
        with (AUDIT / "pass20_authority_resolutions.tsv").open(encoding="utf-8", newline="") as stream:
            resolution = next(
                row for row in csv.DictReader(stream, delimiter="\t")
                if row["item_id"] == "LOW-MT-01485"
            )
        self.assertEqual(resolution["authority_tier"], "official_cn_dump")
        self.assertEqual(resolution["final_value"], "心魔战")
        self.assertEqual(resolution["product_write_status"], "equivalent-already-present")
        paths = [
            ROOT / "magica/js/regularEvent/RegularEventTop.js",
            ROOT / "magica/js/regularEvent/groupBattle/RegularEventGroupBattleTop.js",
        ]
        texts = [path.read_text(encoding="utf-8") for path in paths]
        self.assertEqual(sum(text.count("心情战") for text in texts), 0)
        self.assertEqual(sum(text.count("心魔战") for text in texts), 8)

    def test_04_runtime_literal_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "magica"
            copy_product(ROOT / "magica", product)
            target = product / "js/event/EventArenaRankMatch/Utility.js"
            before = target.read_text(encoding="utf-8")
            self.assertEqual(before.count("+c+a+e+l"), 1)
            target.write_text(
                before.replace("+c+a+e+l", "+c+a+l+e", 1),
                encoding="utf-8",
                newline="\n",
            )

            drifted = build(product)
            item = next(
                row for row in drifted["items"] if row["item_id"] == "LOW-MT-00312"
            )
            self.assertFalse(item["application_allowed"])
            self.assertEqual(item["match_status"], "maintenance-only-current-literal-absent")
            self.assertEqual(item["occurrences"], [])
            self.assertEqual(item["match_count"], 0)
            self.assertEqual(drifted["summary"]["exact_runtime_items"], 179)
            self.assertEqual(drifted["summary"]["maintenance_only_items"], 20)
            self.assertEqual(drifted["summary"]["runtime_occurrences"], 245)
            self.assertEqual(drifted["summary"]["occurrence_collisions"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
