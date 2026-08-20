#!/usr/bin/env python3

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
sys.path.insert(0, str(ROOT / "tools"))


def load_tool():
    path = ROOT / "tools/build-pass20-product-targets.py"
    spec = importlib.util.spec_from_file_location("pass20_product_targets", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


def build(product_root: Path = ROOT / "magica"):
    return TOOL.build(
        AUDIT / "pass20_remaining_manual_review.tsv",
        ROOT / "i18n/generated/input-provenance.tsv",
        ROOT / "i18n/generated/effective.tsv",
        ROOT / "i18n/uiTextList.json",
        product_root,
    )


def copy_product(source: Path, target: Path) -> None:
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

    def test_01_full_human_target_contract(self):
        summary = self.result["summary"]
        self.assertEqual(
            {key: summary[key] for key in (
                "items", "maintenance_rows_bound", "exact_runtime_items",
                "maintenance_only_items", "runtime_occurrences",
                "occurrence_collisions", "unclassified_items",
            )},
            {
                "items": 1564,
                "maintenance_rows_bound": 1564,
                "exact_runtime_items": 1376,
                "maintenance_only_items": 188,
                "runtime_occurrences": 2260,
                "occurrence_collisions": 0,
                "unclassified_items": 0,
            },
        )
        self.assertEqual(
            summary["status_counts"],
            {
                "exact-current-runtime-literal": 1376,
                "maintenance-only-count-or-path-drift": 21,
                "maintenance-only-current-literal-absent": 114,
                "maintenance-only-declared-path-absent": 3,
                "maintenance-only-deletion-already-applied": 1,
                "maintenance-only-truncated-target-ambiguous": 49,
            },
        )
        self.assertTrue(all(not item["shadowed_by_higher_authority"] for item in self.result["items"]))
        self.assertTrue(all(item["canonical_write_allowed_after_human_gate"] for item in self.result["items"]))
        self.assertEqual(
            sum(item["runtime_write_allowed_after_human_gate"] for item in self.result["items"]),
            1376,
        )
        self.assertTrue(all(
            item["runtime_write_allowed_after_human_gate"] == item["application_allowed"]
            for item in self.result["items"]
        ))
        self.assertTrue(all(
            item["source_product_write_allowed_provenance"] == "false"
            for item in self.result["items"]
        ))
        self.assertTrue(all(
            "product_write_allowed_from_review_queue" not in item
            for item in self.result["items"]
        ))

    def test_02_tracked_manifest_is_reproducible(self):
        tracked = json.loads((AUDIT / "pass20_product_targets.json").read_text(encoding="utf-8"))
        self.assertEqual(self.result, tracked)

    def test_03_shadowed_inventory_is_disjoint_and_write_forbidden(self):
        shadow = json.loads(
            (AUDIT / "pass20_authority_shadowed_machine_items.json").read_text(encoding="utf-8")
        )
        self.assertEqual(shadow["summary"]["items"], 25)
        shadow_ids = {row["item_id"] for row in shadow["items"]}
        self.assertFalse(shadow_ids & set(self.items))
        self.assertTrue(all(row["product_write_forbidden"] for row in shadow["items"]))
        self.assertIn("LOW-MT-00401", shadow_ids)
        self.assertEqual(shadow["summary"]["authority_materialization_items"], 2)
        self.assertEqual(shadow["summary"]["authority_materialized_occurrences"], 9)
        self.assertEqual(shadow["summary"]["authority_verified_occurrences"], 10)
        by_id = {row["item_id"]: row for row in shadow["items"]}
        self.assertEqual(by_id["LOW-MT-00395"]["effective_cn"], "圆环助战")
        self.assertEqual(by_id["LOW-MT-00395"]["effective_tier"], "official_cn_dump")
        self.assertEqual(by_id["LOW-MT-00681"]["effective_cn"], "最终连携")
        self.assertEqual(by_id["LOW-MT-00681"]["effective_tier"], "existing_human_reviewed")
        self.assertEqual(by_id["LOW-MT-01134"]["runtime_machine_count"], 0)
        self.assertEqual(by_id["LOW-MT-01134"]["runtime_effective_count"], 5)
        self.assertEqual(by_id["LOW-MT-01450"]["runtime_machine_count"], 0)
        self.assertEqual(by_id["LOW-MT-01450"]["runtime_effective_count"], 6)
        self.assertEqual(
            sum(
                entry["expected_effective_count"]
                for item_id in ("LOW-MT-01134", "LOW-MT-01450")
                for entry in by_id[item_id]["authority_materialization"]["product_paths"]
            ),
            10,
        )
        self.assertEqual(
            sum(
                entry["expected_effective_count"]
                for item_id in ("LOW-MT-01134", "LOW-MT-01450")
                for entry in by_id[item_id]["authority_materialization"]["product_paths"]
                if entry["materialized_from_machine"]
            ),
            9,
        )

    def test_04_low_mt_00674_is_authority_resolved_path_override(self):
        self.assertNotIn("LOW-MT-00674", self.items)
        with (AUDIT / "pass20_authority_resolutions.tsv").open(encoding="utf-8", newline="") as stream:
            resolution = next(
                row for row in csv.DictReader(stream, delimiter="\t")
                if row["item_id"] == "LOW-MT-00674"
            )
        self.assertEqual(resolution["authority_tier"], "official_cn_dump")
        self.assertEqual(resolution["product_write_status"], "applied-and-verified")
        paths = [
            ROOT / "magica/js/event/raid/EventRaidCloseTop.js",
            ROOT / "magica/js/event/raid/EventRaidTop.js",
        ]
        texts = [path.read_text(encoding="utf-8") for path in paths]
        self.assertEqual(sum(text.count("个以上】即可解放</div>") for text in texts), 0)
        self.assertEqual(sum(text.count("个以上】<br>即可解锁全体击败的报酬</div>") for text in texts), 2)

    def test_05_runtime_literal_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            product = Path(temp) / "magica"
            copy_product(ROOT / "magica", product)
            target = product / "js/event/EventArenaRankMatch/Utility.js"
            before = target.read_text(encoding="utf-8")
            self.assertEqual(before.count("+c+a+e+l"), 1)
            target.write_text(before.replace("+c+a+e+l", "+c+a+l+e", 1), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(TOOL.TargetError, "contract drifted"):
                build(product)

    def test_06_shadow_authority_runtime_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            product = root / "magica"
            copy_product(ROOT / "magica", product)
            target = product / "js/regularEvent/accomplish/view/RegularEventAccomplishRecoverView.js"
            before = target.read_text(encoding="utf-8")
            self.assertEqual(before.count('title:"回复HP"'), 5)
            target.write_text(
                before.replace('title:"回复HP"', 'title:"HP 回复"', 1),
                encoding="utf-8", newline="\n",
            )
            code = TOOL.main([
                "--product-root", str(product),
                "--out-json", str(root / "targets.json"),
                "--out-tsv", str(root / "targets.tsv"),
                "--shadow-json", str(root / "shadows.json"),
            ])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
