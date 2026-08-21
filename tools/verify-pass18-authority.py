#!/usr/bin/env python3
"""Verify the Pass18 v26 authority corrections without modifying the product.

This verifier is deliberately narrower than the general runtime-layer audit.  It
checks the exact Pass18 after-images, scans only user-visible dictionary fields
for known translation regressions, protects the twelve root-authored background
translations, validates the engine table, and proves that the Pass18 CSS is
preserved while the explicitly selected Totentanz localization overlay is the
only CSS addition.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "magica" / "i18n_audit" / "release_v26_authority"
MANIFEST = AUDIT / "pass18_authority_corrections.tsv"
BASELINE_RECORD = AUDIT / "pass18_baseline.json"
ENGINE_AUDIT = AUDIT / "pass18_engine_official_additions.tsv"
ENGINE = ROOT / "madomagi" / "engine_i18n.tsv"
REPORT = AUDIT / "pass18_verification.json"

BASELINE_COMMIT = "d5e8f75d93f6760a588e592c22a3754d19370c68"
PASS18_MANIFEST_COMMIT = "95e6284eb7a64f3f54309acbd614056f643f6ccd"
EXPECTED_MANIFEST_ROWS = 939
EXPECTED_PASS18_RUNTIME_DIRECT = 536
EXPECTED_PASS18_RUNTIME_SUPERSEDED = 402
EXPECTED_PASS18_STATIC_DIRECT = 1
EXPECTED_VISIBLE_TERM_CLOSURE_ROWS = 3136
BASE_ENGINE_ROWS = 314
EXPECTED_ENGINE_ROWS = 621
EXPECTED_ENGINE_PHYSICAL_LINES = 622
EXPECTED_ENGINE_OFFICIAL_ROWS = 5
EXPECTED_DICTIONARIES = 23
EXPECTED_CSS_FILES = 19

ROUND3_ROOT = ROOT / "magica" / "research" / "totentanz-full-localization-20260817"
ROUND3_VISIBLE_MANIFEST = ROUND3_ROOT / "visible-ui" / "visible_ui_manifest.json"
ROUND3_CSS_REPORT = ROUND3_ROOT / "visible-ui" / "css_content_verify_final.json"
MANUAL_ROUND3_MANIFEST = (
    ROUND3_ROOT / "manual-visible-round3" / "runtime" / "manual_round3_manifest.json"
)
ROUND4_MANIFEST = ROUND3_ROOT / "visible-residue-closure-round4" / "closure_manifest.json"
VISIBLE_TERM_CLOSURE = ROUND3_ROOT / "runtime-dictionary" / "visible-term-closure-3136.tsv"
VISIBLE_TERM_CLOSURE_SUMMARY = (
    ROUND3_ROOT / "runtime-dictionary" / "visible-term-closure-summary.json"
)
ENGINE_EVIDENCE = ROUND3_ROOT / "engine-i18n"
ENGINE_AP_EVIDENCE = ENGINE_EVIDENCE / "ap-recovery-gap-verification.json"
ENGINE_CONNECT_EVIDENCE = ENGINE_EVIDENCE / "connect-context-authority.json"
ENGINE_FINAL_EVIDENCE = ENGINE_EVIDENCE / "engine-final-authority-corrections.json"
ENGINE_ROOT_EVIDENCE = ENGINE_EVIDENCE / "root-reviewed-term-closure.json"
ENGINE_NATIVE_EVIDENCE = (
    ENGINE_EVIDENCE
    / "official-cn-native-exhaustion-20260821"
    / "official-cn-native-localization-exhaustion.json"
)

PORTABLE_FOLLOWUP_EVIDENCE = (
    ROUND3_ROOT / "portable-followup-evidence-20260819"
)
CONNECT_VISIBLE_EVIDENCE = PORTABLE_FOLLOWUP_EVIDENCE / "connect-visible"
CONNECT_VISIBLE_PATCH = CONNECT_VISIBLE_EVIDENCE / "connect_visible_ui_product_patch.json"
CONNECT_VISIBLE_VERIFICATION = (
    CONNECT_VISIBLE_EVIDENCE / "connect_visible_ui_verification.json"
)
CONNECT_HELP_EVIDENCE = PORTABLE_FOLLOWUP_EVIDENCE / "connect-help"
CONNECT_HELP_VERIFICATION = CONNECT_HELP_EVIDENCE / "connect_help_json_verification.json"
ENGINE_FINAL_VERIFICATION = (
    PORTABLE_FOLLOWUP_EVIDENCE / "engine_final_authority_verification.json"
)

SELECTIVE_CSS_ADDITIONS = frozenset(
    {
        "magica/css/arena/ArenaResult.css",
        "magica/css/chara/CharaCommon.css",
        "magica/css/chara/CharaEnhancementTree.css",
        "magica/css/collection/MemoriaCollection.css",
        "magica/css/event/EventWitch/ExchangeTop.css",
        "magica/css/event/dailytower/EventDailyTower.css",
        "magica/css/event/raid/EventRaidTop.css",
        "magica/css/event/tower/EventTower.css",
        "magica/css/formation/DeckFormation.css",
        "magica/css/memoria/MemoriaComposeTop.css",
        "magica/css/memoria/UserMemoriaList.css",
        "magica/css/mission/MissionTop.css",
        "magica/css/patrol/PatrolLumpFormation.css",
        "magica/css/quest/SecondPartLastBattleConfirm.css",
        "magica/css/quest/SecondPartLastFormation.css",
        "magica/css/regularEvent/extermination/RegularEventExterminationBattleConfirm.css",
        "magica/css/regularEvent/extermination/RegularEventExterminationFormation.css",
        "magica/css/regularEvent/groupBattle/RegularEventGroupBattleBoss.css",
        "magica/css/regularEvent/groupBattle/RegularEventGroupBattleResult.css",
        "magica/css/regularEvent/groupBattle/RegularEventGroupBattleTop.css",
        "magica/css/shop/ShopTop.css",
        "magica/css/user/EventRecord.css",
    }
)
CSS_BASELINE_APPEND = frozenset(
    {
        "magica/css/_common/common.css",
        "magica/css/quest/MainQuest.css",
    }
)

# These are fields rendered as text or otherwise consumed as translated display
# content.  Identifier/code fields and credits (illustrator/designer/voiceActor)
# are intentionally absent, so technical strings cannot become false positives.
VISIBLE_FIELDS = frozenset(
    {
        "areaDetailName",
        "areaName",
        "cardName",
        "chapterNoForView",
        "charaName",
        "className",
        "conditionDescription",
        "description",
        "eventDescription",
        "eventName",
        "kana",
        "message",
        "name",
        "nextClassName",
        "outline",
        "parameter",
        "pieceName",
        "pointTitle",
        "school",
        "shortDescription",
        "storyTitle",
        "title",
        "unit",
    }
)
EXCLUDED_FIELD_CLASSES = {
    "technical": "IDs, codes, enums, dates, paths, openFunctions and reward fields",
    "credits": "illustrator, designer and voiceActor",
}

# mode is either substring, exact, or casefold-substring.  Single-character
# aliases such as 丰/优/希 are never banned globally; only their known erroneous
# contextual forms are listed.
BANNED_RULES: tuple[tuple[str, str, str], ...] = (
    ("visible Doppel/doppel", "casefold-substring", "doppel"),
    ("Japanese swimsuit residue", "substring", "水着"),
    ("Japanese sisters residue", "substring", "姉妹"),
    ("old Mitakihara glyph", "substring", "见滝原"),
    ("historical machine name", "substring", "胜乐金刚"),
    ("historical machine name", "substring", "东祥"),
    ("historical machine name", "substring", "东洋"),
    ("historical machine name", "substring", "苦杏仁"),
    ("old Helka alias", "substring", "赫尔卡"),
    ("old Amaryllis alias", "substring", "阿玛莉莉丝"),
    ("old Dolma alias", "substring", "多尔玛"),
    ("machine-translated character name", "substring", "爱生真昼"),
    ("cross-character trial title", "exact", "麻友的试炼"),
    ("old Livia surname", "substring", "莉薇娅·梅德洛斯"),
    ("hybrid beach translation", "substring", "砂滨"),
    ("Japanese Yura glyph", "substring", "由良蛍"),
    ("old Minou alias", "substring", "米努"),
    ("old Pernelle alias", "substring", "佩雷内尔"),
    ("old Corbeau alias", "substring", "科尔博"),
    ("old Elisa alias", "substring", "伊莉莎"),
    ("Toyo contextual mistranslation", "exact", "208,丰"),
    ("Toyo contextual mistranslation", "exact", "208、丰"),
    ("Yu contextual mistranslation", "exact", "226,悠"),
    ("Yu contextual mistranslation", "exact", "226、悠"),
    ("Shi contextual mistranslation", "exact", "227,希"),
    ("Shi contextual mistranslation", "exact", "227、希"),
    ("Shi trial mistranslation", "exact", "希的试炼"),
    ("MediaWiki conversion leak", "substring", "无望镜-{界}-"),
    ("old Iroha alias", "substring", "伊吕波"),
    ("old Eternal Sakura alias", "substring", "万年樱之谣"),
    ("old Eternal Sakura alias", "substring", "万年樱之传闻"),
    ("old Nanaka alias", "substring", "常盘七夏"),
    ("old Ayaka alias", "substring", "毬子彩花"),
    ("old Rumor Tsuruno alias", "substring", "谣鹤乃"),
    ("old Rumor Sana alias", "substring", "谣莎奈"),
    ("old Ultimate Madoka ticket alias", "substring", "终极小圆"),
    ("old Uwasa Mikoto alias", "substring", "传闻御琴"),
    ("old Uwasa Mikoto alias", "substring", "传闻命"),
    ("old organization alias", "substring", "神滨Magia Union"),
    ("old organization alias", "substring", "Promised Blood"),
    ("old organization alias", "substring", "约定之血"),
    ("old organization alias", "substring", "Neo Magius"),
    ("old organization alias", "substring", "新玛吉斯"),
)

ROOT_TRANSLATIONS = frozenset(
    {
        ("HOME_EV_1131_20191", "description", "主页背景「见泷原中学 屋顶」。"),
        ("HOME_EV_1131_20191", "name", "背景「见泷原中学 屋顶」"),
        ("HOME_EV_1131_20191", "shortDescription", "见泷原中学 屋顶（10周年纪念）"),
        ("HOME_EV_1131_20201", "description", "主页背景「见泷原中学 教室」。"),
        ("HOME_EV_1131_20201", "name", "背景「见泷原中学 教室」"),
        ("HOME_EV_1131_20201", "shortDescription", "见泷原中学 教室（10周年纪念）"),
        ("HOME_EV_1131_20211", "description", "主页背景「见泷原中学 校舍」。"),
        ("HOME_EV_1131_20211", "name", "背景「见泷原中学 校舍」"),
        ("HOME_EV_1131_20211", "shortDescription", "见泷原中学 校舍（10周年纪念）"),
        ("HOME_EV_1131_23051", "description", "主页背景「见泷原市 上学路」。"),
        ("HOME_EV_1131_23051", "name", "背景「见泷原市 上学路」"),
        ("HOME_EV_1131_23051", "shortDescription", "见泷原市 上学路（10周年纪念）"),
    }
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_git(*args: str, text: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=text,
    )
    if result.returncode:
        stderr = result.stderr if text else result.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return result.stdout


def run_python_json(script: Path, *args: str) -> tuple[dict[str, Any], str | None]:
    """Run an existing deterministic layer verifier and parse its JSON output."""
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout = result.stdout.decode("utf-8", "replace")
    stderr = result.stderr.decode("utf-8", "replace").strip()
    if result.returncode:
        return {}, f"{script.name} exited {result.returncode}: {stderr or stdout[-500:]}"
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {}, f"{script.name} did not emit JSON: {exc}"
    if not isinstance(payload, dict):
        return {}, f"{script.name} JSON root is not an object"
    return payload, None


def verify_manifest_lineage(
    rows: list[dict[str, str]], recorded_digest: str
) -> tuple[dict[str, Any], list[str]]:
    """Protect immutable Pass18 row identities while allowing later authority enrichment."""
    errors: list[str] = []
    raw = run_git(
        "show",
        f"{PASS18_MANIFEST_COMMIT}:{MANIFEST.relative_to(ROOT).as_posix()}",
    )
    assert isinstance(raw, bytes)
    baseline_rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8")), delimiter="\t"))
    immutable = (
        "change_id",
        "file",
        "json_pointer",
        "stable_key",
        "field",
        "before",
        "source_tier",
        "manual_review_status",
    )
    baseline_by_id = {row.get("change_id", ""): row for row in baseline_rows}
    current_by_id = {row.get("change_id", ""): row for row in rows}
    identity_failures: list[dict[str, Any]] = []
    for change_id in sorted(set(baseline_by_id) | set(current_by_id)):
        before = baseline_by_id.get(change_id)
        after = current_by_id.get(change_id)
        changed = [key for key in immutable if before and after and before.get(key) != after.get(key)]
        if before is None or after is None or changed:
            identity_failures.append(
                {
                    "change_id": change_id,
                    "missing_original": before is None,
                    "missing_current": after is None,
                    "changed_immutable_fields": changed,
                }
            )
    if identity_failures:
        errors.append(
            f"Pass18 manifest lineage has {len(identity_failures)} immutable identity changes"
        )
    enriched = sum(
        1
        for change_id, row in current_by_id.items()
        if change_id in baseline_by_id and row != baseline_by_id[change_id]
    )
    return {
        "pinned_manifest_commit": PASS18_MANIFEST_COMMIT,
        "recorded_digest": recorded_digest,
        "pinned_rows": len(baseline_rows),
        "current_rows": len(rows),
        "later_enriched_rows": enriched,
        "immutable_identity_failures": identity_failures,
    }, errors


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def unescape_pointer(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve_pointer(document: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON pointer: {pointer}")
    current = document
    for raw in pointer.split("/")[1:]:
        token = unescape_pointer(raw)
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def read_manifest() -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
    required = {
        "change_id",
        "file",
        "json_pointer",
        "stable_key",
        "field",
        "before",
        "after",
        "source_tier",
        "translation_method",
        "manual_review_status",
    }
    if not required.issubset(reader.fieldnames or []):
        errors.append("Pass18 manifest schema is incomplete")
    identities = [(row.get("file"), row.get("json_pointer")) for row in rows]
    if len(identities) != len(set(identities)):
        errors.append("Pass18 manifest has duplicate file/JSON-pointer identities")
    if len(rows) != EXPECTED_MANIFEST_ROWS:
        errors.append(
            f"Pass18 manifest row count is {len(rows)}, expected {EXPECTED_MANIFEST_ROWS}"
        )
    return rows, errors


def read_visible_term_closure() -> tuple[
    list[dict[str, str]], dict[tuple[str, str, str], dict[str, str]], dict[str, Any], list[str]
]:
    """Load the exact post-Pass18 authority layer and bind every row to product."""
    errors: list[str] = []
    required = {
        "closure_id",
        "path",
        "stable_key",
        "field",
        "before",
        "after",
        "source_tier",
        "review_status",
        "machine_translated",
        "evidence",
    }
    try:
        with VISIBLE_TERM_CLOSURE.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            rows = list(reader)
    except (OSError, UnicodeError) as exc:
        return [], {}, {"path": str(VISIBLE_TERM_CLOSURE), "failures": []}, [
            f"cannot read visible-term closure: {exc}"
        ]

    if not required.issubset(reader.fieldnames or []):
        errors.append("visible-term closure schema is incomplete")
    identities = [
        (row.get("path", ""), row.get("stable_key", ""), row.get("field", ""))
        for row in rows
    ]
    duplicate_identities = sorted(
        identity for identity, count in Counter(identities).items() if count > 1
    )
    duplicate_ids = sorted(
        closure_id
        for closure_id, count in Counter(row.get("closure_id", "") for row in rows).items()
        if count > 1 or not closure_id
    )
    if duplicate_identities or duplicate_ids:
        errors.append(
            "visible-term closure contains duplicate/blank identities: "
            f"targets={len(duplicate_identities)}, ids={len(duplicate_ids)}"
        )
    if len(rows) != EXPECTED_VISIBLE_TERM_CLOSURE_ROWS:
        errors.append(
            f"visible-term closure has {len(rows)} rows, "
            f"expected {EXPECTED_VISIBLE_TERM_CLOSURE_ROWS}"
        )

    allowed_tiers = {
        "official-cn",
        "root-reviewed-official-cn-terminology",
        "wiki-exact-stable-id-plus-official-cn-terminology",
    }
    allowed_statuses = {"official-source-verified", "root-reviewed-approved"}
    metadata_failures: list[dict[str, str]] = []
    product_failures: list[dict[str, str]] = []
    document_cache: dict[str, Any] = {}
    for row in rows:
        reasons: list[str] = []
        if row.get("source_tier") not in allowed_tiers:
            reasons.append(f"source_tier={row.get('source_tier')!r}")
        if row.get("review_status") not in allowed_statuses:
            reasons.append(f"review_status={row.get('review_status')!r}")
        if row.get("machine_translated") != "false":
            reasons.append(f"machine_translated={row.get('machine_translated')!r}")
        if not row.get("evidence"):
            reasons.append("evidence is blank")
        if reasons:
            metadata_failures.append(
                {"closure_id": row.get("closure_id", ""), "reasons": "; ".join(reasons)}
            )

        relative = row.get("path", "")
        try:
            document = document_cache.setdefault(relative, load_json(ROOT / relative))
            record = document[row.get("stable_key", "")]
            current = record[row.get("field", "")]
            if current != row.get("after", ""):
                product_failures.append(
                    {
                        "closure_id": row.get("closure_id", ""),
                        "path": relative,
                        "stable_key": row.get("stable_key", ""),
                        "field": row.get("field", ""),
                        "expected": row.get("after", ""),
                        "actual": current if isinstance(current, str) else repr(current),
                    }
                )
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            product_failures.append(
                {
                    "closure_id": row.get("closure_id", ""),
                    "path": relative,
                    "stable_key": row.get("stable_key", ""),
                    "field": row.get("field", ""),
                    "expected": row.get("after", ""),
                    "actual": f"exception: {exc}",
                }
            )

    try:
        summary = load_json(VISIBLE_TERM_CLOSURE_SUMMARY)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        summary = {}
        errors.append(f"cannot read visible-term closure summary: {exc}")
    summary_failures = {
        key: {"actual": summary.get(key), "expected": expected}
        for key, expected in {
            "status": "PASS",
            "entry_count": EXPECTED_VISIBLE_TERM_CLOSURE_ROWS,
            "exact_product_targets_verified": EXPECTED_VISIBLE_TERM_CLOSURE_ROWS,
            "physical_runtime_writes": EXPECTED_VISIBLE_TERM_CLOSURE_ROWS * 2,
            "independent_embedded_dictionary_pairs": EXPECTED_DICTIONARIES,
            "independent_embedded_equal": EXPECTED_DICTIONARIES,
        }.items()
        if summary.get(key) != expected
    }
    if summary_failures:
        errors.append(f"visible-term closure summary differs: {summary_failures}")
    if metadata_failures:
        errors.append(
            f"visible-term closure has {len(metadata_failures)} provenance failures"
        )
    if product_failures:
        errors.append(
            f"visible-term closure has {len(product_failures)} product binding failures"
        )

    index = {identity: row for identity, row in zip(identities, rows)}
    result = {
        "path": VISIBLE_TERM_CLOSURE.relative_to(ROOT).as_posix(),
        "summary_path": VISIBLE_TERM_CLOSURE_SUMMARY.relative_to(ROOT).as_posix(),
        "rows": len(rows),
        "unique_targets": len(set(identities)),
        "metadata_failures": metadata_failures,
        "product_failures": product_failures,
        "summary_failures": summary_failures,
    }
    return rows, index, result, errors


def verify_manifest_after_images(
    rows: list[dict[str, str]],
    closure_index: dict[tuple[str, str, str], dict[str, str]],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    json_cache: dict[str, Any] = {}
    failures: list[dict[str, str]] = []
    direct_runtime = 0
    superseded_runtime = 0
    static_direct = 0
    strict_json_pointer_resolutions = 0
    supersessions: list[dict[str, str]] = []
    for row in rows:
        relative = row["file"]
        path = ROOT / relative
        try:
            if path.suffix.lower() == ".json":
                document = json_cache.setdefault(relative, load_json(path))
                current = resolve_pointer(document, row["json_pointer"])
                strict_json_pointer_resolutions += 1
                if current == row["after"]:
                    direct_runtime += 1
                    ok = True
                else:
                    identity = (relative, row.get("stable_key", ""), row.get("field", ""))
                    closure = closure_index.get(identity)
                    ok = bool(
                        closure
                        and closure.get("before") == row.get("after")
                        and closure.get("after") == current
                    )
                    if ok:
                        superseded_runtime += 1
                        supersessions.append(
                            {
                                "change_id": row.get("change_id", ""),
                                "closure_id": closure.get("closure_id", ""),
                                "file": relative,
                                "json_pointer": row.get("json_pointer", ""),
                            }
                        )
                actual = current if isinstance(current, str) else repr(current)
            else:
                text = path.read_text(encoding="utf-8")
                after_count = text.count(row["after"])
                before_count = text.count(row["before"])
                ok = after_count == 1 and before_count == 0
                if ok:
                    static_direct += 1
                actual = f"after_count={after_count}; before_count={before_count}"
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            ok = False
            actual = f"exception: {exc}"
        if not ok:
            failures.append(
                {
                    "change_id": row.get("change_id", ""),
                    "file": relative,
                    "json_pointer": row.get("json_pointer", ""),
                    "expected_after": row.get("after", ""),
                    "actual": str(actual),
                }
            )
    if failures:
        errors.append(
            f"{len(failures)} Pass18 after-images have no exact approved successor"
        )
    expected_partition = {
        "runtime_direct": EXPECTED_PASS18_RUNTIME_DIRECT,
        "runtime_superseded": EXPECTED_PASS18_RUNTIME_SUPERSEDED,
        "static_direct": EXPECTED_PASS18_STATIC_DIRECT,
    }
    actual_partition = {
        "runtime_direct": direct_runtime,
        "runtime_superseded": superseded_runtime,
        "static_direct": static_direct,
    }
    partition_failures = {
        key: {"actual": actual_partition[key], "expected": expected}
        for key, expected in expected_partition.items()
        if actual_partition[key] != expected
    }
    if partition_failures:
        errors.append(f"Pass18 terminal partition differs: {partition_failures}")
    return {
        "expected_rows": EXPECTED_MANIFEST_ROWS,
        "actual_rows": len(rows),
        "after_image_matches": direct_runtime + superseded_runtime + static_direct,
        "runtime_direct_matches": direct_runtime,
        "runtime_exact_approved_supersessions": superseded_runtime,
        "static_direct_matches": static_direct,
        "strict_json_pointer_resolutions": strict_json_pointer_resolutions,
        "partition_failures": partition_failures,
        "supersessions": supersessions,
        "failures": failures,
    }, errors


def iter_visible_strings(
    value: Any, *, source: str, path: str = "$"
) -> Iterator[tuple[str, str, str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}"
            if isinstance(child, str):
                if key in VISIBLE_FIELDS:
                    yield source, child_path, key, child
            else:
                yield from iter_visible_strings(child, source=source, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_visible_strings(
                child, source=source, path=f"{path}/{index}"
            )


def extract_jquery_payload(path: Path) -> dict[str, Any]:
    text = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode(
        "utf-8-sig"
    )
    runtime_start = text.rfind("(function(){")
    if runtime_start < 0:
        raise ValueError("audited injector start marker missing")
    marker = "var cn = "
    payload_start = text.find(marker, runtime_start)
    if payload_start < 0:
        raise ValueError("var cn payload marker missing")
    payload, _ = json.JSONDecoder().raw_decode(text[payload_start + len(marker) :])
    if not isinstance(payload, dict):
        raise TypeError("jQuery var cn payload must be an object")
    return payload


def rule_matches(mode: str, needle: str, value: str) -> bool:
    if mode == "exact":
        return value == needle
    if mode == "substring":
        return needle in value
    if mode == "casefold-substring":
        return needle.casefold() in value.casefold()
    raise ValueError(f"unknown forbidden-rule mode {mode!r}")


def verify_visible_regressions() -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    policy = load_json(ROOT / "i18n" / "authority-policy.json")
    expected_names = set(policy["dictionary_contract"]["names"])
    actual_paths = {path.stem: path for path in (ROOT / "magica" / "js" / "libs").glob("*.json")}
    if set(actual_paths) != expected_names:
        errors.append(
            "runtime dictionary set mismatch: "
            f"missing={sorted(expected_names-set(actual_paths))}, "
            f"extra={sorted(set(actual_paths)-expected_names)}"
        )

    values: list[tuple[str, str, str, str]] = []
    standalone: dict[str, Any] = {}
    for name in sorted(expected_names & set(actual_paths)):
        try:
            standalone[name] = load_json(actual_paths[name])
            values.extend(
                iter_visible_strings(
                    standalone[name], source=f"magica/js/libs/{name}.json"
                )
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"cannot scan {name}.json: {exc}")

    jquery_values = 0
    try:
        jquery = extract_jquery_payload(ROOT / "magica" / "js" / "libs" / "jquery-3.7.1.min.js")
        before = len(values)
        values.extend(iter_visible_strings(jquery, source="jquery:var cn"))
        jquery_values = len(values) - before
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        errors.append(f"cannot scan jQuery embedded dictionaries: {exc}")

    hits: list[dict[str, str]] = []
    for label, mode, needle in BANNED_RULES:
        for source, path, field, value in values:
            if rule_matches(mode, needle, value):
                hits.append(
                    {
                        "rule": label,
                        "mode": mode,
                        "needle": needle,
                        "source": source,
                        "path": path,
                        "field": field,
                        "value": value,
                    }
                )
    if hits:
        errors.append(f"visible forbidden-regression hits: {len(hits)}")
    standalone_values = len(values) - jquery_values
    return {
        "expected_dictionaries": EXPECTED_DICTIONARIES,
        "actual_dictionaries": len(standalone),
        "visible_fields": sorted(VISIBLE_FIELDS),
        "excluded_field_classes": EXCLUDED_FIELD_CLASSES,
        "standalone_visible_values_scanned": standalone_values,
        "jquery_visible_values_scanned": jquery_values,
        "forbidden_rules": len(BANNED_RULES),
        "forbidden_hits": len(hits),
        "hits": hits,
    }, errors


def verify_root_translations(
    rows: list[dict[str, str]], manifest_result: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    selected = [
        row
        for row in rows
        if "root-personal-human-translation" in row.get("translation_method", "")
    ]
    actual = {
        (row.get("stable_key", ""), row.get("field", ""), row.get("after", ""))
        for row in selected
    }
    missing = sorted(ROOT_TRANSLATIONS - actual)
    extra = sorted(actual - ROOT_TRANSLATIONS)
    bad_status = [
        row.get("change_id", "")
        for row in selected
        if row.get("manual_review_status") != "root-translated-needs-human-review"
    ]
    failed_ids = {item["change_id"] for item in manifest_result["failures"]}
    after_failures = sorted(
        row.get("change_id", "") for row in selected if row.get("change_id", "") in failed_ids
    )
    if len(selected) != len(ROOT_TRANSLATIONS) or missing or extra:
        errors.append("root-personal translation manifest set does not equal the expected 12 fields")
    if bad_status:
        errors.append(f"root-personal translations have wrong review status: {bad_status}")
    if after_failures:
        errors.append(f"root-personal translations missing from product: {after_failures}")
    return {
        "expected": len(ROOT_TRANSLATIONS),
        "actual": len(selected),
        "exact_after_matches": len(selected) - len(after_failures),
        "missing": [list(item) for item in missing],
        "extra": [list(item) for item in extra],
        "bad_review_status_change_ids": bad_status,
        "after_image_failure_change_ids": after_failures,
    }, errors


def verify_engine() -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    raw = ENGINE.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("engine_i18n.tsv has a UTF-8 BOM")
    if b"\r" in raw:
        errors.append("engine_i18n.tsv is not LF-only")
    text = raw.decode("utf-8")
    entries: list[tuple[int, str, str]] = []
    malformed: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) != 2 or not columns[0]:
            malformed.append({"line": lineno, "column_count": len(columns), "text": line})
            continue
        entries.append((lineno, columns[0], columns[1]))
    if malformed:
        errors.append(f"engine_i18n.tsv has {len(malformed)} malformed data lines")

    source_counts = Counter(source for _, source, _ in entries)
    duplicates = {
        source: count for source, count in sorted(source_counts.items()) if count > 1
    }
    if duplicates:
        errors.append(f"engine_i18n.tsv has {len(duplicates)} duplicate source keys")
    if len(entries) != EXPECTED_ENGINE_ROWS:
        errors.append(
            f"engine_i18n.tsv has {len(entries)} data rows, expected {EXPECTED_ENGINE_ROWS}"
        )
    physical_lines = len(text.splitlines())
    if physical_lines != EXPECTED_ENGINE_PHYSICAL_LINES:
        errors.append(
            f"engine_i18n.tsv has {physical_lines} physical lines, "
            f"expected {EXPECTED_ENGINE_PHYSICAL_LINES}"
        )

    mapping = {source: target for _, source, target in entries}
    try:
        native_evidence = load_json(ENGINE_NATIVE_EVIDENCE)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        native_evidence = {}
        errors.append(f"cannot read official CN native engine evidence: {exc}")
    native_records = [
        record
        for record in native_evidence.get("records", [])
        if record.get("product_write_allowed")
    ]
    native_by_source = {record.get("source", ""): record for record in native_records}
    native_failures: list[str] = []
    if (
        native_evidence.get("schema") != "official-cn-native-localization-exhaustion/v1"
        or len(native_evidence.get("records", [])) != 189
        or len(native_evidence.get("dispositions", [])) != 349
        or len(native_by_source) != 182
    ):
        native_failures.append("closure counts/schema differ")
    for source, record in native_by_source.items():
        if mapping.get(source) != record.get("selected_cn"):
            native_failures.append(f"runtime mapping differs for {source}")
    if native_failures:
        errors.append(f"official CN native engine layer differs: {native_failures[:10]}")
    with ENGINE_AUDIT.open(encoding="utf-8", newline="") as handle:
        official = list(csv.DictReader(handle, delimiter="\t"))
    if len(official) != EXPECTED_ENGINE_OFFICIAL_ROWS:
        errors.append(
            f"Pass18 engine official audit has {len(official)} rows, "
            f"expected {EXPECTED_ENGINE_OFFICIAL_ROWS}"
        )
    official_failures: list[dict[str, str]] = []
    for row in official:
        metadata_by_entry = {
            "ENG-P18-004": {
                "source_tier": "official-cn-exact-art-id-join",
                "confidence": "exact-art-id-join",
                "manual_review_status": "verify-join",
            },
            "ENG-P18-005": {
                "source_tier": "official-cn-ui-exact-retained",
                "confidence": "exact-ui-retain",
                "manual_review_status": "official-source-verified",
            },
        }
        expected_metadata = {
            "source_tier": "official-cn",
            "is_machine_translation": "false",
            "confidence": "exact-id-match",
            "manual_review_status": "official-source-verified",
            "runtime_consumed": "true",
            **metadata_by_entry.get(row.get("entry_id", ""), {}),
        }
        reasons: list[str] = []
        if mapping.get(row.get("source_text", "")) != row.get("current_cn", ""):
            reasons.append("runtime mapping missing or target differs")
        for key, expected in expected_metadata.items():
            if row.get(key) != expected:
                reasons.append(f"{key}={row.get(key)!r}, expected {expected!r}")
        if reasons:
            official_failures.append(
                {
                    "entry_id": row.get("entry_id", ""),
                    "source_text": row.get("source_text", ""),
                    "reasons": "; ".join(reasons),
                }
            )
    if official_failures:
        errors.append(
            f"{len(official_failures)} Pass18 official engine mappings failed provenance/runtime checks"
        )

    line_set = set(text.splitlines())
    try:
        ap_evidence = load_json(ENGINE_AP_EVIDENCE)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        ap_evidence = {}
        errors.append(f"cannot read AP engine evidence: {exc}")
    ap_contract = {
        "ok": True,
        "mode": "current-main-compatible",
        "active_rules": 308,
        "exact": 4,
        "prefix": 304,
        "substring": 0,
        "generated_timer_rules": 301,
        "final_engine_rule_count": EXPECTED_ENGINE_ROWS,
    }
    ap_contract_failures = {
        key: {"actual": ap_evidence.get(key), "expected": expected}
        for key, expected in ap_contract.items()
        if ap_evidence.get(key) != expected
    }
    ap_rule_failures: list[dict[str, str]] = []
    active_records = ap_evidence.get("records", [])
    removed_records = ap_evidence.get("removed_unsupported_records", [])
    if not isinstance(active_records, list) or len(active_records) != 308:
        ap_contract_failures["records"] = {
            "actual": len(active_records) if isinstance(active_records, list) else type(active_records).__name__,
            "expected": 308,
        }
        active_records = []
    if not isinstance(removed_records, list) or len(removed_records) != 2:
        ap_contract_failures["removed_unsupported_records"] = {
            "actual": len(removed_records) if isinstance(removed_records, list) else type(removed_records).__name__,
            "expected": 2,
        }
        removed_records = []
    for record in active_records:
        rendered = record.get("rendered", "")
        reasons: list[str] = []
        if record.get("kind") not in {"exact", "prefix"}:
            reasons.append(f"unsupported active kind {record.get('kind')!r}")
        if rendered not in line_set or text.splitlines().count(rendered) != 1:
            reasons.append("rendered rule is not present exactly once")
        if record.get("runtime_contract") != "supported-by-current-main-exact-or-prefix":
            reasons.append("runtime contract is not current-main supported")
        if reasons:
            ap_rule_failures.append(
                {"rule_id": record.get("rule_id", ""), "reasons": "; ".join(reasons)}
            )
    timer_records = [
        record for record in active_records
        if str(record.get("rule_id", "")).startswith("ENGINE-AP-DYNAMIC-TIMER-")
    ]
    expected_timer_sources = {
        "^1 AP will recover in "
        f"{total // 60}:{total % 60:02d} / AP will be fully recovered in "
        for total in range(301)
    }
    actual_timer_sources = {record.get("rendered", "").split("\t", 1)[0] for record in timer_records}
    if len(timer_records) != 301 or actual_timer_sources != expected_timer_sources:
        ap_rule_failures.append(
            {
                "rule_id": "dynamic-timer-coverage",
                "reasons": (
                    f"expected 301 exact M:SS prefixes (0:00..5:00), "
                    f"got records={len(timer_records)}, sources={len(actual_timer_sources)}"
                ),
            }
        )
    for record in removed_records:
        rendered = record.get("rendered", "")
        reasons = []
        if record.get("kind") != "substring":
            reasons.append(f"removed kind is {record.get('kind')!r}, expected substring")
        if rendered in line_set:
            reasons.append("unsupported substring rule remains active")
        if record.get("runtime_contract") != "unsupported-by-current-main-and-removed-from-runtime-table":
            reasons.append("removed rule contract metadata differs")
        if reasons:
            ap_rule_failures.append(
                {"rule_id": record.get("rule_id", ""), "reasons": "; ".join(reasons)}
            )
    active_substring_sources = [source for _, source, _ in entries if source.startswith("~")]
    if active_substring_sources:
        ap_rule_failures.append(
            {
                "rule_id": "active-substring-scan",
                "reasons": f"unsupported ~ rules remain: {active_substring_sources}",
            }
        )
    if ap_contract_failures or ap_rule_failures:
        errors.append(
            "current-main AP engine contract differs: "
            f"metadata={ap_contract_failures}, rules={len(ap_rule_failures)}"
        )

    try:
        connect_evidence = load_json(ENGINE_CONNECT_EVIDENCE)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        connect_evidence = {}
        errors.append(f"cannot read Connect engine evidence: {exc}")
    connect_failures: list[str] = []
    if set(connect_evidence.get("sources", [])) != {"コネクト", "Connect"}:
        connect_failures.append("source set differs")
    if connect_evidence.get("target") != "连携":
        connect_failures.append("target differs")
    if connect_evidence.get("source_tier") != "official-cn-terminology":
        connect_failures.append("source tier differs")
    if connect_evidence.get("machine_translated") is not False:
        connect_failures.append("machine-translated flag differs")
    for source in ("コネクト", "Connect"):
        if mapping.get(source) != "连携":
            connect_failures.append(f"runtime mapping differs for {source}")
    if connect_failures:
        errors.append(f"Connect engine authority contract differs: {connect_failures}")

    authority_layers: dict[str, Any] = {}
    for label, evidence_path, expected_records in (
        ("final_authority", ENGINE_FINAL_EVIDENCE, 9),
        ("root_reviewed", ENGINE_ROOT_EVIDENCE, 41),
    ):
        try:
            evidence = load_json(evidence_path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            authority_layers[label] = {"path": str(evidence_path), "error": str(exc)}
            errors.append(f"cannot read {label} engine evidence: {exc}")
            continue
        records = evidence.get("records", [])
        layer_failures: list[dict[str, str]] = []
        seen_sources: set[str] = set()
        if evidence.get("record_count") != expected_records or not isinstance(records, list):
            layer_failures.append(
                {
                    "review_id": "record-count",
                    "reasons": f"actual={evidence.get('record_count')!r}, expected={expected_records}",
                }
            )
            records = records if isinstance(records, list) else []
        for record in records:
            source = record.get("source", "")
            reasons = []
            if not source or source in seen_sources:
                reasons.append("blank/duplicate source")
            seen_sources.add(source)
            selected_target = native_by_source.get(source, {}).get("selected_cn", record.get("target"))
            if mapping.get(source) != selected_target:
                reasons.append("runtime mapping differs")
            if record.get("machine_translated") is not False:
                reasons.append("machine-translated flag differs")
            if not record.get("evidence"):
                reasons.append("evidence is blank")
            if reasons:
                layer_failures.append(
                    {
                        "review_id": record.get("review_id", ""),
                        "reasons": "; ".join(reasons),
                    }
                )
        if layer_failures:
            errors.append(f"{label} engine layer has {len(layer_failures)} failures")
        authority_layers[label] = {
            "path": evidence_path.relative_to(ROOT).as_posix(),
            "records": len(records),
            "failures": layer_failures,
        }

    try:
        final_verification = load_json(ENGINE_FINAL_VERIFICATION)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        final_verification = {}
        errors.append(f"cannot read final engine apply verification: {exc}")
    final_verification_failures = {
        key: {"actual": final_verification.get(key), "expected": expected}
        for key, expected in {
            "status": "PASS",
            "rule_count": BASE_ENGINE_ROWS,
            "replacement_count": 10,
            "removed_unsupported_count": 2,
            "added_exact_count": 1,
            "duplicate_sources": 0,
            "malformed_rows": 0,
            "protected_unrelated_rows_changed": 0,
        }.items()
        if final_verification.get(key) != expected
    }
    if final_verification_failures:
        errors.append(
            f"final engine apply verification differs: {final_verification_failures}"
        )
    return {
        "path": "madomagi/engine_i18n.tsv",
        "sha256": sha256(ENGINE),
        "bytes": len(raw),
        "encoding": "UTF-8",
        "line_endings": "LF" if b"\r" not in raw else "contains-CR",
        "expected_data_rows": EXPECTED_ENGINE_ROWS,
        "actual_data_rows": len(entries),
        "expected_physical_lines": EXPECTED_ENGINE_PHYSICAL_LINES,
        "actual_physical_lines": physical_lines,
        "malformed_lines": malformed,
        "duplicate_source_keys": duplicates,
        "official_audit_rows": len(official),
        "official_mapping_failures": official_failures,
        "official_cn_native": {
            "path": ENGINE_NATIVE_EVIDENCE.relative_to(ROOT).as_posix(),
            "accepted_sources": len(native_by_source),
            "failures": native_failures,
        },
        "post_pass18_gap_rules": {
            "evidence": ENGINE_AP_EVIDENCE.relative_to(ROOT).as_posix(),
            "result": ap_evidence,
            "contract_failures": ap_contract_failures,
            "rule_failures": ap_rule_failures,
            "active_substring_sources": active_substring_sources,
        },
        "connect_authority": {
            "evidence": ENGINE_CONNECT_EVIDENCE.relative_to(ROOT).as_posix(),
            "sources": connect_evidence.get("sources", []),
            "target": connect_evidence.get("target"),
            "failures": connect_failures,
        },
        "authority_layers": authority_layers,
        "final_apply_verification": {
            "path": ENGINE_FINAL_VERIFICATION.relative_to(ROOT).as_posix(),
            "result": final_verification,
            "failures": final_verification_failures,
        },
    }, errors


def baseline_css_blobs() -> dict[str, str]:
    output = run_git("ls-tree", "-r", "-z", BASELINE_COMMIT, "--", "magica")
    assert isinstance(output, bytes)
    blobs: dict[str, str] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, path_bytes = record.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        path = path_bytes.decode("utf-8")
        if path.startswith("magica/css/") and path.lower().endswith(".css"):
            if kind != "blob" or mode != "100644":
                raise ValueError(f"unexpected baseline CSS tree entry: {record!r}")
            blobs[path] = blob
    return blobs


def css_braces_are_balanced(text: str) -> bool:
    """Balance CSS braces without treating strings or comments as structure."""
    depth = 0
    quote: str | None = None
    escaped = False
    in_comment = False
    index = 0
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if in_comment:
            if char == "*" and following == "/":
                in_comment = False
                index += 2
                continue
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and following == "*":
            in_comment = True
            index += 2
            continue
        elif char in {"\"", "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
        index += 1
    return depth == 0 and quote is None and not in_comment


def json_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_shape(child) for key, child in value.items()}
    if isinstance(value, list):
        return [json_shape(child) for child in value]
    return type(value).__name__


def html_ejs_signature(text: str) -> list[str]:
    return re.findall(r"<%[\s\S]*?%>|<[^>]+>", text)


def verify_connect_followup_layers() -> tuple[dict[str, Any], list[str]]:
    """Bind the approved Connect -> 连携 visible layers to their exact artifacts."""
    errors: list[str] = []
    failures: list[dict[str, str]] = []
    try:
        patch = load_json(CONNECT_VISIBLE_PATCH)
        visible_verification = load_json(CONNECT_VISIBLE_VERIFICATION)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"failures": []}, [f"cannot read Connect visible evidence: {exc}"]

    records = patch.get("records", [])
    allowed_paths = {
        "magica/css/_common/common.css",
        "magica/template/collection/CharaCollectionDetail.html",
        "magica/template/gacha/SelectableGachaCharaSelect.html",
        "magica/js/test/SoundTest.js",
    }
    if (
        patch.get("schema") != "connect-visible-ui-patch/v1"
        or patch.get("files") != 4
        or patch.get("visible_occurrences") != 8
        or not isinstance(records, list)
        or len(records) != 7
    ):
        errors.append("Connect visible patch metadata differs from the approved 4-file/8-occurrence layer")
        records = records if isinstance(records, list) else []
    for record in records:
        relative = record.get("product_path", "")
        reasons: list[str] = []
        if relative not in allowed_paths:
            reasons.append("path outside Connect visible allowlist")
        if record.get("source_tier") != "confirmed-human-visible-mechanic-term":
            reasons.append("source tier differs")
        try:
            text = (ROOT / relative).read_text(encoding="utf-8")
            before_count = text.count(record.get("before", ""))
            after_count = text.count(record.get("after", ""))
            if before_count != 0:
                reasons.append(f"old literal count={before_count}")
            if after_count != int(record.get("occurrences", 0)):
                reasons.append(
                    f"new literal count={after_count}, expected={record.get('occurrences')}"
                )
        except (OSError, UnicodeError, ValueError) as exc:
            reasons.append(f"cannot inspect product: {exc}")
        if reasons:
            failures.append(
                {
                    "path": relative,
                    "before": record.get("before", ""),
                    "after": record.get("after", ""),
                    "reasons": "; ".join(reasons),
                }
            )

    html_structure_failures: list[str] = []
    for relative in sorted(path for path in allowed_paths if path.endswith(".html")):
        original = CONNECT_VISIBLE_EVIDENCE / "originals" / relative
        modified = CONNECT_VISIBLE_EVIDENCE / "modified" / relative
        try:
            original_text = original.read_text(encoding="utf-8")
            modified_text = modified.read_text(encoding="utf-8")
            current_text = (ROOT / relative).read_text(encoding="utf-8")
            if html_ejs_signature(original_text) != html_ejs_signature(modified_text):
                html_structure_failures.append(f"evidence structure drift: {relative}")
            if html_ejs_signature(modified_text) != html_ejs_signature(current_text):
                html_structure_failures.append(f"product structure drift: {relative}")
        except (OSError, UnicodeError) as exc:
            html_structure_failures.append(f"cannot inspect {relative}: {exc}")

    visible_contract = {
        "status": "PASS",
        "files": 4,
        "visible_occurrences": 8,
        "old_visible_literals_remaining": 0,
        "code_identifier_replacements": 0,
        "protected_dictionary_replacements": 0,
        "node_failures": 0,
        "html_ejs_structure_drift": 0,
    }
    verification_failures = {
        key: {"actual": visible_verification.get(key), "expected": expected}
        for key, expected in visible_contract.items()
        if visible_verification.get(key) != expected
    }
    if failures or html_structure_failures or verification_failures:
        errors.append(
            "Connect visible follow-up layer differs: "
            f"literals={len(failures)}, html={len(html_structure_failures)}, "
            f"verification={verification_failures}"
        )

    try:
        help_verification = load_json(CONNECT_HELP_VERIFICATION)
        original_path = CONNECT_HELP_EVIDENCE / "originals/magica/resource/image_web/_json/help.json"
        modified_path = CONNECT_HELP_EVIDENCE / "modified/magica/resource/image_web/_json/help.json"
        current_path = ROOT / "magica/resource/image_web/_json/help.json"
        original_bytes = original_path.read_bytes()
        modified_bytes = modified_path.read_bytes()
        current_bytes = current_path.read_bytes()
        expected_bytes = original_bytes.replace(b"Connect", "连携".encode("utf-8"))
        original_json = json.loads(original_bytes.decode("utf-8"))
        current_json = json.loads(current_bytes.decode("utf-8"))
        help_failures = []
        if original_bytes.count(b"Connect") != 14:
            help_failures.append("baseline Connect count is not 14")
        if modified_bytes != expected_bytes or current_bytes != modified_bytes:
            help_failures.append("current/modified bytes are not the exact approved substitution")
        if current_bytes.count(b"Connect") != 0 or current_bytes.count("连携".encode("utf-8")) != 14:
            help_failures.append("current Connect/连携 counts differ")
        if json_shape(original_json) != json_shape(current_json):
            help_failures.append("JSON shape drift")
        if help_verification.get("schema") != "connect-help-json-verification-v1":
            help_failures.append("verification schema differs")
        if help_verification.get("authority") != "user-confirmed-stable-visible-mechanic-term":
            help_failures.append("authority metadata differs")
        for phase in ("baseline_verification", "modified_verification"):
            if help_verification.get(phase, {}).get("exit_status") not in (0, [0, 0]):
                help_failures.append(f"{phase} exit status differs")
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
        help_verification = {}
        help_failures = [f"cannot inspect Connect help layer: {exc}"]
    if help_failures:
        errors.append(f"Connect help follow-up layer differs: {help_failures}")

    return {
        "visible_patch": CONNECT_VISIBLE_PATCH.relative_to(ROOT).as_posix(),
        "visible_records": len(records),
        "visible_failures": failures,
        "html_ejs_structure_failures": html_structure_failures,
        "visible_verification_failures": verification_failures,
        "help_verification": CONNECT_HELP_VERIFICATION.relative_to(ROOT).as_posix(),
        "help_failures": help_failures,
    }, errors


def verify_manual_round3_layered() -> tuple[dict[str, Any], list[str]]:
    """Verify the round-3 state plus only the explicitly approved later transforms."""
    errors: list[str] = []
    failures: list[dict[str, str]] = []
    try:
        manifest = load_json(MANUAL_ROUND3_MANIFEST)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"failures": []}, [f"cannot read manual-round3 manifest: {exc}"]
    state = MANUAL_ROUND3_MANIFEST.parent
    transforms = {
        "magica/resource/image_web/_json/help.json": (
            ("属性相性", "属性克制", 1),
            ("Connect", "连携", 14),
        ),
        "magica/css/regularEvent/groupBattle/RegularEventGroupBattleRanking.css": (
            ("必要GP", "所需GP", 1),
        ),
        "magica/css/regularEvent/groupBattle/RegularEventGroupBattleUser.css": (
            ("必要GP", "所需GP", 1),
        ),
    }
    targets = manifest.get("targets", [])
    if manifest.get("item_count") != 124 or manifest.get("target_count") != 8:
        errors.append("manual-round3 manifest count contract differs")
    for item in targets if isinstance(targets, list) else []:
        relative = item.get("target", "")
        reasons: list[str] = []
        prepared_path = state / "prepared" / relative
        current_path = ROOT / relative
        try:
            prepared = prepared_path.read_bytes()
            for name in ("prepared", "sources", "bases"):
                snapshot = state / name / relative
                checkpoint = state / "checks" / name / relative
                if snapshot.read_bytes() != checkpoint.read_bytes():
                    reasons.append(f"{name} checkpoint drift")
            expected = prepared
            for before, after, count in transforms.get(relative, ()):
                before_bytes = before.encode("utf-8")
                after_bytes = after.encode("utf-8")
                if expected.count(before_bytes) != count or expected.count(after_bytes) != 0:
                    reasons.append(f"transform baseline drift: {before}->{after}")
                    continue
                expected = expected.replace(before_bytes, after_bytes, count)
            current = current_path.read_bytes()
            if current != expected:
                reasons.append("product differs from prepared plus approved transforms")
            if str(item.get("kind")) == "css":
                if not css_braces_are_balanced(current.decode("utf-8")):
                    reasons.append("CSS structure drift")
            else:
                prepared_json = json.loads(prepared.decode("utf-8"))
                current_json = json.loads(current.decode("utf-8"))
                if json_shape(prepared_json) != json_shape(current_json):
                    reasons.append("JSON shape drift")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            reasons.append(f"cannot inspect target: {exc}")
        if reasons:
            failures.append({"target": relative, "reasons": "; ".join(reasons)})
    if not isinstance(targets, list) or len(targets) != 8 or failures:
        errors.append(
            f"manual-round3 layered product differs: targets={len(targets) if isinstance(targets, list) else -1}, failures={len(failures)}"
        )
    return {
        "manifest": MANUAL_ROUND3_MANIFEST.relative_to(ROOT).as_posix(),
        "targets": len(targets) if isinstance(targets, list) else 0,
        "approved_followup_transforms": sum(len(value) for value in transforms.values()),
        "failures": failures,
    }, errors


def verify_css() -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    baseline = baseline_css_blobs()
    current_paths = {
        path.relative_to(ROOT).as_posix(): path
        for path in (ROOT / "magica" / "css").rglob("*.css")
        if path.is_file()
    }

    visible_manifest = load_json(ROUND3_VISIBLE_MANIFEST)
    visible_items = [
        item
        for item in visible_manifest.get("items", [])
        if str(item.get("path", "")).endswith(".css")
    ]
    visible_paths = {item["path"] for item in visible_items}
    manual_manifest = load_json(MANUAL_ROUND3_MANIFEST)
    manual_paths = {
        item["target"]
        for item in manual_manifest.get("targets", [])
        if item.get("kind") == "css"
    }
    round4_manifest = load_json(ROUND4_MANIFEST)
    round4_paths = {
        item["file"]
        for item in round4_manifest.get("changes", [])
        if str(item.get("file", "")).endswith(".css")
    }
    expected_paths = set(baseline) | visible_paths | manual_paths | round4_paths
    missing = sorted(expected_paths - set(current_paths))
    extra = sorted(set(current_paths) - expected_paths)

    # Baseline files not selected by a later manifest remain byte-for-byte
    # protected.  Selected files are instead bound by their exact layer
    # manifests/verifiers below, so approved upstream architecture changes are
    # not mistaken for translation drift.
    untouched_mismatches: list[dict[str, str]] = []
    untouched_paths = set(baseline) - visible_paths - manual_paths - round4_paths
    for relative in sorted(untouched_paths & set(current_paths)):
        current_blob = run_git(
            "hash-object", "--path", relative, str(current_paths[relative]), text=True
        )
        assert isinstance(current_blob, str)
        current_blob = current_blob.strip()
        if current_blob != baseline[relative]:
            untouched_mismatches.append(
                {
                    "path": relative,
                    "baseline_blob": baseline[relative],
                    "current_filtered_blob": current_blob,
                }
            )

    visible_failures: list[dict[str, Any]] = []
    for item in visible_items:
        path = current_paths.get(item["path"])
        if path is None:
            continue
        text = path.read_text(encoding="utf-8")
        expected_count = int(item.get("count", 1))
        if item.get("operation") == "replace":
            before_count = text.count(item.get("before", ""))
            after_count = text.count(item.get("after", ""))
            if item.get("item_id") == "UI-075":
                final_literal = item.get("after", "").replace(
                    'content:"Connect"', 'content:"连携"'
                )
                final_count = text.count(final_literal)
                ok = before_count == 0 and after_count == 0 and final_count == expected_count
            else:
                final_count = after_count
                ok = before_count == 0 and after_count == expected_count
        elif item.get("operation") == "append":
            before_count = 0
            after_count = text.count(item.get("block", ""))
            final_count = after_count
            ok = after_count == expected_count
        else:
            before_count = after_count = final_count = -1
            ok = False
        if not ok:
            visible_failures.append(
                {
                    "item_id": item.get("item_id"),
                    "path": item.get("path"),
                    "operation": item.get("operation"),
                    "before_count": before_count,
                    "after_count": after_count,
                    "terminal_after_count": final_count,
                    "expected_count": expected_count,
                }
            )

    content_report = load_json(ROUND3_CSS_REPORT)
    report_ok = (
        content_report.get("ok") is True
        and content_report.get("items") == 110
        and content_report.get("files") == 26
    )
    manual_result, manual_errors = verify_manual_round3_layered()
    connect_result, connect_errors = verify_connect_followup_layers()
    round4_result, round4_error = run_python_json(
        ROOT / "tools" / "apply-visible-residue-closure-round4.py", "--verify"
    )
    unbalanced = sorted(
        relative
        for relative, path in current_paths.items()
        if not css_braces_are_balanced(path.read_text(encoding="utf-8"))
    )
    content_re = re.compile(r"content\s*:\s*([\"'])(.*?)(?<!\\)\1", re.S)
    kana_re = re.compile(r"[\u3040-\u30ff]")
    forbidden_values = {
        "Lv", "LV", "Rank", "Stage", "Illustrator", "OVER", "Lv MAX", "BONUS",
        "エピソードLv", "マギアLv", "マギア", "EXスキル", "コネクト", "条件クリアで解放",
        "最終ログイン", "スキルタイプ", "スキル", "アビリティタイプ", "アビリティ",
        "対戦相手", "挑戦する", "受け取る", "参加済", "必要GP", "必要撃退数",
        "到達した撃退Lv", "最高獲得エンブレム", "デイリーダメージ", "現在のグレード",
        "已达到的击退Lv",
    }
    generated_label_failures: list[dict[str, str]] = []
    for relative, path in sorted(current_paths.items()):
        for match in content_re.finditer(path.read_text(encoding="utf-8")):
            value = match.group(2)
            if value in forbidden_values or kana_re.search(value):
                generated_label_failures.append({"path": relative, "value": value})

    if len(baseline) != EXPECTED_CSS_FILES:
        errors.append(
            f"baseline product has {len(baseline)} CSS files, expected {EXPECTED_CSS_FILES}"
        )
    if (
        missing
        or extra
        or untouched_mismatches
        or visible_failures
        or not report_ok
        or manual_errors
        or connect_errors
        or round4_error
        or round4_result.get("mode") != "verify-after"
        or str(round4_result.get("status", "")).upper() != "PASS"
        or unbalanced
        or generated_label_failures
    ):
        errors.append(
            "CSS differs from the layered Pass18/visible/manual/round4 contract: "
            f"missing={len(missing)}, extra={len(extra)}, "
            f"untouched_changed={len(untouched_mismatches)}, "
            f"visible_failures={len(visible_failures)}, unbalanced={len(unbalanced)}, "
            f"generated_label_failures={len(generated_label_failures)}"
        )
    return {
        "baseline_commit": BASELINE_COMMIT,
        "expected_files": EXPECTED_CSS_FILES,
        "baseline_files": len(baseline),
        "current_files": len(current_paths),
        "missing": missing,
        "extra": extra,
        "untouched_baseline_files": len(untouched_paths),
        "untouched_mismatches": untouched_mismatches,
        "visible_round3": {
            "items": len(visible_items),
            "files": len(visible_paths),
            "literal_failures": visible_failures,
            "content_report_ok": report_ok,
            "generated_label_failures": generated_label_failures,
        },
        "manual_round3": {
            "files": len(manual_paths),
            "paths": sorted(manual_paths),
            "errors": manual_errors,
            "result": manual_result,
        },
        "connect_followup": {
            "errors": connect_errors,
            "result": connect_result,
        },
        "round4": {
            "files": len(round4_paths),
            "paths": sorted(round4_paths),
            "execution_error": round4_error,
            "result": round4_result,
        },
        "unbalanced_braces": unbalanced,
    }, errors


def verify_boss_static(rows: list[dict[str, str]]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    relative = "magica/js/regularEvent/groupBattle/view/BossPageView.js"
    selected = [row for row in rows if row.get("file") == relative]
    after_count = before_count = 0
    if len(selected) != 1:
        errors.append(f"expected one BossPageView Pass18 manifest row, got {len(selected)}")
    else:
        text = (ROOT / relative).read_text(encoding="utf-8")
        after_count = text.count(selected[0]["after"])
        before_count = text.count(selected[0]["before"])
        if after_count != 1 or before_count != 0:
            errors.append(
                "BossPageView static authority label is missing or the old label remains"
            )
    return {
        "path": relative,
        "manifest_rows": len(selected),
        "corrected_literal_count": after_count,
        "old_literal_count": before_count,
    }, errors


def main() -> int:
    errors: list[str] = []
    baseline_record = load_json(BASELINE_RECORD)
    manifest_sha = sha256(MANIFEST)
    if baseline_record.get("baseline_head") != BASELINE_COMMIT:
        errors.append("Pass18 baseline record commit differs from verifier constant")

    rows, manifest_read_errors = read_manifest()
    errors.extend(manifest_read_errors)
    lineage_result, part_errors = verify_manifest_lineage(
        rows, str(baseline_record.get("manifest_sha256", ""))
    )
    errors.extend(part_errors)
    _, closure_index, closure_result, part_errors = read_visible_term_closure()
    errors.extend(part_errors)
    manifest_result, part_errors = verify_manifest_after_images(rows, closure_index)
    errors.extend(part_errors)
    root_result, part_errors = verify_root_translations(rows, manifest_result)
    errors.extend(part_errors)
    visible_result, part_errors = verify_visible_regressions()
    errors.extend(part_errors)
    engine_result, part_errors = verify_engine()
    errors.extend(part_errors)
    css_result, part_errors = verify_css()
    errors.extend(part_errors)
    boss_result, part_errors = verify_boss_static(rows)
    errors.extend(part_errors)

    report = {
        "schema": "magireco-cn-v26-pass18-authority-verification/v2",
        "status": "PASS" if not errors else "FAIL",
        "baseline_commit": BASELINE_COMMIT,
        "manifest": {
            "path": MANIFEST.relative_to(ROOT).as_posix(),
            "sha256": manifest_sha,
            "recorded_sha256": baseline_record.get("manifest_sha256"),
            "digest_matches_original": manifest_sha == baseline_record.get("manifest_sha256"),
            "lineage": lineage_result,
            **manifest_result,
        },
        "visible_term_closure": closure_result,
        "visible_regression_scan": visible_result,
        "root_personal_translations": root_result,
        "engine_i18n": engine_result,
        "css_unchanged": css_result,
        "boss_page_static_label": boss_result,
        "errors": errors,
    }
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
