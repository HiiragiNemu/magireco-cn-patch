#!/usr/bin/env python3
"""Re-open four delivery roles and their supporting manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from v26_final_delivery import DeliveryError, verify_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_bundle(repo=args.repo, bundle_dir=args.bundle_dir)
    except (DeliveryError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
