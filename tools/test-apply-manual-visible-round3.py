#!/usr/bin/env python3
"""Independent fixture tests for apply-manual-visible-round3.py."""

from __future__ import annotations

import csv, json, os
from pathlib import Path
import subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/apply-manual-visible-round3.py"
TARGETS = {
    "magica/resource/image_web/_json/help.json": ("help/16/01/title", "title", "JP_HELP", "CN_HELP"),
    "magica/resource/image_web/_json/SecondPartLastInfo.json": ("secondPartLastInfo/enemyInfo/list/0/enemyName", "enemyName", "JP_ENEMY", "CN_ENEMY"),
    "magica/js/event/EventWalpurgis/json/stamp/commentList.json": ("commentList/0", "comment", "JP_STAMP", "CN_STAMP"),
    "magica/css/patrol/PatrolDeckView.css": ("css-content/JP_CSS_A/0", "content", "JP_CSS_A", "CN_CSS_A"),
    "magica/css/regularEvent/groupBattle/RegularEventGroupBattleRanking.css": ("css-content/JP_CSS_B/0", "content", "JP_CSS_B", "CN_CSS_B"),
    "magica/css/regularEvent/groupBattle/RegularEventGroupBattleUser.css": ("css-content/JP_CSS_C/0", "content", "JP_CSS_C", "CN_CSS_C"),
    "magica/json/announcements/announcements.json": ("id=1/text", "text", "<p>JP_NEWS</p>", "<p>CN_NEWS</p>"),
    "magica/json/event_banner/event_banner.json": ("bannerId=7/description", "description", "JP_BANNER", "CN_BANNER"),
}
COLUMNS = ("item_id", "target_path", "stable_key", "field", "source_text", "final_cn", "upstream_source_path")


def source_bytes(target: str) -> bytes:
    if target.endswith("help.json"):
        value = {"help": [{"type": "16", "title": "G", "cols": [{"id": "01", "title": "JP_HELP", "text": "属性相性"}]}]}
    elif target.endswith("SecondPartLastInfo.json"):
        value = {"secondPartLastInfo": {"enemyInfo": {"name": "N", "list": [{"enemyName": "JP_ENEMY"}]}}}
    elif target.endswith("commentList.json"):
        value = {"commentList": ["JP_STAMP"]}
    elif target.endswith("announcements.json"):
        value = [{"id": 1, "subject": "S", "text": "<p>JP_NEWS</p>"}]
    elif target.endswith("event_banner.json"):
        value = [{"bannerId": 7, "description": "JP_BANNER", "bannerText": "T"}]
    else:
        marker = TARGETS[target][2]
        extra = (
            '\nb:before{content:"必要GP";color:blue}'
            if "groupBattle" in target else ""
        )
        return f'a:before{{content:"{marker}";color:red}}{extra}\n'.encode()
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def fixture(base: Path, duplicate: bool = False, outside: bool = False):
    repo, sources, state = base / "repo", base / "sources", base / "state"
    repo.mkdir(parents=True); sources.mkdir()
    rows = []
    for index, (target, values) in enumerate(TARGETS.items()):
        source = sources / f"source-{index}{Path(target).suffix}"
        source.write_bytes(source_bytes(target))
        rows.append(dict(zip(COLUMNS, (f"ITEM-{index}", target, *values, str(source)))))
    if duplicate: rows.append(dict(rows[0], item_id="DUPLICATE"))
    if outside: rows[0]["target_path"] = "magica/not-allowed.json"
    review = base / "manual_translation_round3.tsv"
    with review.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    return repo, sources, state, review


def run(repo: Path, sources: Path, state: Path, review: Path, mode: str, *extra: str, ok: bool = True):
    env = dict(
        os.environ,
        MANUAL_ROUND3_TEST_MODE="1",
        PYTHONIOENCODING="utf-8",
    )
    command = [sys.executable, str(TOOL), mode, "--repo-root", str(repo), "--review-tsv", str(review), "--state-dir", str(state), "--allowed-source-root", str(sources), *extra]
    result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, env=env)
    if ok != (result.returncode == 0): raise AssertionError(f"{command}\n{result.stdout}\n{result.stderr}")
    return result


def absent(repo: Path) -> bool: return all(not (repo / target).exists() for target in TARGETS)
def present(repo: Path) -> bool: return all((repo / target).is_file() for target in TARGETS)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="manual-round3-") as name:
        top = Path(name)
        repo, sources, state, review = fixture(top / "happy")
        manifest = json.loads(run(repo, sources, state, review, "--prepare").stdout)
        assert manifest["target_count"] == 8 and manifest["item_count"] == 8 and absent(repo)
        run(repo, sources, state, review, "--apply"); assert present(repo)
        run(repo, sources, state, review, "--verify")
        layered_targets = {
            "magica/resource/image_web/_json/help.json": ("属性相性", "属性克制"),
            "magica/css/regularEvent/groupBattle/RegularEventGroupBattleRanking.css": ("必要GP", "所需GP"),
            "magica/css/regularEvent/groupBattle/RegularEventGroupBattleUser.css": ("必要GP", "所需GP"),
        }
        for target, (old, new) in layered_targets.items():
            path = repo / target
            before = path.read_bytes()
            assert before.count(old.encode()) == 1 and before.count(new.encode()) == 0
            path.write_bytes(before.replace(old.encode(), new.encode(), 1))
        verification = json.loads(run(repo, sources, state, review, "--verify").stdout)
        statuses = {row["target"]: row["status"] for row in verification["targets"]}
        assert all(statuses[target] == "layered-round4-visible-closure" for target in layered_targets)
        assert sum(status == "exact-manual-round3" for status in statuses.values()) == 5
        layered_bytes = {target: (repo / target).read_bytes() for target in layered_targets}
        run(repo, sources, state, review, "--apply")
        assert all((repo / target).read_bytes() == layered_bytes[target] for target in layered_targets)
        run(repo, sources, state, review, "--rollback"); assert absent(repo)

        repo, sources, state, review = fixture(top / "source-drift")
        run(repo, sources, state, review, "--prepare")
        next(sources.iterdir()).write_text("drift")
        run(repo, sources, state, review, "--apply", ok=False); assert absent(repo)

        repo, sources, state, review = fixture(top / "outside", outside=True)
        run(repo, sources, state, review, "--prepare", ok=False); assert absent(repo)

        repo, sources, state, review = fixture(top / "duplicate", duplicate=True)
        run(repo, sources, state, review, "--prepare", ok=False); assert absent(repo)

        repo, sources, state, review = fixture(top / "write-fail")
        run(repo, sources, state, review, "--prepare")
        run(repo, sources, state, review, "--apply", "--test-fail-after", "3", ok=False)
        assert absent(repo)

        repo, sources, state, review = fixture(top / "target-drift")
        run(repo, sources, state, review, "--prepare"); run(repo, sources, state, review, "--apply")
        target = repo / next(iter(TARGETS)); target.write_text("drift")
        run(repo, sources, state, review, "--verify", ok=False)
        run(repo, sources, state, review, "--rollback", ok=False)
        assert target.read_text() == "drift"

        repo, sources, state, review = fixture(top / "checkpoint-drift")
        run(repo, sources, state, review, "--prepare")
        prepared = state / "prepared" / next(iter(TARGETS))
        data = bytearray(prepared.read_bytes()); data[-2] ^= 1; prepared.write_bytes(data)
        run(repo, sources, state, review, "--apply", ok=False); assert absent(repo)

    print("manual round3 tests: 7/7 PASS")
    return 0


if __name__ == "__main__": raise SystemExit(main())
