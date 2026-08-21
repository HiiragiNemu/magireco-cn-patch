#!/usr/bin/env python3
"""Apply, verify, or roll back the audited Pass20 official-CN replacements.

The manifest contains exact target paths and literal before/after values.  This
tool deliberately does no fuzzy matching and never touches files outside
``magica/``.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = (
    ROOT
    / "magica"
    / "i18n_audit"
    / "release_v26_authority"
    / "pass20_official_static_product_corrections.tsv"
)
FIELDS = (
    "item_id",
    "target_path",
    "before",
    "after",
    "before_count",
    "baseline_after_count",
    "evidence_locator",
    "match_method",
)

# The official CN client retained the English UI label ``BATTLE`` for this
# one training title.  A later explicit product decision translated visible
# system UI English to Chinese, so the runtime intentionally keeps the
# pre-Pass20 literal while the official source evidence remains unchanged.
# Treat that one historical official replacement as superseded rather than
# rewriting the evidence manifest to falsely claim ``战斗`` came from CN.
SUPERSEDED_PRODUCT_ROWS = {
    "LOW-MT-01864": ("战斗 ◆ 上级", "BATTLE ◆ 上级"),
}


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"unexpected manifest columns: {reader.fieldnames!r}")
        rows = list(reader)
    if not rows:
        raise ValueError("empty Pass20 correction manifest")
    return rows


def target_path(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe target path: {value!r}")
    target = (ROOT / relative).resolve()
    magica = (ROOT / "magica").resolve()
    if target != magica and magica not in target.parents:
        raise ValueError(f"target escapes magica/: {value!r}")
    return target


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def expected(row: dict[str, str], state: str) -> tuple[int, int]:
    changed = int(row["before_count"])
    existing = int(row["baseline_after_count"])
    superseded = SUPERSEDED_PRODUCT_ROWS.get(row["item_id"])
    if superseded is not None:
        if (row["before"], row["after"]) != superseded:
            raise ValueError(f"superseded product contract drifted: {row['item_id']}")
        if state == "applied":
            return changed, existing
    if state == "baseline":
        return changed, existing
    return 0, existing + changed


def verify(rows: list[dict[str, str]], state: str) -> None:
    failures: list[str] = []
    for row in rows:
        path = target_path(row["target_path"])
        text = read_text(path)
        want_before, want_after = expected(row, state)
        got_before = text.count(row["before"])
        got_after = text.count(row["after"])
        if (got_before, got_after) != (want_before, want_after):
            failures.append(
                f"{row['item_id']} {row['target_path']}: "
                f"before/after={got_before}/{got_after}, "
                f"expected={want_before}/{want_after}"
            )
    if failures:
        raise ValueError("Pass20 verification failed:\n" + "\n".join(failures))
    print(f"PASS: {len(rows)} exact replacements are in {state} state")


def mutate(rows: list[dict[str, str]], direction: str) -> None:
    source_state = "baseline" if direction == "apply" else "applied"
    target_state = "applied" if direction == "apply" else "baseline"
    verify(rows, source_state)
    grouped: dict[Path, list[dict[str, str]]] = {}
    for row in rows:
        if row["item_id"] in SUPERSEDED_PRODUCT_ROWS:
            continue
        grouped.setdefault(target_path(row["target_path"]), []).append(row)
    for path, file_rows in grouped.items():
        text = read_text(path)
        for row in file_rows:
            old, new = (
                (row["before"], row["after"])
                if direction == "apply"
                else (row["after"], row["before"])
            )
            text = text.replace(old, new, int(row["before_count"]))
        write_text(path, text)
    verify(rows, target_state)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "verify", "rollback"))
    parser.add_argument("--state", choices=("baseline", "applied"), default="applied")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    rows = load_rows(args.manifest.resolve())
    if args.action == "verify":
        verify(rows, args.state)
    else:
        mutate(rows, args.action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
