#!/usr/bin/env python3
"""Contract tests for hot-update producer path classification."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("classify_hotupdate_changes.py")


class HotUpdateChangeClassificationTest(unittest.TestCase):
    def run_cli(
        self,
        paths: list[str],
        *,
        scope: str = "auto",
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--scope",
                scope,
                *(extra_args or []),
            ],
            input="\n".join(paths) + ("\n" if paths else ""),
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )

    def assert_flags(self, proc: subprocess.CompletedProcess[str], js: int, scenario: int):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, f"has_js={js}\nhas_scenario={scenario}\n")

    def test_engine_only_is_js_only(self):
        self.assert_flags(
            self.run_cli(["madomagi/engine_i18n.tsv"]), js=1, scenario=0
        )

    def test_madomagi_native_repair_is_js_only(self):
        self.assert_flags(
            self.run_cli([
                "madomagi/resource/image_native/chara/chara_4051_h.png"
            ]),
            js=1,
            scenario=0,
        )

    def test_madomagi_repair_manifest_is_js_only(self):
        self.assert_flags(
            self.run_cli(["madomagi/repair_manifest.json"]),
            js=1,
            scenario=0,
        )

    def test_each_js_product_tree_is_js_only(self):
        for directory in ("css", "fonts", "js", "resource", "template"):
            with self.subTest(directory=directory):
                self.assert_flags(
                    self.run_cli([f"magica/{directory}/nested/file.dat"]),
                    js=1,
                    scenario=0,
                )

    def test_scenario_tree_is_scenario_only(self):
        self.assert_flags(
            self.run_cli(["madomagi/resource/scenario/json/12345.json"]),
            js=0,
            scenario=1,
        )

    def test_mixed_product_paths_trigger_both(self):
        self.assert_flags(
            self.run_cli(
                [
                    "magica/js/app.js",
                    "madomagi/resource/scenario/json/12345.json",
                ]
            ),
            js=1,
            scenario=1,
        )

    def test_unowned_and_near_match_paths_trigger_neither(self):
        self.assert_flags(
            self.run_cli(
                [
                    "README.md",
                    "i18n/frontend-strings.tsv",
                    "madomagi/engine_i18n.tsv.bak",
                    "madomagi/repair_manifest.json.bak",
                    "madomagi/resource/scenario/jsonish/a.json",
                    "madomagi/resource/image_nativeish/a.png",
                    "magica/javascript/app.js",
                    "magica/js",
                ]
            ),
            js=0,
            scenario=0,
        )

    def test_empty_change_list_triggers_neither(self):
        self.assert_flags(self.run_cli([]), js=0, scenario=0)

    def test_supplemental_scenario_paths_do_not_rebuild_full_package(self):
        listed = "madomagi/resource/scenario/json/listed.json"
        unlisted = "madomagi/resource/scenario/json/unlisted.json"
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw) / "baseline.json"
            config.write_text(json.dumps({"supplemental_product_paths": [listed]}), encoding="utf-8")
            extra = ["--delta-baseline", str(config)]
            cases = [([listed], "auto", 0, 0),
                     ([listed, "magica/js/app.js"], "auto", 1, 0),
                     ([listed, unlisted], "auto", 0, 1),
                     ([listed], "scenario", 0, 1),
                     ([listed], "all", 1, 1),
                     (["ALL"], "auto", 1, 1)]
            for paths, scope, js, scenario in cases:
                with self.subTest(paths=paths, scope=scope):
                    self.assert_flags(self.run_cli(paths, scope=scope, extra_args=extra), js, scenario)

    def test_invalid_supplemental_config_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw) / "baseline.json"
            for invalid in ["not-a-list", [None], ["../x.json"],
                            ["madomagi/resource/scenario/json/../x.json"]]:
                config.write_text(json.dumps({"supplemental_product_paths": invalid}), encoding="utf-8")
                proc = self.run_cli([], extra_args=["--delta-baseline", str(config)])
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("invalid supplemental_product_paths", proc.stderr)

    def test_diff_failure_sentinel_fails_closed_to_both_packages(self):
        self.assert_flags(self.run_cli(["ALL"]), js=1, scenario=1)

    def test_manual_scopes_override_changed_paths(self):
        cases = {
            "js": (1, 0),
            "scenario": (0, 1),
            "all": (1, 1),
        }
        for scope, expected in cases.items():
            with self.subTest(scope=scope):
                self.assert_flags(
                    self.run_cli(["README.md"], scope=scope),
                    js=expected[0],
                    scenario=expected[1],
                )

    def test_cli_output_can_also_be_appended_to_explicit_github_output_path(self):
        with tempfile.TemporaryDirectory() as raw:
            github_output = Path(raw) / "github-output.txt"
            github_output.write_text("existing=value\n", encoding="utf-8", newline="\n")
            proc = self.run_cli(
                ["madomagi/engine_i18n.tsv"],
                extra_args=["--github-output", str(github_output)],
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assert_flags(proc, js=1, scenario=0)
            self.assertEqual(
                github_output.read_bytes(),
                b"existing=value\nhas_js=1\nhas_scenario=0\n",
            )

    def test_github_output_environment_variable_is_supported(self):
        with tempfile.TemporaryDirectory() as raw:
            github_output = Path(raw) / "github-output.txt"
            env = {
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "GITHUB_OUTPUT": str(github_output),
            }
            proc = self.run_cli(
                ["madomagi/resource/scenario/json/a.json"],
                extra_args=["--github-output"],
                env=env,
            )
            self.assert_flags(proc, js=0, scenario=1)
            self.assertEqual(
                github_output.read_bytes(),
                b"has_js=0\nhas_scenario=1\n",
            )


if __name__ == "__main__":
    unittest.main()
