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
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "magica" / "i18n_audit" / "release_v26_authority"
EXCLUDED = ("magica/research/", "magica/i18n_audit/")
ENGINE = "madomagi/engine_i18n.tsv"
EXPECTED_ENGINE_ROWS = 306
MACHINE_REVIEW = AUDIT / "machine_translation_review"
PASS19_CORRECTIONS = AUDIT / "pass19_official_static_corrections.tsv"
FRONTEND_EMPTY_STATUS_COUNTS = {
    "runtime-absent/not-backlog": 18,
    "visible-cn-compatible-identity": 33,
    "identity-punctuation": 1,
    "official-source-verified": 1,
}
FRONTEND_EMPTY_RECORD_IDS = {
    f"MT-{number:05d}" for number in range(1949, 2002)
}
FRONTEND_OFFICIAL_ID = "MT-01968"
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

EXPECTED_MACHINE_REVIEW_COUNTS = {
    "master": 12933,
    "runtime": 9665,
    "static": 303,
    "frontend": 1685,
    "frontend_empty": 53,
    "glossary": 955,
    "overrides_fragments": 16,
    "engine": 306,
    "battle_miss_needs_review": 3,
    "battle_runtime_language_decisions": 8,
    "battle_runtime_unique_misses": 20,
    "pass18": 939,
    "explicit_llm_history": 264,
}


def product_files(suffix: str, root: Path = ROOT):
    return sorted(
        path for path in (root / "magica").rglob(f"*{suffix}")
        if path.is_file()
        and not path.relative_to(root).as_posix().startswith(EXCLUDED)
    )


def verify_product_inventory(root: Path = ROOT) -> dict[str, object]:
    """Verify and describe the package input tree without freezing file counts.

    The deterministic package builder owns the membership contract: every file
    below ``magica/`` except research/audit evidence, plus exactly one engine
    table.  This verifier mirrors that path contract and derives type counts from
    the selected tree, so adding a reviewed HTML/CSS product does not require an
    unrelated numeric constant change.
    """

    root = root.resolve()
    magica = root / "magica"
    engine = root / ENGINE
    assert magica.is_dir(), f"missing product directory: {magica}"
    assert engine.is_file() and not engine.is_symlink(), f"missing regular {ENGINE}"

    members = [ENGINE]
    for path in sorted(magica.rglob("*")):
        assert not path.is_symlink(), f"product tree contains symlink: {path}"
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(EXCLUDED):
            continue
        members.append(relative)

    members.sort()
    assert members.count(ENGINE) == 1, f"{ENGINE} must appear exactly once"
    assert len(members) == len(set(members)), "duplicate product member path"
    folded: dict[str, str] = {}
    for member in members:
        previous = folded.setdefault(member.casefold(), member)
        assert previous == member, f"case-folded product path collision: {previous} / {member}"
        assert member == ENGINE or member.startswith("magica/"), (
            f"unsupported product root: {member}"
        )
        assert not member.startswith(("magica/research/", "magica/i18n_audit/")), (
            f"audit/research leaked into product inventory: {member}"
        )

    magica_members = [member for member in members if member.startswith("magica/")]
    suffix_counts = Counter(Path(member).suffix.lower() for member in magica_members)
    runtime_json = [
        member for member in magica_members
        if member.startswith("magica/js/libs/") and member.endswith(".json")
    ]
    return {
        "package_entries": len(members),
        "magica_entries": len(magica_members),
        "engine_entries": members.count(ENGINE),
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
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(map(str, command))}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return json.loads(result.stdout)


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
    for term, expected_files in EXPECTED_PRODUCT_TERM_FILES.items():
        observed = scan_product_term_files(product_root, term)
        assert observed == expected_files, (
            f"{term} product distribution drift", observed, expected_files
        )
        observed_terms[term] = {
            "occurrences": sum(observed.values()),
            "files": len(observed),
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
        "retired_terms": {"心情战": 0, "属性相性": 0},
        "official_product_node": (
            "magica/template/formation/FormationQuest.html"
            "#div.deckDetailCongeniality>p=属性克制"
        ),
    }


