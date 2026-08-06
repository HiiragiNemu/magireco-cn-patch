#!/usr/bin/env python3
"""Apply the verified current-UI Chinese image overlay.

The current Totentanz tree is always the structural baseline.  This tool only
copies six reviewed menu images to the paths already used by the current CSS
and removes the older CSS tail that redirected those paths to legacy artwork.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path


RESEARCH_REL = Path("research/totentanz-cn-overlay")
MANIFEST_REL = RESEARCH_REL / "manifests/verified_menu_overlay.json"
CSS_REL = Path("css/_common/common.css")
CSS_MARKER = "/* ============================================================\n   主页菜单按钮".encode("utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def require_hash(path: Path, expected: str, role: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{role} missing: {path}")
    actual = sha256(path)
    if actual != expected:
        raise ValueError(
            f"{role} SHA-256 mismatch: {path}\nexpected={expected}\nactual={actual}"
        )


def strip_legacy_css_tail(path: Path, manifest: dict) -> str:
    raw = path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n")
    marker_offset = normalized.find(CSS_MARKER)
    if marker_offset < 0:
        base_md5 = hashlib.md5(raw.rstrip(b"\r\n")).hexdigest()
        if base_md5 == manifest["common_css"]["expected_base_md5"]:
            return "already_clean"
        raise ValueError(f"legacy CSS marker missing and base hash is unexpected: {path}")

    base = normalized[:marker_offset].rstrip(b"\n")
    base_md5 = hashlib.md5(base).hexdigest()
    if base_md5 != manifest["common_css"]["expected_base_md5"]:
        raise ValueError(
            "common.css base changed before the localization tail; refusing to strip it: "
            f"expected={manifest['common_css']['expected_base_md5']} actual={base_md5}"
        )
    path.write_bytes(base)
    return "tail_removed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-magica", type=Path, required=True)
    parser.add_argument("--legacy-magica", type=Path, required=True)
    parser.add_argument("--totentanz-magica", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_magica.resolve()
    legacy = args.legacy_magica.resolve()
    current = args.totentanz_magica.resolve()
    manifest_path = repo / MANIFEST_REL
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    css_state = strip_legacy_css_tail(repo / CSS_REL, manifest)
    applied: list[dict] = []
    for item in manifest["images"]:
        baseline = current / item["target"]
        require_hash(baseline, item["baseline_sha256"], "Totentanz baseline")
        if png_size(baseline) != (item["width"], item["height"]):
            raise ValueError(f"baseline geometry mismatch: {baseline}")

        if item["source_kind"] == "legacy_official":
            source = legacy / item["source"]
        elif item["source_kind"] == "reviewed_generated":
            source = repo / RESEARCH_REL / item["source"]
        else:
            raise ValueError(f"unknown source_kind: {item['source_kind']}")

        require_hash(source, item["output_sha256"], "overlay source")
        if png_size(source) != (item["width"], item["height"]):
            raise ValueError(f"overlay geometry mismatch: {source}")
        target = repo / item["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        require_hash(target, item["output_sha256"], "written overlay")
        applied.append({"target": item["target"], "sha256": item["output_sha256"]})

    print(json.dumps({"css": css_state, "images": applied}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
