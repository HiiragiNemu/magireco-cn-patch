#!/usr/bin/env python3
"""Apply, verify, or roll back stable-key runtime dictionary changes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parent.parent
LIST_KEYS = {
    "chapterList.json": ("chapterId",),
    "charaMessageList.json": ("charaNo", "messageId"),
    "doppelList.json": ("id",),
    "itemList.json": ("itemCode",),
    "pieceList.json": ("pieceId",),
    "sectionList.json": ("sectionId",),
    "shopItemList.json": ("id",),
}


class ApplyError(RuntimeError):
    pass


def record_for(file_name: str, key: str, data: object) -> dict[str, object]:
    if isinstance(data, dict):
        record = data.get(str(key))
        if not isinstance(record, dict):
            raise ApplyError(f"missing key {file_name}:{key}")
        return record
    fields = LIST_KEYS[file_name]
    parts = key.split("/")
    found = [
        row for row in data
        if all(str(row.get(field)) == value for field, value in zip(fields, parts))
    ]
    if len(found) != 1:
        raise ApplyError(f"stable key is not unique {file_name}:{key} count={len(found)}")
    return found[0]


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def run(manifest_path: Path, mode: str, root: Path = ROOT) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "magireco-cn-runtime-dictionary-localization/v1":
        raise ApplyError("manifest schema mismatch")
    changes = manifest.get("changes")
    if not isinstance(changes, list) or len(changes) != manifest.get("change_count"):
        raise ApplyError("manifest change count mismatch")
    grouped: dict[Path, list[dict[str, object]]] = {}
    for change in changes:
        rel = Path(change["file"])
        if rel.is_absolute() or ".." in rel.parts or rel.parts[:3] != ("magica", "js", "libs"):
            raise ApplyError(f"path outside runtime dictionary tree: {rel}")
        grouped.setdefault(root.resolve() / rel, []).append(change)

    originals: dict[Path, bytes] = {}
    outputs: dict[Path, bytes] = {}
    expected_field = "after" if mode in {"verify", "rollback"} else "before"
    desired_field = "before" if mode == "rollback" else "after"
    for path, file_changes in grouped.items():
        originals[path] = path.read_bytes()
        data = json.loads(originals[path].decode("utf-8"))
        for change in file_changes:
            record = record_for(path.name, str(change["key"]), data)
            actual = record.get(change["field"])
            expected = change[expected_field]
            if actual != expected:
                raise ApplyError(
                    f"field drift {path.name}:{change['key']}:{change['field']}: "
                    f"expected={expected!r} actual={actual!r}"
                )
            if mode != "verify":
                record[change["field"]] = change[desired_field]
        outputs[path] = (
            json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")

    if mode != "verify":
        written: list[Path] = []
        try:
            for path in sorted(outputs):
                atomic_write(path, outputs[path])
                written.append(path)
        except Exception:
            for path in reversed(written):
                atomic_write(path, originals[path])
            raise
    return {
        "schema": "magireco-cn-runtime-dictionary-application/v1",
        "status": "PASS",
        "mode": mode,
        "changes": len(changes),
        "files": len(grouped),
        "field_drifts": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true")
    group.add_argument("--verify", action="store_true")
    group.add_argument("--rollback", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    mode = "apply" if args.apply else "verify" if args.verify else "rollback"
    result = run(args.manifest, mode, args.root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
