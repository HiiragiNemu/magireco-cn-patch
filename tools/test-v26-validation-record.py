#!/usr/bin/env python3
"""Synthetic regression tests for the v26 validation recorder."""

from __future__ import annotations

import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from v26_validation_record import (
    DEFAULT_PLAN,
    PLAN_SCHEMA,
    ValidationError,
    inspect_engine,
    main,
    run_validation,
    verify_record,
)


class ValidationRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="v26-validation-test-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Hiiragi Nemu")
        self.git(
            "config",
            "user.email",
            "128921071+HiiragiNemu@users.noreply.github.com",
        )
        (self.repo / "input.txt").write_text("baseline\n", encoding="utf-8", newline="\n")
        self.git("add", "input.txt")
        self.git("commit", "-q", "-m", "baseline")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def write_plan(
        self,
        name: str,
        groups: list[dict[str, object]],
        comparisons: list[dict[str, str]] | None = None,
    ) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "schema": PLAN_SCHEMA,
                    "groups": groups,
                    "comparisons": comparisons or [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def run_plan(
        self, name: str, plan: Path, *, inline_limit: int = 64 * 1024
    ) -> tuple[dict[str, object], Path, Path]:
        output = self.root / f"{name}.record.json"
        artifacts = self.root / f"{name}.artifacts"
        record = run_validation(
            repo=self.repo,
            baseline="HEAD",
            plan_path=plan,
            output=output,
            artifact_dir=artifacts,
            inline_limit=inline_limit,
        )
        return record, output, artifacts

    def test_repository_plan_includes_css_and_html_structure_gates(self) -> None:
        plan = json.loads(DEFAULT_PLAN.read_text(encoding="utf-8"))
        group = next(
            item for item in plan["groups"]
            if item["id"] == "modified-tests-and-authority"
        )
        commands = {item["id"]: item for item in group["commands"]}
        self.assertEqual(
            commands["test-css-visible-content-audit"],
            {
                "id": "test-css-visible-content-audit",
                "argv": ["${PYTHON}", "tools/test-css-visible-content-audit.py"],
                "inputs": [
                    "tools/test-css-visible-content-audit.py",
                    "magica/css",
                    "magica/research/totentanz-full-localization-20260817/"
                    "visible-ui/visible_ui_manifest.json",
                    "magica/research/totentanz-full-localization-20260817/"
                    "visible-ui/css_visible_content_audit.json",
                    "magica/research/totentanz-full-localization-20260817/"
                    "visible-ui/connect_supersession_ui075.json",
                ],
                "timeout_seconds": 600,
            },
        )
        self.assertEqual(
            commands["test-html-structure-contract"],
            {
                "id": "test-html-structure-contract",
                "argv": ["${PYTHON}", "tools/test-build-html-structure-contract.py"],
                "inputs": [
                    "tools/test-build-html-structure-contract.py",
                    "tools/build-html-structure-contract.py",
                    "magica/template",
                    "magica/research/totentanz-full-localization-20260817/"
                    "html-structure-contract-20260819/html_structure_contract.json",
                ],
                "timeout_seconds": 900,
            },
        )

    def test_success_captures_modified_and_isolated_baseline_commands(self) -> None:
        plan = self.write_plan(
            "success",
            [
                {
                    "id": "modified",
                    "root": "modified",
                    "commands": [
                        {
                            "id": "modified-success",
                            "argv": [
                                "${PYTHON}",
                                "-c",
                                "from pathlib import Path; print(Path('input.txt').read_text().strip())",
                            ],
                            "inputs": ["input.txt"],
                        }
                    ],
                },
                {
                    "id": "baseline",
                    "root": "baseline",
                    "commands": [
                        {
                            "id": "baseline-success",
                            "argv": [
                                "${PYTHON}",
                                "-c",
                                "from pathlib import Path; print(Path('input.txt').read_text().strip())",
                            ],
                            "inputs": ["input.txt"],
                        }
                    ],
                },
            ],
        )
        record, output, _artifacts = self.run_plan("success", plan)
        self.assertEqual(record["status"], "PASS")
        self.assertTrue(record["modified"]["real_index_unchanged"])
        self.assertEqual(record["summary"]["command_count"], 4)  # clone, checkout, two tests
        reopened = verify_record(output)
        self.assertEqual(reopened["status"], "PASS")
        self.assertEqual(reopened["literal_streams_reopened"], 8)
        baseline_command = next(
            item for item in record["commands"] if item["id"] == "baseline-success"
        )
        self.assertIn("v26-validation-baseline-", baseline_command["cwd"])
        # The clone may honor host checkout line-ending policy; the evidence
        # therefore records the bytes actually consumed instead of assuming
        # they match the dirty-worktree representation.
        self.assertRegex(
            baseline_command["input_snapshot"]["paths"][0]["snapshot"]["sha256"],
            r"^[0-9a-f]{64}$",
        )

    def test_nonzero_command_makes_entire_record_fail(self) -> None:
        plan = self.write_plan(
            "failure",
            [
                {
                    "id": "modified",
                    "root": "modified",
                    "commands": [
                        {
                            "id": "intentional-exit-seven",
                            "argv": ["${PYTHON}", "-c", "import sys; print('bad'); sys.exit(7)"],
                            "inputs": ["input.txt"],
                        }
                    ],
                }
            ],
        )
        record, output, _artifacts = self.run_plan("failure", plan)
        self.assertEqual(record["status"], "FAIL")
        self.assertEqual(record["commands"][0]["exit_status"], 7)
        self.assertEqual(record["summary"]["nonzero_or_unlaunched_commands"], ["intentional-exit-seven"])
        self.assertEqual(verify_record(output)["status"], "FAIL")

    def test_git_status_after_tracked_mtime_change_cannot_refresh_real_index(self) -> None:
        # `git status` normally updates index stat-cache bytes even when it stages
        # nothing.  The recorder forces GIT_OPTIONAL_LOCKS=0 for every child (and
        # descendants), so a read-only validation remains byte-read-only too.
        current = (self.repo / "input.txt").read_bytes()
        (self.repo / "input.txt").write_bytes(current)
        plan = self.write_plan(
            "git-index-read-only",
            [
                {
                    "id": "modified",
                    "root": "modified",
                    "commands": [
                        {
                            "id": "git-status",
                            "argv": ["git", "status", "--porcelain=v1"],
                            "inputs": ["input.txt"],
                        }
                    ],
                }
            ],
        )
        record, output, _artifacts = self.run_plan("git-index-read-only", plan)
        self.assertEqual(record["status"], "PASS")
        self.assertTrue(record["modified"]["real_index_unchanged"])
        self.assertTrue(record["modified"]["index_guard"]["created"])
        self.assertTrue(record["modified"]["index_guard"]["payload_unchanged"])
        self.assertTrue(record["modified"]["index_guard"]["removed"])
        command = next(item for item in record["commands"] if item["id"] == "git-status")
        self.assertEqual(command["environment_overrides"]["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(verify_record(output)["status"], "PASS")

    def test_index_guard_blocks_descendant_that_discards_read_only_environment(self) -> None:
        # A separately authored helper may discard the inherited environment.
        # The conventional index.lock guard still prevents its optional status
        # refresh from changing the caller's real linked-worktree index bytes.
        current = (self.repo / "input.txt").read_bytes()
        (self.repo / "input.txt").write_bytes(current)
        code = (
            "import os, subprocess; "
            "os.environ.pop('GIT_OPTIONAL_LOCKS', None); "
            "raise SystemExit(subprocess.run(['git','status','--porcelain=v1']).returncode)"
        )
        plan = self.write_plan(
            "git-index-guard",
            [
                {
                    "id": "modified",
                    "root": "modified",
                    "commands": [
                        {
                            "id": "git-status-with-reset-environment",
                            "argv": ["${PYTHON}", "-c", code],
                            "inputs": ["input.txt"],
                        }
                    ],
                }
            ],
        )
        record, output, _artifacts = self.run_plan("git-index-guard", plan)
        self.assertEqual(record["status"], "PASS")
        self.assertTrue(record["modified"]["real_index_unchanged"])
        self.assertEqual(
            record["modified"]["index_before"]["sha256"],
            record["modified"]["index_after"]["sha256"],
        )
        self.assertTrue(record["modified"]["index_guard"]["payload_unchanged"])
        self.assertTrue(record["modified"]["index_guard"]["removed"])
        self.assertEqual(verify_record(output)["status"], "PASS")

    def test_cli_returns_nonzero_when_any_command_is_nonzero(self) -> None:
        plan = self.write_plan(
            "cli-failure",
            [
                {
                    "id": "modified",
                    "root": "modified",
                    "commands": [
                        {
                            "id": "cli-exit-three",
                            "argv": ["${PYTHON}", "-c", "raise SystemExit(3)"],
                            "inputs": ["input.txt"],
                        }
                    ],
                }
            ],
        )
        output = self.root / "cli-failure.record.json"
        artifacts = self.root / "cli-failure.artifacts"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exit_status = main(
                [
                    "run",
                    "--repo",
                    str(self.repo),
                    "--baseline",
                    "HEAD",
                    "--plan",
                    str(plan),
                    "--output",
                    str(output),
                    "--artifact-dir",
                    str(artifacts),
                ]
            )
        self.assertEqual(exit_status, 1)
        self.assertEqual(verify_record(output)["status"], "FAIL")

    def test_deterministic_double_run_compares_literal_file_bytes(self) -> None:
        writer = (
            "from pathlib import Path; import sys; "
            "Path(sys.argv[1]).write_bytes(b'deterministic\\x00payload'); print(sys.argv[1])"
        )
        plan = self.write_plan(
            "double",
            [
                {
                    "id": "modified",
                    "root": "modified",
                    "commands": [
                        {
                            "id": "build-a",
                            "argv": ["${PYTHON}", "-c", writer, "${ARTIFACT_ROOT}/a.bin"],
                            "inputs": ["input.txt"],
                            "outputs": [
                                {
                                    "path": "${ARTIFACT_ROOT}/a.bin",
                                    "delivery_role": "modified_artifact",
                                }
                            ],
                        },
                        {
                            "id": "build-b",
                            "argv": ["${PYTHON}", "-c", writer, "${ARTIFACT_ROOT}/b.bin"],
                            "inputs": ["input.txt"],
                            "outputs": ["${ARTIFACT_ROOT}/b.bin"],
                        },
                    ],
                }
            ],
            [
                {
                    "id": "a-equals-b",
                    "left": "${ARTIFACT_ROOT}/a.bin",
                    "right": "${ARTIFACT_ROOT}/b.bin",
                    "expect": "equal",
                }
            ],
        )
        record, output, _artifacts = self.run_plan("double", plan)
        self.assertEqual(record["status"], "PASS")
        self.assertTrue(record["comparisons"][0]["equal"])
        self.assertEqual(
            record["comparisons"][0]["left"]["sha256"],
            record["comparisons"][0]["right"]["sha256"],
        )
        self.assertEqual(
            record["delivery_handoff"]["roles"]["modified_artifact"][0]["snapshot"]["sha256"],
            record["comparisons"][0]["left"]["sha256"],
        )
        self.assertEqual(verify_record(output)["persistent_outputs_reopened"], 2)

    def test_sidecar_tamper_is_detected_on_reopen(self) -> None:
        plan = self.write_plan(
            "sidecar",
            [
                {
                    "id": "modified",
                    "root": "modified",
                    "commands": [
                        {
                            "id": "large-output",
                            "argv": ["${PYTHON}", "-c", "import sys; sys.stdout.buffer.write(b'x'*4096)"],
                            "inputs": ["input.txt"],
                        }
                    ],
                }
            ],
        )
        record, output, _artifacts = self.run_plan("sidecar", plan, inline_limit=8)
        stream = record["commands"][0]["stdout"]
        self.assertEqual(stream["storage"], "sidecar")
        sidecar = output.parent / stream["path"]
        sidecar.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValidationError, "stream byte count or SHA-256 mismatch"):
            verify_record(output)

    def test_engine_inspector_reports_prefix_and_empty_target_behavior(self) -> None:
        engine = self.root / "engine.tsv"
        engine.write_text(
            "# ja<TAB>zhCN\n戻る\t返回\n消す\t\n^prefix %s\t前缀 %s\n",
            encoding="utf-8",
            newline="\n",
        )
        report = inspect_engine(engine)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["rows"], 3)
        self.assertEqual(report["prefix_rows"], 1)
        self.assertEqual(report["empty_target_rows"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
