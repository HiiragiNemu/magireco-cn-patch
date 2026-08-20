#!/usr/bin/env python3
"""Apply, verify, or roll back exact visible-UI localization edits.

The manifest is intentionally literal and path-scoped.  It never performs a
repository-wide replacement and it fails before writing if any expected source
literal has drifted.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    REPO
    / "magica"
    / "research"
    / "totentanz-full-localization-20260817"
    / "visible-ui"
    / "visible_ui_manifest.json"
)


def load_manifest(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("manifest items must be a non-empty list")
    seen: set[str] = set()
    for item in items:
        item_id = item.get("item_id")
        if not item_id or item_id in seen:
            raise ValueError(f"invalid or duplicate item_id: {item_id!r}")
        seen.add(item_id)
        if item.get("operation") not in {"replace", "append"}:
            raise ValueError(f"unsupported operation for {item_id}")
        rel = Path(item["path"])
        if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != "magica":
            raise ValueError(f"path escapes magica product tree: {rel}")
    return items


def read_utf8(path: Path) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError(f"binary file is not allowed: {path}")
    return raw.decode("utf-8")


def append_block(text: str, block: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    normalized = block.replace("\r\n", "\n").replace("\n", newline)
    if text and not text.endswith(("\n", "\r")):
        text += newline
    return text + normalized + ("" if normalized.endswith(newline) else newline)


def remove_appended_block(text: str, block: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    normalized = block.replace("\r\n", "\n").replace("\n", newline)
    candidates = [normalized + newline, normalized]
    for candidate in candidates:
        if text.count(candidate) == 1:
            return text.replace(candidate, "", 1)
    raise ValueError("appended block is not present exactly once")


def inspect(item: dict, text: str) -> dict:
    if item["operation"] == "replace":
        return {
            "before_count": text.count(item["before"]),
            "after_count": text.count(item["after"]),
        }
    return {
        "before_count": 0,
        "after_count": text.count(item["block"]),
    }


def require_state(item: dict, counts: dict, state: str) -> None:
    expected = int(item.get("count", 1))
    baseline_after = int(item.get("baseline_after_count", 0))
    if state == "before":
        want = (
            (expected, baseline_after)
            if item["operation"] == "replace"
            else (0, 0)
        )
    else:
        want = (
            (0, baseline_after + expected)
            if item["operation"] == "replace"
            else (0, expected)
        )
    got = (counts["before_count"], counts["after_count"])
    if got != want:
        raise ValueError(
            f"{item['item_id']} state drift: expected {state} {want}, got {got}"
        )


def transform(item: dict, text: str, mode: str) -> str:
    if item["operation"] == "replace":
        if mode == "apply":
            return text.replace(item["before"], item["after"])
        return text.replace(item["after"], item["before"])
    if mode == "apply":
        return append_block(text, item["block"])
    return remove_appended_block(text, item["block"])


def atomic_write(path: Path, raw: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check-before", "apply", "verify", "rollback"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    items = load_manifest(args.manifest.resolve())
    source_state = "after" if args.mode in {"verify", "rollback"} else "before"
    target_state = "after" if args.mode == "apply" else "before"
    records: list[dict] = []
    original: dict[Path, bytes] = {}
    proposed: dict[Path, bytes] = {}

    for item in items:
        path = REPO / item["path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        text = read_utf8(path)
        counts = inspect(item, text)
        require_state(item, counts, source_state)
        records.append({"item_id": item["item_id"], "path": item["path"], **counts})
        if args.mode in {"apply", "rollback"}:
            original.setdefault(path, path.read_bytes())
            proposed[path] = transform(item, proposed.get(path, text.encode("utf-8")).decode("utf-8"), args.mode).encode("utf-8")

    if args.mode in {"apply", "rollback"}:
        written: list[Path] = []
        try:
            for path in sorted(proposed):
                atomic_write(path, proposed[path])
                written.append(path)
            for item in items:
                text = read_utf8(REPO / item["path"])
                require_state(item, inspect(item, text), target_state)
        except Exception:
            for path in reversed(written):
                atomic_write(path, original[path])
            raise

    report = {
        "ok": True,
        "mode": args.mode,
        "items": len(items),
        "files": len({item["path"] for item in items}),
        "records": records,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
