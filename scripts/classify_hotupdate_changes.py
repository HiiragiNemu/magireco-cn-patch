#!/usr/bin/env python3
"""Classify changed repository paths by hot-update package ownership.

Paths are read one per line from standard input.  Automatic classification is
deliberately narrow so an unrelated repository change cannot publish either
large runtime package by accident.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable, NamedTuple


SCENARIO_PREFIX = "madomagi/resource/scenario/json/"
JS_PREFIXES = tuple(
    f"magica/{directory}/"
    for directory in ("css", "fonts", "js", "json", "resource", "template")
)
ENGINE_TABLE = "madomagi/engine_i18n.tsv"
REPAIR_MANIFEST = "madomagi/repair_manifest.json"
MADOMAGI_REPAIR_PREFIX = "madomagi/resource/image_native/"
SCOPES = ("auto", "js", "scenario", "all")


class Classification(NamedTuple):
    has_js: int
    has_scenario: int


def classify(paths: Iterable[str], scope: str = "auto", supplemental_paths: Iterable[str] = ()) -> Classification:
    """Return package flags for *paths* under the requested manual/auto scope."""

    if scope == "js":
        return Classification(has_js=1, has_scenario=0)
    if scope == "scenario":
        return Classification(has_js=0, has_scenario=1)
    if scope == "all":
        return Classification(has_js=1, has_scenario=1)
    if scope != "auto":
        raise ValueError(f"unsupported scope: {scope}")

    has_js = False
    has_scenario = False
    supplemental = set(supplemental_paths)
    for raw_path in paths:
        path = raw_path.rstrip("\r\n")
        if not path:
            continue
        # The workflow emits this fail-closed sentinel when the comparison
        # range cannot be evaluated.  Missing a package is worse than doing
        # one conservative full rebuild in that exceptional case.
        if path == "ALL":
            has_js = True
            has_scenario = True
            continue
        if (
            path == ENGINE_TABLE
            or path == REPAIR_MANIFEST
            or path.startswith(JS_PREFIXES)
            or path.startswith(MADOMAGI_REPAIR_PREFIX)
        ):
            has_js = True
        if path.startswith(SCENARIO_PREFIX) and path not in supplemental:
            has_scenario = True

    return Classification(has_js=int(has_js), has_scenario=int(has_scenario))


def format_outputs(result: Classification) -> str:
    """Render GitHub Actions-compatible scalar outputs deterministically."""

    return (
        f"has_js={result.has_js}\n"
        f"has_scenario={result.has_scenario}\n"
    )


def resolve_github_output(value: str | None, parser: argparse.ArgumentParser) -> Path | None:
    if value is None:
        return None
    if value:
        return Path(value)
    env_value = os.environ.get("GITHUB_OUTPUT")
    if not env_value:
        parser.error("--github-output requires PATH or the GITHUB_OUTPUT environment variable")
    return Path(env_value)


def parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=SCOPES,
        default="auto",
        help="auto classifies stdin paths; other values explicitly select packages",
    )
    parser.add_argument(
        "--delta-baseline",
        type=Path,
        help="explicit package-16 scenario paths do not trigger automatic full scenario rebuilds",
    )
    parser.add_argument(
        "--github-output",
        nargs="?",
        const="",
        metavar="PATH",
        help="also append outputs to PATH (or $GITHUB_OUTPUT when PATH is omitted)",
    )
    return parser.parse_args(argv), parser


def main(argv: list[str] | None = None) -> int:
    args, parser = parse_args(argv)
    supplemental = []
    if args.delta_baseline is not None:
        config = json.loads(args.delta_baseline.read_text(encoding="utf-8"))
        supplemental = config.get("supplemental_product_paths", [])
        if not isinstance(supplemental, list) or any(
            not isinstance(p, str) or not p.startswith(SCENARIO_PREFIX) or not p.endswith(".json")
            or "\\" in p or ":" in p or any(ord(c) < 32 for c in p)
            or any(part in ("", ".", "..") for part in p.split("/"))
            for p in supplemental
        ):
            parser.error("invalid supplemental_product_paths in delta baseline")
    result = classify(sys.stdin, scope=args.scope, supplemental_paths=supplemental)
    payload = format_outputs(result)
    sys.stdout.write(payload)

    output_path = resolve_github_output(args.github_output, parser)
    if output_path is not None:
        with output_path.open("ab") as stream:
            stream.write(payload.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