def verify_frontend_empty_closure(rows: list[dict[str, str]], product_root: Path = ROOT):
    """Fail closed on the exact 53 retired frontend candidates.

    These are not a generic empty-target allowlist: every record is classified
    into one of four audited outcomes.  The sole official correction is also
    tied to its source manifest and the exact current product DOM node.
    """

    assert len(rows) == len(FRONTEND_EMPTY_RECORD_IDS)
    record_ids = {row["record_id"] for row in rows}
    assert len(record_ids) == len(rows), "duplicate frontend empty record id"
    assert record_ids == FRONTEND_EMPTY_RECORD_IDS, (
        "frontend empty record identity drift",
        sorted(record_ids ^ FRONTEND_EMPTY_RECORD_IDS),
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
            assert row["record_id"] == "MT-01986"
            assert row["suggested_cn"] == row["original_text"] == "・"
            assert row["source_bucket"] == "legacy-ai"
            assert row["source_tier"] == "current-product-visible-identity-audit"
            assert row["issue_type"] == "frontend_visible_identity_retain"
            assert row["runtime_consumed"] == "visible exact runtime node; offline candidate remains unselected"
        elif status == "official-source-verified":
            assert row["record_id"] == FRONTEND_OFFICIAL_ID
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

    return {
        "records": len(rows),
        "status_counts": dict(FRONTEND_EMPTY_STATUS_COUNTS),
        "official_record": FRONTEND_OFFICIAL_ID,
        "official_source_sha256": OFFICIAL_FORMATION_SHA256,
        "product_node": "magica/template/formation/FormationQuest.html#div.deckDetailCongeniality>p",
    }


def verify_machine_review():
    summary_path = MACHINE_REVIEW / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["schema"] == "magireco-cn-v26-machine-translation-review/v2"
    counts = summary["counts"]
    for key, expected in EXPECTED_MACHINE_REVIEW_COUNTS.items():
        assert counts[key] == expected, (key, counts[key], expected)
    assert counts["engine_partition"] == {
        "engine_runtime_i18n_intentional_fragment": 1,
        "engine_runtime_i18n_official": 7,
        "engine_runtime_i18n_root_translation": 1,
        "engine_runtime_i18n_unverified": 296,
        "engine_runtime_i18n_wiki": 1,
    }
    assert counts["pass18_root_personal_needs_review"] == 12

    tables = {
        "full_machine_translation_review.tsv": counts["master"],
        "runtime_translation_review.tsv": counts["runtime"],
        "static_js_html_review.tsv": counts["static"],
        "frontend_all_1685.tsv": counts["frontend"],
        "frontend_untranslated_53.tsv": counts["frontend_empty"],
        "glossary_wiki_955.tsv": counts["glossary"],
        "overrides_fragments_16.tsv": counts["overrides_fragments"],
        "engine_i18n_review_306.tsv": counts["engine"],
        "battle_miss_needs_review.tsv": counts["battle_miss_needs_review"],
        "battle_runtime_language_decisions_8.tsv": counts["battle_runtime_language_decisions"],
        "battle_runtime_unique_misses_20.tsv": counts["battle_runtime_unique_misses"],
        "pass18_authority_corrections_939.tsv": counts["pass18"],
        "explicit_llm_history_264.tsv": counts["explicit_llm_history"],
    }
    parsed = {}
    for name, expected in tables.items():
        parsed[name] = read_tsv(MACHINE_REVIEW / name)
        assert len(parsed[name]) == expected, (name, len(parsed[name]), expected)

    frontend_empty = parsed["frontend_untranslated_53.tsv"]
    frontend_closure = verify_frontend_empty_closure(frontend_empty)
    frontend_empty_ids = {row["record_id"] for row in frontend_empty}

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
    assert empty_current_ids == frontend_empty_ids | {"MT-00004"}, empty_current_ids ^ (frontend_empty_ids | {"MT-00004"})

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
    engine_review = parsed["engine_i18n_review_306.tsv"]
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
        "frontend_empty_closure": frontend_closure,
        "checksummed_artifacts": len(checksum_rows),
        "sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
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
    raw = path.read_bytes()
    return {
        "path": display_path(path), "file_entries": len(names),
        "duplicate_paths": 0, "crc_errors": 0, "byte_mismatches": 0,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "engine_entries": names.count(ENGINE),
        "scenario_entries": sum(name.startswith("madomagi/resource/scenario/") for name in names),
        "audit_entries": sum(name.startswith(EXCLUDED) for name in names),
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
    json_files = sorted((ROOT / "magica/js/libs").glob("*.json"))
    suffix_counts = inventory["suffix_counts"]
    assert isinstance(suffix_counts, dict)
    assert len(js_files) == suffix_counts.get(".js", 0)
    assert len(html_files) == suffix_counts.get(".html", 0)
    assert len(css_files) == suffix_counts.get(".css", 0)
    assert len(json_files) == inventory["runtime_json_dictionaries"]

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
    engine = verify_engine(ROOT / ENGINE)
    machine_review = verify_machine_review()
    pass19 = verify_pass19_product_closure()

    report = {
        "schema": "magireco-cn-v26-product-verification/v1",
        "status": "PASS",
        "counts": {
            "product_js": len(js_files), "js_syntax_failures": len(js_failures),
            "product_html": len(html_files), "product_css": len(css_files),
            "runtime_json_dictionaries": len(json_files),
            "package_entries": inventory["package_entries"],
            "package_magica_entries": inventory["magica_entries"],
            "visible_untranslated_backlog": len(remaining_rows),
            "manual_review_rows": checklist_summary["total_rows"],
            "machine_translation_review_rows": machine_review["counts"]["master"],
        },
        "runtime_layer": runtime,
        "product_inventory": inventory,
        "authority_guard": authority,
        "ui_union": {
            "status": ui["status"], "main_only": "12/12", "pass_only": "14/14",
            "specified_gacha": "3/3", "sensitive_attribute_drift": 0,
        },
        "engine_i18n": engine,
        "pass18_authority": pass18,
        "pass19_static_authority": pass19,
        "machine_translation_review": machine_review,
    }
    if args.zip:
        report["zip"] = verify_zip(args.zip)

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
