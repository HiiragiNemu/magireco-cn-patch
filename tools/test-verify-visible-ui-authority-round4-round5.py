#!/usr/bin/env python3
"""Mutation tests for the read-only round-4/round-5 authority verifier."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/verify-visible-ui-authority-round4-round5.py"
ROUND4 = Path(
    "magica/research/totentanz-full-localization-20260817/"
    "visible-ui-authority-round4-chara-kana"
)
ROUND5 = Path(
    "magica/research/totentanz-full-localization-20260817/"
    "visible-ui-authority-round5-sisters"
)
FILES = (
    Path("magica/js/libs/charaList.json"),
    Path("magica/js/libs/pieceList.json"),
    Path("magica/js/libs/jquery-3.7.1.min.js"),
    ROUND4 / "character_kana_apply_manifest.json",
    ROUND4 / "application_verification.json",
    ROUND4 / "character_kana_visible_candidates.tsv",
    ROUND4 / "official_chara_kana_structural_sample.tsv",
    ROUND4 / "protected_operation_siblings.json",
    ROUND5 / "remaining_explicit_visible_apply_manifest.json",
    ROUND5 / "application_verification.json",
    ROUND5 / "remaining_explicit_visible_candidates.tsv",
    ROUND5 / "protected_operation_siblings.json",
)


def run(repo: Path, success: bool = True) -> dict:
    command = [sys.executable, str(TOOL), "--repo-root", str(repo)]
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
    )
    if success != (result.returncode == 0):
        raise AssertionError(f"{command}\n{result.stdout}\n{result.stderr}")
    payload = json.loads(result.stdout)
    assert (payload["status"] == "PASS") == success
    return payload


def fixture(base: Path, name: str) -> Path:
    repo = base / name
    for relative in FILES:
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return repo


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    live = run(ROOT)
    assert live["round4"]["operations"] == 139
    assert live["round4"]["latin_kana"] == 0
    assert live["round5"]["piece_1731"] == "姐妹"
    assert live["runtime"]["charaList_embedded_equals_standalone"]
    assert live["runtime"]["pieceList_embedded_equals_standalone"]

    with tempfile.TemporaryDirectory(prefix="visible-authority-r4-r5-") as temporary:
        base = Path(temporary)

        repo = fixture(base, "happy")
        run(repo)

        repo = fixture(base, "latin-kana")
        path = repo / "magica/js/libs/charaList.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in rows if row["id"] == 1020)["kana"] = "Satori Kagome"
        write_json(path, rows)
        failure = run(repo, success=False)
        assert any("Latin kana remains" in error for error in failure["errors"])

        repo = fixture(base, "duplicate-id")
        path = repo / "magica/js/libs/charaList.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows.append(dict(rows[0]))
        write_json(path, rows)
        failure = run(repo, success=False)
        assert any("duplicate stable key" in error for error in failure["errors"])

        repo = fixture(base, "unclear-source")
        path = repo / ROUND4 / "character_kana_apply_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["operations"][0]["source_tier"] = "unknown"
        write_json(path, manifest)
        failure = run(repo, success=False)
        assert any("source tier drift" in error for error in failure["errors"])

        repo = fixture(base, "piece-drift")
        path = repo / "magica/js/libs/pieceList.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in rows if row["pieceId"] == 1731)["pieceName"] = "Sisters"
        write_json(path, rows)
        failure = run(repo, success=False)
        assert any("not localized" in error for error in failure["errors"])

        repo = fixture(base, "embedded-drift")
        path = repo / "magica/js/libs/jquery-3.7.1.min.js"
        text = path.read_text(encoding="utf-8")
        needle = '"id":1020,"name":"佐鸟笼目","kana":"佐鸟笼目"'
        assert needle in text
        replacement = needle.replace('"kana":"佐鸟笼目"', '"kana":"BROKEN"')
        path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
        failure = run(repo, success=False)
        assert any("jQuery payload differs" in error for error in failure["errors"])

        repo = fixture(base, "sibling-field-drift")
        path = repo / "magica/js/libs/charaList.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in rows if row["id"] == 1020)["school"] = "漂移"
        write_json(path, rows)
        failure = run(repo, success=False)
        assert any("non-kana sibling field drift" in error for error in failure["errors"])

    print("visible authority round4/round5 tests: 7/7 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
