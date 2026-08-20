#!/usr/bin/env python3
"""Apply the 152 same-geometry official-CN image candidates fail-closed."""

from __future__ import annotations

import argparse
import csv
import json
import os
import struct
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "magica/research/totentanz-full-localization-20260817"
SOURCE_TSV = RESEARCH / "source-exhaustion/image_unresolved_actionable.tsv"
OUTPUT = RESEARCH / "official-cn-image-overlay-round2"
MANIFEST = OUTPUT / "overlay_manifest.json"
PRODUCT = ROOT / "magica/resource/image_web"
EXCLUDED_FROM_DIRECT_COPY = {
    "resource/image_web/page/arena/reward/reward_header_a.png":
        "旧国服图仍为日文“報酬一覧”，必须另行制作中文当前画布",
}


def png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    if len(head) != 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", head[16:24])


def same_bytes(left: Path, right: Path) -> bool:
    if not left.is_file() or not right.is_file() or left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as first, right.open("rb") as second:
        while True:
            a = first.read(1024 * 1024)
            b = second.read(1024 * 1024)
            if a != b:
                return False
            if not a:
                return True


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare() -> dict:
    with SOURCE_TSV.open("r", encoding="utf-8-sig", newline="") as handle:
        inventory = list(csv.DictReader(handle, delimiter="\t"))
    rows: list[dict] = []
    for item in inventory:
        if item["geometry_status"] != "same-geometry":
            continue
        if item["path"].replace("\\", "/") in EXCLUDED_FROM_DIRECT_COPY:
            continue
        path = item["path"].replace("\\", "/")
        prefix = "resource/image_web/"
        if not path.startswith(prefix) or ".." in Path(path).parts:
            raise ValueError(f"invalid product path: {path}")
        path = path[len(prefix):]
        source = Path(item["old_cn_source"])
        current = Path(item["current_us_reference"])
        target = PRODUCT / Path(path)
        if not source.is_file() or not current.is_file():
            raise FileNotFoundError(path)
        if png_size(source) != png_size(current):
            raise ValueError(f"geometry drift in same-geometry set: {path}")
        state = "absent" if not target.is_file() else "same" if same_bytes(source, target) else "different"
        if state == "different":
            raise ValueError(f"unexpected existing product target: {path}")
        rows.append({
            "item_id": item["item_id"],
            "path": path,
            "source": str(source),
            "current_us_reference": str(current),
            "width": png_size(source)[0],
            "height": png_size(source)[1],
            "bytes": source.stat().st_size,
            "declared_source_sha256": item["old_sha256"],
            "declared_current_sha256": item["current_sha256"],
            "product_before": state,
            "authority": "official-cn-legacy-client-image",
            "reference_count": int(item["reference_count"]),
            "reference_evidence": item["reference_evidence"],
        })
    rows.sort(key=lambda value: value["path"])
    if len(rows) != 151 or len({row["path"] for row in rows}) != 151:
        raise ValueError(f"expected 151 unique direct-copy rows, got {len(rows)}")
    result = {
        "schema": "official-cn-image-web-overlay-round2/v1",
        "source_inventory": str(SOURCE_TSV),
        "product_root": str(PRODUCT),
        "items": len(rows),
        "bytes": sum(row["bytes"] for row in rows),
        "literal_references": sum(row["reference_count"] for row in rows),
        "product_tree_writes": 0,
        "excluded_from_direct_copy": EXCLUDED_FROM_DIRECT_COPY,
        "rows": rows,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def load_manifest() -> dict:
    result = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if result.get("schema") != "official-cn-image-web-overlay-round2/v1":
        raise ValueError("manifest schema mismatch")
    if result.get("items") != 151 or len(result.get("rows", [])) != 151:
        raise ValueError("manifest row count mismatch")
    return result


def apply_or_verify(result: dict, write: bool) -> dict:
    changed = 0
    written: list[Path] = []
    try:
        for item in result["rows"]:
            source = Path(item["source"])
            target = PRODUCT / Path(item["path"])
            if source.stat().st_size != item["bytes"] or png_size(source) != (item["width"], item["height"]):
                raise ValueError(f"official source drift: {item['path']}")
            if write and not target.is_file():
                if item["product_before"] != "absent":
                    raise ValueError(f"product before-state drift: {item['path']}")
                atomic_write(target, source.read_bytes())
                written.append(target)
                changed += 1
            if not same_bytes(source, target):
                raise ValueError(f"product overlay mismatch: {item['path']}")
            if png_size(target) != (item["width"], item["height"]):
                raise ValueError(f"product geometry mismatch: {item['path']}")
    except Exception:
        for target in reversed(written):
            target.unlink(missing_ok=True)
        raise
    return {"status": "PASS", "items": 151, "changed": changed, "product_tree_writes": changed}


def rollback(result: dict) -> dict:
    removed = 0
    for item in result["rows"]:
        target = PRODUCT / Path(item["path"])
        if item["product_before"] != "absent":
            raise ValueError(f"rollback requires baseline-absent target: {item['path']}")
        if target.is_file():
            if not same_bytes(Path(item["source"]), target):
                raise ValueError(f"rollback target drift: {item['path']}")
            target.unlink()
            removed += 1
    return {"status": "PASS", "removed": removed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "apply", "verify", "rollback"))
    args = parser.parse_args()
    if args.mode == "prepare":
        result = prepare()
        output = {key: result[key] for key in ("items", "bytes", "literal_references", "product_tree_writes")}
    else:
        result = load_manifest()
        if args.mode == "apply":
            output = apply_or_verify(result, True)
        elif args.mode == "verify":
            output = apply_or_verify(result, False)
        else:
            output = rollback(result)
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
