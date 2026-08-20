#!/usr/bin/env python3
"""Bind the fixed madomagi native repair overlay to the repository product tree.

Only ``madomagi/resource/image_native/**`` is eligible.  The tool can copy the
user-provided repair directory into the repository and writes a deterministic
path/size manifest.  Scenario, database, and asset-manifest files are outside
this contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile


SCHEMA = "magireco-cn-madomagi-repair/v1"
PREFIX = "madomagi/resource/image_native/"
MANIFEST = "madomagi/repair_manifest.json"


class RepairError(RuntimeError):
    pass


def collect(source_root: Path) -> list[dict[str, object]]:
    source_root = source_root.resolve()
    image_native = source_root / "resource" / "image_native"
    if not image_native.is_dir():
        raise RepairError(f"missing repair subtree: {image_native}")
    entries: list[dict[str, object]] = []
    for source in sorted(image_native.rglob("*")):
        if source.is_symlink():
            raise RepairError(f"symlink is forbidden: {source}")
        if not source.is_file():
            continue
        suffix = source.relative_to(source_root).as_posix()
        member = f"madomagi/{suffix}"
        pure = PurePosixPath(member)
        if pure.is_absolute() or ".." in pure.parts or not member.startswith(PREFIX):
            raise RepairError(f"unsafe repair path: {member}")
        entries.append({"path": member, "bytes": source.stat().st_size})
    if not entries:
        raise RepairError("repair source is empty")
    return entries


def sync(source_root: Path, repo_root: Path, entries: list[dict[str, object]]) -> None:
    source_root = source_root.resolve()
    repo_root = repo_root.resolve()
    destination = repo_root / "madomagi" / "resource" / "image_native"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as raw:
        staged = Path(raw) / "image_native"
        shutil.copytree(source_root / "resource" / "image_native", staged)
        for entry in entries:
            rel = PurePosixPath(str(entry["path"])).relative_to(PREFIX.rstrip("/"))
            copied = staged.joinpath(*rel.parts)
            original = source_root.joinpath(*PurePosixPath(str(entry["path"])[len("madomagi/"):]).parts)
            if copied.read_bytes() != original.read_bytes():
                raise RepairError(f"staged repair differs from source: {entry['path']}")
        if destination.exists():
            shutil.rmtree(destination)
        staged.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()

    entries = collect(args.source)
    if args.sync:
        sync(args.source, args.repo, entries)
    manifest = {
        "schema": SCHEMA,
        "source_fixture": "A:/madomagi",
        "package_prefix": PREFIX,
        "file_count": len(entries),
        "total_bytes": sum(int(entry["bytes"]) for entry in entries),
        "entries": entries,
    }
    out = args.repo.resolve() / MANIFEST
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": "PASS", "manifest": str(out), "files": len(entries),
                      "bytes": manifest["total_bytes"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
