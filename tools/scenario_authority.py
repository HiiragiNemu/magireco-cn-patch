#!/usr/bin/env python3
"""Repair authoritative CN scenario text while retaining current runtime structure."""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


TEXT_FIELDS = {
    "textLeft",
    "textRight",
    "textCenter",
    "narration",
    "Fnarration",
    "fnarration",
    "progressNarration",
    "progressFnarration",
    "text",
    "textSelect",
    "textAvLeft",
    "textAvRight",
    "textAvCenter",
}
NAME_FIELDS = {
    "nameLeft",
    "nameRight",
    "nameCenter",
    "nameNarration",
    "nameFnarration",
    "nameAvLeft",
    "nameAvRight",
    "nameAvCenter",
}
TRANSLATABLE_FIELDS = TEXT_FIELDS | NAME_FIELDS
TOKEN_RE = re.compile(r"\[(?P<kind>[A-Za-z0-9_]+):(?P<body>[^\]]*)\]")
RANDOM_SUFFIX_RE = re.compile(r"^(?P<stable>\d+(?:-\d+)?)(?:_[A-Za-z0-9]{5})?$")
SPECIAL_SEQUENCE_NAME_MAP = {
    "521310-11": {"絵本のページ": "绘本页面", "なぎさ": "渚", "キュゥべえ": "丘比", "？？？": "？？？"},
    "521310-12": {"なぎさ": "渚", "キュゥべえ": "丘比", "ユゥ": "梦", "？？？": "？？？"},
    "521310-20": {"なぎさ": "渚", "キュゥべえ": "丘比"},
}


class RepairError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def decode_style(path: Path) -> tuple[str, bool, bool]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    return ("\r\n" if "\r\n" in text else "\n", text.endswith(("\n", "\r")), raw.startswith(b"\xef\xbb\xbf"))


def render_like(obj: Any, style_path: Path) -> bytes:
    newline, final_newline, bom = decode_style(style_path)
    text = json.dumps(obj, ensure_ascii=False, indent=1)
    if newline != "\n":
        text = text.replace("\n", newline)
    if final_newline:
        text += newline
    raw = text.encode("utf-8")
    return (b"\xef\xbb\xbf" + raw) if bom else raw


def find_repo_root(path: Path) -> Path:
    current = path.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    raise RepairError(f"Git root not found for {path}")


def materialize(
    *,
    target: Path,
    rendered: bytes,
    repo_root: Path,
    label: str,
    stage_root: Path | None,
    apply: bool,
) -> str | None:
    staged: Path | None = None
    if stage_root is not None:
        staged = stage_root / label / target.relative_to(repo_root)
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(rendered)
        if staged.read_bytes() != rendered:
            raise RepairError(f"staging verification failed: {staged}")
    if apply:
        target.write_bytes(rendered)
        if target.read_bytes() != rendered:
            raise RepairError(f"write verification failed: {target}")
    return str(staged) if staged else None


def stable_id(path_or_name: str) -> str | None:
    stem = Path(path_or_name).stem
    match = RANDOM_SUFFIX_RE.match(stem)
    return match.group("stable") if match else None


