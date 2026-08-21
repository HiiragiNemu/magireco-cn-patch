#!/usr/bin/env python3
"""End-to-end verification for the v26 JS/WebView + engine TSV release."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "magica" / "i18n_audit" / "release_v26_authority"
EXCLUDED = ("magica/research/", "magica/i18n_audit/")
ENGINE = "madomagi/engine_i18n.tsv"
REPAIR_PREFIX = "madomagi/resource/image_native/"
REPAIR_MANIFEST = "madomagi/repair_manifest.json"
EXPECTED_ENGINE_ROWS = 615
MACHINE_REVIEW = AUDIT / "machine_translation_review"
PASS19_CORRECTIONS = AUDIT / "pass19_official_static_corrections.tsv"
ROUND3_ROOT = ROOT / "magica" / "research" / "totentanz-full-localization-20260817"
ROUND3_VISIBLE_MANIFEST = ROUND3_ROOT / "visible-ui-authority-round3" / "visible_ui_authority_round3_manifest.json"
ROUND3_CSS_VERIFICATION = ROUND3_ROOT / "visible-ui" / "css_content_verify_final.json"
ROUND3_IMAGE_OVERLAY = ROUND3_ROOT / "official-cn-image-overlay-round2" / "overlay_manifest.json"
ROUND3_IMAGE_CANVAS = ROUND3_ROOT / "current-canvas-image-round2" / "manifest.json"
HTML_STRUCTURE_TOOL = ROOT / "tools" / "build-html-structure-contract.py"
ROUND3_STATIC_MEMBERS = (
    "magica/js/event/raid/EventRaidMessage.json",
    "magica/template/chara/CharaList.html",
    "magica/template/collection/CharaCollection.html",
    "magica/template/quest/CharaQuest.html",
    "magica/template/user/MyPage.html",
)
FRONTEND_EMPTY_STATUS_COUNTS = {
    "runtime-absent/not-backlog": 18,
    "visible-cn-compatible-identity": 33,
    "identity-punctuation": 1,
    "official-source-verified": 1,
}
FRONTEND_EMPTY_STABLE_KEY_STATUS = {
    "global:0a9105b64231be7ff6b5": "visible-cn-compatible-identity",
    "global:0ba4a522d61b690bc808": "visible-cn-compatible-identity",
    "global:139349ae2024c7b0cb66": "runtime-absent/not-backlog",
    "global:1653151accee8a673eb5": "runtime-absent/not-backlog",
    "global:17fc4a0d39f616373959": "runtime-absent/not-backlog",
    "global:1d80f6e84eb88218b3cf": "runtime-absent/not-backlog",
    "global:21adedb16f095c1c9dbe": "visible-cn-compatible-identity",
    "global:247f96db649ef7bc8158": "visible-cn-compatible-identity",
    "global:250558ed3152ec3e23ef": "runtime-absent/not-backlog",
    "global:385dc40306774957d51b": "visible-cn-compatible-identity",
    "global:3bc18cfd7f105b5436bb": "runtime-absent/not-backlog",
    "global:504d9cf3acd3e8aa21f7": "visible-cn-compatible-identity",
    "global:54936347233a66e46f05": "runtime-absent/not-backlog",
    "global:58c5363bbc8e8c7801b3": "visible-cn-compatible-identity",
    "global:5a3aa9c3233df5ca2fab": "visible-cn-compatible-identity",
    "global:5e10466af9402b5612fc": "visible-cn-compatible-identity",
    "global:609b244eeafebab0b919": "visible-cn-compatible-identity",
    "global:6665ac4ca7f216509cba": "visible-cn-compatible-identity",
    "global:6ab22b863490d365d46b": "visible-cn-compatible-identity",
    "global:6ec4009aee4bddf7aa31": "official-source-verified",
    "global:6f23b8f870b39941382c": "visible-cn-compatible-identity",
    "global:79ce7c7e749732a59a8c": "visible-cn-compatible-identity",
    "global:7a019de4df4cdb2f3087": "runtime-absent/not-backlog",
    "global:7f1aadb517eb8109d02d": "runtime-absent/not-backlog",
    "global:859902e249af102fa272": "visible-cn-compatible-identity",
    "global:8b3a3f2114a17bf13859": "runtime-absent/not-backlog",
    "global:8ddcf27b4dac793d6bd3": "runtime-absent/not-backlog",
    "global:8faf1f2557511c7ae002": "visible-cn-compatible-identity",
    "global:99a2c6f00139f2983e4f": "visible-cn-compatible-identity",
    "global:9ab37a2a780884c94afd": "visible-cn-compatible-identity",
    "global:a75982d2f551033552a5": "visible-cn-compatible-identity",
    "global:b4a29cce993cfaf89d59": "visible-cn-compatible-identity",
    "global:be8694bf471ae99b2d3f": "visible-cn-compatible-identity",
    "global:bf7823c56d97233cbf82": "visible-cn-compatible-identity",
    "global:c08429a0618bb2fc1a7d": "runtime-absent/not-backlog",
    "global:c32cf7571e38a30a7ec0": "runtime-absent/not-backlog",
    "global:caf32677d62cc4340ec2": "visible-cn-compatible-identity",
    "global:cb5cfa0c3e59fe868f85": "identity-punctuation",
    "global:cd3b13999120d21b32fa": "runtime-absent/not-backlog",
    "global:cf129929e3e69ee01829": "visible-cn-compatible-identity",
    "global:d0da207c16280c478172": "visible-cn-compatible-identity",
    "global:d12aaa6b8295cd6f21ac": "runtime-absent/not-backlog",
    "global:d7b6359b08d443ff0031": "visible-cn-compatible-identity",
    "global:d902c1b1fa4aaad56527": "visible-cn-compatible-identity",
    "global:dee3a60702bf6f8a6387": "visible-cn-compatible-identity",
    "global:e10c0e0d483296cdb83c": "visible-cn-compatible-identity",
    "global:e969459d2dfe755ea748": "runtime-absent/not-backlog",
    "global:ea06d7d1b29b6d8f8e19": "visible-cn-compatible-identity",
    "global:ed6c8a6903b72b7ffd47": "visible-cn-compatible-identity",
    "global:f10bbb4d2dc49ec5d0ab": "runtime-absent/not-backlog",
    "global:f555fa8469649c51c0dd": "visible-cn-compatible-identity",
    "global:f649706b08b5e03ee2f4": "runtime-absent/not-backlog",
    "global:ffcefb10562cd485531a": "visible-cn-compatible-identity",
}
FRONTEND_OFFICIAL_STABLE_KEY = "global:6ec4009aee4bddf7aa31"
FRONTEND_PUNCTUATION_STABLE_KEY = "global:cb5cfa0c3e59fe868f85"
OFFICIAL_FORMATION_SHA256 = "8a73978062da1662bb7405d93ca37ef4e924b8a0b14bd66a56237e6ea8480f8d"
WIKI_PAGES_INDEX_SHA256 = "e3fda452a6e6e90d75025ae89c2dc1cb9bd40cc69540bf843e1eb2c3061b078a"

EXPECTED_PASS19_ROWS = {
    "P19-00001": {
        "file": "magica/template/formation/FormationQuest.html",
        "before": "属性相性", "after": "属性克制",
        "source_tier": "official_cn_dump",
        "source_sha256": OFFICIAL_FORMATION_SHA256,
        "match_method": "exact-path-dom-match",
        "confidence": "exact", "review_status": "official-source-verified",
        "expected_count": "1", "expected_after_count": "1",
    },
    "P19-00002": {
        "file": "magica/js/regularEvent/groupBattle/view/BossPageView.js",
        "before": "心情战", "after": "心魔战",
        "source_tier": "official_cn_dump",
        "source_sha256": "2714cc84dc89e4da207aad6311f9824af1b945bf9abf3674e17add727293e8a2",
        "match_method": "exact-path-term-match",
        "confidence": "exact", "review_status": "official-source-verified",
        "expected_count": "2", "expected_after_count": "2",
    },
    "P19-00003": {
        "file": "magica/js/regularEvent/groupBattle/view/UserPageView.js",
        "before": "心情战", "after": "心魔战",
        "source_tier": "official_cn_dump",
        "source_sha256": "3c4e6a200f6c7a705154f9653f7d062840bc47a77477b17d56c3aff575c29565",
        "match_method": "exact-path-term-match",
        "confidence": "exact", "review_status": "official-source-verified",
        "expected_count": "2", "expected_after_count": "2",
    },
    "P19-00004": {
        "file": "magica/js/regularEvent/RegularEventTop.js",
        "before": "心情战", "after": "心魔战",
        "source_tier": "official_cn_dump",
        "source_sha256": "a3b8963fdd47326bc1539beb86be915208e09e0cdaf10e186ac26673bc3fc588",
        "match_method": "exact-path-term-match",
        "confidence": "exact", "review_status": "official-source-verified",
        "expected_count": "1", "expected_after_count": "3",
    },
    "P19-00005": {
        "file": "magica/js/regularEvent/groupBattle/RegularEventGroupBattleTop.js",
        "before": "心情战", "after": "心魔战",
        "source_tier": "wiki", "source_sha256": WIKI_PAGES_INDEX_SHA256,
        "match_method": "exact-wiki-term-with-official-same-path-absence",
        "confidence": "high", "review_status": "wiki-source-verified",
        "expected_count": "3", "expected_after_count": "5",
    },
    "P19-00006": {
        "file": "magica/js/view/user/GlobalMenuView.js",
        "before": "心情战", "after": "心魔战",
        "source_tier": "wiki", "source_sha256": WIKI_PAGES_INDEX_SHA256,
        "match_method": "exact-wiki-term-with-official-same-path-absence",
        "confidence": "high", "review_status": "wiki-source-verified",
        "expected_count": "2", "expected_after_count": "2",
    },
}

EXPECTED_PRODUCT_TERM_FILES = {
    "心魔战": {
        "magica/js/collection/StoryCollection.js": 1,
        "magica/js/regularEvent/groupBattle/RegularEventGroupBattleTop.js": 5,
        "magica/js/regularEvent/groupBattle/view/BossPageView.js": 2,
        "magica/js/regularEvent/groupBattle/view/UserPageView.js": 2,
        "magica/js/regularEvent/RegularEventTop.js": 3,
        "magica/js/view/user/GlobalMenuView.js": 2,
        "magica/template/regularEvent/groupBattle/RegularEventGroupBattleBoss.html": 1,
        "magica/template/regularEvent/groupBattle/RegularEventGroupCommon.html": 1,
        "magica/template/test/EffectTest.html": 1,
        "magica/template/test/SdCharaTest.html": 1,
        "magica/template/user/EventRecord.html": 1,
    },
    "属性克制": {
        "magica/js/libs/cardMagiaMap.json": 5,
        "magica/js/libs/emotionSkillMap.json": 8,
        "magica/js/libs/itemList.json": 1,
        "magica/js/libs/jquery-3.7.1.min.js": 14,
        "magica/template/formation/FormationQuest.html": 1,
    },
}

# Later, separately audited localization rounds legitimately added the same
# accepted term outside the original Pass19 footprint.  Keep the Pass19 result
# counters unchanged while binding those additional product occurrences too.
EXPECTED_POST_PASS19_TERM_FILES = {
    "心魔战": {
        "magica/json/event_banner/event_banner.json": 1,
        "magica/resource/image_web/_json/help.json": 8,
        "magica/template/formation/DeckFormation.html": 1,
    },
    "属性克制": {
        "magica/resource/image_web/_json/help.json": 1,
    },
}

EXPECTED_MACHINE_REVIEW_COUNTS = {
    "master": 15976,
    "runtime": 12399,
    "static": 303,
    "frontend": 1685,
    "frontend_empty": 53,
    "glossary": 955,
    "overrides_fragments": 16,
    "engine": 615,
    "battle_miss_needs_review": 3,
    "battle_runtime_language_decisions": 8,
    "battle_runtime_unique_misses": 20,
    "pass18": 939,
    "visible_term_closure": 3136,
    "explicit_llm_history": 264,
}
EXPECTED_ENGINE_PARTITION = {
    "engine_runtime_i18n_confirmed_human": 301,
    "engine_runtime_i18n_intentional_fragment": 1,
    "engine_runtime_i18n_official": 58,
    "engine_runtime_i18n_root_reviewed": 252,
    "engine_runtime_i18n_wiki": 3,
}
EXPECTED_VISIBLE_TERM_CLOSURE_PARTITION = {
    "official-cn": 762,
    "root-reviewed-official-cn-terminology": 2372,
    "wiki-exact-stable-id-plus-official-cn-terminology": 2,
}

EXPECTED_PRODUCT_JSON_PATHS = tuple(sorted((
    "magica/js/event/EventWalpurgis/json/stamp/commentList.json",
    "magica/js/event/raid/EventRaidMessage.json",
    "magica/js/libs/arenaClassList.json",
    "magica/js/libs/cardList.json",
    "magica/js/libs/cardMagiaMap.json",
    "magica/js/libs/cardSkillMap.json",
    "magica/js/libs/chapterList.json",
    "magica/js/libs/charaList.json",
    "magica/js/libs/charaMessageList.json",
    "magica/js/libs/doppelCardMagiaMap.json",
    "magica/js/libs/doppelList.json",
    "magica/js/libs/emotionSkillMap.json",
    "magica/js/libs/enemyList.json",
    "magica/js/libs/eventList.json",
    "magica/js/libs/eventStoryList.json",
    "magica/js/libs/formationSheetList.json",
    "magica/js/libs/giftList.json",
    "magica/js/libs/itemList.json",
    "magica/js/libs/live2dList.json",
    "magica/js/libs/patrolAreaList.json",
    "magica/js/libs/pieceList.json",
    "magica/js/libs/pieceSkillMap.json",
    "magica/js/libs/placeSkillMap.json",
    "magica/js/libs/sectionList.json",
    "magica/js/libs/shopItemList.json",
    "magica/json/announcements/announcements.json",
    "magica/json/event_banner/event_banner.json",
    "magica/resource/image_web/_json/SecondPartLastInfo.json",
    "magica/resource/image_web/_json/help.json",
    "magica/resource/image_web/_json/puellaHistoria/overview.json",
)))


def product_files(suffix: str, root: Path = ROOT):
    return sorted(
        path for path in (root / "magica").rglob(f"*{suffix}")
        if path.is_file()
        and not path.relative_to(root).as_posix().startswith(EXCLUDED)
    )


def selected_product_json_files(root: Path = ROOT) -> list[Path]:
    """Return the complete JSON product surface, excluding audit evidence."""

    roots = (
        (root / "magica/js/libs", False),
        (root / "magica/js/event", True),
        (root / "magica/json", True),
        (root / "magica/resource/image_web/_json", True),
    )
    selected: set[Path] = set()
    for base, recursive in roots:
        if not base.is_dir():
            continue
        iterator = base.rglob("*.json") if recursive else base.glob("*.json")
        selected.update(path for path in iterator if path.is_file())
    return sorted(selected)


def verify_product_json(
    root: Path = ROOT,
    expected_paths: tuple[str, ...] = EXPECTED_PRODUCT_JSON_PATHS,
) -> dict[str, object]:
    """Parse every product JSON and reject missing, extra, or malformed files."""

    root = root.resolve()
    files = selected_product_json_files(root)
    by_relative = {
        path.relative_to(root).as_posix(): path
        for path in files
    }
    actual_paths = tuple(sorted(by_relative))
    expected = tuple(sorted(expected_paths))
    assert actual_paths == expected, (
        "product JSON path set mismatch: "
        f"missing={sorted(set(expected) - set(actual_paths))} "
        f"extra={sorted(set(actual_paths) - set(expected))}"
    )

    failures: list[dict[str, str]] = []
    for relative in actual_paths:
        path = by_relative[relative]
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append({"path": relative, "error": str(exc)})
    assert not failures, f"invalid product JSON: {failures}"

    runtime = [
        relative for relative in actual_paths
        if relative.startswith("magica/js/libs/")
    ]
    return {
        "status": "PASS",
        "files": len(actual_paths),
        "runtime_dictionaries": len(runtime),
        "auxiliary_files": len(actual_paths) - len(runtime),
        "parse_failures": 0,
        "paths": list(actual_paths),
    }


def verify_product_inventory(root: Path = ROOT) -> dict[str, object]:
    """Verify and describe the package input tree without freezing file counts.

    The deterministic package builder owns the membership contract: every file
    below ``magica/`` except research/audit evidence, exactly one engine table,
    and the native repair files selected by ``madomagi/repair_manifest.json``.
    The manifest is both the required control input and a ZIP payload so the
    extracted native repair layer remains self-describing.
    """

    root = root.resolve()
    magica = root / "magica"
    engine = root / ENGINE
    repair_manifest_path = root / REPAIR_MANIFEST
    repair_root = root / REPAIR_PREFIX
    assert magica.is_dir(), f"missing product directory: {magica}"
    assert engine.is_file() and not engine.is_symlink(), f"missing regular {ENGINE}"
    assert repair_manifest_path.is_file() and not repair_manifest_path.is_symlink(), (
        f"missing regular {REPAIR_MANIFEST}"
    )
    assert repair_root.is_dir() and not repair_root.is_symlink(), (
        f"missing regular repair directory: {repair_root}"
    )

    try:
        repair_manifest = json.loads(repair_manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssertionError(f"invalid repair manifest: {exc}") from exc
    assert isinstance(repair_manifest, dict), "repair manifest root must be an object"
    assert repair_manifest.get("schema") == "magireco-cn-madomagi-repair/v1", (
        "repair manifest schema mismatch"
    )
    repair_rows = repair_manifest.get("entries")
    assert isinstance(repair_rows, list) and repair_rows, (
        "repair manifest entries must be a non-empty array"
    )
    declared_repairs: dict[str, int] = {}
    declared_order: list[str] = []
    for index, row in enumerate(repair_rows):
        assert isinstance(row, dict), f"repair manifest entry {index} is not an object"
        member = row.get("path")
        byte_count = row.get("bytes")
        assert isinstance(member, str), f"repair manifest entry {index} has no path"
        pure = PurePosixPath(member)
        assert (
            member.startswith(REPAIR_PREFIX)
            and not pure.is_absolute()
            and ".." not in pure.parts
            and pure.as_posix() == member
        ), f"unsafe repair manifest path: {member!r}"
        assert member not in declared_repairs, f"duplicate repair manifest path: {member}"
        assert type(byte_count) is int and byte_count >= 0, (
            f"invalid repair manifest byte count: {member}"
        )
        declared_order.append(member)
        declared_repairs[member] = byte_count
    assert declared_order == sorted(declared_order), "repair manifest paths are not sorted"
    assert type(repair_manifest.get("file_count")) is int, (
        "repair manifest file_count is not an integer"
    )
    assert repair_manifest["file_count"] == len(declared_repairs), (
        "repair manifest file_count mismatch"
    )
    declared_total_bytes = sum(declared_repairs.values())
    assert type(repair_manifest.get("total_bytes")) is int, (
        "repair manifest total_bytes is not an integer"
    )
    assert repair_manifest["total_bytes"] == declared_total_bytes, (
        "repair manifest total_bytes mismatch"
    )

    actual_repairs: dict[str, int] = {}
    for path in sorted(repair_root.rglob("*")):
        assert not path.is_symlink(), f"repair tree contains symlink: {path}"
        if path.is_file():
            actual_repairs[path.relative_to(root).as_posix()] = path.stat().st_size
    assert set(actual_repairs) == set(declared_repairs), (
        "repair manifest path set mismatch: "
        f"missing={sorted(set(declared_repairs) - set(actual_repairs))[:10]} "
        f"extra={sorted(set(actual_repairs) - set(declared_repairs))[:10]}"
    )
    repair_byte_errors = sorted(
        member for member in declared_repairs
        if actual_repairs[member] != declared_repairs[member]
    )
    assert not repair_byte_errors, (
        f"repair manifest byte count mismatch: {repair_byte_errors[:10]}"
    )

    package_members = [ENGINE, REPAIR_MANIFEST, *sorted(declared_repairs)]
    inventory_members = list(package_members)
    for path in sorted(magica.rglob("*")):
        assert not path.is_symlink(), f"product tree contains symlink: {path}"
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(EXCLUDED):
            continue
        package_members.append(relative)
        inventory_members.append(relative)

    package_members.sort()
    inventory_members.sort()
    assert package_members.count(ENGINE) == 1, f"{ENGINE} must appear exactly once"
    assert inventory_members.count(REPAIR_MANIFEST) == 1, (
        f"{REPAIR_MANIFEST} must appear exactly once"
    )
    assert len(inventory_members) == len(set(inventory_members)), (
        "duplicate product inventory path"
    )
    folded: dict[str, str] = {}
    for member in inventory_members:
        previous = folded.setdefault(member.casefold(), member)
        assert previous == member, f"case-folded product path collision: {previous} / {member}"
        assert (
            member == ENGINE
            or member == REPAIR_MANIFEST
            or member.startswith(REPAIR_PREFIX)
            or member.startswith("magica/")
        ), (
            f"unsupported product root: {member}"
        )
        assert not member.startswith(("magica/research/", "magica/i18n_audit/")), (
            f"audit/research leaked into product inventory: {member}"
        )

    magica_members = [
        member for member in package_members if member.startswith("magica/")
    ]
    suffix_counts = Counter(Path(member).suffix.lower() for member in magica_members)
    runtime_json = [
        member for member in magica_members
        if member.startswith("magica/js/libs/") and member.endswith(".json")
    ]
    return {
        "inventory_entries": len(inventory_members),
        "package_entries": len(package_members),
        "magica_entries": len(magica_members),
        "engine_entries": package_members.count(ENGINE),
        "repair_manifest_entries": inventory_members.count(REPAIR_MANIFEST),
        "repair_entries": len(declared_repairs),
        "repair_total_bytes": declared_total_bytes,
        "repair_validation": {
            "status": "PASS",
            "manifest": REPAIR_MANIFEST,
            "manifest_entries": len(declared_repairs),
            "actual_entries": len(actual_repairs),
            "total_bytes": declared_total_bytes,
            "path_set_exact": True,
            "byte_counts_exact": True,
            "errors": [],
        },
        "scenario_entries": 0,
        "audit_research_entries": 0,
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "runtime_json_dictionaries": len(runtime_json),
    }


def display_path(path: Path) -> str:
    """Return a stable repository-relative path when the file is in-tree."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def run_json(command):
    child_env = {
        **os.environ,
        "GIT_OPTIONAL_LOCKS": "0",
        # A redirected Windows child otherwise emits its locale code page while
        # this verifier correctly expects JSON to be UTF-8.
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True,
        env=child_env,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(map(str, command))}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return json.loads(result.stdout)


