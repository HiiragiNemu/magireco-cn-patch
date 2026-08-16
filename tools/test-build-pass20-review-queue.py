#!/usr/bin/env python3

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"


def load_tool():
    path = ROOT / "tools/build-pass20-review-queue.py"
    spec = importlib.util.spec_from_file_location("pass20_queue_tested", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


class Pass20ReviewQueueTests(unittest.TestCase):
    def test_queue_is_exactly_reproducible_and_excludes_existing_official_resolution(self):
        header, rows = TOOL.build(TOOL.DECISIONS, TOOL.RESOLUTIONS)
        self.assertEqual(len(rows), 199)
        self.assertNotIn("LOW-MT-01485", {row["item_id"] for row in rows})
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "queue.tsv"
            TOOL.write(output, header, rows)
            self.assertEqual(output.read_bytes(), TOOL.OUTPUT.read_bytes())

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
                TOOL.build(TOOL.DECISIONS, target)


if __name__ == "__main__":
    unittest.main(verbosity=2)
