#!/usr/bin/env python3
"""Build a deterministic frontend overlay ZIP without research-only files."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


RUNTIME_ROOTS = ("css", "fonts", "js", "resource", "template")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-magica", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    root = args.repo_magica.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = sorted(
        path
        for name in RUNTIME_ROOTS
        for path in (root / name).rglob("*")
        if path.is_file()
    )

    records: list[dict] = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            rel = path.relative_to(root).as_posix()
            arcname = f"magica/{rel}"
            data = path.read_bytes()
            info = zipfile.ZipInfo(arcname, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            records.append({"path": arcname, "bytes": len(data), "sha256": sha256_bytes(data)})

    payload = output.read_bytes()
    manifest = {
        "schema_version": 1,
        "archive": str(output),
        "archive_bytes": len(payload),
        "archive_sha256": sha256_bytes(payload),
        "files": len(records),
        "entries": records,
    }
    manifest_path = args.manifest or output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("archive", "archive_bytes", "archive_sha256", "files")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
