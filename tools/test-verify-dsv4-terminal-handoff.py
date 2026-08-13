#!/usr/bin/env python3
"""Regression tests for the committed DSV4 terminal handoff verifier."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/verify-dsv4-terminal-handoff.py"
SPEC = importlib.util.spec_from_file_location("verify_dsv4_terminal_handoff", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TerminalHandoffVerifierTests(unittest.TestCase):
    def test_committed_terminal_handoff_passes(self) -> None:
        result = MODULE.verify(MODULE.DEFAULT_ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["decision_queue"]["human_required"], 522)
        self.assertEqual(result["decision_queue"]["current_product_low_tier"], 258)
        self.assertEqual(result["patch_entries"], result["rollback_entries"])
        self.assertFalse(result["product_tree_writes"])

    def test_byte_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dsv4-handoff-drift-") as td:
            copy = Path(td) / "handoff"
            copy.mkdir()
            for source in MODULE.DEFAULT_ROOT.iterdir():
                if source.is_file():
                    os.link(source, copy / source.name)
            manifest = copy / "manifest.json"
            manifest.unlink()
            manifest.write_bytes((MODULE.DEFAULT_ROOT / "manifest.json").read_bytes() + b"\n")
            with self.assertRaises(MODULE.HandoffError):
                MODULE.verify(copy)


if __name__ == "__main__":
    unittest.main(verbosity=2)
