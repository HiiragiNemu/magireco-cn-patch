#!/usr/bin/env python3
"""Verify the Pass18 v26 authority corrections without modifying the product.

This verifier is deliberately narrower than the general runtime-layer audit.  It
checks the exact Pass18 after-images, scans only user-visible dictionary fields
for known translation regressions, protects the twelve root-authored background
translations, validates the engine table, and proves that CSS is identical to
the recorded Pass18 baseline commit.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
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
EXPECTED_MANIFEST_ROWS = 939
EXPECTED_ENGINE_ROWS = 303
EXPECTED_ENGINE_OFFICIAL_ROWS = 5
EXPECTED_DICTIONARIES = 23
EXPECTED_CSS_FILES = 25

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


def verify_manifest_after_images(
    rows: list[dict[str, str]],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    json_cache: dict[str, Any] = {}
    failures: list[dict[str, str]] = []
    matches = 0
    for row in rows:
        relative = row["file"]
        path = ROOT / relative
        try:
            if path.suffix.lower() == ".json":
                document = json_cache.setdefault(relative, load_json(path))
                current = resolve_pointer(document, row["json_pointer"])
                ok = current == row["after"]
                actual = current if isinstance(current, str) else repr(current)
            else:
                text = path.read_text(encoding="utf-8")
                after_count = text.count(row["after"])
                before_count = text.count(row["before"])
                ok = after_count == 1 and before_count == 0
                actual = f"after_count={after_count}; before_count={before_count}"
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, IndexError, ValueError) as exc:
            ok = False
            actual = f"exception: {exc}"
        if ok:
            matches += 1
        else:
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
        errors.append(f"{len(failures)} Pass18 manifest after-images do not match")
    return {
        "expected_rows": EXPECTED_MANIFEST_ROWS,
        "actual_rows": len(rows),
        "after_image_matches": matches,
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

    mapping = {source: target for _, source, target in entries}
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
    return {
        "path": "madomagi/engine_i18n.tsv",
        "sha256": sha256(ENGINE),
        "bytes": len(raw),
        "encoding": "UTF-8",
        "line_endings": "LF" if b"\r" not in raw else "contains-CR",
        "expected_data_rows": EXPECTED_ENGINE_ROWS,
        "actual_data_rows": len(entries),
        "malformed_lines": malformed,
        "duplicate_source_keys": duplicates,
        "official_audit_rows": len(official),
        "official_mapping_failures": official_failures,
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
        if path.lower().endswith(".css"):
            if kind != "blob" or mode != "100644":
                raise ValueError(f"unexpected baseline CSS tree entry: {record!r}")
            blobs[path] = blob
    return blobs


def verify_css() -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    expected = baseline_css_blobs()
    current_paths = {
        path.relative_to(ROOT).as_posix(): path
        for path in (ROOT / "magica").rglob("*.css")
        if path.is_file()
    }
    missing = sorted(set(expected) - set(current_paths))
    extra = sorted(set(current_paths) - set(expected))
    mismatched: list[dict[str, str]] = []
    for relative in sorted(set(expected) & set(current_paths)):
        current_blob = run_git(
            "hash-object", "--path", relative, str(current_paths[relative]), text=True
        )
        assert isinstance(current_blob, str)
        current_blob = current_blob.strip()
        if current_blob != expected[relative]:
            mismatched.append(
                {
                    "path": relative,
                    "baseline_blob": expected[relative],
                    "current_filtered_blob": current_blob,
                }
            )
    if len(expected) != EXPECTED_CSS_FILES:
        errors.append(
            f"baseline has {len(expected)} CSS files, expected {EXPECTED_CSS_FILES}"
        )
    if missing or extra or mismatched:
        errors.append(
            "CSS differs from Pass18 baseline: "
            f"missing={len(missing)}, extra={len(extra)}, changed={len(mismatched)}"
        )
    return {
        "baseline_commit": BASELINE_COMMIT,
        "expected_files": EXPECTED_CSS_FILES,
        "baseline_files": len(expected),
        "current_files": len(current_paths),
        "missing": missing,
        "extra": extra,
        "mismatched": mismatched,
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
    if baseline_record.get("manifest_sha256") != manifest_sha:
        errors.append("Pass18 manifest SHA-256 differs from the recorded baseline")

    rows, manifest_read_errors = read_manifest()
    errors.extend(manifest_read_errors)
    manifest_result, part_errors = verify_manifest_after_images(rows)
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
        "schema": "magireco-cn-v26-pass18-authority-verification/v1",
        "status": "PASS" if not errors else "FAIL",
        "baseline_commit": BASELINE_COMMIT,
        "manifest": {
            "path": MANIFEST.relative_to(ROOT).as_posix(),
            "sha256": manifest_sha,
            "recorded_sha256": baseline_record.get("manifest_sha256"),
            **manifest_result,
        },
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
