#!/usr/bin/env python3
"""Prepare, apply, verify, and roll back the bounded round-4 residue closure."""

from __future__ import annotations

import pass18_css_successors

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
ROUND = ROOT / "magica/research/totentanz-full-localization-20260817/visible-residue-closure-round4"
DEFAULT_MANIFEST = ROUND / "closure_manifest.json"
DEFAULT_STATE = ROUND / "runtime"
ALLOWED = {
    "magica/css/regularEvent/groupBattle/RegularEventGroupBattleRanking.css": "css",
    "magica/css/regularEvent/groupBattle/RegularEventGroupBattleUser.css": "css",
    "magica/js/libs/cardList.json": "card",
    "magica/js/libs/eventStoryList.json": "story",
    "magica/js/libs/pieceList.json": "piece",
    "magica/js/libs/sectionList.json": "section",
}
GENERATED = "magica/js/libs/jquery-3.7.1.min.js"
LATER_CURATION = ROOT / "magica/research/totentanz-full-localization-20260817/remote-main-curation-20260820/APPLIED.tsv"


class ClosureError(RuntimeError):
    pass


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name); stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


def confined(root: Path, rel: str) -> Path:
    path = (root / rel).resolve()
    if root.resolve() not in path.parents:
        raise ClosureError(f"path escapes repository: {rel}")
    return path


def record_for(kind: str, key: str, data: Any) -> dict:
    if not isinstance(data, list):
        raise ClosureError(f"{kind} dictionary must be a list")
    field = {"card": "cardId", "section": "sectionId", "story": "storyIds", "piece": "pieceId"}[kind]
    found = [row for row in data if str(row.get(field)) == key]
    if len(found) != 1:
        raise ClosureError(f"stable key not unique: {kind}:{key} count={len(found)}")
    return found[0]


def key_field_for(kind: str) -> str:
    return {"card": "cardId", "section": "sectionId", "story": "storyIds", "piece": "pieceId"}[kind]


def load_later_supersessions(root: Path) -> dict[tuple[str, str], dict[str, str]]:
    path = root / LATER_CURATION.relative_to(ROOT)
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    required = {"file", "leaf_path", "local", "after", "source_tier", "evidence", "source_commit"}
    if rows and not required.issubset(rows[0]):
        raise ClosureError("later authority curation schema mismatch")
    result: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        identity = (row["file"], row["leaf_path"])
        if identity in result:
            raise ClosureError(f"duplicate later authority identity: {identity}")
        result[identity] = row
    return result


def transform(kind: str, source: bytes, rows: list[dict], before_field: str, after_field: str) -> bytes:
    if kind == "css":
        text = source.decode("utf-8")
        for row in rows:
            before, after = str(row[before_field]), str(row[after_field])
            if text.count(before) != 1:
                raise ClosureError(f"CSS literal drift: {row['item_id']} count={text.count(before)}")
            text = text.replace(before, after, 1)
        return text.encode("utf-8")
    data = json.loads(source.decode("utf-8"))
    for row in rows:
        record = record_for(kind, str(row["key"]), data)
        actual = record.get(row["field"])
        if actual != row[before_field]:
            raise ClosureError(f"field drift {row['file']}:{row['key']}:{row['field']}: {actual!r}")
        record[row["field"]] = row[after_field]
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "magireco-visible-residue-closure-round4/v1":
        raise ClosureError("manifest schema mismatch")
    rows = data.get("changes")
    if not isinstance(rows, list) or len(rows) != 39:
        raise ClosureError("manifest change count mismatch")
    targets = {row.get("file") for row in rows}
    if targets != set(ALLOWED):
        raise ClosureError(f"target allowlist mismatch: {sorted(targets)}")
    identities = [(row.get("file"), str(row.get("key")), row.get("field")) for row in rows]
    if len(identities) != len(set(identities)):
        raise ClosureError("duplicate change identity")
    return data


