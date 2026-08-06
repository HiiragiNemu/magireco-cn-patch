from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
DEFAULT_OLD = HERE / "old_cn"
DEFAULT_CURRENT = HERE / "extracted" / "totentanz-frontend" / "totentanz-frontend"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate resource copy-map inputs and an optional staged result.")
    ap.add_argument("--map", type=Path, default=HERE / "safe_copy_map.json")
    ap.add_argument("--old-root", type=Path, default=DEFAULT_OLD)
    ap.add_argument("--current-root", type=Path, default=DEFAULT_CURRENT)
    ap.add_argument("--staged-root", type=Path, help="If set, every staged target must equal its mapped old source.")
    args = ap.parse_args()
    rows = json.loads(args.map.read_text(encoding="utf-8"))
    errors = []
    for row in rows:
        src = args.old_root / row["source"]
        dst = args.current_root / row["target"]
        if not src.is_file() or not dst.is_file():
            errors.append(f"missing input: {row['source']} -> {row['target']}")
            continue
        if sha256(src) != row["source_sha256"]:
            errors.append(f"source hash drift: {row['source']}")
        if sha256(dst) != row["target_sha256"]:
            errors.append(f"target baseline hash drift: {row['target']}")
        if Image.open(src).size != Image.open(dst).size:
            errors.append(f"dimension mismatch: {row['source']} -> {row['target']}")
        if args.staged_root:
            staged = args.staged_root / row["target"]
            if not staged.is_file() or sha256(staged) != sha256(src):
                errors.append(f"staged copy mismatch: {row['target']}")
    print(json.dumps({"checked": len(rows), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
