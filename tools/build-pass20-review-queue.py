#!/usr/bin/env python3
"""Rebuild the unresolved current-text Pass20 queue from frozen decisions and authority resolutions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
DECISIONS = AUDIT / "dsv4_human_decisions.tsv"
RESOLUTIONS = AUDIT / "pass20_authority_resolutions.tsv"
OUTPUT = AUDIT / "pass20_remaining_manual_review.tsv"
REQUIRED_VERDICTS = {"manual-required", "correction", "unresolved"}
DECISION_FIELDS = {
    "human_decision", "reviewer", "timestamp", "final_value", "human_revision", "human_notes",
}


class QueueError(RuntimeError):
    pass


def load_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw:
        raise QueueError(f"TSV must be UTF-8-no-BOM with LF endings: {path}")
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if not header or any(None in row for row in rows):
        raise QueueError(f"invalid TSV structure: {path}")
    return header, rows


def build(decisions_path: Path, resolutions_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    header, decisions = load_tsv(decisions_path)
    _, resolutions = load_tsv(resolutions_path)
    resolution_ids: set[str] = set()
    for row in resolutions:
        item_id = row["item_id"]
        if not item_id or item_id in resolution_ids:
            raise QueueError(f"authority resolutions contain a missing or duplicate item_id: {item_id!r}")
        resolution_ids.add(item_id)
    decision_ids: set[str] = set()
    queue: list[dict[str, str]] = []
    for row in decisions:
        item_id = row["item_id"]
        if not item_id or item_id in decision_ids:
            raise QueueError(f"decision table contains a missing or duplicate item_id: {item_id!r}")
        decision_ids.add(item_id)
        if (
            row["review_kind"] == "current-low-tier-translation-review"
            and row["parent_verdict"] in REQUIRED_VERDICTS
            and item_id not in resolution_ids
        ):
            if any(row[field] for field in DECISION_FIELDS):
                raise QueueError(f"unresolved queue candidate already carries a human decision: {item_id}")
            queue.append(row)
    if len(queue) != 199 or len({row["item_id"] for row in queue}) != 199:
        raise QueueError(f"expected 199 unresolved current-text items, found {len(queue)}")
    if "LOW-MT-01485" in {row["item_id"] for row in queue}:
        raise QueueError("LOW-MT-01485 must be closed by existing official authority")
    return header, queue


def write(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--resolutions", type=Path, default=RESOLUTIONS)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    try:
        header, rows = build(args.decisions, args.resolutions)
        write(args.out, header, rows)
        print(f"PASS: wrote {len(rows)} unresolved current-text items to {args.out}")
        return 0
    except (QueueError, OSError, UnicodeError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