def state_manifest(state: Path) -> Path:
    return state / "state.json"


def prepare(root: Path, manifest_path: Path, state: Path) -> dict:
    manifest_bytes = manifest_path.read_bytes(); manifest = read_manifest(manifest_path)
    grouped: dict[str, list[dict]] = {}
    for row in manifest["changes"]: grouped.setdefault(row["file"], []).append(row)
    temp = state / f".prepare-{os.getpid()}"
    if temp.exists(): shutil.rmtree(temp)
    entries = []
    try:
        for rel in sorted(grouped):
            path = confined(root, rel); base = path.read_bytes(); kind = ALLOWED[rel]
            expected = transform(kind, base, grouped[rel], "before", "after")
            for area, content in (("bases", base), ("prepared", expected)):
                out = temp / area / rel; out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(content)
            entries.append({"target": rel, "kind": kind, "item_ids": [row["item_id"] for row in grouped[rel]], "before_size": len(base), "after_size": len(expected)})
        state.mkdir(parents=True, exist_ok=True)
        for area in ("bases", "prepared"):
            dest = state / area
            if dest.exists(): shutil.rmtree(dest)
            os.replace(temp / area, dest)
        atomic_write(state / "manifest.snapshot.json", manifest_bytes)
        payload = {"schema": 1, "mode": "prepared", "repo_root": str(root.resolve()), "manifest": str(manifest_path.resolve()), "entries": entries, "product_tree_writes": 0}
        atomic_write(state_manifest(state), (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        return {"status": "PASS", "mode": "prepare", "changes": 39, "targets": len(entries), "product_tree_writes": 0}
    finally:
        if temp.exists(): shutil.rmtree(temp)


def load_state(
    root: Path,
    manifest_path: Path,
    state: Path,
    *,
    allow_relocated_root: bool = False,
) -> tuple[dict, dict]:
    if not state_manifest(state).is_file(): raise ClosureError("prepared state missing")
    saved = json.loads(state_manifest(state).read_text(encoding="utf-8")); manifest = read_manifest(manifest_path)
    if (
        Path(saved.get("repo_root", "")).resolve() != root.resolve()
        and not allow_relocated_root
    ):
        raise ClosureError("repository root drift")
    if not (state / "manifest.snapshot.json").is_file() or (state / "manifest.snapshot.json").read_bytes() != manifest_path.read_bytes():
        raise ClosureError("manifest checkpoint drift")
    for entry in saved["entries"]:
        rel = entry["target"]
        if rel not in ALLOWED or not (state / "bases" / rel).is_file() or not (state / "prepared" / rel).is_file():
            raise ClosureError(f"state target invalid: {rel}")
    return saved, manifest


def run_injector(root: Path) -> None:
    env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run([sys.executable, str(root / "Build_JS_Injector.py")], cwd=root, env=env, text=True, encoding="utf-8", capture_output=True)
    if proc.returncode:
        raise ClosureError("runtime injector failed: " + (proc.stdout + proc.stderr).strip())


def embedded_runtime(root: Path) -> dict:
    text = confined(root, GENERATED).read_text(encoding="utf-8")
    start = text.rfind("(function(){")
    marker = "var cn = "; payload_start = text.find(marker, start)
    if start < 0 or payload_start < 0: raise ClosureError("runtime payload marker missing")
    payload_start += len(marker)
    data, _ = json.JSONDecoder().raw_decode(text[payload_start:])
    return data


def verify_retained(root: Path, manifest: dict) -> int:
    cache: dict[str, Any] = {}
    for row in manifest["protected_retained"]:
        rel = row["file"]
        if rel not in cache: cache[rel] = json.loads(confined(root, rel).read_text(encoding="utf-8"))
        kind = "section" if rel.endswith("sectionList.json") else "piece" if rel.endswith("pieceList.json") else "story"
        field_name = {"section": "sectionId", "piece": "pieceId", "story": "storyIds"}[kind]
        found = [record for record in cache[rel] if str(record.get(field_name)) == str(row["key"])]
        if len(found) != 1 or found[0].get(row["field"]) != row["value"]:
            raise ClosureError(f"protected retained drift: {row['item_id']}")
    return len(manifest["protected_retained"])


def verify_entry_fields(
    root: Path,
    state: Path,
    entry: dict,
    rows: list[dict],
    expected: str,
    supersessions: dict[tuple[str, str], dict[str, str]] | None = None,
) -> int:
    """Verify this round's bounded fields without freezing later authority edits.

    CSS targets are byte-frozen because each file contains only this round's
    scoped change.  JSON dictionaries continue to receive later official/Wiki
    corrections, so comparing their entire historical snapshot would reject
    legitimate supersessions outside this round's stable keys.
    """
    rel = entry["target"]
    kind = entry["kind"]
    area = "prepared" if expected == "after" else "bases"
    if kind == "css":
        if confined(root, rel).read_bytes() != (state / area / rel).read_bytes():
            if expected != "after" or not pass18_css_successors.accept_round4(root, entry, rows):
                raise ClosureError(f"product byte drift: {rel}")
        return 0

    data = json.loads(confined(root, rel).read_text(encoding="utf-8"))
    reviewed_css_round4 = pass18_css_successors.reviewed_round4_targets(root, entry, rows) if expected == "after" else {}
    value_field = "after" if expected == "after" else "before"
    supersessions = supersessions or {}
    accepted_supersessions = 0
    for row in rows:
        record = record_for(kind, str(row["key"]), data)
        actual = record.get(row["field"])
        wanted = row[value_field]
        if actual != wanted:
            reviewed_key = (row["item_id"], str(row["key"]), row["field"])
            if reviewed_key in reviewed_css_round4 and reviewed_css_round4[reviewed_key] == actual:
                accepted_supersessions += 1
                continue
            index = data.index(record)
            approved = supersessions.get((rel, f"{index}/{row['field']}"))
            if not (
                approved
                and approved["local"] == row["after"]
                and approved["after"] == actual
                and approved["source_commit"].startswith("origin/main@")
            ):
                raise ClosureError(
                    f"round4 field drift: {rel}:{row['key']}:{row['field']}: "
                    f"{actual!r} != {wanted!r}"
                )
            accepted_supersessions += 1
    return accepted_supersessions


def rollback_json_fields(
    rel: str,
    kind: str,
    source: bytes,
    rows: list[dict],
    supersessions: dict[tuple[str, str], dict[str, str]],
) -> bytes:
    data = json.loads(source.decode("utf-8"))
    for row in rows:
        record = record_for(kind, str(row["key"]), data)
        actual = record.get(row["field"])
        if actual == row["after"]:
            record[row["field"]] = row["before"]
            continue
        index = data.index(record)
        approved = supersessions.get((rel, f"{index}/{row['field']}"))
        if not (
            approved
            and approved["local"] == row["after"]
            and approved["after"] == actual
            and approved["source_commit"].startswith("origin/main@")
        ):
            raise ClosureError(
                f"rollback field drift: {rel}:{row['key']}:{row['field']}: {actual!r}"
            )
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def verify(root: Path, manifest_path: Path, state: Path, expected: str = "after") -> dict:
    # Verification is intentionally portable across clean Git checkouts.  The
    # checkpoint's manifest snapshot and per-target prepared/base files remain
    # byte-bound below; only the historical absolute checkout path is ignored.
    # Mutating apply/rollback operations retain the strict root binding.
    saved, manifest = load_state(
        root, manifest_path, state, allow_relocated_root=True
    )
    supersessions = load_later_supersessions(root)
    grouped: dict[str, list[dict]] = {}
    for row in manifest["changes"]:
        grouped.setdefault(row["file"], []).append(row)
    accepted_supersessions = 0
    for entry in saved["entries"]:
        accepted_supersessions += verify_entry_fields(
            root, state, entry, grouped[entry["target"]], expected, supersessions
        )
    runtime = embedded_runtime(root)
    for name in ("cardList", "eventStoryList", "pieceList", "sectionList"):
        standalone = json.loads(confined(root, f"magica/js/libs/{name}.json").read_text(encoding="utf-8"))
        key_name = {"cardList": "cardId", "eventStoryList": "storyIds", "pieceList": "pieceId", "sectionList": "sectionId"}[name]
        mapped = {str(row[key_name]): row for row in standalone}
        if runtime.get(name) != mapped: raise ClosureError(f"embedded runtime mismatch: {name}")
    retained = verify_retained(root, manifest)
    return {
        "status": "PASS",
        "mode": f"verify-{expected}",
        "changes": 39,
        "targets": len(saved["entries"]),
        "generated_runtime": 1,
        "protected_retained": retained,
        "runtime_dictionary_matches": 4,
        "json_field_scoped_verification": 1,
        "approved_later_authority_supersessions": accepted_supersessions,
    }


def write_state(state: Path, saved: dict) -> None:
    atomic_write(state_manifest(state), (json.dumps(saved, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def apply(root: Path, manifest_path: Path, state: Path) -> dict:
    saved, _ = load_state(root, manifest_path, state); written: list[str] = []
    try:
        for entry in saved["entries"]:
            rel = entry["target"]; path = confined(root, rel); base = (state / "bases" / rel).read_bytes(); after = (state / "prepared" / rel).read_bytes()
            if path.read_bytes() not in (base, after): raise ClosureError(f"unexpected product state: {rel}")
            if path.read_bytes() != after: atomic_write(path, after); written.append(rel)
        run_injector(root)
        result = verify(root, manifest_path, state, "after")
    except BaseException:
        for rel in reversed(written): atomic_write(confined(root, rel), (state / "bases" / rel).read_bytes())
        run_injector(root); raise
    saved.update(mode="applied-and-verified", product_tree_writes=len(written) + 1); write_state(state, saved)
    atomic_write(state / "modified_verification.json", (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return result


def rollback(root: Path, manifest_path: Path, state: Path) -> dict:
    saved, manifest = load_state(root, manifest_path, state); verify(root, manifest_path, state, "after")
    grouped: dict[str, list[dict]] = {}
    for row in manifest["changes"]: grouped.setdefault(row["file"], []).append(row)
    supersessions = load_later_supersessions(root)
    restored: list[str] = []
    originals: dict[str, bytes] = {}
    try:
        for entry in saved["entries"]:
            rel = entry["target"]; path = confined(root, rel); originals[rel] = path.read_bytes()
            if entry["kind"] == "css":
                replacement = (state / "bases" / rel).read_bytes()
            else:
                replacement = rollback_json_fields(
                    rel, entry["kind"], originals[rel], grouped[rel], supersessions
                )
            atomic_write(path, replacement); restored.append(rel)
        run_injector(root)
        result = verify(root, manifest_path, state, "before")
    except BaseException:
        for rel in restored: atomic_write(confined(root, rel), originals[rel])
        run_injector(root); raise
    saved.update(mode="rolled-back-and-verified", product_tree_writes=0); write_state(state, saved)
    atomic_write(state / "rollback_verification.json", (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "apply", "verify", "rollback", "verify_before"): modes.add_argument("--" + name.replace("_", "-"), action="store_true")
    parser.add_argument("--repo-root", type=Path, default=ROOT); parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST); parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args(); root, manifest_path, state = args.repo_root.resolve(), args.manifest.resolve(), args.state_dir.resolve()
    result = prepare(root, manifest_path, state) if args.prepare else apply(root, manifest_path, state) if args.apply else rollback(root, manifest_path, state) if args.rollback else verify(root, manifest_path, state, "before" if args.verify_before else "after")
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
