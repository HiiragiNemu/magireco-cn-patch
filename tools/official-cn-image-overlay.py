#!/usr/bin/env python3
"""Allowlist-only official-CN image_web overlay; never copies the full old tree."""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "magica/research/totentanz-full-localization-20260817/official-cn-image-overlay"
SELECTED = RESEARCH / "selected_paths.txt"
MANIFEST = RESEARCH / "overlay_manifest.json"
SOURCE_DEFAULT = Path(r"A:\magicaOLD\resource\image_web")
REFERENCE_DEFAULT = Path(r"A:\totentanz-frontend\resource\image_web")
PRODUCT_DEFAULT = REPO / "magica/resource/image_web"

# The current US files in these locations drifted from the dimensions already
# declared by the live CSS.  The old official-CN assets match that CSS contract,
# so the differing source canvas is intentional and independently allowlisted.
GEOMETRY_EXCEPTIONS = {
    "page/arena/confirm/btn_battle_start.png": {
        "official": (298, 90), "current": (300, 93), "css": (298, 90)
    },
    "page/arena/matching/btn_mirrors_formation.png": {
        "official": (182, 52), "current": (184, 56), "css": (182, 52)
    },
    "page/chara/text_customize.png": {
        "official": (304, 16), "current": (276, 16), "container_max_width": 364
    },
    "page/chara/text_magia.png": {
        "official": (304, 16), "current": (303, 16), "container_max_width": 364
    },
    "page/formation/first_reward.png": {
        "official": (90, 24), "current": (90, 18), "css": (90, 24)
    },
}


def png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    if len(head) != 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", head[16:24])


def same_bytes(a: Path, b: Path) -> bool:
    return a.is_file() and b.is_file() and a.stat().st_size == b.stat().st_size and a.read_bytes() == b.read_bytes()


def selected_paths() -> list[str]:
    values = [line.strip().replace("\\", "/") for line in SELECTED.read_text("utf-8").splitlines()]
    values = [value for value in values if value and not value.startswith("#")]
    if len(values) != len(set(values)):
        raise ValueError("selected_paths.txt must be unique")
    values.sort()
    for value in values:
        p = Path(value)
        if p.is_absolute() or ".." in p.parts or p.suffix.lower() != ".png":
            raise ValueError(f"invalid selected path: {value}")
    return values


def source_texts() -> list[str]:
    texts: list[str] = []
    for suffix in ("*.css", "*.html", "*.js", "*.json"):
        for path in (REPO / "magica").rglob(suffix):
            if "/research/" in path.as_posix():
                continue
            try:
                texts.append(path.read_text("utf-8"))
            except UnicodeDecodeError:
                pass
    return texts


