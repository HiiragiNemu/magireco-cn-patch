#!/usr/bin/env python3
"""Contract and transaction tests for the round-3 recovery tool."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/apply-authority-source-exhaustion-round3.py"
EVIDENCE = (
    ROOT
    / "magica/research/totentanz-full-localization-20260817"
    / "authority-source-exhaustion-round3"
)
TARGETS = (
    "magica/js/event/raid/EventRaidMessage.json",
    "magica/resource/image_web/_json/help.json",
    "magica/resource/image_web/_json/puellaHistoria/overview.json",
    "magica/template/chara/CharaList.html",
    "magica/template/collection/CharaCollection.html",
    "magica/template/quest/CharaQuest.html",
    "magica/template/terms/Terms.html",
    "magica/template/user/MyPage.html",
)


def run(repo: Path, state: Path, mode: str, *extra: str, success: bool = True):
    env = dict(os.environ, ROUND3_TEST_MODE="1")
    command = [
        sys.executable, str(TOOL), mode, "--repo-root", str(repo),
        "--evidence-dir", str(EVIDENCE), "--state-dir", str(state), *extra,
    ]
    result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, env=env)
    if success != (result.returncode == 0):
        raise AssertionError(f"{command}\n{result.stdout}\n{result.stderr}")
    return result


def absent(repo: Path) -> bool:
    return all(not (repo / target).exists() for target in TARGETS)


def present(repo: Path) -> bool:
    return all((repo / target).is_file() for target in TARGETS)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="round3-test-") as temporary:
        base = Path(temporary)

        repo, state = base / "happy", base / "happy-state"
        repo.mkdir()
        manifest = json.loads(run(repo, state, "--prepare").stdout)
        assert manifest["authority_records"] == 275 and manifest["target_count"] == 8
        assert absent(repo)
        run(repo, state, "--apply"); assert present(repo)
        run(repo, state, "--verify")
        run(repo, state, "--rollback"); assert absent(repo)

        repo, state = base / "unexpected", base / "unexpected-state"
        repo.mkdir(); run(repo, state, "--prepare")
        bad = repo / TARGETS[3]; bad.parent.mkdir(parents=True); bad.write_text("unexpected")
        run(repo, state, "--apply", success=False)
        assert bad.read_text() == "unexpected" and sum((repo / item).exists() for item in TARGETS) == 1

        repo, state = base / "apply-fail", base / "apply-fail-state"
        repo.mkdir(); run(repo, state, "--prepare")
        run(repo, state, "--apply", "--test-fail-after", "3", success=False)
        assert absent(repo)

        repo, state = base / "rollback-fail", base / "rollback-fail-state"
        repo.mkdir(); run(repo, state, "--prepare"); run(repo, state, "--apply")
        run(repo, state, "--rollback", "--test-fail-after", "3", success=False)
        assert present(repo); run(repo, state, "--verify")

        drift = repo / TARGETS[0]; drift.write_text("drift")
        run(repo, state, "--verify", success=False)
        run(repo, state, "--rollback", success=False)
        assert drift.read_text() == "drift"

    print("round3 tests: 5/5 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
