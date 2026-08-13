#!/usr/bin/env python3
"""Contract tests for hot-update producer path classification."""

from __future__ import annotations

import os
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
                    "madomagi/resource/scenario/jsonish/a.json",
                    "magica/javascript/app.js",
                    "magica/js",
                ]
            ),
            js=0,
            scenario=0,
        )

    def test_empty_change_list_triggers_neither(self):
        self.assert_flags(self.run_cli([]), js=0, scenario=0)

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
