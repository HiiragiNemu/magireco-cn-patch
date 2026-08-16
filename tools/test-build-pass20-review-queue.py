#!/usr/bin/env python3

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))


def load_tool():
    path = TOOLS / "build-pass20-review-queue.py"
    spec = importlib.util.spec_from_file_location("pass20_queue_tested", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


class Pass20ReviewQueueTests(unittest.TestCase):
    def build(self, resolutions=TOOL.RESOLUTIONS):
        return TOOL.build(
            TOOL.FULL_REVIEW, TOOL.DECISIONS, resolutions, TOOL.OFFICIAL_REVIEW,
            TOOL.PROVENANCE, TOOL.EFFECTIVE,
        )

    def test_dual_scope_is_exactly_reproducible(self):
        header, inventory, human, priority, shadowed = self.build()
        self.assertEqual((len(inventory), len(human), len(priority), len(shadowed)), (1589, 1565, 199, 24))
        self.assertEqual(sum(row["parent_verdict"] == "approved" for row in human), 1366)
        self.assertNotIn("LOW-MT-01485", {row["item_id"] for row in human})
        self.assertTrue(all(row["product_write_forbidden"] == "true" for row in shadowed))
        self.assertTrue(all(row["allowed_human_decisions"] == "[]" for row in shadowed))
        self.assertTrue(all(row["canonical_write_allowed_after_human_gate"] == "false" for row in shadowed))
        self.assertTrue(all(row["canonical_write_allowed_after_human_gate"] == "true" for row in human))
        self.assertTrue(all(row["product_write_allowed"] == "false" for row in human))
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            outputs = (
                ("inventory.tsv", inventory, TOOL.MACHINE_INVENTORY),
                ("human.tsv", human, TOOL.HUMAN_QUEUE),
                ("priority.tsv", priority, TOOL.PRIORITY_QUEUE),
                ("shadow.tsv", shadowed, TOOL.SHADOW_TSV),
            )
            for name, rows, tracked in outputs:
                output = temp / name
                TOOL.write_tsv(output, header, rows)
                self.assertEqual(output.read_bytes(), tracked.read_bytes())

    def test_human_queue_order_is_priority_then_approved(self):
        _, _, human, priority, _ = self.build()
        self.assertEqual([row["item_id"] for row in human[:199]], [row["item_id"] for row in priority])
        self.assertTrue(all(row["parent_verdict"] != "approved" for row in human[:199]))
        self.assertTrue(all(row["parent_verdict"] == "approved" for row in human[199:]))

    def test_duplicate_resolution_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "resolutions.tsv"
            with TOOL.RESOLUTIONS.open("r", encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream, delimiter="\t")
                header = list(reader.fieldnames or [])
                rows = list(reader)
            rows.append(dict(rows[0]))
            with target.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(TOOL.QueueError, "duplicate item_id"):
                self.build(target)

    def test_low_mt_00674_cannot_be_swapped_out_of_official_resolutions(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "resolutions.tsv"
            with TOOL.RESOLUTIONS.open("r", encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream, delimiter="\t")
                header = list(reader.fieldnames or [])
                rows = list(reader)
            official = next(row for row in rows if row["item_id"] == "LOW-MT-00674")
            official["item_id"] = "LOW-MT-00317"
            with target.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(TOOL.ContractError, "stable-ID set drifted"):
                self.build(target)


if __name__ == "__main__":
    unittest.main(verbosity=2)
