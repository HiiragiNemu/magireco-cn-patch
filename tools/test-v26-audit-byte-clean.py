#!/usr/bin/env python3
"""Verify that committed v26 audit bytes survive Git clean filters unchanged."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MACHINE = ROOT / "magica/i18n_audit/release_v26_authority/machine_translation_review"
PROTECTED = ROOT / "magica/i18n_audit/release_v26_authority/protected_authority"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_lf_only(path: Path) -> None:
    data = path.read_bytes()
    if b"\r" in data:
        raise AssertionError(f"non-LF line ending in audited text file: {path}")


def git_blob(path: Path, *, filtered: bool) -> str:
    args = ["git", "-C", str(ROOT), "hash-object"]
    if filtered:
        args.extend(["--path", path.relative_to(ROOT).as_posix()])
    else:
        args.append("--no-filters")
    args.append(str(path))
    return subprocess.check_output(
        args,
        text=True,
        encoding="utf-8",
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    ).strip()


def verify_machine_sums() -> int:
    checked = 0
    for raw in (MACHINE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not raw:
            continue
        expected, relative = raw.split("  ", 1)
        target = (MACHINE / relative).resolve()
        actual = sha256(target)
        if actual != expected:
            raise AssertionError(
                f"machine-review SHA256SUMS drift for {relative}: {actual} != {expected}"
            )
        checked += 1
    return checked


def main() -> None:
    text_files = sorted(
        path
        for folder in (MACHINE, PROTECTED)
        for path in folder.rglob("*")
        if path.is_file() and path.suffix != ".gz"
    )
    git_clean_checked = 0
    for path in text_files:
        assert_lf_only(path)
        raw_blob = git_blob(path, filtered=False)
        clean_blob = git_blob(path, filtered=True)
        if raw_blob != clean_blob:
            raise AssertionError(
                f"Git clean would mutate audited bytes: {path.relative_to(ROOT).as_posix()}"
            )
        git_clean_checked += 1

    summary = json.loads((MACHINE / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((PROTECTED / "protection_manifest.json").read_text(encoding="utf-8"))
    expected_summary = manifest["baseline"]["machine_review_summary_sha256"]
    actual_summary = sha256(MACHINE / "summary.json")
    if actual_summary != expected_summary:
        raise AssertionError(
            f"protection manifest summary binding drift: {actual_summary} != {expected_summary}"
        )
    if summary.get("counts", {}).get("master") != 12930:
        raise AssertionError("unexpected machine-review master count")

    print(
        json.dumps(
            {
                "status": "PASS",
                "lf_text_files": len(text_files),
                "git_clean_unchanged": git_clean_checked,
                "sha256sums_entries": verify_machine_sums(),
                "machine_review_summary_sha256": actual_summary,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
