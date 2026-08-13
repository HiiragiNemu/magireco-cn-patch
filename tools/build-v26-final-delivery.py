#!/usr/bin/env python3
"""Generate four delivery roles plus their supporting manifest outside the repo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from v26_final_delivery import (
    DEFAULT_ARTIFACT_CONTRACT,
    DEFAULT_BASELINE,
    DeliveryError,
    generate_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument(
        "--artifact",
        type=Path,
        required=True,
        help="existing cn_js_update.zip candidate; opened read-only and copied",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--expected-entries",
        type=int,
        default=DEFAULT_ARTIFACT_CONTRACT["file_entries"],
    )
    parser.add_argument(
        "--expected-magica-entries",
        type=int,
        default=DEFAULT_ARTIFACT_CONTRACT["magica_entries"],
    )
    parser.add_argument(
        "--expected-engine-entries",
        type=int,
        default=DEFAULT_ARTIFACT_CONTRACT["engine_entries"],
    )
    parser.add_argument(
        "--expected-scenario-entries",
        type=int,
        default=DEFAULT_ARTIFACT_CONTRACT["scenario_entries"],
    )
    parser.add_argument(
        "--expected-audit-research-entries",
        type=int,
        default=DEFAULT_ARTIFACT_CONTRACT["audit_research_entries"],
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--final-tree", help="commit/tree-ish containing the final allowlisted tree")
    source.add_argument("--from-worktree", action="store_true", help="stage only allowlisted worktree paths into an isolated index")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = generate_bundle(
            repo=args.repo,
            baseline=args.baseline,
            allowlist_path=args.allowlist,
            artifact_path=args.artifact,
            output_dir=args.output_dir,
            artifact_contract={
                "file_entries": args.expected_entries,
                "magica_entries": args.expected_magica_entries,
                "engine_entries": args.expected_engine_entries,
                "scenario_entries": args.expected_scenario_entries,
                "audit_research_entries": args.expected_audit_research_entries,
            },
            final_treeish=args.final_tree,
            from_worktree=args.from_worktree,
        )
    except (DeliveryError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