def verify_html_structure_contract() -> dict[str, object]:
    report = run_json([sys.executable, str(HTML_STRUCTURE_TOOL), "--verify"])
    assert report["status"] == "PASS"
    assert report["html_files"] == 225
    assert report["source_path_missing"] == 0
    assert report["strict_source_structure_matches"] == 213
    assert report["version_divergent_frozen_product"] == 12
    assert report["product_structure_drift"] == 0
    assert report["source_structure_drift"] == 0
    return report


def verify_engine(path: Path):
    raw = path.read_bytes()
    assert raw and not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw, "engine_i18n.tsv must use LF"
    text = raw.decode("utf-8")
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        assert "\t" in line, f"engine_i18n.tsv:{number}: missing TAB"
        source, target = line.split("\t", 1)
        assert source, f"engine_i18n.tsv:{number}: empty source"
        rows.append((source, target))
    assert len(rows) == EXPECTED_ENGINE_ROWS, len(rows)
    assert len({source for source, _ in rows}) == len(rows), "duplicate engine source"
    return {"rows": len(rows), "empty_targets": sum(not target for _, target in rows),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def read_tsv(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def scan_product_term_files(product_root: Path, term: str) -> dict[str, int]:
    """Return exact in-product occurrences, excluding research/audit evidence."""

    found: dict[str, int] = {}
    for path in sorted((product_root / "magica").rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".js", ".html", ".json", ".css"}:
            continue
        relative = path.relative_to(product_root).as_posix()
        if relative.startswith(EXCLUDED):
            continue
        count = path.read_text(encoding="utf-8").count(term)
        if count:
            found[relative] = count
    return found


def verify_pass19_product_closure(
    rows: list[dict[str, str]] | None = None,
    product_root: Path = ROOT,
):
    """Bind every Pass19 authority decision to the exact v26 product state."""

    if rows is None:
        rows = read_tsv(PASS19_CORRECTIONS)
    assert len(rows) == len(EXPECTED_PASS19_ROWS), len(rows)
    by_id = {row["change_id"]: row for row in rows}
    assert len(by_id) == len(rows), "duplicate Pass19 change_id"
    assert set(by_id) == set(EXPECTED_PASS19_ROWS), (
        "Pass19 identity drift", sorted(set(by_id) ^ set(EXPECTED_PASS19_ROWS))
    )

    for change_id, expected in EXPECTED_PASS19_ROWS.items():
        row = by_id[change_id]
        for key, value in expected.items():
            assert row[key] == value, (change_id, key, row[key], value)
        assert row["machine_translated"] == "false", change_id
        assert row["locator"] and row["source_locator"] and row["evidence"], change_id
        if row["source_tier"] == "official_cn_dump":
            assert row["source_locator"].startswith("D:/magia/MyProducts/MAGIA RECORD CN/"), change_id
        else:
            assert row["source_tier"] == "wiki", change_id
            assert "magireco-wiki-data/data/pages_index.json#キモチ戦→心魔战" in row["source_locator"], change_id

        path = product_root / row["file"]
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert text.count(row["before"]) == 0, (change_id, "reflux", row["before"])
        assert text.count(row["after"]) == int(row["expected_after_count"]), (
            change_id, row["after"], text.count(row["after"]), row["expected_after_count"]
        )

    observed_terms = {}
    post_pass19_terms = {}
    for term, expected_files in EXPECTED_PRODUCT_TERM_FILES.items():
        observed = scan_product_term_files(product_root, term)
        later_files = EXPECTED_POST_PASS19_TERM_FILES.get(term, {})
        expected_all = {**expected_files, **later_files}
        assert observed == expected_all, (
            f"{term} product distribution drift", observed, expected_all
        )
        # Report the original Pass19 footprint as before; later rounds are a
        # separately named layer rather than silently changing its semantics.
        observed_terms[term] = {
            "occurrences": sum(expected_files.values()),
            "files": len(expected_files),
        }
        if later_files:
            post_pass19_terms[term] = {
                "occurrences": sum(later_files.values()),
                "files": len(later_files),
            }

    for retired in ("心情战", "属性相性"):
        observed = scan_product_term_files(product_root, retired)
        assert observed == {}, (f"retired term reflux: {retired}", observed)

    formation = product_root / "magica/template/formation/FormationQuest.html"
    match = re.search(
        r'<div\b[^>]*\bclass=["\'][^"\']*\bdeckDetailCongeniality\b[^"\']*["\'][^>]*>.*?<p>\s*([^<]+?)\s*</p>',
        formation.read_text(encoding="utf-8"),
        flags=re.DOTALL,
    )
    assert match, "FormationQuest deckDetailCongeniality paragraph missing"
    assert match.group(1) == "属性克制", match.group(1)

    return {
        "manifest_rows": len(rows),
        "source_tiers": dict(sorted(Counter(row["source_tier"] for row in rows).items())),
        "machine_translated": False,
        "corrected_occurrences": sum(int(row["expected_count"]) for row in rows),
        "product_terms": observed_terms,
        "post_pass19_product_terms": post_pass19_terms,
        "retired_terms": {"心情战": 0, "属性相性": 0},
        "official_product_node": (
            "magica/template/formation/FormationQuest.html"
            "#div.deckDetailCongeniality>p=属性克制"
        ),
    }


def verify_visible_connect_term() -> dict[str, object]:
    """Keep the approved mechanic label visible-only and out of JSON keys/code."""
    path = ROOT / "magica/resource/image_web/_json/help.json"
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)

    key_hits: list[str] = []

    def walk(value: object, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_path = f"{prefix}/{key}"
                if "Connect" in str(key) or "コネクト" in str(key):
                    key_hits.append(key_path)
                walk(child, key_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{prefix}/{index}")

    walk(data)
    assert not key_hits, f"Connect occurs in JSON keys: {key_hits[:3]}"
    assert text.count("Connect") == 0, "visible Connect reflux in help.json"
    assert text.count("コネクト") == 0, "visible コネクト reflux in help.json"
    assert text.count("连携") == 14, "help.json 连携 count drift"
    return {
        "file": "magica/resource/image_web/_json/help.json",
        "old_visible_occurrences": 0,
        "approved_visible_occurrences": 14,
        "json_key_changes": 0,
    }


def verify_frontend_empty_closure(rows: list[dict[str, str]], product_root: Path = ROOT):
    """Fail closed on the exact 53 retired frontend candidates.

    These are not a generic empty-target allowlist: every record is classified
    into one of four audited outcomes.  The sole official correction is also
    tied to its source manifest and the exact current product DOM node.
    """

    assert len(rows) == len(FRONTEND_EMPTY_STABLE_KEY_STATUS)
    record_ids = {row["record_id"] for row in rows}
    assert len(record_ids) == len(rows), "duplicate frontend empty record id"
    stable_key_status = {
        row["stable_key_or_line"]: row["review_status"] for row in rows
    }
    assert len(stable_key_status) == len(rows), "duplicate frontend stable source key"
    assert stable_key_status == FRONTEND_EMPTY_STABLE_KEY_STATUS, (
        "frontend stable source identity drift",
        sorted(set(stable_key_status) ^ set(FRONTEND_EMPTY_STABLE_KEY_STATUS)),
    )
    assert Counter(row["review_status"] for row in rows) == FRONTEND_EMPTY_STATUS_COUNTS

    for row in rows:
        assert row["component"] == "frontend_untranslated"
        assert row["scope"] == "frontend_i18n_input"
        assert row["file"] == "i18n/frontend-strings.tsv"
        assert row["field"] == "candidate_cn"
        assert row["current_cn"] == ""
        assert row["machine_translated"] == "false"
        assert row["manual_review_status"] == row["review_status"]
        assert row["authority_status"] == row["review_status"]

        status = row["review_status"]
        if status == "runtime-absent/not-backlog":
            assert row["suggested_cn"] == ""
            assert row["source_bucket"] == "legacy-ai"
            assert row["source_tier"] == "current-product-exact-node-audit"
            assert row["issue_type"] == "frontend_source_absent_not_translation_backlog"
            assert row["runtime_consumed"] == "false; exact source is absent from current runtime nodes"
        elif status == "visible-cn-compatible-identity":
            assert row["suggested_cn"] == row["original_text"]
            assert row["source_bucket"] == "legacy-ai"
            assert row["source_tier"] == "current-product-visible-identity-audit"
            assert row["issue_type"] == "frontend_visible_identity_retain"
            assert row["runtime_consumed"] == "visible exact runtime node; offline candidate remains unselected"
        elif status == "identity-punctuation":
            assert row["stable_key_or_line"] == FRONTEND_PUNCTUATION_STABLE_KEY
            assert row["suggested_cn"] == row["original_text"] == "・"
            assert row["source_bucket"] == "legacy-ai"
            assert row["source_tier"] == "current-product-visible-identity-audit"
            assert row["issue_type"] == "frontend_visible_identity_retain"
            assert row["runtime_consumed"] == "visible exact runtime node; offline candidate remains unselected"
        elif status == "official-source-verified":
            assert row["stable_key_or_line"] == FRONTEND_OFFICIAL_STABLE_KEY
            assert row["original_text"] == "属性相性"
            assert row["suggested_cn"] == "属性克制"
            assert row["source_bucket"] == "official"
            assert row["source_tier"] == "official-cn-exact-path-dom-match"
            assert row["confidence"] == "exact-path-dom-match"
            assert row["highest_authority_match"] == "属性克制"
            assert row["issue_type"] == "frontend_official_cn_exact_path_dom_match"
            assert "official-cn-static/magica/template/formation/FormationQuest.html" in row["evidence_path_or_key"]
            assert f"sha256={OFFICIAL_FORMATION_SHA256}" in row["evidence_path_or_key"]
        else:  # Counter equality above makes any unlisted state a hard failure.
            raise AssertionError(f"unclassified frontend empty status: {status}")

    pass19_rows = read_tsv(AUDIT / "pass19_official_static_corrections.tsv")
    exact_source_rows = [
        row for row in pass19_rows
        if row["change_id"] == "P19-00001"
    ]
    assert len(exact_source_rows) == 1, exact_source_rows
    source = exact_source_rows[0]
    assert source == {
        "change_id": "P19-00001",
        "file": "magica/template/formation/FormationQuest.html",
        "locator": "div.deckDetailCongeniality>p",
        "before": "属性相性",
        "after": "属性克制",
        "source_tier": "official_cn_dump",
        "source_locator": "D:/magia/MyProducts/MAGIA RECORD CN/静态数据/static/magica/template/formation/FormationQuest.html#div.deckDetailCongeniality>p",
        "source_sha256": OFFICIAL_FORMATION_SHA256,
        "match_method": "exact-path-dom-match",
        "machine_translated": "false",
        "confidence": "exact",
        "review_status": "official-source-verified",
        "evidence": "旧国服静态产品树同路径同 DOM 节点逐字为属性克制；Full_Raw_Dump_V2/TopPage_001.json 另有属性克制用词佐证",
        "expected_count": "1",
        "expected_after_count": "1",
    }

    formation = product_root / "magica/template/formation/FormationQuest.html"
    assert formation.is_file(), formation
    product_text = formation.read_text(encoding="utf-8")
    match = re.search(
        r'<div\b[^>]*\bclass=["\'][^"\']*\bdeckDetailCongeniality\b[^"\']*["\'][^>]*>.*?<p>\s*([^<]+?)\s*</p>',
        product_text,
        flags=re.DOTALL,
    )
    assert match, "FormationQuest deckDetailCongeniality paragraph missing"
    assert match.group(1) == "属性克制", match.group(1)
    assert "属性相性" not in match.group(0), match.group(0)

    official_row = next(
        row for row in rows if row["stable_key_or_line"] == FRONTEND_OFFICIAL_STABLE_KEY
    )
    return {
        "records": len(rows),
        "status_counts": dict(FRONTEND_EMPTY_STATUS_COUNTS),
        # Informational only: aggregate MT row numbers may legitimately move.
        "official_record": official_row["record_id"],
        "official_stable_key": FRONTEND_OFFICIAL_STABLE_KEY,
        "official_source_sha256": OFFICIAL_FORMATION_SHA256,
        "product_node": "magica/template/formation/FormationQuest.html#div.deckDetailCongeniality>p",
    }


def verify_visible_term_closure_review(rows: list[dict[str, str]]) -> dict[str, object]:
    """Validate the exact 3,136-row runtime-dictionary authority layer."""

    assert len(rows) == 3136, len(rows)
    by_id = {row["closure_id"]: row for row in rows}
    assert len(by_id) == len(rows), "duplicate visible-term closure_id"
    identities = {
        (row["path"], row["stable_key"], row["field"])
        for row in rows
    }
    assert len(identities) == len(rows), "duplicate visible-term stable target"
    assert Counter(row["source_tier"] for row in rows) == (
        EXPECTED_VISIBLE_TERM_CLOSURE_PARTITION
    )
    assert Counter(row["review_status"] for row in rows) == {
        "official-source-verified": 762,
        "root-reviewed-approved": 2374,
    }
    assert {row["machine_translated"] for row in rows} == {"false"}
    assert all(row["before"] != row["after"] for row in rows)
    assert all(row["current_product_cn"] == row["after"] for row in rows)
    assert all(row["path"].startswith("magica/js/libs/") for row in rows)
    assert all(row["stable_key"] and row["field"] and row["evidence"] for row in rows)

    expected_component = {
        "official-cn": "runtime_visible_term_closure_official",
        "root-reviewed-official-cn-terminology": (
            "runtime_visible_term_closure_root_reviewed"
        ),
        "wiki-exact-stable-id-plus-official-cn-terminology": (
            "runtime_visible_term_closure_wiki"
        ),
    }
    for row in rows:
        assert row["inventory_component"] == expected_component[row["source_tier"]]
    return {
        "rows": len(rows),
        "partition": dict(EXPECTED_VISIBLE_TERM_CLOSURE_PARTITION),
        "machine_translated": False,
        "unique_targets": len(identities),
    }


def verify_pass18_review_contract(
    rows: list[dict[str, str]],
    closure_rows: list[dict[str, str]],
) -> dict[str, object]:
    """Bind Pass18 history to direct current values or one exact supersession."""

    assert len(rows) == 939, len(rows)
    by_id = {row["change_id"]: row for row in rows}
    assert len(by_id) == len(rows), "duplicate Pass18 change_id"
    assert set(by_id) == {f"P18-{number:05d}" for number in range(1, 940)}

    closure_by_id = {row["closure_id"]: row for row in closure_rows}
    assert len(closure_by_id) == len(closure_rows), "duplicate visible-term closure_id"
    statuses = Counter(row["pass18_current_status"] for row in rows)
    assert statuses == {
        "direct-current-after-image": 537,
        "visible-term-closure-exact-supersession": 402,
    }
    lookup_methods = Counter(row["strict_lookup_method"] for row in rows)
    assert lookup_methods == {"stable-key": 912, "json-pointer": 26, "static-literal": 1}

    static_rows = [row for row in rows if row["strict_lookup_method"] == "static-literal"]
    assert len(static_rows) == 1
    static_row = static_rows[0]
    assert static_row["file"] == (
        "magica/js/regularEvent/groupBattle/view/BossPageView.js"
    )
    assert static_row["pass18_current_status"] == "direct-current-after-image"
    assert static_row["current_product_cn"] == static_row["after"]

    runtime_direct = 0
    superseded_ids: set[str] = set()
    for row in rows:
        status = row["pass18_current_status"]
        if status == "direct-current-after-image":
            assert not row["superseding_closure_id"]
            assert not row["superseding_source_tier"]
            assert not row["superseding_review_status"]
            assert row["current_product_cn"] == row["after"]
            if row["strict_lookup_method"] != "static-literal":
                runtime_direct += 1
            continue

        closure_id = row["superseding_closure_id"]
        assert closure_id and closure_id not in superseded_ids
        superseded_ids.add(closure_id)
        closure = closure_by_id[closure_id]
        assert closure["path"] == row["file"]
        assert closure["stable_key"] == row["stable_key"]
        assert closure["field"] == row["field"]
        assert closure["before"] == row["after"]
        assert closure["after"] == row["current_product_cn"]
        assert closure["current_product_cn"] == row["current_product_cn"]
        assert closure["source_tier"] == row["superseding_source_tier"]
        assert closure["review_status"] == row["superseding_review_status"]

    assert runtime_direct == 536, runtime_direct
    assert len(superseded_ids) == 402, len(superseded_ids)
    return {
        "rows": len(rows),
        "runtime_direct_current": runtime_direct,
        "runtime_exact_visible_term_supersession": len(superseded_ids),
        "static_direct_current": len(static_rows),
        "strict_lookup_methods": dict(sorted(lookup_methods.items())),
    }


def verify_machine_review():
    summary_path = MACHINE_REVIEW / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["schema"] == "magireco-cn-v26-machine-translation-review/v2"
    counts = summary["counts"]
    for key, expected in EXPECTED_MACHINE_REVIEW_COUNTS.items():
        assert counts[key] == expected, (key, counts[key], expected)
    assert counts["engine_partition"] == EXPECTED_ENGINE_PARTITION
    assert counts["pass18_root_personal_needs_review"] == 12
    assert counts["pass18_runtime_direct_current"] == 536
    assert counts["pass18_runtime_exact_visible_term_supersession"] == 402
    assert counts["pass18_static_direct_current"] == 1
    assert counts["visible_term_closure_partition"] == (
        EXPECTED_VISIBLE_TERM_CLOSURE_PARTITION
    )

    tables = {
        "full_machine_translation_review.tsv": counts["master"],
        "runtime_translation_review.tsv": counts["runtime"],
        "static_js_html_review.tsv": counts["static"],
        "frontend_all_1685.tsv": counts["frontend"],
        "frontend_untranslated_53.tsv": counts["frontend_empty"],
        "glossary_wiki_955.tsv": counts["glossary"],
        "overrides_fragments_16.tsv": counts["overrides_fragments"],
        "engine_i18n_review_615.tsv": counts["engine"],
        "battle_miss_needs_review.tsv": counts["battle_miss_needs_review"],
        "battle_runtime_language_decisions_8.tsv": counts["battle_runtime_language_decisions"],
        "battle_runtime_unique_misses_20.tsv": counts["battle_runtime_unique_misses"],
        "pass18_authority_corrections_939.tsv": counts["pass18"],
        "visible_term_closure_3136.tsv": counts["visible_term_closure"],
        "explicit_llm_history_264.tsv": counts["explicit_llm_history"],
    }
    parsed = {}
    for name, expected in tables.items():
        parsed[name] = read_tsv(MACHINE_REVIEW / name)
        assert len(parsed[name]) == expected, (name, len(parsed[name]), expected)

    frontend_empty = parsed["frontend_untranslated_53.tsv"]
    frontend_closure = verify_frontend_empty_closure(frontend_empty)
    frontend_empty_ids = {row["record_id"] for row in frontend_empty}
    visible_term_closure = verify_visible_term_closure_review(
        parsed["visible_term_closure_3136.tsv"]
    )
    pass18_contract = verify_pass18_review_contract(
        parsed["pass18_authority_corrections_939.tsv"],
        parsed["visible_term_closure_3136.tsv"],
    )

    master = parsed["full_machine_translation_review.tsv"]
    required_columns = {
        "record_id", "original_text", "current_cn", "suggested_cn",
        "product_or_reference_location", "source_tier", "source_bucket",
        "evidence_path_or_key", "machine_translated", "confidence", "review_status",
    }
    assert required_columns <= set(master[0]), sorted(required_columns - set(master[0]))
    allowed_buckets = {"official", "wiki", "legacy-ai", "new-root-human", "unknown"}
    seen_ids = set()
    empty_current_ids = set()
    for row in master:
        record_id = row["record_id"]
        assert record_id and record_id not in seen_ids, record_id
        seen_ids.add(record_id)
        assert row["product_or_reference_location"]
        assert row["source_tier"] and row["source_bucket"] in allowed_buckets
        assert row["evidence_path_or_key"] and row["machine_translated"]
        assert row["confidence"] and row["review_status"]
        if not row["original_text"]:
            assert row.get("missing_original_reason")
        if not row["current_cn"]:
            empty_current_ids.add(record_id)
            if record_id not in frontend_empty_ids:
                assert row["review_status"] in {
                    "documented-intentional", "needs-review/root-translation-required"
                }, (record_id, row["review_status"])
    # The physical engine line is the stable identity for the documented
    # cross-node deletion rule ``上昇する -> ''``.  Aggregate MT record numbers
    # move whenever an earlier engine row is added or removed.
    intentional_empty_rows = [
        row
        for row in master
        if not row["current_cn"]
        and row["review_status"] == "documented-intentional"
        and row["source_tier"] == "intentional-structural-rule"
    ]
    assert len(intentional_empty_rows) == 1, intentional_empty_rows
    intentional_empty = intentional_empty_rows[0]
    assert intentional_empty["component"] == "engine_runtime_i18n_intentional_fragment"
    assert intentional_empty["stable_key_or_line"] == "42"
    assert intentional_empty["product_or_reference_location"] == (
        "madomagi/engine_i18n.tsv#42/zhCN"
    )
    intentional_empty_ids = {intentional_empty["record_id"]}
    assert empty_current_ids == frontend_empty_ids | intentional_empty_ids, (
        empty_current_ids ^ (frontend_empty_ids | intentional_empty_ids)
    )

    battle = parsed["battle_miss_needs_review.tsv"]
    assert all(row["machine_translated"] == "unknown" for row in battle)
    assert all(row["review_status"] == "needs-review/root-translation-required"
               for row in battle)

    battle_decisions = parsed["battle_runtime_language_decisions_8.tsv"]
    battle_inventory = parsed["battle_runtime_unique_misses_20.tsv"]
    detailed_sources = {
        row["detailed_translation_row"]
        for row in battle_inventory
        if row["detailed_translation_row"]
    }
    assert detailed_sources == {row["source_text"] for row in battle_decisions}
    assert sum(row["action"].startswith(("translate-", "review-"))
               for row in battle_inventory) == 7
    assert sum(row["action"] == "no-rule-required"
               for row in battle_inventory) == 1
    assert sum(row["current_candidate_machine_translation"] == "unknown"
               for row in battle_decisions) == 4
    assert sum(row["review_status"] == "needs-human-review"
               for row in battle_decisions) == 2
    assert sum(row["review_status"] == "needs-review-parallel-art"
               for row in battle_decisions) == 1

    engine_product = []
    for line in (ROOT / ENGINE).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        engine_product.append(tuple(line.split("\t", 1)))
    engine_review = parsed["engine_i18n_review_615.tsv"]
    review_pairs = [(row["original_text"], row["current_cn"]) for row in engine_review]
    assert sorted(engine_product) == sorted(review_pairs), "engine review/product mismatch"

    checksum_rows = []
    for number, line in enumerate(
        (MACHINE_REVIEW / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line:
            continue
        digest, name = line.split("  ", 1)
        path = (MACHINE_REVIEW / name).resolve()
        assert path.is_file(), (number, name)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == digest, (name, actual, digest)
        checksum_rows.append(name)
    assert len(checksum_rows) >= 20

    return {
        "schema": summary["schema"],
        "counts": {key: counts[key] for key in EXPECTED_MACHINE_REVIEW_COUNTS},
        "engine_partition": counts["engine_partition"],
        "source_buckets": counts["by_source_bucket"],
        "machine_translation_flags": counts["by_machine_translation"],
        "pass18_root_personal_needs_review": counts["pass18_root_personal_needs_review"],
        "pass18_contract": pass18_contract,
        "visible_term_closure": visible_term_closure,
        "frontend_empty_closure": frontend_closure,
        "checksummed_artifacts": len(checksum_rows),
        "sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
    }


def verify_round3_package_contract(
    root: Path = ROOT,
    package_members: set[str] | None = None,
) -> dict[str, int]:
    """Verify this round's manifest-bound visible files are package inputs.

    Research manifests are evidence only and remain excluded from the ZIP.  Their
    referenced product JS/HTML/CSS/image files must nevertheless exist and be
    selected by the package path contract.
    """
    root = root.resolve()
    evidence_root = root / "magica" / "research" / "totentanz-full-localization-20260817"
    visible = json.loads((evidence_root / "visible-ui-authority-round3" / "visible_ui_authority_round3_manifest.json").read_text(encoding="utf-8"))
    css = json.loads((evidence_root / "visible-ui" / "css_content_verify_final.json").read_text(encoding="utf-8"))
    overlay = json.loads((evidence_root / "official-cn-image-overlay-round2" / "overlay_manifest.json").read_text(encoding="utf-8"))
    canvas = json.loads((evidence_root / "current-canvas-image-round2" / "manifest.json").read_text(encoding="utf-8"))

    assert visible["summary"] == {
        "items": 52, "files": 16, "official_literal_positions": 49,
        "new_human_literal_positions": 17, "total_literal_positions": 66,
        "manifest_literal_replacements": 62,
    }
    assert css["ok"] is True and css["items"] == 110 and css["files"] == 26
    assert overlay["items"] == 151 and len(overlay["rows"]) == 151
    assert canvas["status"] == "PASS" and len(canvas["rows"]) == 9

    required = set(ROUND3_STATIC_MEMBERS)
    required.update(row["path"] for row in visible["items"])
    required.update(row["path"] for row in css["records"])
    image_rows = [*overlay["rows"], *canvas["rows"]]
    required.update("magica/resource/image_web/" + row["path"] for row in image_rows)
    for member in required:
        product_path = root / member
        assert product_path.is_file(), f"round3 required product file missing: {member}"
        assert not member.startswith(EXCLUDED), f"round3 product member is excluded: {member}"

    for row in visible["items"]:
        actual = (root / row["path"]).read_text(encoding="utf-8")
        assert actual.count(row["after"]) == row["count"], (
            "round3 visible text drift", row["item_id"], row["path"]
        )
        assert actual.count(row["before"]) == row["baseline_after_count"], (
            "round3 visible old text reflux", row["item_id"], row["path"]
        )
    for row in image_rows:
        product_path = root / "magica/resource/image_web" / row["path"]
        assert product_path.stat().st_size == row["bytes"], (
            "round3 image byte-size drift", row["path"]
        )

    if package_members is not None:
        missing = required - package_members
        assert not missing, f"round3 files absent from ZIP: {sorted(missing)[:5]}"
    return {
        "required_members": len(required),
        "visible_text_items": len(visible["items"]),
        "css_records": len(css["records"]),
        "official_image_members": len(overlay["rows"]),
        "current_canvas_image_members": len(canvas["rows"]),
    }


def verify_zip(path: Path):
    expected = {}
    for file in (ROOT / "magica").rglob("*"):
        if not file.is_file():
            continue
        name = file.relative_to(ROOT).as_posix()
        if name.startswith(EXCLUDED):
            continue
        expected[name] = file.read_bytes()
    expected[ENGINE] = (ROOT / ENGINE).read_bytes()
    expected[REPAIR_MANIFEST] = (ROOT / REPAIR_MANIFEST).read_bytes()
    for file in (ROOT / REPAIR_PREFIX).rglob("*"):
        if file.is_file():
            expected[file.relative_to(ROOT).as_posix()] = file.read_bytes()

    with zipfile.ZipFile(path) as archive:
        infos = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in infos]
        assert len(names) == len(set(names)), "duplicate ZIP paths"
        assert set(names) == set(expected), (
            sorted(set(expected) - set(names))[:10],
            sorted(set(names) - set(expected))[:10],
        )
        assert archive.testzip() is None, "ZIP CRC failure"
        mismatches = [name for name in names if archive.read(name) != expected[name]]
        assert not mismatches, f"ZIP bytes differ from product tree: {mismatches[:10]}"
        round3 = verify_round3_package_contract(ROOT, set(names))
    raw = path.read_bytes()
    return {
        "path": display_path(path), "file_entries": len(names),
        "duplicate_paths": 0, "crc_errors": 0, "byte_mismatches": 0,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "engine_entries": names.count(ENGINE),
        "repair_manifest_entries": names.count(REPAIR_MANIFEST),
        "repair_entries": sum(name.startswith(REPAIR_PREFIX) for name in names),
        "scenario_entries": sum(name.startswith("madomagi/resource/scenario/") for name in names),
        "audit_entries": sum(name.startswith(EXCLUDED) for name in names),
        "round3_package_contract": round3,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    runtime = run_json([sys.executable, str(ROOT / "tools/verify-runtime-layer.py")])
    authority = run_json([
        sys.executable, str(ROOT / "tools/i18n-authority-guard.py"), "--json"
    ])
    pass18 = run_json([sys.executable, str(ROOT / "tools/verify-pass18-authority.py")])
    assert runtime["status"] == "PASS" and authority["ok"] is True
    assert pass18["status"] == "PASS"

    inventory = verify_product_inventory()
    js_files = product_files(".js")
    js_failures = []
    for path in js_files:
        result = subprocess.run(
            ["node", "--check", str(path)], capture_output=True, text=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
            encoding="utf-8", errors="replace", check=False,
        )
        if result.returncode:
            js_failures.append({"path": path.relative_to(ROOT).as_posix(),
                                "stderr": result.stderr})
    assert not js_failures, js_failures[:3]

    html_files = product_files(".html")
    css_files = product_files(".css")
    product_json = verify_product_json()
    html_structure = verify_html_structure_contract()
    suffix_counts = inventory["suffix_counts"]
    assert isinstance(suffix_counts, dict)
    assert len(js_files) == suffix_counts.get(".js", 0)
    assert len(html_files) == suffix_counts.get(".html", 0)
    assert len(html_files) == html_structure["html_files"]
    assert len(css_files) == suffix_counts.get(".css", 0)
    assert product_json["files"] == suffix_counts.get(".json", 0)
    assert (
        product_json["runtime_dictionaries"]
        == inventory["runtime_json_dictionaries"]
    )

    ui = json.loads((AUDIT / "ui_union_validation.json").read_text(encoding="utf-8"))
    assert ui["status"] == "PASS"
    assert ui["checks"]["main_only_12"]["matched"] == 12
    assert ui["checks"]["pass_only_14"]["matched"] == 14
    assert ui["checks"]["specified_gacha_3"]["matched"] == 3
    assert ui["checks"]["node_syntax"]["failures"] == []
    assert ui["checks"]["html_sensitive_attributes"]["status"] == "PASS"

    remaining = ROOT / "magica/i18n_audit/manual_cn_pass16/untranslated_remaining.tsv"
    with remaining.open(encoding="utf-8-sig", newline="") as handle:
        remaining_rows = list(csv.DictReader(handle, delimiter="\t"))
    assert not remaining_rows, "visible untranslated backlog is not empty"

    checklist_summary = json.loads(
        (AUDIT / "manual_review_checklist.summary.json").read_text(encoding="utf-8")
    )
    assert checklist_summary["total_rows"] == 1183
    visible_connect = verify_visible_connect_term()
    engine = verify_engine(ROOT / ENGINE)
    machine_review = verify_machine_review()
    pass19 = verify_pass19_product_closure()

    report = {
        "schema": "magireco-cn-v26-product-verification/v1",
        "status": "PASS",
        "counts": {
            "product_js": len(js_files), "js_syntax_failures": len(js_failures),
            "product_html": len(html_files), "product_css": len(css_files),
            "html_structure_drift": html_structure["product_structure_drift"],
            "html_version_divergent_frozen": (
                html_structure["version_divergent_frozen_product"]
            ),
            "product_json": product_json["files"],
            "product_json_parse_failures": product_json["parse_failures"],
            "runtime_json_dictionaries": product_json["runtime_dictionaries"],
            "auxiliary_product_json": product_json["auxiliary_files"],
            "product_inventory_entries": inventory["inventory_entries"],
            "package_entries": inventory["package_entries"],
            "package_magica_entries": inventory["magica_entries"],
            "package_repair_entries": inventory["repair_entries"],
            "package_repair_total_bytes": inventory["repair_total_bytes"],
            "visible_untranslated_backlog": len(remaining_rows),
            "manual_review_rows": checklist_summary["total_rows"],
            "machine_translation_review_rows": machine_review["counts"]["master"],
        },
        "runtime_layer": runtime,
        "product_inventory": inventory,
        "product_json": product_json,
        "html_structure_contract": html_structure,
        "authority_guard": authority,
        "ui_union": {
            "status": ui["status"], "main_only": "12/12", "pass_only": "14/14",
            "specified_gacha": "3/3", "sensitive_attribute_drift": 0,
        },
        "engine_i18n": engine,
        "visible_connect_term": visible_connect,
        "pass18_authority": pass18,
        "pass19_static_authority": pass19,
        "machine_translation_review": machine_review,
    }
    if args.zip:
        zip_report = verify_zip(args.zip)
        assert zip_report["file_entries"] == inventory["package_entries"], (
            "ZIP/product inventory entry count mismatch"
        )
        assert zip_report["repair_entries"] == inventory["repair_entries"], (
            "ZIP/product repair entry count mismatch"
        )
        assert zip_report["scenario_entries"] == 0
        assert zip_report["audit_entries"] == 0
        report["zip"] = zip_report

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8", newline="\n")
    # Bypass the legacy Windows console codec so a verified UTF-8 report never
    # fails after the output file has already been written.
    sys.stdout.buffer.write(rendered.encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
