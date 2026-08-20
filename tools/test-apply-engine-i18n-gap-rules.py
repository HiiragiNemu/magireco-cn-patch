#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
SCRIPT = TOOLS / "apply-engine-i18n-gap-rules.py"

STATIC = [
    "50 AP Potion\tAP回复药50",
    "AP Potion\tAP回复药",
    "Magia Stones\t魔法石",
    "^Use \t消费 ",
    "^Stock: \t持有数 ",
    "^Cost: \t消费 ",
    "Restore\t回复",
]
UNSUPPORTED = [
    "~ AP will recover in \t AP恢复倒计时：",
    "~ / AP will be fully recovered in \t / AP全满倒计时：",
]


def base_table() -> str:
    rules = [f"BASE-{index:03d}\t基础-{index:03d}" for index in range(307)]
    return "# engine fixture\n" + "\n".join(rules + STATIC) + "\n"


def timer_rules() -> list[str]:
    result = []
    for total_seconds in range(301):
        minutes, seconds = divmod(total_seconds, 60)
        timer = f"{minutes}:{seconds:02d}"
        result.append(
            f"^1 AP will recover in {timer} / AP will be fully recovered in "
            f"\t距回复1 AP还有 {timer} / 距AP全部回复还有 "
        )
    return result


def active_table() -> str:
    return base_table() + "\n".join(timer_rules()) + "\n"


class EngineGapRuleTests(unittest.TestCase):
    def run_tool(self, mode: str, table: Path, report: Path, ok: bool = True):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), mode, "--table", str(table), "--report", str(report)],
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=env,
        )
        self.assertEqual(proc.returncode == 0, ok, proc.stdout + proc.stderr)
        return proc

    def test_apply_verify_rollback_round_trip_preserves_all_unrelated_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            table = root / "engine_i18n.tsv"
            report = root / "report.json"
            original = base_table()
            table.write_text(original, encoding="utf-8", newline="")
            self.run_tool("check-before", table, report)
            self.run_tool("apply", table, report)
            self.assertEqual(table.read_text(encoding="utf-8"), active_table())
            self.run_tool("verify", table, report)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["mode"], "current-main-compatible")
            self.assertEqual(data["operation"], "verify")
            self.assertEqual(data["active_rules"], 308)
            self.assertEqual(data["rules"], 308)
            self.assertEqual(data["exact"], 4)
            self.assertEqual(data["prefix"], 304)
            self.assertEqual(data["substring"], 0)
            self.assertEqual(data["baseline_rules"], 314)
            self.assertEqual(data["generated_timer_rules"], 301)
            self.assertEqual(data["unsupported_rules"], 2)
            self.assertEqual(data["unsupported_present"], 0)
            self.assertEqual(data["logical_rule_count"], 615)
            self.assertEqual(data["physical_line_count"], 616)
            self.assertEqual(data["final_engine_rule_count"], 615)
            self.assertTrue(data["timer_coverage"]["all_values_present"])
            self.assertEqual(data["timer_coverage"]["value_count"], 301)
            self.assertEqual(len(data["removed_unsupported_records"]), 2)
            self.assertEqual(
                {row["source_tier"] for row in data["records"]},
                {"official-cn", "confirmed-human"},
            )
            self.assertTrue(
                all(
                    row["runtime_contract"] == "supported-by-current-main-exact-or-prefix"
                    for row in data["records"]
                )
            )
            self.assertTrue(
                all(
                    row["runtime_contract"]
                    == "unsupported-by-current-main-and-removed-from-runtime-table"
                    for row in data["removed_unsupported_records"]
                )
            )
            self.assertTrue(data["unrelated_content_preserved"])
            self.run_tool("rollback", table, report)
            self.assertEqual(table.read_bytes(), original.encode("utf-8"))

    def test_competing_source_fails_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            table = root / "engine_i18n.tsv"
            report = root / "report.json"
            original = base_table().replace("BASE-000\t基础-000", "50 AP Potion\t错误值")
            table.write_text(original, encoding="utf-8", newline="")
            self.run_tool("apply", table, report, ok=False)
            self.assertEqual(table.read_bytes(), original.encode("utf-8"))

    def test_every_native_timer_value_translates_both_labels_and_preserves_full_timer(self):
        rules = []
        for line in timer_rules():
            source, target = line[1:].split("\t", 1)
            rules.append((source, target))
        self.assertEqual(len(rules), 301)
        for total_seconds in range(301):
            minutes, seconds = divmod(total_seconds, 60)
            timer = f"{minutes}:{seconds:02d}"
            source = f"1 AP will recover in {timer} / AP will be fully recovered in 12:34:56"
            expected = f"距回复1 AP还有 {timer} / 距AP全部回复还有 12:34:56"
            matched = next((target + source[len(prefix):] for prefix, target in rules if source.startswith(prefix)), None)
            self.assertEqual(matched, expected)

        outside = "1 AP will recover in 5:01 / AP will be fully recovered in 12:34:56"
        self.assertIsNone(next((target + outside[len(prefix):] for prefix, target in rules if outside.startswith(prefix)), None))

    def test_unsupported_timer_backflow_fails_without_write(self):
        for unsupported in UNSUPPORTED:
            with self.subTest(unsupported=unsupported), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                table = root / "engine_i18n.tsv"
                report = root / "report.json"
                original = active_table() + unsupported + "\n"
                table.write_text(original, encoding="utf-8", newline="")
                self.run_tool("verify", table, report, ok=False)
                self.assertEqual(table.read_bytes(), original.encode("utf-8"))

    def test_duplicate_active_rule_fails_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            table = root / "engine_i18n.tsv"
            report = root / "report.json"
            original = active_table() + timer_rules()[0] + "\n"
            table.write_text(original, encoding="utf-8", newline="")
            self.run_tool("verify", table, report, ok=False)
            self.assertEqual(table.read_bytes(), original.encode("utf-8"))

    def test_active_target_drift_fails_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            table = root / "engine_i18n.tsv"
            report = root / "report.json"
            original = active_table().replace("Restore\t回复", "Restore\t错误值")
            table.write_text(original, encoding="utf-8", newline="")
            self.run_tool("verify", table, report, ok=False)
            self.assertEqual(table.read_bytes(), original.encode("utf-8"))

    def test_unrelated_count_drift_fails_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            table = root / "engine_i18n.tsv"
            report = root / "report.json"
            original = active_table() + "UNEXPECTED\t意外\n"
            table.write_text(original, encoding="utf-8", newline="")
            self.run_tool("verify", table, report, ok=False)
            self.assertEqual(table.read_bytes(), original.encode("utf-8"))

    def test_repeated_apply_fails_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            table = root / "engine_i18n.tsv"
            report = root / "report.json"
            table.write_text(base_table(), encoding="utf-8", newline="")
            self.run_tool("apply", table, report)
            applied = table.read_bytes()
            self.run_tool("apply", table, report, ok=False)
            self.assertEqual(table.read_bytes(), applied)


if __name__ == "__main__":
    unittest.main(verbosity=2)
