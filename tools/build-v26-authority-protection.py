#!/usr/bin/env python3
"""Generate the committed v26 high-authority field protection baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from v26_authority_protection import build_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tsv", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = build_snapshot(
        args.root,
        output_tsv=args.tsv,
        output_manifest=args.manifest,
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "protected_fields": manifest["counts"]["protected_fields"],
                "protected_files": manifest["counts"]["protected_files"],
                "aggregate_sha256": manifest["baseline"]["protected_fields_aggregate_sha256"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

