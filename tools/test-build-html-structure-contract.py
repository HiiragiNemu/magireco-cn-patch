#!/usr/bin/env python3
"""Focused tests for the frozen HTML structure contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools/build-html-structure-contract.py"
SPEC = importlib.util.spec_from_file_location("html_structure_contract", TOOL)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class HtmlStructureContractTests(unittest.TestCase):
    def test_repository_contract_reopens_without_external_source_drives(self) -> None:
        contract = json.loads(MOD.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        report = MOD.verify_contract(
            ROOT,
            contract,
            verify_external_sources=False,
        )
        self.assertEqual(report["html_files"], 225)
        self.assertEqual(report["strict_source_structure_matches"], 213)
        self.assertEqual(report["version_divergent_frozen_product"], 12)
        self.assertEqual(report["product_structure_drift"], 0)
        self.assertFalse(report["external_sources_verified"])

    def test_verify_cli_reopens_committed_contract_offline(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(TOOL), "--verify"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["html_files"], 225)
        self.assertFalse(report["external_sources_verified"])

    def test_visible_text_and_approved_attribute_values_are_translatable(self) -> None:
        source = b'''<div id="fixed" class="box" data-mode="strict"
            data-title="Japanese" title="Japanese" placeholder="Japanese"
            value="Japanese"><%= "Japanese" + model.count %>Japanese</div>'''
        translated = '''<div id="fixed" class="box" data-mode="strict"
            data-title="中文" title="中文" placeholder="中文"
            value="中文"><%= "中文" + model.count %>中文</div>'''.encode("utf-8")
        self.assertEqual(
            MOD.structure_signature(source),
            MOD.structure_signature(translated),
        )

    def test_tags_sensitive_attributes_and_ejs_control_are_strict(self) -> None:
        baseline = b'<div id="fixed" class="box" data-mode="strict"><%= "x" + model.n %></div>'
        changes = (
            b'<section id="fixed" class="box" data-mode="strict"><%= "x" + model.n %></section>',
            b'<div id="fixed" class="box" data-mode="changed"><%= "x" + model.n %></div>',
            b'<div id="fixed" class="box" data-mode="strict"><%= "x" - model.n %></div>',
        )
        frozen = MOD.structure_signature(baseline)
        for changed in changes:
            with self.subTest(changed=changed):
                self.assertNotEqual(frozen, MOD.structure_signature(changed))

    def test_version_divergent_frozen_product_rejects_each_structure_kind(self) -> None:
        product_path = "magica/template/versioned.html"
        baseline = '<div id="fixed" data-mode="strict"><%= "x" + model.n %></div>\n'
        mutations = (
            '<section id="fixed" data-mode="strict"><%= "x" + model.n %></section>\n',
            '<div id="fixed" data-mode="changed"><%= "x" + model.n %></div>\n',
            '<div id="fixed" data-mode="strict"><%= "x" - model.n %></div>\n',
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            product = root / product_path
            product.parent.mkdir(parents=True)
            product.write_text(baseline, encoding="utf-8", newline="\n")
            old_reference = root / "old/versioned.html"
            old_reference.parent.mkdir(parents=True)
            old_reference.write_text("<p>old CN structure</p>\n", encoding="utf-8")
            evidence = root / "evidence.json"
            evidence.write_text("{}\n", encoding="utf-8")
            contract = {
                "schema": "magireco-cn-html-structure-contract/v1",
                "file_count": 1,
                "source_kind_counts": {"version-divergent-frozen-product": 1},
                "entries": [{
                    "path": product_path,
                    "source_kind": "version-divergent-frozen-product",
                    "source_locator": product_path,
                    "reference_source_kind": "magicaOLD-cn-text-only",
                    "reference_source_locator": str(old_reference),
                    "reference_structure_equal": False,
                    "frozen_structure": MOD.structure_signature(baseline.encode("utf-8")),
                    "translation_evidence": ["evidence.json"],
                }],
            }
            report = MOD.verify_contract(
                root, contract, 1, frozenset({product_path})
            )
            self.assertEqual(report["version_divergent_frozen_product"], 1)

            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    product.write_text(mutation, encoding="utf-8", newline="\n")
                    with self.assertRaisesRegex(
                        AssertionError, "frozen HTML structure drift"
                    ):
                        MOD.verify_contract(
                            root, contract, 1, frozenset({product_path})
                        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
