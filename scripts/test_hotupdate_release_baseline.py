#!/usr/bin/env python3
"""Tests for authoritative ``latest`` Release hot-update baselines."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from hotupdate_release_baseline import (
    ReleaseBaselineError,
    validate_release_baseline,
)


class ReleaseFixture:
    def __init__(self, root: Path, scope: str = "js") -> None:
        self.root = root
        self.asset_dir = root / "assets"
        self.asset_dir.mkdir()
        self.scope = scope
        self.assets: list[dict] = []
        self.next_id = 1
        if scope == "js":
            self.zip_name = "cn_js_update.zip"
            self.version_name = "version_js.json"
        else:
            self.zip_name = "cn_scenario_update.zip"
            self.version_name = "version_scenario.json"

    def add_asset(self, name: str, data: bytes, *, download: bool) -> None:
        self.assets.append(
            {
                "id": self.next_id,
                "name": name,
                "size": len(data),
                "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
            }
        )
        self.next_id += 1
        if download:
            (self.asset_dir / name).write_bytes(data)

    def add_triplet(self, *, version: int, data: bytes, preview: bool = False) -> None:
        suffix = "_new" if preview else ""
        zip_name = self.zip_name.replace(".zip", f"{suffix}.zip")
        version_name = self.version_name.replace(".json", f"{suffix}.json")
        md5 = hashlib.md5(data).hexdigest()
        version_bytes = json.dumps(
            {"version": version, "size": len(data), "md5": md5}
        ).encode()
        self.add_asset(zip_name, data, download=True)
        self.add_asset(version_name, version_bytes, download=True)

    def write_release(self, *, tag: str = "latest") -> Path:
        path = self.root / "release.json"
        path.write_text(
            json.dumps(
                {
                    "id": 99,
                    "tag_name": tag,
                    "html_url": "https://example.invalid/releases/latest",
                    "published_at": "2026-08-13T00:00:00Z",
                    "assets": self.assets,
                }
            ),
            encoding="utf-8",
        )
        return path

    def validate(self):
        return validate_release_baseline(
            self.scope,
            self.write_release(),
            self.asset_dir,
            self.root / "validated" / self.version_name,
            self.root
            / "validated"
            / self.version_name.replace(".json", "_new.json"),
            self.root / "report.json",
        )


class HotUpdateReleaseBaselineTest(unittest.TestCase):
    def test_stable_release_triplet_becomes_canonical_baseline(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = ReleaseFixture(Path(raw))
            fixture.add_triplet(version=52, data=b"stable-js")
            report = fixture.validate()
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["stable"]["version"]["version"], 52)
            self.assertIsNone(report["preview"])
            self.assertFalse(report["repository_configures_trusted"])
            canonical = json.loads(
                (Path(raw) / "validated" / "version_js.json").read_text()
            )
            self.assertEqual(canonical["size"], len(b"stable-js"))

    def test_complete_preview_triplet_is_validated_as_candidate(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = ReleaseFixture(Path(raw))
            fixture.add_triplet(version=52, data=b"stable-js")
            fixture.add_triplet(version=65, data=b"preview-js", preview=True)
            report = fixture.validate()
            self.assertEqual(report["preview"]["version"]["version"], 65)
            candidate = json.loads(
                (Path(raw) / "validated" / "version_js_new.json").read_text()
            )
            self.assertEqual(candidate["version"], 65)

    def test_incomplete_preview_triplet_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = ReleaseFixture(Path(raw))
            fixture.add_triplet(version=52, data=b"stable-js")
            fixture.add_asset("version_js_new.json", b"{}", download=True)
            with self.assertRaisesRegex(ReleaseBaselineError, "preview triplet is incomplete"):
                fixture.validate()

    def test_downloaded_zip_must_match_release_snapshot(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = ReleaseFixture(Path(raw))
            fixture.add_triplet(version=52, data=b"stable-js")
            fixture.assets[0]["size"] += 1
            with self.assertRaisesRegex(ReleaseBaselineError, "metadata mismatch"):
                fixture.validate()

    def test_version_size_and_md5_must_match_zip_bytes(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = ReleaseFixture(Path(raw))
            fixture.add_triplet(version=52, data=b"stable-js")
            version_path = fixture.asset_dir / fixture.version_name
            bad_version = json.dumps(
                {"version": 52, "size": len(b"stable-js"), "md5": "0" * 32}
            ).encode()
            version_path.write_bytes(bad_version)
            version_asset = next(
                asset for asset in fixture.assets if asset["name"] == fixture.version_name
            )
            version_asset["size"] = len(bad_version)
            version_asset["digest"] = (
                "sha256:" + hashlib.sha256(bad_version).hexdigest()
            )
            with self.assertRaisesRegex(ReleaseBaselineError, "zip bytes disagree"):
                fixture.validate()

    def test_downloaded_json_digest_must_match_release_snapshot(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = ReleaseFixture(Path(raw))
            fixture.add_triplet(version=52, data=b"stable-js")
            (fixture.asset_dir / fixture.version_name).write_bytes(b"tampered")
            with self.assertRaisesRegex(ReleaseBaselineError, "metadata mismatch"):
                fixture.validate()

    def test_release_asset_digest_is_required(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = ReleaseFixture(Path(raw))
            fixture.add_triplet(version=52, data=b"stable-js")
            fixture.assets[0]["digest"] = None
            with self.assertRaisesRegex(ReleaseBaselineError, "SHA-256"):
                fixture.validate()

    def test_exact_latest_tag_and_unique_asset_names_are_required(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fixture = ReleaseFixture(root)
            fixture.add_triplet(version=52, data=b"stable-js")
            release = fixture.write_release(tag="v52")
            with self.assertRaisesRegex(ReleaseBaselineError, "exact latest tag"):
                validate_release_baseline(
                    "js",
                    release,
                    fixture.asset_dir,
                    root / "version.json",
                    root / "candidate.json",
                    root / "report.json",
                )

            fixture.assets.append(dict(fixture.assets[0]))
            release = fixture.write_release()
            with self.assertRaisesRegex(ReleaseBaselineError, "duplicate asset name"):
                validate_release_baseline(
                    "js",
                    release,
                    fixture.asset_dir,
                    root / "version.json",
                    root / "candidate.json",
                    root / "report.json",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