def walk_fields(obj: Any, fields: set[str]) -> list[tuple[tuple[Any, ...], str]]:
    found: list[tuple[tuple[Any, ...], str]] = []

    def walk(value: Any, path: tuple[Any, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                child = path + (key,)
                if key in fields and isinstance(item, str):
                    found.append((child, item))
                walk(item, child)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, path + (index,))

    walk(obj)
    return found


def get_path(obj: Any, path: tuple[Any, ...]) -> Any:
    value = obj
    for part in path:
        value = value[part]
    return value


def set_path(obj: Any, path: tuple[Any, ...], value: Any) -> None:
    parent = obj
    for part in path[:-1]:
        parent = parent[part]
    parent[path[-1]] = value


def runtime_tokens(value: str) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for match in TOKEN_RE.finditer(value):
        kind = match.group("kind")
        if kind.startswith("text"):
            continue
        tokens.append({"kind": kind, "raw": match.group(0), "start": match.start(), "end": match.end()})
    return tokens


def strip_runtime_tokens(value: str) -> str:
    tokens = runtime_tokens(value)
    if not tokens:
        return value
    parts: list[str] = []
    cursor = 0
    for token in tokens:
        parts.append(value[cursor : token["start"]])
        cursor = token["end"]
    parts.append(value[cursor:])
    return "".join(parts)


def insert_by_authority_ratio(source_without_runtime: str, authority: str, auth_tokens: list[dict[str, Any]]) -> str:
    auth_without_runtime = strip_runtime_tokens(authority)
    auth_visible_length = max(len(auth_without_runtime), 1)
    insertions: dict[int, list[str]] = defaultdict(list)
    for token in auth_tokens:
        prefix = authority[: token["start"]]
        visible_before = len(strip_runtime_tokens(prefix))
        offset = round((visible_before / auth_visible_length) * len(source_without_runtime))
        insertions[offset].append(token["raw"])
    output: list[str] = []
    for index in range(len(source_without_runtime) + 1):
        output.extend(insertions.get(index, []))
        if index < len(source_without_runtime):
            output.append(source_without_runtime[index])
    return "".join(output)


def merge_runtime_tokens(source_cn: str, authority: str) -> str:
    source_tokens = runtime_tokens(source_cn)
    auth_tokens = runtime_tokens(authority)
    if not source_tokens and not auth_tokens:
        return source_cn

    matcher = difflib.SequenceMatcher(
        None,
        [token["kind"] for token in source_tokens],
        [token["kind"] for token in auth_tokens],
        autojunk=False,
    )
    source_to_auth: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            source_to_auth[block.a + offset] = block.b + offset

    if not source_to_auth:
        result = insert_by_authority_ratio(strip_runtime_tokens(source_cn), authority, auth_tokens)
    else:
        auth_to_source = {auth: source for source, auth in source_to_auth.items()}
        before: dict[int, list[str]] = defaultdict(list)
        after: dict[int, list[str]] = defaultdict(list)
        matched_auth = sorted(auth_to_source)
        for auth_index, token in enumerate(auth_tokens):
            if auth_index in auth_to_source:
                continue
            next_matches = [index for index in matched_auth if index > auth_index]
            if next_matches:
                before[auth_to_source[next_matches[0]]].append(token["raw"])
            else:
                previous = max(index for index in matched_auth if index < auth_index)
                after[auth_to_source[previous]].append(token["raw"])

        output: list[str] = []
        cursor = 0
        for source_index, token in enumerate(source_tokens):
            output.append(source_cn[cursor : token["start"]])
            output.extend(before.get(source_index, []))
            if source_index in source_to_auth:
                output.append(auth_tokens[source_to_auth[source_index]]["raw"])
            output.extend(after.get(source_index, []))
            cursor = token["end"]
        output.append(source_cn[cursor:])
        result = "".join(output)

    result_tokens = [(token["kind"], token["raw"]) for token in runtime_tokens(result)]
    expected_tokens = [(token["kind"], token["raw"]) for token in auth_tokens]
    if result_tokens != expected_tokens:
        raise RepairError(f"runtime token merge failed: {result_tokens!r} != {expected_tokens!r}")
    return result


def overlay_by_path(source_cn: Any, authority: Any) -> tuple[Any, int]:
    output = copy.deepcopy(authority)
    source_fields = dict(walk_fields(source_cn, TRANSLATABLE_FIELDS))
    target_fields = dict(walk_fields(authority, TRANSLATABLE_FIELDS))
    if set(source_fields) != set(target_fields):
        raise RepairError(f"translation paths differ: source={len(source_fields)} authority={len(target_fields)}")
    for path, source_value in source_fields.items():
        target_value = target_fields[path]
        value = merge_runtime_tokens(source_value, target_value) if path[-1] in TEXT_FIELDS else source_value
        if path[-1] in TEXT_FIELDS and strip_runtime_tokens(value) != strip_runtime_tokens(source_value):
            raise RepairError(f"Chinese visible text changed at {path!r}")
        set_path(output, path, value)
    return output, len(source_fields)


def overlay_by_sequence(source_cn: Any, authority: Any, name_map: dict[str, str]) -> tuple[Any, int]:
    output = copy.deepcopy(authority)
    source_texts = walk_fields(source_cn, TEXT_FIELDS)
    target_texts = walk_fields(authority, TEXT_FIELDS)
    if len(source_texts) != len(target_texts):
        raise RepairError(f"ordered text counts differ: {len(source_texts)} != {len(target_texts)}")
    for (_, source_value), (target_path, target_value) in zip(source_texts, target_texts):
        value = merge_runtime_tokens(source_value, target_value)
        if strip_runtime_tokens(value) != strip_runtime_tokens(source_value):
            raise RepairError(f"ordered Chinese visible text changed at {target_path!r}")
        set_path(output, target_path, value)
    for target_path, target_value in walk_fields(authority, NAME_FIELDS):
        if target_value not in name_map:
            raise RepairError(f"missing name mapping for {target_value!r}")
        set_path(output, target_path, name_map[target_value])
    return output, len(source_texts) + len(walk_fields(authority, NAME_FIELDS))


def build_overlap_name_map(source_cn: Any, authority: Any) -> dict[str, str]:
    source = dict(walk_fields(source_cn, NAME_FIELDS))
    target = dict(walk_fields(authority, NAME_FIELDS))
    mapping: dict[str, set[str]] = defaultdict(set)
    for path in set(source) & set(target):
        mapping[target[path]].add(source[path])
    ambiguous = {key: values for key, values in mapping.items() if len(values) != 1}
    if ambiguous:
        raise RepairError(f"ambiguous name map: {ambiguous!r}")
    result = {key: next(iter(values)) for key, values in mapping.items()}
    missing = sorted(set(target.values()) - set(result))
    if missing:
        raise RepairError(f"unmapped authority names: {missing!r}")
    return result


def index_unique(root: Path) -> dict[str, Path]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in root.rglob("*.json"):
        grouped[path.name].append(path)
    duplicates = {name: paths for name, paths in grouped.items() if len(paths) != 1}
    if duplicates:
        raise RepairError(f"duplicate filenames under {root}: {sorted(duplicates)[:5]}")
    return {name: paths[0] for name, paths in grouped.items()}


def canonical_pairs(cn_root: Path, target_names: set[str]) -> list[tuple[str, Path, str]]:
    """Find every authoritative CN variant whose historical suffix differs.

    The target/Totentanz filename set is the current runtime identity.  A Reader
    CN file absent from that set is not ignored: it must have exactly one current
    target with the same stable story/section id.
    """
    candidates: dict[str, list[Path]] = defaultdict(list)
    targets: dict[str, list[str]] = defaultdict(list)
    for path in cn_root.rglob("*.json"):
        sid = stable_id(path.name)
        if sid and path.name not in target_names:
            candidates[sid].append(path)
    for name in target_names:
        sid = stable_id(name)
        if sid:
            targets[sid].append(name)

    pairs: list[tuple[str, Path, str]] = []
    for sid in sorted(candidates):
        if len(candidates[sid]) != 1 or len(targets.get(sid, [])) != 1:
            raise RepairError(
                f"{sid}: unstable canonical mapping "
                f"cn={len(candidates[sid])} target={len(targets.get(sid, []))}"
            )
        pairs.append((sid, candidates[sid][0], targets[sid][0]))
    return pairs


def canonicalize_reader(args: argparse.Namespace) -> dict[str, Any]:
    reader_repo = args.reader_repo.resolve()
    cn_root = reader_repo / "magireco-translate-data-master" / "Scenarios_full"
    cn_index = index_unique(cn_root)
    modern_index = index_unique(args.modern_root.resolve())
    tot_index = index_unique(args.totentanz_root.resolve())
    game_adv_root = args.game_root.resolve() / "adv"
    game_index = index_unique(game_adv_root)
    game_repo = find_repo_root(game_adv_root)
    stage_root = args.stage_root.resolve() if args.stage_root else None
    rows = []
    reader_changed = 0
    game_changed = 0
    for sid, canonical_path, target_name in canonical_pairs(cn_root, set(tot_index)):
        target = cn_index.get(target_name)
        modern = modern_index.get(target_name)
        tot = tot_index.get(target_name)
        if target is None or modern is None or tot is None:
            raise RepairError(f"{sid}: missing target/authority for {target_name}")
        source_obj = load_json(canonical_path)
        modern_obj = load_json(modern)
        tot_obj = load_json(tot)
        source_paths = {path for path, _ in walk_fields(source_obj, TRANSLATABLE_FIELDS)}
        modern_paths = {path for path, _ in walk_fields(modern_obj, TRANSLATABLE_FIELDS)}
        tot_paths = {path for path, _ in walk_fields(tot_obj, TRANSLATABLE_FIELDS)}
        if source_paths == modern_paths:
            output, field_count = overlay_by_path(source_obj, modern_obj)
            authority = "modern-v4"
        elif source_paths == tot_paths:
            output, field_count = overlay_by_path(source_obj, tot_obj)
            authority = "totentanz-v4"
        elif sid in SPECIAL_SEQUENCE_NAME_MAP:
            output, field_count = overlay_by_sequence(source_obj, tot_obj, SPECIAL_SEQUENCE_NAME_MAP[sid])
            authority = "totentanz-v4-ordered"
        else:
            raise RepairError(f"{sid}: no deterministic translation mapping")
        rendered = render_like(output, target)
        before = target.read_bytes()
        reader_is_changed = before != rendered
        game_target = game_index.get(target_name)
        if game_target is None:
            raise RepairError(f"{sid}: game target missing for {target_name}")
        game_is_changed = game_target.read_bytes() != rendered
        reader_stage = materialize(
            target=target,
            rendered=rendered,
            repo_root=reader_repo,
            label="reader",
            stage_root=stage_root,
            apply=args.apply and reader_is_changed,
        )
        game_stage = materialize(
            target=game_target,
            rendered=rendered,
            repo_root=game_repo,
            label="game",
            stage_root=stage_root,
            apply=args.apply and game_is_changed,
        )
        reader_changed += int(reader_is_changed)
        game_changed += int(game_is_changed)
        rows.append({"stable": sid, "canonical": str(canonical_path), "readerTarget": str(target), "gameTarget": str(game_target), "readerStaged": reader_stage, "gameStaged": game_stage, "authority": authority, "fields": field_count, "readerChanged": reader_is_changed, "gameChanged": game_is_changed})
    return {"mode": "apply" if args.apply else ("stage" if stage_root else "audit"), "pairs": len(rows), "readerChangedFiles": reader_changed, "gameChangedFiles": game_changed, "rows": rows}


def repair_game(args: argparse.Namespace) -> dict[str, Any]:
    classification = load_json(args.classification.resolve())
    if "files" in classification:
        rels = sorted(set(classification["files"]))
    else:
        rels = sorted(
            set(classification["groups"]["neither"])
            | set(classification["groups"]["tot=modern"])
        )
    game_root = args.game_root.resolve()
    modern_root = args.modern_json_root.resolve()
    game_repo = find_repo_root(game_root)
    stage_root = args.stage_root.resolve() if args.stage_root else None
    rows = []
    changed = 0
    for rel in rels:
        game_path = game_root / rel
        modern_path = modern_root / rel
        source_obj = load_json(game_path)
        authority_obj = load_json(modern_path)
        source_paths = {path for path, _ in walk_fields(source_obj, TRANSLATABLE_FIELDS)}
        target_paths = {path for path, _ in walk_fields(authority_obj, TRANSLATABLE_FIELDS)}
        if source_paths == target_paths:
            output, field_count = overlay_by_path(source_obj, authority_obj)
            method = "path"
        elif rel in {"adv/scenario_3/320021-3.json", "adv/scenario_3/330151-3.json"}:
            name_map = build_overlap_name_map(source_obj, authority_obj)
            output, field_count = overlay_by_sequence(source_obj, authority_obj, name_map)
            method = "ordered"
        else:
            raise RepairError(f"{rel}: no deterministic structural mapping")
        rendered = render_like(output, game_path)
        before = game_path.read_bytes()
        is_changed = before != rendered
        staged = materialize(
            target=game_path,
            rendered=rendered,
            repo_root=game_repo,
            label="game",
            stage_root=stage_root,
            apply=args.apply and is_changed,
        )
        changed += int(is_changed)
        rows.append({"path": rel, "target": str(game_path), "staged": staged, "method": method, "fields": field_count, "changed": is_changed})
    return {"mode": "apply" if args.apply else ("stage" if stage_root else "audit"), "files": len(rows), "changedFiles": changed, "rows": rows}


def repair_reader_runtime(args: argparse.Namespace) -> dict[str, Any]:
    """Apply the exact repaired game/V4 structure back to Reader CN JSON.

    The input audit is intentionally explicit.  It lists only Reader files whose
    runtime structure differs from the already repaired game scenario with the
    same deployed filename.  Chinese visible text and speaker names continue to
    come from Reader; only current runtime fields/tokens come from the game/V4
    authority.
    """

    if args.reader_runtime_audit is None:
        return {"mode": "disabled", "files": 0, "changedFiles": 0, "rows": []}

    audit = load_json(args.reader_runtime_audit.resolve())
    if audit.get("schema") != "reader-game-runtime-structure-audit/v1":
        raise RepairError("reader runtime audit schema is invalid")
    mismatches = audit.get("mismatches")
    if not isinstance(mismatches, list):
        raise RepairError("reader runtime audit mismatch list is invalid")
    expected = audit.get("counts", {}).get("masked_mismatch")
    if expected != len(mismatches):
        raise RepairError(
            f"reader runtime audit count mismatch: {expected!r} != {len(mismatches)}"
        )

    reader_repo = args.reader_repo.resolve()
    reader_root = (
        reader_repo / "magireco-translate-data-master" / "Scenarios_full"
    ).resolve()
    game_root = args.game_root.resolve()
    stage_root = args.stage_root.resolve() if args.stage_root else None
    rows = []
    changed = 0
    seen_reader: set[str] = set()

    for entry in mismatches:
        if not isinstance(entry, dict):
            raise RepairError("reader runtime audit entry is invalid")
        reader_rel = entry.get("reader")
        game_rel = entry.get("game")
        if not isinstance(reader_rel, str) or not isinstance(game_rel, str):
            raise RepairError("reader runtime audit paths are invalid")
        if reader_rel in seen_reader:
            raise RepairError(f"duplicate reader runtime target: {reader_rel}")
        seen_reader.add(reader_rel)

        reader_path = (reader_root / Path(reader_rel)).resolve()
        game_path = (game_root / Path(game_rel)).resolve()
        if reader_root not in reader_path.parents or game_root not in game_path.parents:
            raise RepairError(f"unsafe reader runtime audit path: {reader_rel}")
        if not reader_path.is_file() or not game_path.is_file():
            raise RepairError(f"reader runtime audit target is missing: {reader_rel}")

        source_obj = load_json(reader_path)
        authority_obj = load_json(game_path)
        source_paths = {
            path for path, _ in walk_fields(source_obj, TRANSLATABLE_FIELDS)
        }
        target_paths = {
            path for path, _ in walk_fields(authority_obj, TRANSLATABLE_FIELDS)
        }
        if source_paths == target_paths:
            output, field_count = overlay_by_path(source_obj, authority_obj)
            method = "path"
        elif game_rel in {
            "adv/scenario_3/320021-3.json",
            "adv/scenario_3/330151-3.json",
        }:
            name_map = build_overlap_name_map(source_obj, authority_obj)
            output, field_count = overlay_by_sequence(
                source_obj, authority_obj, name_map
            )
            method = "ordered"
        else:
            raise RepairError(
                f"{reader_rel}: no deterministic Reader runtime mapping"
            )

        source_visible = [
            strip_runtime_tokens(value)
            for _, value in walk_fields(source_obj, TEXT_FIELDS)
        ]
        output_visible = [
            strip_runtime_tokens(value)
            for _, value in walk_fields(output, TEXT_FIELDS)
        ]
        if source_visible != output_visible:
            raise RepairError(f"Reader visible text changed: {reader_rel}")
        output_tokens = [
            [(token["kind"], token["raw"]) for token in runtime_tokens(value)]
            for _, value in walk_fields(output, TEXT_FIELDS)
        ]
        authority_tokens = [
            [(token["kind"], token["raw"]) for token in runtime_tokens(value)]
            for _, value in walk_fields(authority_obj, TEXT_FIELDS)
        ]
        if output_tokens != authority_tokens:
            raise RepairError(f"Reader runtime tokens differ: {reader_rel}")
        source_names = {
            value for _, value in walk_fields(source_obj, NAME_FIELDS)
        }
        output_names = {value for _, value in walk_fields(output, NAME_FIELDS)}
        if not output_names.issubset(source_names):
            raise RepairError(f"Reader speaker names changed: {reader_rel}")

        rendered = render_like(output, reader_path)
        before = reader_path.read_bytes()
        is_changed = before != rendered
        staged = materialize(
            target=reader_path,
            rendered=rendered,
            repo_root=reader_repo,
            label="reader-runtime",
            stage_root=stage_root,
            apply=args.apply and is_changed,
        )
        changed += int(is_changed)
        rows.append(
            {
                "reader": reader_rel,
                "game": game_rel,
                "target": str(reader_path),
                "staged": staged,
                "method": method,
                "fields": field_count,
                "changed": is_changed,
            }
        )

    return {
        "mode": "apply" if args.apply else ("stage" if stage_root else "audit"),
        "files": len(rows),
        "changedFiles": changed,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reader-repo", type=Path, required=True)
    parser.add_argument("--story-index", type=Path, required=True)
    parser.add_argument("--modern-root", type=Path, required=True)
    parser.add_argument("--totentanz-root", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--modern-json-root", type=Path, required=True)
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--reader-runtime-audit", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = {
        "schema": "authoritative-scenario-repair/v2",
        "reader": canonicalize_reader(args),
        "gameStructure": repair_game(args),
        "readerRuntimeStructure": repair_reader_runtime(args),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"readerPairs": report["reader"]["pairs"], "readerChanged": report["reader"]["readerChangedFiles"], "gameTranslationChanged": report["reader"]["gameChangedFiles"], "gameStructureFiles": report["gameStructure"]["files"], "gameStructureChanged": report["gameStructure"]["changedFiles"], "readerRuntimeFiles": report["readerRuntimeStructure"]["files"], "readerRuntimeChanged": report["readerRuntimeStructure"]["changedFiles"]}, ensure_ascii=False))
    print(f"REPORT={args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
