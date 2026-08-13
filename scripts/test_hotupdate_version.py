#!/usr/bin/env python3
"""Regression tests for preview-to-publish version stability."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hotupdate_version import choose_candidate_version, decide_candidate_version


class HotUpdateVersionTest(unittest.TestCase):
    @staticmethod
    def write(path: Path, version: int, size: int = 100, md5: str = "a" * 32) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": version, "size": size, "md5": md5}),
            encoding="utf-8",
        )

    def test_two_stage_js_preview_then_publish_reuses_v26(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "configures" / "version_js.json"
            candidate = root / "configures" / "version_js_new.json"
            self.write(official, 25)

            preview = choose_candidate_version(official, [candidate], 200, "b" * 32)
            self.assertEqual(preview, 26)
            self.write(candidate, preview, 200, "b" * 32)

            publish = choose_candidate_version(official, [candidate], 200, "b" * 32)
            self.assertEqual(publish, 26)

    def test_js_preview_does_not_change_scenario_version(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_official = root / "version_js.json"
            js_candidate = root / "version_js_new.json"
            scenario_official = root / "version_scenario.json"
            scenario_candidate = root / "version_scenario_new.json"
            self.write(js_official, 25)
            self.write(scenario_official, 3217)

            self.write(
                js_candidate,
                choose_candidate_version(js_official, [js_candidate], 200, "b" * 32),
                200,
                "b" * 32,
            )
            self.assertEqual(
                choose_candidate_version(js_official, [js_candidate], 200, "b" * 32),
                26,
            )
            self.assertEqual(
                choose_candidate_version(
                    scenario_official, [scenario_candidate], 200, "b" * 32
                ),
                3218,
            )
            self.assertFalse(scenario_candidate.exists())

    def test_matching_legacy_preview_gap_is_reused_for_publish(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            candidate = root / "candidate.json"
            self.write(official, 10)
            self.write(candidate, 65, 200, "b" * 32)
            decision = decide_candidate_version(
                official, [candidate], 200, "b" * 32
            )
            self.assertEqual(decision.version, 65)
            self.assertEqual(decision.strategy, "reuse-matching-preview")

    def test_different_bytes_after_legacy_preview_gap_allocate_next_version(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            candidate = root / "candidate.json"
            self.write(official, 52, 150, "a" * 32)
            self.write(candidate, 65, 200, "b" * 32)
            decision = decide_candidate_version(
                official, [candidate], 300, "c" * 32
            )
            self.assertEqual(decision.version, 66)
            self.assertEqual(decision.strategy, "allocate-after-different-preview")
            self.assertEqual(decision.existing_candidate_version, 65)
            self.assertEqual(decision.package_md5, "c" * 32)

    def test_nonforward_candidate_identity_is_not_reused_for_new_bytes(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            candidate = root / "candidate.json"
            self.write(official, 65, 200, "a" * 32)
            self.write(candidate, 65, 300, "b" * 32)
            self.assertEqual(
                choose_candidate_version(official, [candidate], 300, "b" * 32),
                66,
            )

    def test_reverting_to_official_bytes_after_high_preview_remains_monotonic(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            candidate = root / "candidate.json"
            self.write(official, 52, 200, "a" * 32)
            self.write(candidate, 65, 300, "b" * 32)
            decision = decide_candidate_version(
                official, [candidate], 200, "a" * 32
            )
            self.assertEqual(decision.version, 66)
            self.assertEqual(decision.strategy, "allocate-after-different-preview")

    def test_missing_official_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with self.assertRaisesRegex(ValueError, "official version file is missing"):
                choose_candidate_version(root / "missing.json", [], 200, "b" * 32)

    def test_malformed_official_or_candidate_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            candidate = root / "candidate.json"
            official.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "malformed"):
                choose_candidate_version(official, [], 200, "b" * 32)

            self.write(official, 25)
            candidate.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "malformed"):
                choose_candidate_version(official, [candidate], 200, "b" * 32)

    def test_valid_official_without_candidate_increments_once(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            self.write(official, 25)
            self.assertEqual(
                choose_candidate_version(
                    official, [root / "missing-new.json"], 200, "b" * 32
                ),
                26,
            )

    def test_published_package_retry_keeps_official_version(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            candidate = root / "candidate.json"
            self.write(official, 26, 200, "b" * 32)
            self.write(candidate, 26, 200, "b" * 32)
            self.assertEqual(
                choose_candidate_version(official, [candidate], 200, "b" * 32),
                26,
            )

    def test_decision_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            self.write(official, 25)
            decision = decide_candidate_version(
                official, [root / "missing.json"], 200, "b" * 32
            )
            self.assertEqual(
                decision.to_dict(),
                {
                    "version": 26,
                    "strategy": "allocate-after-official",
                    "official_version": 25,
                    "official_size": 100,
                    "official_md5": "a" * 32,
                    "existing_candidate_version": None,
                    "existing_candidate_size": None,
                    "existing_candidate_md5": None,
                    "package_size": 200,
                    "package_md5": "b" * 32,
                },
            )

    def test_disagreeing_candidate_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            official = root / "official.json"
            candidate_a = root / "a.json"
            candidate_b = root / "b.json"
            self.write(official, 25)
            self.write(candidate_a, 26, 200, "b" * 32)
            self.write(candidate_b, 26, 201, "c" * 32)
            with self.assertRaisesRegex(ValueError, "disagree"):
                choose_candidate_version(
                    official, [candidate_a, candidate_b], 200, "b" * 32
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