def prepare(source: Path, reference: Path, product: Path) -> dict:
    texts = source_texts()
    prior_rows: dict[str, dict] = {}
    if MANIFEST.is_file():
        try:
            prior = json.loads(MANIFEST.read_text("utf-8"))
            if prior.get("schema") == "official-cn-image-web-overlay-v1":
                prior_rows = {row["path"]: row for row in prior.get("rows", [])}
        except (OSError, ValueError, TypeError, KeyError):
            prior_rows = {}
    rows: list[dict] = []
    errors: list[str] = []
    for rel in selected_paths():
        old = source / rel
        current = reference / rel
        target = product / rel
        if not old.is_file():
            errors.append(f"official source missing: {rel}")
            continue
        if not current.is_file():
            errors.append(f"current US source missing: {rel}")
            continue
        old_size = png_size(old)
        current_size = png_size(current)
        exception = GEOMETRY_EXCEPTIONS.get(rel)
        if old_size != current_size:
            if not exception or exception["official"] != old_size or exception["current"] != current_size:
                errors.append(f"geometry mismatch: {rel}: official={old_size}, current={current_size}")
                continue
        live_state = "absent" if not target.is_file() else "same" if same_bytes(old, target) else "different"
        prior_row = prior_rows.get(rel)
        # Re-preparing after an applied overlay must not erase the original
        # rollback state.  Preserve it only when the source contract is stable.
        if prior_row and prior_row.get("bytes") == old.stat().st_size \
                and (prior_row.get("width"), prior_row.get("height")) == old_size:
            state = prior_row["product_before"]
        else:
            state = live_state
        needle = f"/magica/resource/image_web/{rel}"
        rows.append(
            {
                "path": rel,
                "authority": "official-cn-legacy-client",
                "source": str(old),
                "current_us_source": str(current),
                "width": old_size[0],
                "height": old_size[1],
                "current_us_width": current_size[0],
                "current_us_height": current_size[1],
                "bytes": old.stat().st_size,
                "product_before": state,
                "product_live_state_at_prepare": live_state,
                "literal_reference_count": sum(text.count(needle) for text in texts),
                "decision": (
                    "copy-official-cn-same-path-css-geometry-exception"
                    if exception else "copy-official-cn-same-path-same-geometry"
                ),
                "geometry_evidence": exception,
            }
        )
    if errors:
        raise ValueError("\n".join(errors))
    data = {
        "schema": "official-cn-image-web-overlay-v1",
        "source_root": str(source),
        "reference_root": str(reference),
        "product_root": str(product),
        "items": len(rows),
        "source_bytes": sum(row["bytes"] for row in rows),
        "literal_references": sum(row["literal_reference_count"] for row in rows),
        "authority_order": ["official-cn", "wiki", "confirmed-human", "new-human"],
        "product_tree_writes": 0,
        "rows": rows,
    }
    RESEARCH.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return data


def load_manifest() -> dict:
    data = json.loads(MANIFEST.read_text("utf-8"))
    if data.get("schema") != "official-cn-image-web-overlay-v1":
        raise ValueError("unexpected overlay manifest schema")
    if [row["path"] for row in data["rows"]] != selected_paths():
        raise ValueError("manifest/allowlist drift")
    return data


def atomic_write(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_name, target)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def apply_or_verify(data: dict, product: Path, apply: bool) -> dict:
    changed = 0
    for row in data["rows"]:
        source = Path(row["source"])
        target = product / row["path"]
        if source.stat().st_size != row["bytes"] or png_size(source) != (row["width"], row["height"]):
            raise ValueError(f"official source drift: {row['path']}")
        if apply and not same_bytes(source, target):
            if target.is_file() and row["product_before"] not in {"same", "different"}:
                raise ValueError(f"product before drift: {row['path']}")
            atomic_write(target, source.read_bytes())
            changed += 1
        if not same_bytes(source, target):
            raise ValueError(f"official overlay mismatch: {row['path']}")
        if png_size(target) != (row["width"], row["height"]):
            raise ValueError(f"product geometry drift: {row['path']}")
    return {"status": "PASS", "items": len(data["rows"]), "changed": changed, "product_tree_writes": changed}


def rollback(data: dict, product: Path) -> dict:
    removed = 0
    for row in data["rows"]:
        target = product / row["path"]
        if row["product_before"] != "absent":
            raise ValueError(f"independent rollback only supports baseline-absent rows: {row['path']}")
        if target.is_file():
            source = Path(row["source"])
            if not same_bytes(source, target):
                raise ValueError(f"rollback target drift: {row['path']}")
            target.unlink()
            removed += 1
    return {"status": "PASS", "removed": removed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "apply", "verify", "rollback"))
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--reference", type=Path, default=REFERENCE_DEFAULT)
    parser.add_argument("--product", type=Path, default=PRODUCT_DEFAULT)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = prepare(args.source, args.reference, args.product)
        result = {key: result[key] for key in ("items", "source_bytes", "literal_references", "product_tree_writes")}
    else:
        data = load_manifest()
        if args.mode == "apply":
            result = apply_or_verify(data, args.product, True)
        elif args.mode == "verify":
            result = apply_or_verify(data, args.product, False)
        else:
            result = rollback(data, args.product)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
