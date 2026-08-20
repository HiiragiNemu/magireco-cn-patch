#!/usr/bin/env python3
"""Deterministically apply, verify, or roll back visible-text closure round 6."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_DEFAULT = Path(__file__).resolve().parents[1]
STATE_REL = Path("magica/research/totentanz-full-localization-20260817/visible-closure-round6/runtime")
SOURCE_ROUTER_DEFAULT = Path(r"A:\totentanz-frontend\js\quest\secondPartLast\Router.js")

SPECS = [
    {"path": "template/arena/ArenaTop.html", "kind": "html", "before_state": "present", "operations": [
        {"before": "NEXT...&nbsp;", "after": "下一镜层…&nbsp;", "source_tier": "root-reviewed"}]},
    {"path": "template/follow/FollowTop.html", "kind": "html", "before_state": "present", "operations": [
        {"before": f">Rank{rank}〜<", "after": f">等级{rank}～<", "source_tier": "root-reviewed"}
        for rank in (1, 10, 20, 40, 60, 80, 100)]},
    {"path": "template/memoria/MemoriaPopup.html", "kind": "html", "before_state": "present", "operations": [
        {"before": '<span class="c_gold">NEXT</span>&nbsp;', "after": '<span class="c_gold">距升级</span>&nbsp;',
         "source_tier": "root-reviewed-context-equivalent"}]},
    {"path": "template/quest/MainQuest.html", "kind": "html", "before_state": "present", "operations": [
        {"before": '<span class="chapterNo">Ch.<span>', "after": '<span class="chapterNo"><span>',
         "source_tier": "official-cn-same-node-structure"},
        {"before": '<span class="sectionNo">Ch.<%="<%= model.chapterNoForView %\\>"%>: <%="<%= model.section.genericIndex %\\>"%>话</span>',
         "after": '<span class="sectionNo"><%="<%= model.chapterNoForView %\\>"%> <%="<%= model.section.genericIndex %\\>"%>话</span>',
         "source_tier": "official-cn-same-node-structure"},
        {"before": "※You cannot retry the challenge.", "after": "※该挑战无法再次进行。", "source_tier": "root-reviewed"}]},
    {"path": "template/quest/SubQuest.html", "kind": "html", "before_state": "present", "operations": [
        {"before": '<span class="chapterNo">Ch <span>', "after": '<span class="chapterNo"><span>',
         "source_tier": "official-cn-same-node-structure"},
        {"before": '<span class="sectionNo">Ch.<%="<%= model.chapterNoForView %\\>"%>: <%="<%= model.section.genericIndex %\\>"%>话</span>',
         "after": '<span class="sectionNo"><%="<%= model.chapterNoForView %\\>"%> <%="<%= model.section.genericIndex %\\>"%>话</span>',
         "source_tier": "official-cn-same-node-structure"}]},
    {"path": "js/quest/secondPartLast/Router.js", "kind": "js", "before_state": "absent", "operations": [
        {"before": 'a.battleTitle="LAST BATTLE"', "after": 'a.battleTitle="最终战"', "source_tier": "root-reviewed"}]},
]

OFFICIAL_CONNECT_IDS = (10014, 10015, 10025, 10045, 10184, 10185, 10193, 10194, 10195)


def clean(data: bytes) -> bytes:
    return data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def safe_product_path(repo: Path, relative: str) -> Path:
    root = (repo / "magica").resolve()
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError(f"target escapes magica: {relative}")
    return target


def state_path(repo: Path, recorded: str) -> Path:
    path = (repo / recorded).resolve()
    if repo.resolve() not in path.parents:
        raise ValueError(f"state path escapes repo: {recorded}")
    return path


def ejs_tokens(text: str) -> list[str]:
    result, pos = [], 0
    while True:
        start = text.find("<%", pos)
        if start < 0:
            return result
        end = text.find("%>", start + 2)
        if end < 0:
            raise ValueError("unterminated EJS token")
        result.append(text[start : end + 2])
        pos = end + 2


def build_after(spec: dict, before: bytes) -> bytes:
    source = clean(before).decode("utf-8")
    result = source
    for operation in spec["operations"]:
        old, new = operation["before"], operation["after"]
        if result.count(old) != 1:
            raise ValueError(f"{spec['path']}: exact before count is not one: {old}")
        if new in result:
            raise ValueError(f"{spec['path']}: after literal already present: {new}")
        result = result.replace(old, new, 1)
    if spec["kind"] == "html" and ejs_tokens(source) != ejs_tokens(result):
        raise ValueError(f"{spec['path']}: EJS tokens changed")
    return result.encode("utf-8")


def patch_bytes(repo: Path, entries: list[dict]) -> bytes:
    chunks: list[str] = []
    for row in entries:
        before = state_path(repo, row["before_path"]).read_text(encoding="utf-8") if row["before_state"] == "present" else ""
        after = state_path(repo, row["after_path"]).read_text(encoding="utf-8")
        old_name = "a/" + row["product_path"] if row["before_state"] == "present" else "/dev/null"
        chunks.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=old_name,
                                           tofile="b/" + row["product_path"]))
    return "".join(chunks).encode("utf-8")


def prepare(repo: Path, source_router: Path, state: Path) -> dict:
    if not source_router.is_file():
        raise FileNotFoundError(source_router)
    entries = []
    for spec in SPECS:
        target = safe_product_path(repo, spec["path"])
        if spec["before_state"] == "present":
            if not target.is_file():
                raise FileNotFoundError(target)
            # Preserve the original bytes exactly for rollback.  build_after()
            # performs the deliberate LF normalization only for the product.
            before = target.read_bytes()
        else:
            if target.exists():
                raise ValueError(f"new target already exists: {target}")
            before = clean(source_router.read_bytes())
        after = build_after(spec, before)
        before_path, after_path = state / "before" / spec["path"], state / "after" / spec["path"]
        write_atomic(before_path, before)
        write_atomic(after_path, after)
        entries.append({
            "product_path": "magica/" + spec["path"], "kind": spec["kind"], "before_state": spec["before_state"],
            "before_path": str(before_path.relative_to(repo)).replace("\\", "/"),
            "after_path": str(after_path.relative_to(repo)).replace("\\", "/"),
            "before_bytes": len(before), "after_bytes": len(after), "operations": spec["operations"],
        })
    manifest = {
        "schema": 1, "scope": "visible-closure-round6", "target_count": len(entries),
        "literal_count": sum(len(row["operations"]) for row in entries), "entries": entries,
        "official_connect_retained": {"stable_skill_ids": list(OFFICIAL_CONNECT_IDS), "count": 9,
            "reason": "official CN stable-ID shortDescription uses Connect; the conditional user wording does not override it"},
    }
    rollback = {"schema": 1, "command": "python tools/apply-visible-closure-round6.py --rollback", "entries": [
        {"product_path": row["product_path"], "required_current_bytes_path": row["after_path"],
         "restore_state": row["before_state"], "restore_bytes_path": row["before_path"] if row["before_state"] == "present" else None}
        for row in entries]}
    write_atomic(state / "manifest.json", json_bytes(manifest))
    write_atomic(state / "rollback.json", json_bytes(rollback))
    write_atomic(state / "visible_closure_round6.patch", patch_bytes(repo, entries))
    return manifest


def load_manifest(repo: Path, state: Path) -> dict:
    manifest = json.loads((state / "manifest.json").read_text(encoding="utf-8"))
    rows = manifest.get("entries")
    expected = ["magica/" + spec["path"] for spec in SPECS]
    if manifest.get("target_count") != 6 or manifest.get("literal_count") != 15:
        raise ValueError("manifest counts mismatch")
    if not isinstance(rows, list) or [row.get("product_path") for row in rows] != expected:
        raise ValueError("manifest fixed path/order mismatch")
    for spec, row in zip(SPECS, rows):
        if row.get("kind") != spec["kind"] or row.get("before_state") != spec["before_state"]:
            raise ValueError(f"manifest role mismatch: {row.get('product_path')}")
        expected_before = str((state / "before" / spec["path"]).relative_to(repo)).replace("\\", "/")
        expected_after = str((state / "after" / spec["path"]).relative_to(repo)).replace("\\", "/")
        if row.get("before_path") != expected_before or row.get("after_path") != expected_after:
            raise ValueError(f"manifest state path mismatch: {row.get('product_path')}")
        if row.get("operations") != spec["operations"]:
            raise ValueError(f"manifest operation mismatch: {row.get('product_path')}")
        before, after = state_path(repo, row["before_path"]).read_bytes(), state_path(repo, row["after_path"]).read_bytes()
        if len(before) != row.get("before_bytes") or len(after) != row.get("after_bytes"):
            raise ValueError(f"staging byte-count drift: {row.get('product_path')}")
        if build_after(spec, before) != after:
            raise ValueError(f"staging semantic drift: {row.get('product_path')}")
    return manifest


def gate_before(repo: Path, row: dict) -> None:
    target = repo / row["product_path"]
    if row["before_state"] == "absent":
        if target.exists():
            raise ValueError(f"before gate expected absent: {row['product_path']}")
    elif not target.is_file() or target.read_bytes() != state_path(repo, row["before_path"]).read_bytes():
        raise ValueError(f"before gate drift: {row['product_path']}")


def apply(repo: Path, state: Path, fail_after: int | None = None) -> dict:
    manifest = load_manifest(repo, state)
    for row in manifest["entries"]:
        gate_before(repo, row)
    changed: list[tuple[Path, bytes | None]] = []
    try:
        for index, row in enumerate(manifest["entries"], 1):
            target, original = repo / row["product_path"], None
            if target.exists():
                original = target.read_bytes()
            write_atomic(target, state_path(repo, row["after_path"]).read_bytes())
            changed.append((target, original))
            if fail_after == index:
                raise RuntimeError("synthetic apply failure")
    except Exception:
        for target, original in reversed(changed):
            if original is None:
                target.unlink(missing_ok=True)
            else:
                write_atomic(target, original)
        raise
    record = {"operation": "apply", "result": "passed", "changed_files": 6, "literal_changes": 15}
    write_atomic(state / "apply-record.json", json_bytes(record))
    return record


def run_command(command: list[str], cwd: Path) -> dict:
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, encoding="utf-8")
    return {"command": subprocess.list2cmdline(command), "cwd": str(cwd), "stdout": proc.stdout,
            "stderr": proc.stderr, "exit_status": proc.returncode}


def connect_retained(repo: Path) -> dict:
    data = json.loads((repo / "magica/js/libs/cardSkillMap.json").read_text(encoding="utf-8-sig"))
    values = {}
    for skill_id in OFFICIAL_CONNECT_IDS:
        value = data[str(skill_id)]["shortDescription"]
        if "Connect后" not in value:
            raise ValueError(f"official Connect literal drift: {skill_id}")
        values[str(skill_id)] = value
    runtime = (repo / "magica/js/libs/jquery-3.7.1.min.js").read_text(encoding="utf-8-sig")
    if runtime.count("Connect后") != 9:
        raise ValueError("embedded official Connect count drift")
    return {"stable_skill_ids": values, "standalone_count": 9, "embedded_runtime_count": 9,
            "status": "official-cn-retained"}


def verify(repo: Path, state: Path) -> dict:
    manifest = load_manifest(repo, state)
    checked = []
    for spec, row in zip(SPECS, manifest["entries"]):
        target, after = repo / row["product_path"], state_path(repo, row["after_path"]).read_bytes()
        if not target.is_file() or clean(target.read_bytes()) != after:
            raise ValueError(f"modified byte gate failed: {row['product_path']}")
        text = after.decode("utf-8")
        for operation in row["operations"]:
            if operation["before"] in text or text.count(operation["after"]) != 1:
                raise ValueError(f"literal verification failed: {row['product_path']}")
        if spec["kind"] == "html":
            before = clean(state_path(repo, row["before_path"]).read_bytes()).decode("utf-8")
            if ejs_tokens(before) != ejs_tokens(text):
                raise ValueError(f"EJS verification failed: {row['product_path']}")
        checked.append({"product_path": row["product_path"], "bytes": len(after), "status": "exact"})
    commands = [run_command(["node", "--check", str(repo / "magica/js/quest/secondPartLast/Router.js")], repo)]
    if any(row["exit_status"] != 0 for row in commands):
        raise ValueError("JavaScript syntax command failed")
    report = {"schema": 1, "result": "passed", "checked_files": 6, "literal_changes": 15,
              "entries": checked, "commands": commands, "official_connect_retained": connect_retained(repo),
              "product_write_scope": [row["product_path"] for row in manifest["entries"]]}
    write_atomic(state / "verification.json", json_bytes(report))
    return report


def rollback(repo: Path, state: Path, fail_after: int | None = None) -> dict:
    manifest = load_manifest(repo, state)
    for row in manifest["entries"]:
        target = repo / row["product_path"]
        if not target.is_file() or clean(target.read_bytes()) != state_path(repo, row["after_path"]).read_bytes():
            raise ValueError(f"rollback after gate failed: {row['product_path']}")
    changed: list[tuple[Path, bytes]] = []
    removed = 0
    try:
        for index, row in enumerate(manifest["entries"], 1):
            target, after = repo / row["product_path"], (repo / row["product_path"]).read_bytes()
            changed.append((target, after))
            if row["before_state"] == "present":
                write_atomic(target, state_path(repo, row["before_path"]).read_bytes())
            else:
                target.unlink()
                removed += 1
            if fail_after == index:
                raise RuntimeError("synthetic rollback failure")
    except Exception:
        for target, after in reversed(changed):
            write_atomic(target, after)
        raise
    record = {"operation": "rollback", "result": "passed", "restored_existing": 5, "removed_created": removed}
    write_atomic(state / "rollback-record.json", json_bytes(record))
    return record


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--verify", action="store_true")
    modes.add_argument("--rollback", action="store_true")
    parser.add_argument("--repo", type=Path, default=REPO_DEFAULT)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--source-router", type=Path, default=SOURCE_ROUTER_DEFAULT)
    parser.add_argument("--synthetic-fail-after", type=int)
    args = parser.parse_args()
    repo = args.repo.resolve()
    state = args.state.resolve() if args.state else repo / STATE_REL
    if args.prepare:
        result = prepare(repo, args.source_router.resolve(), state)
    elif args.apply:
        result = apply(repo, state, args.synthetic_fail_after)
    elif args.verify:
        result = verify(repo, state)
    else:
        result = rollback(repo, state, args.synthetic_fail_after)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
