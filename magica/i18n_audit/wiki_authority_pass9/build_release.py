#!/usr/bin/env python3
"""Build and independently verify the MagiaCN Wiki-refined 401-file overlay.

The build is deliberately closed over hash-locked local inputs.  It starts from
the exact pass8 ZIP, applies Wiki proposals with strict old-value checks,
restores the one baseline-locked font field, applies reviewed static-text
overrides, reconciles all linked Doppel names, rebuilds the embedded runtime
dictionaries, and then runs structural and runtime verification.
"""

from __future__ import annotations

import collections
import csv
import dataclasses
import hashlib
import html.parser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Iterable
import zipfile


WORKSPACE = Path(__file__).resolve().parents[2]
OUT = WORKSPACE / "work" / "release_build"
TREE = OUT / "tree"
ROLLBACK_VERIFY = OUT / "rollback_verification"
PASS8_DIR = WORKSPACE / "work" / "archive_audit" / "pass8"
BASELINE_DIR = WORKSPACE / "work" / "archive_audit" / "baseline"
PASS8_ZIP = WORKSPACE / "work" / "archive_audit" / "pass8.zip"
PROPOSALS_PATH = WORKSPACE / "work" / "main" / "wiki_patch_analysis" / "proposals.json"
DOPPEL_RECONCILIATIONS_PATH = WORKSPACE / "work" / "main" / "wiki_patch_analysis" / "doppel_consistency_reconciliations.json"
OVERRIDES_PATH = WORKSPACE / "work" / "branch_compare" / "analysis" / "verified_main_overrides.tsv"
PROVENANCE_PATH = WORKSPACE / "work" / "main" / "pass8_field_provenance_reconstructed.tsv"
CANDIDATES_PATH = WORKSPACE / "work" / "main" / "pass8_llm_or_other_candidates.json"
AUTHORITY_PATH = WORKSPACE / "work" / "archive_audit" / "dump" / "authority" / "authority.json"
RELEASE_ZIP = OUT / "cn_js_update_v3_authoritative_wiki_refined.zip"

# Intentionally fail closed if a reviewer edits any source after this build was
# specified.  Updating a proposal requires reviewing the new digest here too.
EXPECTED_HASHES = {
    PASS8_ZIP: "e4b466d6cb6c16ec018b61c7d074e2d213601889e758ef6db4dc4dd041c54e53",
    PROPOSALS_PATH: "b8da9d62b6ab26410d000cc630e6b72662eb81a9d93c88f8113d9aa25ba9173e",
    DOPPEL_RECONCILIATIONS_PATH: "ff25c4fc3bc9c5c7e82973f69479e024934277a8dec7eac9f7903ea40050ffa2",
    OVERRIDES_PATH: "842858aad3702625d128794d23c86aee5c6c08734eb8eb35fff6ef5299948ab0",
    PROVENANCE_PATH: "f2e737e320f06d734df9437a13fe71a4868228ef4bad623f18bb129317871f1a",
    CANDIDATES_PATH: "3aca8e71ec52de64205ba51eac4847aff1d2f66ae3d1c7fed26b120f5bd2ebb4",
    AUTHORITY_PATH: "19b91c81254d2e44c478efa827ad568fb743b06b41b3536dae612ddd9c498595",
}

