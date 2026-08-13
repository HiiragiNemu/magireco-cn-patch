#!/usr/bin/env python3
"""Fail closed if a protected translation or its provenance has drifted."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from v26_authority_protection import ProtectionError, verify_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--skip-freshness",
        action="store_true",
        help="Only for isolated unit tests; CI/release must regenerate machine review and use the default.",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the JSON verification record with explicit LF bytes.",
    )
    args = parser.parse_args()
    try:
        report = verify_snapshot(args.root, require_freshness=not args.skip_freshness)
    except ProtectionError as exc:
        failure = {"status": "FAIL", "error": str(exc)}
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(failure, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        if args.json:
            print(json.dumps(failure, ensure_ascii=False))
        else:
            print(f"FAIL: {exc}")
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "PASS: "
            f"{report['protected_fields']} protected fields / "
            f"{report['protected_files']} files / "
            f"aggregate {report['protected_fields_aggregate_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
