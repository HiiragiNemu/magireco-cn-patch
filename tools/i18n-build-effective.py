#!/usr/bin/env python3
"""Build an audit-only effective view of the migrated i18n maintenance inputs.

This command never reads or writes ``magica/``.  It combines the four TSV
maintenance inputs according to the documented authority layers, emits provenance
and conflict reports, and fails after writing the reports when two different
translations have the same highest authority weight.

The migrated frontend translations are deliberately *not* called human reviewed.
Their per-candidate lineage is frozen in ``migration-source-summary.json`` from the
legacy repository's final ``git blame`` evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_MAINTENANCE_ORDER = (
    ("official_cn_dump", 500),
    ("wiki", 400),
    ("existing_human_reviewed", 300),
    ("legacy_unverified_ai_assisted", 200),
    ("new_proposal", 100),
)

PROVENANCE_COLUMNS = (
    "candidate_id",
    "key",
    "scope",
    "path_prefix",
    "source_text",
    "candidate_cn",
    "status",
    "authority",
    "weight",
    "selected",
    "source_file",
    "source_line",
    "source_batch",
    "source_commit",
    "evidence",
)
EFFECTIVE_COLUMNS = (
    "key",
    "scope",
    "path_prefix",
    "source_text",
    "selected_cn",
    "authority",
    "weight",
    "source_file",
    "source_line",
    "source_batch",
    "evidence",
)
CONFLICT_COLUMNS = (
    "key",
    "scope",
    "path_prefix",
    "source_text",
    "resolution",
    "fatal",
    "winner_cn",
    "winner_authority",
    "competing_candidates",
    "evidence",
)


class AuditError(ValueError):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return json.load(handle)


def normalized_lf_bytes(path: Path) -> bytes:
    text = path.read_text(encoding="utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_lf_bytes(path)).hexdigest()


def fingerprint(source_text: str, candidate_cn: str) -> str:
    return hashlib.sha256((source_text + "\0" + candidate_cn).encode("utf-8")).hexdigest()


def stable_key(scope: str, path_prefix: str, source_text: str) -> str:
    digest = hashlib.sha256(
        (scope + "\0" + path_prefix + "\0" + source_text).encode("utf-8")
    ).hexdigest()[:20]
    return f"{scope}:{digest}"


def candidate_id(source_file: str, source_line: int, key: str, candidate_cn: str) -> str:
    return hashlib.sha256(
        f"{source_file}\0{source_line}\0{key}\0{candidate_cn}".encode("utf-8")
    ).hexdigest()[:24]


def read_data_rows(path: Path) -> list[tuple[int, list[str]]]:
    rows: list[tuple[int, list[str]]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line_no, row in enumerate(csv.reader(handle, delimiter="\t"), 1):
            if not row or row[0].startswith("#"):
                continue
            rows.append((line_no, row))
    return rows


def validate_policy(policy: dict[str, Any]) -> dict[str, int]:
    actual = tuple(
        (entry.get("id"), entry.get("weight"))
        for entry in policy.get("maintenance_input_authority_order", [])
    )
    if actual != EXPECTED_MAINTENANCE_ORDER:
        raise AuditError(
            "maintenance input authority order mismatch: "
            f"expected {EXPECTED_MAINTENANCE_ORDER!r}, got {actual!r}"
        )
    contract = policy.get("maintenance_input_contract", {})
    if contract.get("audit_only") is not True or contract.get("may_write_magica") is not False:
        raise AuditError("maintenance input contract must be audit-only and forbid magica writes")
    return dict(actual)


def validate_source_snapshot(
    i18n_dir: Path, migration: dict[str, Any], table_rows: dict[str, list[tuple[int, list[str]]]]
) -> None:
    expected = migration.get("source_tables", {})
    for filename, rows in table_rows.items():
        info = expected.get(filename)
        if not isinstance(info, dict):
            raise AuditError(f"migration summary missing source_tables.{filename}")
        path = i18n_dir / filename
        actual_hash = normalized_sha256(path)
        if actual_hash != info.get("normalized_lf_sha256"):
            raise AuditError(
                f"{filename} differs from its audited migration snapshot: "
                f"expected {info.get('normalized_lf_sha256')}, got {actual_hash}"
            )
        if len(rows) != info.get("data_rows"):
            raise AuditError(
                f"{filename} row count mismatch: expected {info.get('data_rows')}, got {len(rows)}"
            )


def make_candidate(
    *,
    scope: str,
    path_prefix: str,
    source_text: str,
    candidate_cn: str,
    status: str,
    authority: str,
    weights: dict[str, int],
    source_file: str,
    source_line: int,
    source_batch: str,
    source_commit: str = "",
    evidence: str,
) -> dict[str, Any]:
    key = stable_key(scope, path_prefix, source_text)
    return {
        "candidate_id": candidate_id(source_file, source_line, key, candidate_cn),
        "key": key,
        "scope": scope,
        "path_prefix": path_prefix,
        "source_text": source_text,
        "candidate_cn": candidate_cn,
        "status": status,
        "authority": authority,
        "weight": weights[authority],
        "selected": False,
        "source_file": source_file,
        "source_line": source_line,
        "source_batch": source_batch,
        "source_commit": source_commit,
        "evidence": evidence,
    }


def build_candidates(
    table_rows: dict[str, list[tuple[int, list[str]]]],
    migration: dict[str, Any],
    weights: dict[str, int],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    frontend_info = migration["source_tables"]["frontend-strings.tsv"]
    lineage = frontend_info.get("translated_candidate_lineage", {})
    commit_by_batch: dict[str, str] = {}
    for batch in frontend_info.get("translation_batches", []):
        commits = [
            item.get("sha", "") if isinstance(item, dict) else str(item)
            for item in batch.get("commits", [])
        ]
        commit_by_batch[batch["id"]] = ",".join(item for item in commits if item)

    for line_no, row in table_rows["frontend-strings.tsv"]:
        if len(row) != 5:
            raise AuditError(f"frontend-strings.tsv:{line_no}: expected 5 columns, got {len(row)}")
        ja, zh = row[0], row[1]
        if not ja:
            raise AuditError(f"frontend-strings.tsv:{line_no}: empty source text")
        if zh:
            fp = fingerprint(ja, zh)
            lineage_entry = lineage.get(fp)
            if not lineage_entry:
                raise AuditError(
                    f"frontend-strings.tsv:{line_no}: translated candidate has no migration lineage; "
                    "record it as an explicitly reviewed source or a new proposal first"
                )
            if isinstance(lineage_entry, dict):
                batch = lineage_entry.get("batch", "")
                source_commit = lineage_entry.get("commit", "")
            else:  # schema-v1 compatibility for compact hand-authored fixtures
                batch = str(lineage_entry)
                source_commit = commit_by_batch.get(batch, "")
            if not batch:
                raise AuditError(f"frontend-strings.tsv:{line_no}: empty lineage batch")
            status = "present"
            evidence = (
                "legacy git-blame lineage; AI co-author batch; no per-entry human-review evidence"
            )
        else:
            batch = "legacy-extraction-untranslated"
            source_commit = ""
            status = "absent"
            evidence = "legacy extraction row has no translation candidate"
        candidates.append(
            make_candidate(
                scope="global",
                path_prefix="",
                source_text=ja,
                candidate_cn=zh,
                status=status,
                authority="legacy_unverified_ai_assisted",
                weights=weights,
                source_file="i18n/frontend-strings.tsv",
                source_line=line_no,
                source_batch=batch,
                source_commit=source_commit,
                evidence=evidence,
            )
        )

    locks = set(migration["source_tables"]["glossary.tsv"].get("wiki_authority_locks", []))
    for line_no, row in table_rows["glossary.tsv"]:
        if len(row) != 2 or not row[0] or not row[1]:
            raise AuditError(f"glossary.tsv:{line_no}: expected two non-empty columns")
        batch = "wiki-canonical-lock" if row[0] in locks else "wiki-migrated-glossary"
        candidates.append(
            make_candidate(
                scope="global",
                path_prefix="",
                source_text=row[0],
                candidate_cn=row[1],
                status="present",
                authority="wiki",
                weights=weights,
                source_file="i18n/glossary.tsv",
                source_line=line_no,
                source_batch=batch,
                evidence=(
                    "official old-CN dump absent for this late character; Wiki selected"
                    if batch == "wiki-canonical-lock"
                    else "migrated Wiki glossary candidate"
                ),
            )
        )

    for filename, scope in (("overrides.tsv", "override"), ("fragments.tsv", "fragment")):
        for line_no, row in table_rows[filename]:
            if len(row) != 3 or not row[0] or not row[1] or not row[2]:
                raise AuditError(f"{filename}:{line_no}: expected three non-empty columns")
            candidates.append(
                make_candidate(
                    scope=scope,
                    path_prefix=row[0],
                    source_text=row[1],
                    candidate_cn=row[2],
                    status="present",
                    authority="legacy_unverified_ai_assisted",
                    weights=weights,
                    source_file=f"i18n/{filename}",
                    source_line=line_no,
                    source_batch="legacy-unverified-mixed-patch",
                    evidence="path-specific human/model patch without per-entry review provenance",
                )
            )

    return candidates


def select_effective(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate["key"]].append(candidate)

    effective: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for key in sorted(groups):
        group = groups[key]
        present = [entry for entry in group if entry["status"] == "present"]
        if not present:
            continue
        top_weight = max(entry["weight"] for entry in present)
        top = [entry for entry in present if entry["weight"] == top_weight]
        top_values = sorted({entry["candidate_cn"] for entry in top})
        fatal = len(top_values) > 1
        winner = sorted(
            top,
            key=lambda entry: (
                entry["candidate_cn"], entry["source_file"], entry["source_line"]
            ),
        )[0]
        if not fatal:
            for entry in top:
                entry["selected"] = True
            effective.append(
                {
                    "key": key,
                    "scope": winner["scope"],
                    "path_prefix": winner["path_prefix"],
                    "source_text": winner["source_text"],
                    "selected_cn": winner["candidate_cn"],
                    "authority": winner["authority"],
                    "weight": winner["weight"],
                    "source_file": winner["source_file"],
                    "source_line": winner["source_line"],
                    "source_batch": winner["source_batch"],
                    "evidence": winner["evidence"],
                }
            )

        all_values = {entry["candidate_cn"] for entry in present}
        if fatal or len(all_values) > 1:
            competing = [
                {
                    "candidate_cn": entry["candidate_cn"],
                    "authority": entry["authority"],
                    "weight": entry["weight"],
                    "source": f"{entry['source_file']}:{entry['source_line']}",
                }
                for entry in sorted(
                    present,
                    key=lambda entry: (
                        -entry["weight"], entry["candidate_cn"], entry["source_file"],
                        entry["source_line"],
                    ),
                )
            ]
            conflicts.append(
                {
                    "key": key,
                    "scope": winner["scope"],
                    "path_prefix": winner["path_prefix"],
                    "source_text": winner["source_text"],
                    "resolution": (
                        "fatal-equal-weight-conflict" if fatal else "resolved-by-higher-authority"
                    ),
                    "fatal": fatal,
                    "winner_cn": "" if fatal else winner["candidate_cn"],
                    "winner_authority": "" if fatal else winner["authority"],
                    "competing_candidates": json.dumps(
                        competing, ensure_ascii=False, separators=(",", ":")
                    ),
                    "evidence": (
                        "different targets share the highest weight; selection blocked"
                        if fatal
                        else "lower-weight candidate retained only in provenance"
                    ),
                }
            )
    return effective, conflicts


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(columns), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            cooked = {
                key: (
                    "true" if value is True else "false" if value is False else str(value)
                )
                for key, value in row.items()
            }
            writer.writerow(cooked)


def run(
    *, i18n_dir: Path, out_dir: Path, policy_path: Path, migration_path: Path
) -> tuple[dict[str, Any], int]:
    policy = load_json(policy_path)
    migration = load_json(migration_path)
    weights = validate_policy(policy)
    filenames = (
        "frontend-strings.tsv", "glossary.tsv", "overrides.tsv", "fragments.tsv"
    )
    table_rows = {name: read_data_rows(i18n_dir / name) for name in filenames}
    validate_source_snapshot(i18n_dir, migration, table_rows)
    candidates = build_candidates(table_rows, migration, weights)
    effective, conflicts = select_effective(candidates)

    candidates.sort(key=lambda entry: (entry["key"], -entry["weight"], entry["candidate_id"]))
    effective.sort(key=lambda entry: entry["key"])
    conflicts.sort(key=lambda entry: entry["key"])
    write_tsv(out_dir / "input-provenance.tsv", PROVENANCE_COLUMNS, candidates)
    write_tsv(out_dir / "effective.tsv", EFFECTIVE_COLUMNS, effective)
    write_tsv(out_dir / "conflicts.tsv", CONFLICT_COLUMNS, conflicts)

    present = [entry for entry in candidates if entry["status"] == "present"]
    fatal_count = sum(bool(entry["fatal"]) for entry in conflicts)
    table_summary: dict[str, Any] = {}
    for filename in filenames:
        source_file = f"i18n/{filename}"
        relevant = [entry for entry in candidates if entry["source_file"] == source_file]
        table_summary[filename] = {
            "data_rows": len(table_rows[filename]),
            "present_candidates": sum(entry["status"] == "present" for entry in relevant),
            "absent_candidates": sum(entry["status"] == "absent" for entry in relevant),
            "authority_counts": dict(sorted(Counter(
                entry["authority"] for entry in relevant if entry["status"] == "present"
            ).items())),
            "source_batch_counts": dict(sorted(Counter(
                entry["source_batch"] for entry in relevant if entry["status"] == "present"
            ).items())),
            "normalized_lf_sha256": normalized_sha256(i18n_dir / filename),
        }
    summary = {
        "schema_version": 1,
        "mode": "audit-only",
        "authority_order": [
            {"id": authority, "weight": weight}
            for authority, weight in EXPECTED_MAINTENANCE_ORDER
        ],
        "input_tables": table_summary,
        "candidate_rows": len(candidates),
        "present_candidates": len(present),
        "human_reviewed_candidates": sum(
            entry["authority"] == "existing_human_reviewed" for entry in present
        ),
        "effective_rows": len(effective),
        "selected_authority_counts": dict(sorted(Counter(
            entry["authority"] for entry in effective
        ).items())),
        "resolved_conflicts": sum(not bool(entry["fatal"]) for entry in conflicts),
        "fatal_equal_weight_conflicts": fatal_count,
        "product_tree_writes": 0,
        "magica_consumed": False,
        "runtime_consumed": False,
        "result": "failed-equal-weight-conflict" if fatal_count else "pass",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "summary.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return summary, (2 if fatal_count else 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--i18n-dir", type=Path, default=REPO_ROOT / "i18n")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "i18n" / "generated")
    parser.add_argument("--policy", type=Path, default=REPO_ROOT / "i18n" / "authority-policy.json")
    parser.add_argument(
        "--migration-summary",
        type=Path,
        default=REPO_ROOT / "i18n" / "migration-source-summary.json",
    )
    args = parser.parse_args()
    try:
        summary, exit_code = run(
            i18n_dir=args.i18n_dir.resolve(),
            out_dir=args.out_dir.resolve(),
            policy_path=args.policy.resolve(),
            migration_path=args.migration_summary.resolve(),
        )
    except (AuditError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"i18n authority audit failed: {exc}", file=sys.stderr)
        return 2
    print(
        "i18n authority audit: "
        f"candidates={summary['present_candidates']}, "
        f"effective={summary['effective_rows']}, "
        f"resolved_conflicts={summary['resolved_conflicts']}, "
        f"fatal_conflicts={summary['fatal_equal_weight_conflicts']}, "
        "magica_writes=0"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