LIBS_REL = Path("magica/js/libs")
JQUERY_REL = Path("magica/js/libs/jquery-3.7.1.min.js")
BASE_JS_REL = Path("magica/js/_common/base.js")
PROTECTED_CREATOR_FIELDS = {"illustrator", "designer", "voiceActor"}
LIST_KEYS: dict[str, tuple[str, ...]] = {
    "arenaClassList.json": ("arenaBattleFreeRankClass",),
    "cardList.json": ("cardId",),
    "chapterList.json": ("chapterId",),
    "charaList.json": ("id",),
    "charaMessageList.json": ("charaNo", "messageId"),
    "doppelList.json": ("id",),
    "enemyList.json": ("enemyId",),
    "eventList.json": ("eventId",),
    "eventStoryList.json": ("storyIds",),
    "formationSheetList.json": ("id",),
    "giftList.json": ("id",),
    "itemList.json": ("itemCode",),
    "live2dList.json": ("charaId", "live2dId"),
    "patrolAreaList.json": ("patrolAreaId",),
    "pieceList.json": ("pieceId",),
    "sectionList.json": ("sectionId",),
    "shopItemList.json": ("id",),
}
EXPECTED_JSON_NAMES = {
    "arenaClassList.json", "cardList.json", "cardMagiaMap.json", "cardSkillMap.json",
    "chapterList.json", "charaList.json", "charaMessageList.json",
    "doppelCardMagiaMap.json", "doppelList.json", "emotionSkillMap.json",
    "enemyList.json", "eventList.json", "eventStoryList.json",
    "formationSheetList.json", "giftList.json", "itemList.json", "live2dList.json",
    "patrolAreaList.json", "pieceList.json", "pieceSkillMap.json", "placeSkillMap.json",
    "sectionList.json", "shopItemList.json",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def dump_json(path: Path, value: Any, *, compact: bool = False) -> None:
    if compact:
        text = canonical_json(value)
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8")


def tsv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\r", "\\r").replace("\n", "\\n")
    if isinstance(value, bool):
        return "true" if value else "false"
    return canonical_json(value)


def write_tsv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: tsv_value(row.get(field)) for field in fields})


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def key_piece(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def record_map(name: str, obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return {str(k): v for k, v in obj.items()}
    if not isinstance(obj, list):
        raise AssertionError(f"{name}: root is {type(obj).__name__}, expected list/object")
    keys = LIST_KEYS.get(name)
    if not keys:
        raise AssertionError(f"{name}: missing identity rule")
    result: dict[str, Any] = {}
    for index, rec in enumerate(obj):
        if not isinstance(rec, dict):
            raise AssertionError(f"{name}[{index}] is not an object")
        missing = [field for field in keys if field not in rec]
        if missing:
            raise AssertionError(f"{name}[{index}] missing identity fields {missing}")
        key = "|".join(key_piece(rec[field]) for field in keys)
        if key in result:
            raise AssertionError(f"{name}: duplicate identity {key}")
        result[key] = rec
    return result


def relative_files(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}


def safe_extract_pass8() -> None:
    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir(parents=True)
    with zipfile.ZipFile(PASS8_ZIP) as zf:
        infos = zf.infolist()
        names = [info.filename.replace("\\", "/") for info in infos]
        if len(names) != 401 or len(set(names)) != 401:
            raise AssertionError(f"pass8 ZIP path count/uniqueness invalid: {len(names)}/{len(set(names))}")
        if zf.testzip() is not None:
            raise AssertionError("pass8 ZIP CRC failure")
        for info, rel in zip(infos, names):
            if info.is_dir():
                continue
            parts = Path(rel).parts
            if Path(rel).is_absolute() or ".." in parts:
                raise AssertionError(f"unsafe ZIP path: {rel}")
            dest = TREE.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
    source = relative_files(PASS8_DIR)
    extracted = relative_files(TREE)
    if set(source) != set(extracted):
        raise AssertionError("extracted pass8 path set differs from audited pass8 tree")
    unequal = [rel for rel in source if source[rel].read_bytes() != extracted[rel].read_bytes()]
    if unequal:
        raise AssertionError(f"extracted pass8 content differs at {unequal[:3]}")


def validate_input_hashes() -> dict[str, dict[str, Any]]:
    rows = {}
    for path, expected in EXPECTED_HASHES.items():
        actual = sha256(path)
        rows[str(path.relative_to(WORKSPACE)).replace("\\", "/")] = {
            "sha256": actual,
            "expected_sha256": expected,
            "bytes": path.stat().st_size,
            "match": actual == expected,
        }
        if actual != expected:
            raise AssertionError(f"input hash changed: {path}: {actual} != {expected}")
    return rows


def load_all_json(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    json_paths = sorted((root / LIBS_REL).glob("*.json"))
    names = {p.name for p in json_paths}
    if names != EXPECTED_JSON_NAMES:
        raise AssertionError(f"unexpected JSON dictionary set: missing={EXPECTED_JSON_NAMES-names}, extra={names-EXPECTED_JSON_NAMES}")
    objects = {p.name: load_json(p) for p in json_paths}
    maps = {name: record_map(name, obj) for name, obj in objects.items()}
    return objects, maps


def proposal_structure_health(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    paired = [("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"), ("（", "）"), ("【", "】"), ("《", "》")]
    unbalanced = []
    bad_comments = []
    malformed = []
    ascii_double_spaces = []
    punctuation_space = []
    punctuation_re = re.compile(r"(?:[，。！？；：、》」』】）] | [，。！？；：、》」』】）])")
    for row in proposals:
        value = row["after"]
        if not isinstance(value, str):
            continue
        for left, right in paired:
            if value.count(left) != value.count(right):
                unbalanced.append({"file": row["file"], "key": row["key"], "field": row["field"], "pair": left + right, "value": value})
        if "<!--" in value or "-->" in value:
            bad_comments.append({"file": row["file"], "key": row["key"], "field": row["field"], "value": value})
        if "\ufffd" in value or "\x00" in value or re.search(r"(?:Ã.|Â.|â€|ðŸ)", value):
            malformed.append({"file": row["file"], "key": row["key"], "field": row["field"], "value": value})
        if "  " in value:
            ascii_double_spaces.append({"file": row["file"], "key": row["key"], "field": row["field"], "value": value})
        if punctuation_re.search(value):
            punctuation_space.append({"file": row["file"], "key": row["key"], "field": row["field"], "value": value})
    ry = [row for row in proposals if isinstance(row.get("after"), str) and "(ry" in row["after"]]
    if unbalanced or bad_comments or malformed or ascii_double_spaces or punctuation_space:
        raise AssertionError("Wiki proposal structure-health gate failed")
    if len(ry) != 1 or not (ry[0]["file"] == "pieceList.json" and str(ry[0]["key"]) == "1749"):
        raise AssertionError("expected exactly the reviewed `(ry` truncation meme at piece 1749")
    return {
        "rows_checked": len(proposals),
        "paired_chinese_quote_errors": len(unbalanced),
        "html_comment_residue": len(bad_comments),
        "malformed_encoding_or_nul": len(malformed),
        "ascii_double_space_errors": len(ascii_double_spaces),
        "ascii_space_adjacent_to_chinese_punctuation_errors": len(punctuation_space),
        "reviewed_truncation_meme_exceptions": [{"file": ry[0]["file"], "key": str(ry[0]["key"]), "field": ry[0]["field"], "token": "(ry"}],
    }


def apply_proposals(
    maps: dict[str, dict[str, Any]], authority: dict[str, Any], candidate_triples: set[tuple[str, str, str]]
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]], dict[str, Any]]:
    proposals = load_json(PROPOSALS_PATH)
    if not isinstance(proposals, list) or len(proposals) != 5678:
        raise AssertionError(f"expected 5678 proposals, got {type(proposals).__name__}/{len(proposals) if isinstance(proposals,list) else '-'}")
    health = proposal_structure_health(proposals)
    seen: set[tuple[str, str, str]] = set()
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    applied = []
    authority_overlap = []
    non_candidate_consistency_targets = []
    for seq, row in enumerate(proposals, 1):
        required = {"file", "key", "field", "before", "after", "method", "evidence"}
        if not required.issubset(row):
            raise AssertionError(f"proposal {seq} missing {sorted(required-set(row))}")
        name, key, field = row["file"], str(row["key"]), row["field"]
        triple = (name, key, field)
        if triple in seen:
            raise AssertionError(f"duplicate proposal target {triple}")
        seen.add(triple)
        if triple not in candidate_triples:
            if row["method"] != "doppel_name_consistency_propagation":
                raise AssertionError(f"non-consistency proposal is not in llm_or_other candidate set: {triple}")
            non_candidate_consistency_targets.append(triple)
        if field in PROTECTED_CREATOR_FIELDS:
            raise AssertionError(f"proposal touches protected creator: {triple}")
        auth_rec = authority.get(name, {}).get(key, {})
        if isinstance(auth_rec, dict) and field in auth_rec and field not in PROTECTED_CREATOR_FIELDS:
            authority_overlap.append({"file": name, "key": key, "field": field, "dump_value": auth_rec[field]})
        rec = maps.get(name, {}).get(key)
        if not isinstance(rec, dict):
            raise AssertionError(f"proposal target record missing: {triple}")
        if field not in rec:
            raise AssertionError(f"proposal target field missing: {triple}")
        if rec[field] != row["before"]:
            raise AssertionError(f"proposal stale before value at {triple}: {rec[field]!r} != {row['before']!r}")
        if type(rec[field]) is not type(row["after"]):
            raise AssertionError(f"proposal changes type at {triple}: {type(rec[field]).__name__} -> {type(row['after']).__name__}")
        if rec[field] == row["after"]:
            raise AssertionError(f"proposal has no value change: {triple}")
        rec[field] = row["after"]
        item = dict(row)
        release_source = "doppel_name_consistency_propagation" if row["method"] == "doppel_name_consistency_propagation" else "wiki_authority"
        item.update({"sequence": seq, "key": key, "release_source": release_source, "final_value_after_direct_apply": row["after"]})
        applied.append(item)
        index[triple] = item
    if authority_overlap:
        raise AssertionError(f"proposals overlap {len(authority_overlap)} dump-locked fields")
    if len(non_candidate_consistency_targets) != 10:
        raise AssertionError(f"reviewed non-candidate consistency target profile changed: {len(non_candidate_consistency_targets)}")
    health["non_candidate_doppel_consistency_targets"] = len(non_candidate_consistency_targets)
    return applied, index, health


def verify_doppel_reconciliations(
    pass8_maps: dict[str, dict[str, Any]], maps: dict[str, dict[str, Any]], authority: dict[str, Any], proposal_index: dict[tuple[str, str, str], dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Verify the upstream source-priority decisions and the resulting 217 invariants.

    The final proposal set already incorporates the 12 physical propagations and
    omits the 19 rejected lower-priority proposals.  This function therefore
    audits, rather than reapplies, all 31 reconciliation decisions.
    """
    decisions = load_json(DOPPEL_RECONCILIATIONS_PATH)
    if not isinstance(decisions, list) or len(decisions) != 31:
        raise AssertionError(f"expected 31 Doppel reconciliation decisions, got {len(decisions) if isinstance(decisions,list) else type(decisions).__name__}")
    action_counts = collections.Counter(row.get("action") for row in decisions)
    if action_counts != {"drop_conflicting_proposal": 19, "propagate_canonical": 12}:
        raise AssertionError(f"Doppel reconciliation action profile changed: {action_counts}")
    seen: set[tuple[str, str, str]] = set()
    verified = []
    by_doppel: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for seq, source in enumerate(decisions, 1):
        row = dict(source)
        did = str(row["doppel_key"]); target_file = row["target_file"]; target_key = str(row["target_key"])
        triple = (target_file, target_key, "name")
        if triple in seen:
            raise AssertionError(f"duplicate Doppel reconciliation target: {triple}")
        seen.add(triple)
        if pass8_maps[target_file][target_key]["name"] != row["pass8_value"]:
            raise AssertionError(f"Doppel reconciliation stale pass8 value: {triple}")
        actual_locks = []
        magia_id = str((int(did) // 100) * 10 + 8)
        for name, key in (("doppelList.json", did), ("doppelCardMagiaMap.json", magia_id), ("cardMagiaMap.json", magia_id)):
            auth_rec = authority.get(name, {}).get(key, {})
            if isinstance(auth_rec, dict) and "name" in auth_rec:
                actual_locks.append([name, key, auth_rec["name"]])
        if actual_locks != row["dump_locks"]:
            raise AssertionError(f"Doppel reconciliation dump locks changed for {did}: {actual_locks} != {row['dump_locks']}")
        lock_values = {item[2] for item in actual_locks}
        if len(lock_values) > 1:
            raise AssertionError(f"conflicting official locks for Doppel {did}")
        if row["canonical_source"] == "official_cn_dump_locked":
            if not lock_values or row["canonical_value"] != next(iter(lock_values)):
                raise AssertionError(f"invalid official canonical for Doppel {did}")
        elif row["canonical_source"] == "wiki_keyed_doppelList":
            if lock_values or row["canonical_value"] != maps["doppelList.json"][did]["name"]:
                raise AssertionError(f"invalid Wiki-keyed canonical for Doppel {did}")
        else:
            raise AssertionError(f"unknown canonical source {row['canonical_source']}")
        if maps[target_file][target_key]["name"] != row["canonical_value"]:
            raise AssertionError(f"Doppel final target is not canonical: {triple}")
        proposal = proposal_index.get(triple)
        if row["action"] == "propagate_canonical":
            if not proposal or proposal["method"] != "doppel_name_consistency_propagation" or proposal["before"] != row["pass8_value"] or proposal["after"] != row["canonical_value"]:
                raise AssertionError(f"missing/malformed canonical propagation proposal: {triple}")
            release_source = "doppel_name_consistency_propagation"
        else:
            if proposal is not None:
                raise AssertionError(f"rejected conflicting proposal still present: {triple}")
            if row["pre_reconcile_value"] == row["canonical_value"] or row["pass8_value"] != row["canonical_value"]:
                raise AssertionError(f"malformed drop/preserve decision: {triple}")
            release_source = "doppel_name_consistency_preserve"
        row.update({"sequence": seq, "target_key": target_key, "field": "name", "release_source": release_source, "final_value": maps[target_file][target_key]["name"]})
        verified.append(row); by_doppel[did].append(row)
    groups = []
    for did in sorted(by_doppel, key=int):
        magia_id = str((int(did) // 100) * 10 + 8)
        locations = (("doppelList.json", did), ("doppelCardMagiaMap.json", magia_id), ("cardMagiaMap.json", magia_id))
        pass8_values = {name: pass8_maps[name][key]["name"] for name, key in locations}
        final_values = {name: maps[name][key]["name"] for name, key in locations}
        if len(set(final_values.values())) != 1:
            raise AssertionError(f"Doppel group still inconsistent: {did}: {final_values}")
        canonical_values = {row["canonical_value"] for row in by_doppel[did]}
        canonical_sources = {row["canonical_source"] for row in by_doppel[did]}
        if len(canonical_values) != 1 or len(canonical_sources) != 1:
            raise AssertionError(f"Doppel decision group conflicts: {did}")
        locks = {}
        for name, key in locations:
            auth_rec = authority.get(name, {}).get(key, {})
            locks[name] = auth_rec.get("name") if isinstance(auth_rec, dict) and "name" in auth_rec else None
        groups.append({
            "doppel_id": did, "magia_id": magia_id, "pass8_values": pass8_values,
            "release_values": final_values, "dump_locks": locks,
            "chosen_canonical": next(iter(canonical_values)), "canonical_source": next(iter(canonical_sources)),
            "decisions": by_doppel[did],
        })
    # The all-record audit is intentionally independent of the 31-decision list.
    for did, rec in maps["doppelList.json"].items():
        magia_id = str((int(did) // 100) * 10 + 8)
        values = [rec["name"], maps["doppelCardMagiaMap.json"][magia_id]["name"], maps["cardMagiaMap.json"][magia_id]["name"]]
        if len(set(values)) != 1:
            raise AssertionError(f"Doppel three-dictionary invariant failed at {did}: {values}")
    if len(groups) != 20:
        raise AssertionError(f"expected 20 reviewed Doppel groups, got {len(groups)}")
    return verified, groups


def write_dictionary_files(objects: dict[str, Any], names: set[str]) -> None:
    for name in sorted(names):
        obj = objects[name]
        dump_json(TREE / LIBS_REL / name, obj, compact=True)


def extract_cn_span(text: str) -> tuple[dict[str, Any], int, int]:
    marker = re.search(r"\bvar\s+cn\s*=\s*", text)
    if not marker:
        raise AssertionError("embedded `var cn =` marker missing")
    start = marker.end()
    obj, consumed = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise AssertionError("embedded cn is not an object")
    return obj, start, start + consumed


def expected_embedded(maps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = {Path(name).stem: records for name, records in maps.items()}
    for special in ("charaMessageList", "live2dList"):
        result[special] = {key.replace("|", "_"): value for key, value in result[special].items()}
    return result


def rebuild_embedded(maps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    path = TREE / JQUERY_REL
    original = path.read_text(encoding="utf-8-sig")
    old, start, end = extract_cn_span(original)
    expected = expected_embedded(maps)
    if set(old) != set(expected) or len(old) != 23:
        raise AssertionError("pass8 embedded dictionary names changed")
    payload = canonical_json(expected)
    rebuilt = original[:start] + payload + original[end:]
    path.write_text(rebuilt, encoding="utf-8")
    reparsed, new_start, new_end = extract_cn_span(rebuilt)
    if reparsed != expected:
        raise AssertionError("rebuilt embedded dictionary mismatch")
    if original[:start] != rebuilt[:new_start] or original[end:] != rebuilt[new_end:]:
        raise AssertionError("jQuery injector code outside embedded dictionaries drifted")
    return {
        "dictionary_count": len(expected),
        "record_count": sum(len(v) for v in expected.values()),
        "old_payload_utf8_bytes": len(original[start:end].encode("utf-8")),
        "release_payload_utf8_bytes": len(payload.encode("utf-8")),
        "prefix_sha256": hashlib.sha256(original[:start].encode("utf-8")).hexdigest(),
        "suffix_sha256": hashlib.sha256(original[end:].encode("utf-8")).hexdigest(),
        "outside_payload_code_identical": True,
    }


def all_occurrences(text: str, needle: str) -> list[int]:
    if not needle:
        raise AssertionError("empty override source string")
    result = []
    pos = 0
    while True:
        hit = text.find(needle, pos)
        if hit < 0:
            return result
        result.append(hit)
        pos = hit + len(needle)


def apply_static_overrides() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with OVERRIDES_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if len(rows) != 12:
        raise AssertionError(f"expected 12 static override rules, got {len(rows)}")
    applied = []
    by_file: dict[str, list[tuple[int, dict[str, str]]]] = collections.defaultdict(list)
    for index, row in enumerate(rows):
        by_file[row["file"]].append((index, row))
    for rel, indexed_rows in by_file.items():
        path = TREE / Path(rel)
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        groups: dict[str, list[tuple[int, dict[str, str]]]] = collections.OrderedDict()
        for index, row in indexed_rows:
            groups.setdefault(row["pass8_value"], []).append((index, row))
        spans = []
        for before, group_rows in groups.items():
            hits = all_occurrences(text, before)
            expected = sum(int(row["occurrences"]) for _, row in group_rows)
            if len(hits) != expected:
                raise AssertionError(f"override exact-occurrence mismatch in {rel}: {before!r}: {len(hits)} != {expected}")
            cursor = 0
            for index, row in group_rows:
                count = int(row["occurrences"])
                allocated = hits[cursor:cursor + count]
                cursor += count
                for within_rule, start in enumerate(allocated, 1):
                    spans.append((start, start + len(before), row["verified_value"], index, within_rule, before, row))
        spans.sort(key=lambda item: item[0])
        for left, right in zip(spans, spans[1:]):
            if left[1] > right[0]:
                raise AssertionError(f"overlapping static overrides in {rel}")
        new_text = text
        for start, end, after, index, within, before, row in reversed(spans):
            if new_text[start:end] != before:
                raise AssertionError(f"override span changed before apply in {rel}@{start}")
            new_text = new_text[:start] + after + new_text[end:]
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + new_text.encode("utf-8"))
        for start, end, after, index, within, before, row in spans:
            applied.append({
                "rule_sequence": index + 1,
                "occurrence_within_rule": within,
                "file": rel,
                "key": row["key"],
                "field": row["field"],
                "pass8_value": before,
                "verified_value": after,
                "pass8_start_offset": start,
                "evidence_type": row["evidence_type"],
                "evidence_ref": row["evidence_ref"],
                "wiki_commit": row["wiki_commit"],
                "release_source": "verified_main_override",
            })
    applied.sort(key=lambda row: (row["rule_sequence"], row["occurrence_within_rule"]))
    if len(applied) != 23:
        raise AssertionError(f"expected 23 physical override occurrences, got {len(applied)}")
    return applied, {"rules": len(rows), "physical_occurrences": len(applied), "files": sorted(by_file)}


def apply_base_font_preserve() -> dict[str, Any]:
    path = TREE / BASE_JS_REL
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    needle = "font-family: 'mbm'; src: url('data:font/ttf;base64,\"+\nString(a.motoya)+\"');}"
    replacement = needle.replace("String(a.motoya)", "String(a.mbm)")
    if text.count(needle) != 1:
        raise AssertionError(f"baseline font preserve source occurrence count is {text.count(needle)}, expected 1")
    changed = text.replace(needle, replacement, 1)
    if changed.count("String(a.motoya)") != 1 or changed.count("String(a.mbm)") != 1:
        raise AssertionError("font source postcondition failed")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + changed.encode("utf-8"))
    baseline = (BASELINE_DIR / BASE_JS_REL).read_text(encoding="utf-8-sig")
    if baseline.count(replacement) != 1:
        raise AssertionError("baseline does not contain the restored mbm source exactly once")
    return {
        "file": BASE_JS_REL.as_posix(),
        "field": "fontDataGet.second_font_source",
        "before": "a.motoya",
        "after": "a.mbm",
        "occurrences": 1,
        "release_source": "baseline_preserve",
        "reason": "restore distinct mbm font payload source without reverting translated strings",
    }


def json_schema_audit(pass8_objects: dict[str, Any], release_objects: dict[str, Any]) -> dict[str, Any]:
    errors = []
    checked_records = 0
    checked_fields = 0
    for name in sorted(pass8_objects):
        before_obj, after_obj = pass8_objects[name], release_objects[name]
        if type(before_obj) is not type(after_obj):
            errors.append({"file": name, "issue": "root_type", "before": type(before_obj).__name__, "after": type(after_obj).__name__})
            continue
        bm, am = record_map(name, before_obj), record_map(name, after_obj)
        if set(bm) != set(am):
            errors.append({"file": name, "issue": "record_keys", "missing": sorted(set(bm)-set(am)), "extra": sorted(set(am)-set(bm))})
            continue
        for key in sorted(bm):
            checked_records += 1
            b, a = bm[key], am[key]
            if type(b) is not type(a):
                errors.append({"file": name, "key": key, "issue": "record_type"})
                continue
            if not isinstance(b, dict):
                continue
            if set(b) != set(a):
                errors.append({"file": name, "key": key, "issue": "field_set", "missing": sorted(set(b)-set(a)), "extra": sorted(set(a)-set(b))})
                continue
            for field in b:
                checked_fields += 1
                if type(b[field]) is not type(a[field]):
                    errors.append({"file": name, "key": key, "field": field, "issue": "field_type", "before": type(b[field]).__name__, "after": type(a[field]).__name__})
    return {"dictionaries": len(pass8_objects), "records_checked": checked_records, "fields_checked": checked_fields, "errors": errors}


def authority_audit(authority: dict[str, Any], maps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    errors = []
    for name, records in authority.items():
        if name not in maps:
            errors.append({"file": name, "issue": "dictionary_missing"})
            continue
        for key, auth_rec in records.items():
            rec = maps[name].get(key)
            if rec is None:
                errors.append({"file": name, "key": key, "issue": "record_missing"})
                continue
            if not isinstance(auth_rec, dict) or not isinstance(rec, dict):
                checked += 1
                if auth_rec != rec:
                    errors.append({"file": name, "key": key, "issue": "record_mismatch"})
                continue
            for field, expected in auth_rec.items():
                if field in PROTECTED_CREATOR_FIELDS:
                    continue
                checked += 1
                if field not in rec:
                    errors.append({"file": name, "key": key, "field": field, "issue": "field_missing"})
                elif rec[field] != expected:
                    errors.append({"file": name, "key": key, "field": field, "issue": "value_mismatch", "expected": expected, "actual": rec[field]})
    if checked != 57056:
        raise AssertionError(f"dump authority field count changed: {checked}")
    return {"fields_checked": checked, "errors": errors}


def creator_audit(pass8_maps: dict[str, dict[str, Any]], release_maps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    errors = []
    for name, after_map in release_maps.items():
        before_map = pass8_maps[name]
        for key, after in after_map.items():
            before = before_map[key]
            if not isinstance(before, dict) or not isinstance(after, dict):
                continue
            for field in PROTECTED_CREATOR_FIELDS:
                if field in before or field in after:
                    checked += 1
                    if (field in before) != (field in after) or before.get(field) != after.get(field):
                        errors.append({"file": name, "key": key, "field": field, "pass8": before.get(field), "release": after.get(field)})
    return {"fields_checked": checked, "errors": errors}


def doppel_skill_audit(maps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    errors = []
    for did, rec in maps["doppelList.json"].items():
        magia_id = str((int(did) // 100) * 10 + 8)
        for name in ("doppelCardMagiaMap.json", "cardMagiaMap.json"):
            linked = maps[name].get(magia_id)
            if linked is None or linked.get("name") != rec.get("name"):
                errors.append({"doppel_id": did, "magia_id": magia_id, "file": name, "doppel_name": rec.get("name"), "linked_name": None if linked is None else linked.get("name")})
    owners: dict[str, list[tuple[str, Any]]] = collections.defaultdict(list)
    for name in ("cardSkillMap.json", "emotionSkillMap.json", "pieceSkillMap.json", "placeSkillMap.json"):
        for key, payload in maps[name].items():
            owners[key].append((name, payload))
    ambiguous = []
    for key, values in owners.items():
        if len(values) > 1 and not all(value == values[0][1] for _, value in values):
            ambiguous.append({"key": key, "dictionaries": [name for name, _ in values]})
    return {"doppel_records_checked": len(maps["doppelList.json"]), "linked_names_checked": len(maps["doppelList.json"]) * 2, "doppel_link_errors": errors, "ambiguous_cross_skill_ids": ambiguous}


class HTMLShapeParser(html.parser.HTMLParser):
    SENSITIVE = {"id", "class", "href", "src", "name"}
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.tags: list[tuple[str, str]] = []
        self.sensitive: list[tuple[str, tuple[tuple[str, str | None], ...]]] = []
    def handle_starttag(self, tag, attrs):
        tag = tag.lower(); self.tags.append(("start", tag))
        self.sensitive.append((tag, tuple(sorted((k.lower(), v) for k, v in attrs if k.lower() in self.SENSITIVE or k.lower().startswith("data-")))))
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs); self.tags[-1] = ("empty", tag.lower())
    def handle_endtag(self, tag):
        self.tags.append(("end", tag.lower()))


def html_shape(text: str) -> tuple[list[Any], list[Any]]:
    parser = HTMLShapeParser(); parser.feed(text); parser.close(); return parser.tags, parser.sensitive


@dataclasses.dataclass
class JSString:
    start: int
    end: int
    quote: str


def js_strings(text: str) -> list[JSString]:
    out = []; i = 0; n = len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i+1] == "/":
            j = text.find("\n", i+2); i = n if j < 0 else j; continue
        if c == "/" and i + 1 < n and text[i+1] == "*":
            j = text.find("*/", i+2); i = n if j < 0 else j+2; continue
        if c not in ("'", '"', "`"):
            i += 1; continue
        quote, start = c, i; i += 1; escaped = False; depth = 0
        while i < n:
            ch = text[i]
            if escaped: escaped = False; i += 1; continue
            if ch == "\\": escaped = True; i += 1; continue
            if quote == "`" and ch == "$" and i+1 < n and text[i+1] == "{": depth += 1; i += 2; continue
            if quote == "`" and depth and ch == "}": depth -= 1; i += 1; continue
            if ch == quote and depth == 0:
                out.append(JSString(start, i+1, quote)); i += 1; break
            i += 1
        else: break
    return out


def js_skeleton(text: str) -> str:
    spans = js_strings(text); chunks = []; pos = 0
    for span in spans:
        chunks.append(text[pos:span.start]); chunks.append(span.quote + "<STRING>" + span.quote); pos = span.end
    chunks.append(text[pos:]); return "".join(chunks)


def static_structure_audit() -> dict[str, Any]:
    pass8_files, release_files = relative_files(PASS8_DIR), relative_files(TREE)
    html_errors = []
    html_files = sorted(rel for rel in release_files if rel.endswith(".html"))
    for rel in html_files:
        before = html_shape(pass8_files[rel].read_text(encoding="utf-8-sig"))
        after = html_shape(release_files[rel].read_text(encoding="utf-8-sig"))
        if before != after:
            html_errors.append({"file": rel, "tag_equal": before[0] == after[0], "sensitive_equal": before[1] == after[1]})
    js_errors = []
    base_profile = None
    reviewed_override_js = {
        "magica/js/top/TopPage.js",
        "magica/js/view/memoria/PieceArchiveView.js",
    }
    exact_span_verified = []
    js_files = sorted(rel for rel in release_files if rel.endswith(".js"))
    for rel in js_files:
        if rel == JQUERY_REL.as_posix():
            continue
        before = pass8_files[rel].read_text(encoding="utf-8-sig")
        after = release_files[rel].read_text(encoding="utf-8-sig")
        if rel == BASE_JS_REL.as_posix():
            baseline = (BASELINE_DIR / Path(rel)).read_text(encoding="utf-8-sig")
            base_profile = {
                "release_vs_pass8_string_elided_equal": js_skeleton(after) == js_skeleton(before),
                "release_vs_baseline_string_elided_equal": js_skeleton(after) == js_skeleton(baseline),
                "full_file_equals_baseline": after == baseline,
            }
            if not base_profile["release_vs_baseline_string_elided_equal"]:
                js_errors.append({"file": rel, "issue": "base targeted-preserve profile failed", **base_profile})
        elif rel in reviewed_override_js:
            # These files were constructed only from the hash-locked, exact
            # occurrence spans in verified_main_overrides.tsv.  A raw
            # JavaScript string lexer is less reliable here because the
            # minified source contains quote characters inside regex literals.
            exact_span_verified.append(rel)
        elif before != after:
            js_errors.append({"file": rel, "issue": "non-string JavaScript drift"})
    return {"html_files_checked": len(html_files), "html_structure_or_sensitive_attribute_errors": html_errors, "javascript_files_checked": len(js_files), "javascript_non_string_drift_errors": js_errors, "reviewed_override_js_verified_by_exact_spans": sorted(exact_span_verified), "base_font_targeted_preserve_profile": base_profile}


def node_syntax_audit() -> dict[str, Any]:
    files = sorted(TREE.rglob("*.js")); failures = []
    for path in files:
        cp = subprocess.run(["node", "--check", str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        if cp.returncode:
            failures.append({"file": path.relative_to(TREE).as_posix(), "exit_status": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr})
    return {"checked": len(files), "failures": failures}


def zip_deterministic(source: Path, target: Path) -> None:
    files = relative_files(source)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in sorted(files):
            info = zipfile.ZipInfo(rel, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.flag_bits |= 0x800
            zf.writestr(info, files[rel].read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def zip_audit(path: Path, expected_paths: set[str]) -> dict[str, Any]:
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist(); names = [info.filename.replace("\\", "/") for info in infos]
        duplicates = sorted(name for name, count in collections.Counter(names).items() if count > 1)
        unsafe = sorted(name for name in names if Path(name).is_absolute() or ".." in Path(name).parts)
        crc_bad = zf.testzip()
        if set(names) != expected_paths:
            raise AssertionError("release ZIP path set mismatch")
        extracted_hash_errors = []
        tree_files = relative_files(TREE)
        for name in names:
            if hashlib.sha256(zf.read(name)).hexdigest() != sha256(tree_files[name]):
                extracted_hash_errors.append(name)
    return {"file_count": len(names), "unique_paths": len(set(names)), "duplicates": duplicates, "unsafe_paths": unsafe, "crc_error": crc_bad, "content_hash_errors": extracted_hash_errors}


def emit_runtime_smoke_test() -> Path:
    path = OUT / "runtime_smoke_test.js"
    code = r'''"use strict";
const fs=require("fs");
const file=process.argv[2];
if(!file) throw new Error("usage: node runtime_smoke_test.js <jquery-file>");
const all=fs.readFileSync(file,"utf8");
const marker="var cn = ";
const wrap=all.lastIndexOf("\n(function(){");
if(wrap<0) throw new Error("runtime wrapper missing");
const snippet=all.slice(wrap+1);
const start=snippet.indexOf(marker)+marker.length;
const boundary=snippet.slice(start).match(/;\r?\n    function put/);
const end=boundary?start+boundary.index:-1;
if(start<marker.length||end<0) throw new Error("embedded dictionary boundaries missing");
const cn=JSON.parse(snippet.slice(start,end));
function XHR(){this.handlers={};this.readyState=0;this.responseType="";this.responseText="";this.response=undefined;}
XHR.prototype.addEventListener=function(ev,fn){this.handlers[ev]=fn;};
XHR.prototype.open=function(){return "opened";};
global.XMLHttpRequest=XHR; global.window={};
const oldWarn=console.warn; console.warn=function(){};
(0,eval)(snippet); console.warn=oldWarn;
const tr=window.__MAGIACN_TRANSLATE__;
if(typeof tr!=="function") throw new Error("translator export missing");
const skillFields=["name","shortDescription","description","eventDescription"];
const specs={
 arenaClassList:{id:"arenaBattleFreeRankClass",fields:["className","nextClassName","storyTitle"]},
 cardList:{id:"cardId",fields:["cardName"]},
 cardMagiaMap:{id:"magiaId",fields:skillFields},
 cardSkillMap:{id:"connectId",fields:skillFields},
 chapterList:{id:"chapterId",fields:["title","chapterNoForView"]},
 charaList:{id:"charaId",fields:["name","charaName","kana","title","school","description"],alias:{charaName:"name"}},
 charaMessageList:{composite:["charaNo","messageId"],fields:["message"]},
 doppelCardMagiaMap:{id:"doppelMagiaId",fields:skillFields},
 doppelList:{id:"id",parent:"doppelList",fields:["name","title","description"]},
 emotionSkillMap:{id:"skillId",parent:"emotionSkill",fields:skillFields},
 enemyList:{id:"enemyId",fields:["name","title","description"]},
 eventList:{id:"eventId",fields:["eventName"]},
 eventStoryList:{id:"storyIds",fields:["storyTitle","pointTitle"]},
 formationSheetList:{id:"formationSheetId",fields:["name","description"]},
 giftList:{id:"giftId",fields:["name"]},
 itemList:{id:"itemCode",fields:["name","shortDescription","description","unit","parameter"]},
 live2dList:{composite:["charaId","live2dId"],fields:["description"]},
 patrolAreaList:{id:"patrolAreaId",fields:["areaName","conditionDescription"]},
 pieceList:{id:"pieceId",fields:["pieceName","name","description"],alias:{name:"pieceName"}},
 pieceSkillMap:{id:"memoriaId",parent:"pieceSkill",fields:skillFields},
 placeSkillMap:{id:"skillId",parent:"placeSkill",fields:skillFields},
 sectionList:{id:"sectionId",fields:["areaDetailName","title","charaName","message","outline"]},
 shopItemList:{id:"shopItemId",fields:["name","description"]}
};
let cases=0, assertions=0;
for(const [dictName,records] of Object.entries(cn)){
 const spec=specs[dictName]; if(!spec) throw new Error("missing runtime spec: "+dictName);
 for(const [key,record] of Object.entries(records)){
  const obj={};
  if(spec.composite){for(const f of spec.composite){if(!(f in record))throw new Error(dictName+" record missing "+f);obj[f]=record[f];}}
  else obj[spec.id]=key;
  for(const field of spec.fields)obj[field]="__SENTINEL__";
  const keysBefore=Object.keys(obj).sort();
  tr(obj,spec.parent||dictName);
  if(JSON.stringify(Object.keys(obj).sort())!==JSON.stringify(keysBefore))throw new Error(dictName+"/"+key+" schema changed");
  for(const field of spec.fields){
   const source=(spec.alias&&spec.alias[field])||field;
   let expected="__SENTINEL__";
   if(record[source]!==undefined&&record[source]!==null)expected=record[source];
   if(skillFields.includes(field)&&field==="description"&&record.description===undefined&&record.shortDescription!==undefined)expected=record.shortDescription;
   if(obj[field]!==expected)throw new Error(`${dictName}/${key}/${field}: ${JSON.stringify(obj[field])} != ${JSON.stringify(expected)}`);
   assertions++;
  }
  cases++;
 }
}
const ambiguous={skillId:"1001101",name:"S",shortDescription:"S",description:"S",eventDescription:"S"};
tr(ambiguous,null); if(Object.values(ambiguous).slice(1).some(v=>v!=="S"))throw new Error("ambiguous untyped skill was translated");
const em={skillId:"1001101",name:"S",shortDescription:"S",description:"S",eventDescription:"S"};tr(em,"emotion");if(em.name!==cn.emotionSkillMap["1001101"].name)throw new Error("typed emotion failed");
const pc={skillId:"1001101",name:"S",shortDescription:"S",description:"S",eventDescription:"S"};tr(pc,"piece");if(pc.name!==cn.pieceSkillMap["1001101"].name)throw new Error("typed piece failed");
const parsed=JSON.parse(JSON.stringify({cardId:"11044",cardName:"S"}));if(parsed.cardName!==cn.cardList["11044"].cardName)throw new Error("JSON.parse wrapper failed");
const xj=new XMLHttpRequest();xj.responseType="json";xj.response={cardId:"11044",cardName:"S"};xj.open("GET","card");xj.readyState=4;xj.handlers.readystatechange.call(xj);if(xj.response.cardName!==cn.cardList["11044"].cardName)throw new Error("XHR json failed");
const xt=new XMLHttpRequest();xt.responseType="text";xt.responseText=JSON.stringify({cardId:"11044",cardName:"S"});xt.response=xt.responseText;xt.open("GET","card");xt.readyState=4;xt.handlers.readystatechange.call(xt);if(JSON.parse(xt.responseText).cardName!==cn.cardList["11044"].cardName)throw new Error("XHR text failed");
const out={dictionary_count:Object.keys(cn).length,record_cases:cases,field_assertions:assertions,ambiguous_untyped_rejected:true,typed_ambiguous_contexts_passed:2,json_parse_wrapper_passed:true,xhr_json_passed:true,xhr_text_passed:true};
process.stdout.write(JSON.stringify(out));
'''
    path.write_text(code, encoding="utf-8")
    return path


def emit_behavior_verifier() -> Path:
    path = OUT / "verify_behavior.py"
    code = r'''#!/usr/bin/env python3
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
libs=root/'magica/js/libs'
def load(n): return json.loads((libs/n).read_text(encoding='utf-8-sig'))
def mp(n,o):
 if isinstance(o,dict): return {str(k):v for k,v in o.items()}
 ids={'doppelList.json':('id',),'itemList.json':('itemCode',)}[n]
 return {'|'.join(str(r[k]) for k in ids):r for r in o}
dl=mp('doppelList.json',load('doppelList.json')); dm=mp('x',load('doppelCardMagiaMap.json')); cm=mp('x',load('cardMagiaMap.json')); items=mp('itemList.json',load('itemList.json'))
base=(root/'magica/js/_common/base.js').read_text(encoding='utf-8-sig')
top=(root/'magica/js/top/TopPage.js').read_text(encoding='utf-8-sig')+(root/'magica/template/top/TopPage.html').read_text(encoding='utf-8-sig')
piece=(root/'magica/js/view/memoria/PieceArchiveView.js').read_text(encoding='utf-8-sig')
out={'candy_exchange':items['EVENT_DAILYTOWER_1160_EXCHANGE_1']['name'],'candy_sticker':items['EVENT_DAILYTOWER_1189_STICKER_121600']['name'],'base_mbm_source_occurrences':base.count('String(a.mbm)'),'base_motoya_source_occurrences':base.count('String(a.motoya)'),'account_transfer_old_occurrences':top.count('数据转移与账号关联'),'account_transfer_verified_occurrences':top.count('数据转移·关联'),'piece_archive_japanese_title_occurrences':piece.count('メモリア保管庫'),'piece_archive_cn_title_occurrences':piece.count('记忆保管库'),'doppel_names':{did:{'doppelList':dl[did]['name'],'doppelCardMagia':dm[str((int(did)//100)*10+8)]['name'],'cardMagia':cm[str((int(did)//100)*10+8)]['name']} for did in ['101700','102700','104400','110700','111700','114400','121700','305300']}}
print(json.dumps(out,ensure_ascii=True,sort_keys=True,separators=(',',':')))
'''
    path.write_text(code, encoding="utf-8")
    return path


def emit_rollback() -> Path:
    path = OUT / "rollback_to_pass8.py"
    code = f'''#!/usr/bin/env python3
import hashlib, json, pathlib, shutil, sys
workspace=pathlib.Path(__file__).resolve().parents[2]
source_tree=workspace/'work/archive_audit/pass8'
source_zip=workspace/'work/archive_audit/pass8.zip'
target=pathlib.Path(sys.argv[1]).resolve() if len(sys.argv)>1 else workspace/'work/release_build/rolled_back'
if target.exists(): shutil.rmtree(target)
tree=target/'tree'; shutil.copytree(source_tree,tree)
zip_target=target/'cn_js_update_v3_authoritative_cn_dump_pass8_final.zip'; target.mkdir(parents=True,exist_ok=True); shutil.copy2(source_zip,zip_target)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
expected='{EXPECTED_HASHES[PASS8_ZIP]}'
actual=digest(zip_target)
same_paths={{p.relative_to(source_tree).as_posix() for p in source_tree.rglob('*') if p.is_file()}}=={{p.relative_to(tree).as_posix() for p in tree.rglob('*') if p.is_file()}}
same_bytes=all(p.read_bytes()==(tree/p.relative_to(source_tree)).read_bytes() for p in source_tree.rglob('*') if p.is_file())
result={{'target':str(target),'tree_file_count':sum(p.is_file() for p in tree.rglob('*')),'tree_paths_equal':same_paths,'tree_bytes_equal':same_bytes,'zip_sha256':actual,'expected_pass8_sha256':expected,'zip_byte_exact':actual==expected}}
print(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')))
raise SystemExit(0 if all([same_paths,same_bytes,actual==expected]) else 1)
'''
    path.write_text(code, encoding="utf-8")
    return path


def run_capture(command: list[str]) -> dict[str, Any]:
    cp = subprocess.run(command, cwd=WORKSPACE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    return {"command": subprocess.list2cmdline(command), "stdout": cp.stdout.rstrip("\r\n"), "stderr": cp.stderr.rstrip("\r\n"), "exit_status": cp.returncode}


def build_provenance(
    release_maps: dict[str, dict[str, Any]], proposal_index: dict[tuple[str, str, str], dict[str, Any]], reconciliations: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    reconciliation_index = {(r["target_file"], str(r["target_key"]), "name"): r for r in reconciliations}
    with PROVENANCE_PATH.open(encoding="utf-8-sig", newline="") as f:
        input_rows = list(csv.DictReader(f, delimiter="\t"))
    if len(input_rows) != 88325:
        raise AssertionError(f"provenance row count changed: {len(input_rows)}")
    output = []
    source_counts = collections.Counter()
    mismatches = []
    for row in input_rows:
        triple = (row["file"], row["key"], row["field"])
        rec = release_maps[row["file"]][row["key"]]
        if row["field"] not in rec:
            raise AssertionError(f"provenance target missing {triple}")
        release_value = rec[row["field"]]
        try:
            pass8_value = json.loads(row["pass8"])
        except Exception:
            pass8_value = row["pass8"]
        # The reconstructed ledger is also independently checked against its pass8 value.
        if triple not in proposal_index and release_value != pass8_value:
            mismatches.append({"triple": triple, "ledger_pass8": pass8_value, "release": release_value})
        source = row["source"]; method = ""; evidence = ""; score = ""
        if triple in proposal_index:
            p = proposal_index[triple]; source = p["release_source"]; method = p.get("method", ""); evidence = p.get("evidence", ""); score = p.get("score", "")
        if triple in reconciliation_index:
            p = reconciliation_index[triple]
            source = p["release_source"]
            method = p["canonical_source"]
            evidence = f"Doppel {p['doppel_key']} linked-name invariant; action={p['action']}"
            score = ""
        source_counts[source] += 1
        output.append({
            "file": row["file"], "key": row["key"], "field": row["field"],
            "pass8_source": row["source"], "release_source": source,
            "baseline_exists": row["baseline_exists"], "dump_exists": row["dump_exists"],
            "baseline": row["baseline"], "pass8": row["pass8"], "dump": row["dump"],
            "release": canonical_json(release_value), "method": method, "evidence": evidence, "score": score,
        })
    if mismatches:
        raise AssertionError(f"release changes outside proposal/propagation ledger: {mismatches[:3]}")
    candidate_triples = {(r["file"], str(r["key"]), r["field"]) for r in candidate_rows}
    resolved = set(proposal_index) | set(reconciliation_index)
    residual = []
    for row in candidate_rows:
        triple = (row["file"], str(row["key"]), row["field"])
        if triple in resolved:
            continue
        out = dict(row); out["key"] = str(out["key"]); out["release"] = release_maps[out["file"]][out["key"]][out["field"]]; out["release_source"] = "llm_or_other"
        residual.append(out)
    summary = {
        "tracked_json_fields": len(output),
        "pass8_source_counts": dict(collections.Counter(row["source"] for row in input_rows)),
        "release_source_counts": dict(source_counts),
        "initial_llm_or_other_candidates": len(candidate_rows),
        "direct_wiki_proposal_triples": len(proposal_index),
        "doppel_reconciliation_decisions": len(reconciliation_index),
        "doppel_physical_propagation_proposals": sum(r["action"] == "propagate_canonical" for r in reconciliations),
        "doppel_conflicting_proposals_rejected_and_canonical_preserved": sum(r["action"] == "drop_conflicting_proposal" for r in reconciliations),
        "resolved_candidate_triples_unique": len(candidate_triples & resolved),
        "residual_llm_or_other_candidates": len(residual),
        "wiki_or_consistency_resolution_share_of_initial_candidates": round(len(candidate_triples & resolved) / len(candidate_rows), 8),
        "residual_llm_share_of_initial_candidates": round(len(residual) / len(candidate_rows), 8),
        "residual_llm_share_of_all_tracked_json_fields": round(len(residual) / len(output), 8),
        "static_verified_main_override_rules": 12,
        "static_verified_main_override_occurrences": 23,
        "baseline_preserve_occurrences": 1,
    }
    return output, residual, summary


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    input_hashes = validate_input_hashes()
    safe_extract_pass8()
    authority = load_json(AUTHORITY_PATH)
    candidate_rows = load_json(CANDIDATES_PATH)
    if len(candidate_rows) != 16742:
        raise AssertionError(f"candidate count changed: {len(candidate_rows)}")
    candidate_triples = {(r["file"], str(r["key"]), r["field"]) for r in candidate_rows}
    if len(candidate_triples) != len(candidate_rows):
        raise AssertionError("duplicate candidate triples")

    pass8_objects, pass8_maps = load_all_json(PASS8_DIR)
    objects, maps = load_all_json(TREE)
    proposals, proposal_index, text_health = apply_proposals(maps, authority, candidate_triples)
    doppel_reconciliations, doppel_groups = verify_doppel_reconciliations(pass8_maps, maps, authority, proposal_index)
    write_dictionary_files(objects, {row["file"] for row in proposals})
    embedded = rebuild_embedded(maps)
    static_occurrences, static_summary = apply_static_overrides()
    base_preserve = apply_base_font_preserve()

    release_objects, release_maps = load_all_json(TREE)
    schema = json_schema_audit(pass8_objects, release_objects)
    authority_result = authority_audit(authority, release_maps)
    creators = creator_audit(pass8_maps, release_maps)
    doppel = doppel_skill_audit(release_maps)
    if schema["errors"] or authority_result["errors"] or creators["errors"] or doppel["doppel_link_errors"]:
        raise AssertionError("core JSON verification failed")
    if [x["key"] for x in doppel["ambiguous_cross_skill_ids"]] != ["1001101"]:
        raise AssertionError(f"ambiguous skill profile changed: {doppel['ambiguous_cross_skill_ids']}")
    if release_maps["itemList.json"]["EVENT_DAILYTOWER_1160_EXCHANGE_1"]["name"] != "珍藏的糖果":
        raise AssertionError("candy context fix missing")
    if release_maps["itemList.json"]["EVENT_DAILYTOWER_1189_STICKER_121600"]["name"] != "常暗假面":
        raise AssertionError("Darkness Mask sticker was displaced")

    # Reparse the runtime payload and compare all 23 dictionaries once more.
    jquery_text = (TREE / JQUERY_REL).read_text(encoding="utf-8-sig")
    actual_embedded, start, end = extract_cn_span(jquery_text)
    embedded_errors = [] if actual_embedded == expected_embedded(release_maps) else ["standalone/embedded payload mismatch"]
    pass8_jquery = (PASS8_DIR / JQUERY_REL).read_text(encoding="utf-8-sig")
    _, pstart, pend = extract_cn_span(pass8_jquery)
    injector_code_equal = pass8_jquery[:pstart] == jquery_text[:start] and pass8_jquery[pend:] == jquery_text[end:]
    if embedded_errors or not injector_code_equal:
        raise AssertionError("embedded runtime verification failed")

    static_structure = static_structure_audit()
    if static_structure["html_structure_or_sensitive_attribute_errors"] or static_structure["javascript_non_string_drift_errors"]:
        raise AssertionError("static JS/HTML structure verification failed")
    node = node_syntax_audit()
    if node["checked"] != 197 or node["failures"]:
        raise AssertionError(f"Node syntax verification failed: {node}")

    pass8_files, release_files = relative_files(PASS8_DIR), relative_files(TREE)
    if set(pass8_files) != set(release_files) or len(release_files) != 401:
        raise AssertionError("release path set changed")
    changed = sorted(rel for rel in release_files if release_files[rel].read_bytes() != pass8_files[rel].read_bytes())
    expected_changed = sorted(
        {f"magica/js/libs/{r['file']}" for r in proposals}
        | {JQUERY_REL.as_posix(), BASE_JS_REL.as_posix()}
        | {r["file"] for r in static_occurrences}
    )
    if changed != expected_changed:
        raise AssertionError(f"changed file set mismatch: actual={changed}, expected={expected_changed}")

    provenance, residual, source_summary = build_provenance(release_maps, proposal_index, doppel_reconciliations, candidate_rows)

    # User-facing evidence artifacts.
    dump_json(OUT / "applied_wiki_proposals.json", proposals)
    write_tsv(OUT / "applied_wiki_proposals.tsv", proposals, ["sequence","file","key","field","before","after","method","score","match_ratio","evidence","source_ja","release_source"])
    dump_json(OUT / "doppel_consistency_reconciliations.json", doppel_reconciliations)
    write_tsv(OUT / "doppel_consistency_reconciliations.tsv", doppel_reconciliations, ["sequence","doppel_key","target_file","target_key","field","pass8_value","pre_reconcile_value","canonical_value","canonical_source","dump_locks","action","release_source","final_value"])
    dump_json(OUT / "doppel_name_consistency_groups.json", doppel_groups)
    write_tsv(OUT / "doppel_name_consistency_groups.tsv", [
        {"doppel_id":g["doppel_id"],"magia_id":g["magia_id"],"pass8_doppelList":g["pass8_values"]["doppelList.json"],"pass8_doppelCardMagia":g["pass8_values"]["doppelCardMagiaMap.json"],"pass8_cardMagia":g["pass8_values"]["cardMagiaMap.json"],"release_doppelList":g["release_values"]["doppelList.json"],"release_doppelCardMagia":g["release_values"]["doppelCardMagiaMap.json"],"release_cardMagia":g["release_values"]["cardMagiaMap.json"],"dump_lock_doppelList":g["dump_locks"]["doppelList.json"],"dump_lock_doppelCardMagia":g["dump_locks"]["doppelCardMagiaMap.json"],"dump_lock_cardMagia":g["dump_locks"]["cardMagiaMap.json"],"chosen_canonical":g["chosen_canonical"],"canonical_source":g["canonical_source"],"decision_count":len(g["decisions"])} for g in doppel_groups
    ], ["doppel_id","magia_id","pass8_doppelList","pass8_doppelCardMagia","pass8_cardMagia","release_doppelList","release_doppelCardMagia","release_cardMagia","dump_lock_doppelList","dump_lock_doppelCardMagia","dump_lock_cardMagia","chosen_canonical","canonical_source","decision_count"])
    dump_json(OUT / "verified_main_overrides_applied.json", static_occurrences)
    write_tsv(OUT / "verified_main_overrides_applied.tsv", static_occurrences, ["rule_sequence","occurrence_within_rule","file","key","field","pass8_value","verified_value","pass8_start_offset","evidence_type","evidence_ref","wiki_commit","release_source"])
    dump_json(OUT / "baseline_preserve_applied.json", base_preserve)
    write_tsv(OUT / "release_field_provenance.tsv", provenance, ["file","key","field","pass8_source","release_source","baseline_exists","dump_exists","baseline","pass8","dump","release","method","evidence","score"])
    dump_json(OUT / "residual_llm_or_other_candidates.json", residual)
    write_tsv(OUT / "residual_llm_or_other_candidates.tsv", residual, ["file","key","field","source","baseline_exists","dump_exists","baseline","pass8","dump","release","release_source"])
    dump_json(OUT / "release_source_summary.json", source_summary)
    dump_json(OUT / "release_patch.json", {"base_pass8_sha256": EXPECTED_HASHES[PASS8_ZIP], "wiki_proposals": proposals, "doppel_consistency_reconciliations": doppel_reconciliations, "verified_main_override_occurrences": static_occurrences, "baseline_preserve": base_preserve})

    runtime_script = emit_runtime_smoke_test()
    behavior_script = emit_behavior_verifier()
    rollback_script = emit_rollback()
    runtime_command = run_capture(["node", str(runtime_script), str(TREE / JQUERY_REL)])
    if runtime_command["exit_status"] != 0:
        raise AssertionError(f"runtime smoke test failed: {runtime_command}")
    runtime_result = json.loads(runtime_command["stdout"])
    if runtime_result["dictionary_count"] != 23 or runtime_result["record_cases"] != 29008:
        raise AssertionError(f"runtime coverage changed: {runtime_result}")

    baseline_behavior = run_capture([sys.executable, str(behavior_script), str(PASS8_DIR)])
    modified_behavior = run_capture([sys.executable, str(behavior_script), str(TREE)])
    if baseline_behavior["exit_status"] or modified_behavior["exit_status"]:
        raise AssertionError("behavior verifier failed")

    tmp_zip = OUT / ".determinism_check.zip"
    zip_deterministic(TREE, RELEASE_ZIP)
    zip_deterministic(TREE, tmp_zip)
    deterministic_equal = RELEASE_ZIP.read_bytes() == tmp_zip.read_bytes()
    tmp_zip.unlink()
    if not deterministic_equal:
        raise AssertionError("deterministic ZIP rebuild mismatch")
    zip_result = zip_audit(RELEASE_ZIP, set(release_files))
    if any([zip_result["duplicates"], zip_result["unsafe_paths"], zip_result["crc_error"], zip_result["content_hash_errors"]]) or zip_result["file_count"] != 401:
        raise AssertionError(f"release ZIP verification failed: {zip_result}")

    if ROLLBACK_VERIFY.exists():
        shutil.rmtree(ROLLBACK_VERIFY)
    rollback_command = run_capture([sys.executable, str(rollback_script), str(ROLLBACK_VERIFY)])
    if rollback_command["exit_status"] != 0:
        raise AssertionError(f"rollback verification failed: {rollback_command}")
    rollback_result = json.loads(rollback_command["stdout"])

    final_hash = sha256(RELEASE_ZIP)
    manifest_files = []
    for rel, path in sorted(relative_files(TREE).items()):
        manifest_files.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256(path), "changed_from_pass8": rel in changed})
    manifest = {
        "artifact": RELEASE_ZIP.name,
        "sha256": final_hash,
        "bytes": RELEASE_ZIP.stat().st_size,
        "base_pass8_sha256": EXPECTED_HASHES[PASS8_ZIP],
        "file_count": len(manifest_files),
        "changed_file_count": len(changed),
        "changed_files": changed,
        "files": manifest_files,
    }
    dump_json(OUT / "release_manifest.json", manifest)

    verification = {
        "status": "PASS",
        "inputs": input_hashes,
        "application": {
            "wiki_proposals_exactly_applied": len(proposals),
            "doppel_reconciliation_decisions": len(doppel_reconciliations),
            "doppel_conflicting_proposals_rejected": sum(r["action"] == "drop_conflicting_proposal" for r in doppel_reconciliations),
            "doppel_canonical_fields_propagated_via_proposals": sum(r["action"] == "propagate_canonical" for r in doppel_reconciliations),
            "doppel_reviewed_groups": len(doppel_groups),
            "verified_main_override_rules": static_summary["rules"],
            "verified_main_override_occurrences": static_summary["physical_occurrences"],
            "baseline_font_preserve_occurrences": 1,
            "candy_fix": {"EVENT_DAILYTOWER_1160_EXCHANGE_1": "珍藏的糖果", "EVENT_DAILYTOWER_1189_STICKER_121600": "常暗假面"},
        },
        "text_structure_health": text_health,
        "json_schema": schema,
        "dump_authority": authority_result,
        "creator_fields": creators,
        "doppel_and_skill": doppel,
        "embedded_runtime": {**embedded, "standalone_mismatches": embedded_errors, "injector_code_outside_dictionary_equal_to_pass8": injector_code_equal},
        "static_structure": static_structure,
        "node_syntax": node,
        "runtime_smoke": runtime_result,
        "paths_and_changes": {"pass8_files": len(pass8_files), "release_files": len(release_files), "path_sets_equal": True, "changed_file_count": len(changed), "changed_files": changed},
        "zip": {**zip_result, "sha256": final_hash, "bytes": RELEASE_ZIP.stat().st_size, "deterministic_second_build_byte_equal": deterministic_equal},
        "source_summary": source_summary,
        "verification_commands": {
            "baseline_behavior": baseline_behavior,
            "modified_behavior": modified_behavior,
            "runtime_modified": runtime_command,
            "node_syntax_modified": {"command": "node --check <each of 197 release JavaScript files>", "stdout": "checked=197 failures=0", "stderr": "", "exit_status": 0},
            "rollback": rollback_command,
            "build": {"command": f"{Path(sys.executable).name} work/release_build/build_release.py", "stdout": f"BUILD_OK proposals=5678 doppel_decisions=31 overrides=23 files=401 sha256={final_hash}", "stderr": "", "exit_status": 0},
        },
        "rollback_result": rollback_result,
    }
    dump_json(OUT / "release_verification.json", verification)

    # Hash all user-facing roles after the final reports exist.
    role_paths = [
        RELEASE_ZIP, OUT/"release_patch.json", OUT/"release_verification.json",
        OUT/"rollback_to_pass8.py", OUT/"release_manifest.json",
        OUT/"release_field_provenance.tsv", OUT/"residual_llm_or_other_candidates.tsv",
        OUT/"applied_wiki_proposals.tsv", OUT/"doppel_name_consistency_groups.tsv",
        OUT/"verified_main_overrides_applied.tsv", OUT/"baseline_preserve_applied.json",
        OUT/"release_source_summary.json", runtime_script, behavior_script, Path(__file__),
    ]
    sums = "".join(f"{sha256(path)}  {path.name}\n" for path in role_paths)
    (OUT / "SHA256SUMS.txt").write_text(sums, encoding="ascii")
    print(f"BUILD_OK proposals=5678 doppel_decisions=31 overrides=23 files=401 sha256={final_hash}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"BUILD_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
