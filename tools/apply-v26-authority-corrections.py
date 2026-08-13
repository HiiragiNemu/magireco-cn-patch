#!/usr/bin/env python3
"""Apply or verify the v26 per-field authority correction manifest.

The manifest stores an exact before/after image for every changed visible field.
JSON is rewritten with the repository's deterministic UTF-8/LF/indent-2 format.
For the one static JS label, an exact single-occurrence literal replacement is
used; code identifiers and CSS are never rewritten by this tool.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = (
    ROOT
    / "magica"
    / "i18n_audit"
    / "release_v26_authority"
    / "pass18_authority_corrections.tsv"
)


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    required = {
        "change_id", "file", "json_pointer", "stable_key", "field",
        "before", "after", "source_tier", "evidence",
        "translation_method", "manual_review_status", "confidence",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"invalid manifest schema: {path}")
    identities = [(row["file"], row["json_pointer"]) for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate file/pointer in authority manifest")
    return rows


def unescape_pointer(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def resolve_pointer(document, pointer: str):
    if not pointer.startswith("/"):
        raise ValueError(f"not a JSON pointer: {pointer}")
    tokens = [unescape_pointer(token) for token in pointer.split("/")[1:]]
    parent = document
    for token in tokens[:-1]:
        parent = parent[int(token)] if isinstance(parent, list) else parent[token]
    leaf = tokens[-1]
    return parent, int(leaf) if isinstance(parent, list) else leaf


def process_json(path: Path, rows: list[dict[str, str]], apply: bool):
    document = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    states = Counter()
    for row in rows:
        parent, leaf = resolve_pointer(document, row["json_pointer"])
        current = parent[leaf]
        if current == row["after"]:
            states["already_after"] += 1
        elif current == row["before"]:
            states["before"] += 1
            if apply:
                parent[leaf] = row["after"]
                changed += 1
        else:
            raise AssertionError(
                f"preimage drift {row['file']}#{row['json_pointer']}: "
                f"expected {row['before']!r} or {row['after']!r}, got {current!r}"
            )
    if apply and changed:
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return changed, states


def process_text(path: Path, rows: list[dict[str, str]], apply: bool):
    text = path.read_text(encoding="utf-8")
    changed = 0
    states = Counter()
    for row in rows:
        before_count = text.count(row["before"])
        after_count = text.count(row["after"])
        if after_count == 1 and before_count == 0:
            states["already_after"] += 1
        elif before_count == 1 and after_count == 0:
            states["before"] += 1
            if apply:
                text = text.replace(row["before"], row["after"], 1)
                changed += 1
        else:
            raise AssertionError(
                f"literal preimage drift {row['file']}: "
                f"before_count={before_count}, after_count={after_count}"
            )
    if apply and changed:
        path.write_text(text, encoding="utf-8", newline="\n")
    return changed, states


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = args.manifest.resolve()
    rows = read_manifest(manifest)
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["file"], []).append(row)

    total_changed = 0
    total_states = Counter()
    files = []
    for relative, file_rows in sorted(grouped.items()):
        path = ROOT / relative
        if path.suffix.lower() == ".json":
            changed, states = process_json(path, file_rows, args.apply)
        else:
            changed, states = process_text(path, file_rows, args.apply)
        total_changed += changed
        total_states.update(states)
        files.append({"file": relative, "rows": len(file_rows), "changed": changed})

    if not args.apply and total_states["before"]:
        raise AssertionError(
            f"verification found {total_states['before']} unapplied manifest rows"
        )
    print(json.dumps({
        "schema": "magireco-cn-v26-authority-corrections/v1",
        "mode": "apply" if args.apply else "verify",
        "status": "PASS",
        "manifest_rows": len(rows),
        "files": files,
        "changed": total_changed,
        "states": dict(total_states),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
