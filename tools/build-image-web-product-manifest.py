#!/usr/bin/env python3
"""Build or verify the exact localized ``magica/resource/image_web`` set.

Only files backed by one of the completed image or JSON localization evidence
layers are admitted.  The v26 package builder consumes this path contract, so
an unrelated file copied into ``image_web`` cannot silently enter the ZIP.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = Path("magica/research/totentanz-full-localization-20260817")
OUTPUT_DIR = RESEARCH / "image-web-product-closure-20260820"
MANIFEST = OUTPUT_DIR / "image_web_product_manifest.json"
TSV = OUTPUT_DIR / "image_web_product_manifest.tsv"
README = OUTPUT_DIR / "README_CN.md"
IMAGE_ROOT = Path("magica/resource/image_web")
SCHEMA = "magireco-image-web-product-manifest/v1"
EXPECTED_GROUP_COUNTS = {
    "official-cn-dynamic-batch-a": 162,
    "official-cn-dynamic-direct": 357,
    "official-cn-dynamic-remaining": 162,
    "official-cn-same-path": 159,
    "official-cn-gap-direct": 151,
    "official-cn-gap-current-canvas": 8,
    "careful-human-gap-current-canvas": 1,
    "careful-human-current-canvas": 58,
    "preexisting-verified-ui": 19,
    "localized-runtime-json": 3,
}

PREEXISTING_VERIFIED: dict[str, tuple[str, str]] = {
    "common/global/connecting.png": (
        "confirmed-human-current-canvas",
        "Git history 12ac9b35; reviewed loading label and Kyubey outline",
    ),
    "common/global/gacha_badge.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/gacha_badge_a.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_back.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_battle.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_gacha.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_memoria.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_mission.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_quest.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_shop.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_team.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/global_unit.png": ("official-cn-legacy-client-image", "exact official-CN asset"),
    "common/global/update2/global_gacha.png": (
        "official-cn-current-canvas-adaptation", "official label reused on update2 canvas"
    ),
    "common/global/update2/global_memoria.png": (
        "official-cn-current-canvas-adaptation", "official label reused on update2 canvas"
    ),
    "common/global/update2/global_mission.png": (
        "official-cn-current-canvas-adaptation", "official label reused on update2 canvas"
    ),
    "common/global/update2/global_shop.png": (
        "official-cn-current-canvas-adaptation", "official label reflowed on update2 canvas"
    ),
    "common/global/update2/global_team.png": (
        "official-cn-current-canvas-adaptation", "official label reflowed on update2 canvas"
    ),
    "common/global/update2/global_unit.png": (
        "official-cn-current-canvas-adaptation", "official label reused on update2 canvas"
    ),
    "regularEvent/groupBattle/common/result/result_title_header.png": (
        "confirmed-human-current-canvas",
        "Git history 01abb847; reviewed Totentanz group-battle result label",
    ),
}

RUNTIME_JSON: dict[str, tuple[str, str]] = {
    "_json/help.json": (
        "mixed-official-cn-and-reviewed-root-translation",
        "authority-source-exhaustion-round3 plus manual-visible-round3",
    ),
    "_json/SecondPartLastInfo.json": (
        "reviewed-root-translation", "manual-visible-round3 stable-key review"
    ),
    "_json/puellaHistoria/overview.json": (
        "wiki-authority",
        "authority-source-exhaustion-round3/wiki_puella_historia_overview.tsv",
    ),
}


class ManifestError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"JSON evidence is not an object: {path}")
    return value


def normalize_relative_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        raise ManifestError(f"invalid image_web path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != raw:
        raise ManifestError(f"unsafe image_web path: {raw!r}")
    if path.suffix.casefold() not in {".png", ".json"}:
        raise ManifestError(f"unsupported image_web product type: {raw}")
    return raw


def png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ManifestError("invalid PNG signature or header")
    return struct.unpack(">II", data[16:24])


def records(value: dict[str, Any], key: str, expected: int, evidence: Path) -> list[dict[str, Any]]:
    rows = value.get(key)
    if not isinstance(rows, list) or len(rows) != expected or not all(isinstance(row, dict) for row in rows):
        raise ManifestError(f"{evidence} expected {expected} object rows in {key}")
    return rows


def build_manifest(root: Path, dynamic_root: Path) -> dict[str, Any]:
    root = root.resolve()
    dynamic_root = dynamic_root.resolve()
    image_root = root / IMAGE_ROOT
    if not image_root.is_dir():
        raise ManifestError(f"missing image_web product root: {image_root}")
    entries: dict[str, dict[str, Any]] = {}

    def add(relative: str, *, source_group: str, authority: str, evidence: str, method: str) -> None:
        relative = normalize_relative_path(relative.removeprefix("resource/image_web/"))
        if relative in entries:
            raise ManifestError(f"evidence groups overlap at {relative}")
        product = image_root.joinpath(*PurePosixPath(relative).parts)
        if not product.is_file() or product.is_symlink():
            raise ManifestError(f"manifest product file missing or linked: {relative}")
        raw = product.read_bytes()
        row: dict[str, Any] = {
            "path": f"{IMAGE_ROOT.as_posix()}/{relative}",
            "relative_path": relative,
            "media_type": product.suffix.casefold().removeprefix("."),
            "source_group": source_group,
            "authority": authority,
            "method": method,
            "evidence": evidence,
            "bytes": len(raw),
        }
        if product.suffix.casefold() == ".png":
            row["width"], row["height"] = png_dimensions(raw)
        else:
            try:
                json.loads(raw.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ManifestError(f"invalid runtime JSON {relative}: {exc}") from exc
        entries[relative] = row

    overlay1 = root / RESEARCH / "official-cn-image-overlay/overlay_manifest.json"
    for row in records(load_json(overlay1), "rows", 159, overlay1):
        add(
            row["path"], source_group="official-cn-same-path",
            authority=row.get("authority", "official-cn-legacy-client-image"),
            evidence=f"{overlay1.relative_to(root).as_posix()}#{row['path']}",
            method=row.get("decision", "copy-official-cn-same-path"),
        )

    overlay2 = root / RESEARCH / "official-cn-image-overlay-round2/overlay_manifest.json"
    for row in records(load_json(overlay2), "rows", 151, overlay2):
        add(
            row["path"], source_group="official-cn-gap-direct",
            authority=row.get("authority", "official-cn-legacy-client-image"),
            evidence=f"{overlay2.relative_to(root).as_posix()}#{row['item_id']}",
            method="copy-official-cn-same-path",
        )

    canvas = root / RESEARCH / "current-canvas-image-round2/manifest.json"
    for row in records(load_json(canvas), "rows", 9, canvas):
        authority = row["authority"]
        group = "official-cn-gap-current-canvas" if authority == "official-cn-legacy-client-image" else "careful-human-gap-current-canvas"
        add(
            row["path"], source_group=group, authority=authority,
            evidence=f"{canvas.relative_to(root).as_posix()}#{row['path']}",
            method=row["method"],
        )

    localized = root / RESEARCH / "web-images/localized_ui_image_manifest.json"
    for row in records(load_json(localized), "assets", 58, localized):
        add(
            row["path"], source_group="careful-human-current-canvas",
            authority=row["authority"],
            evidence=f"{localized.relative_to(root).as_posix()}#{row['path']}",
            method="reviewed-current-canvas-localization",
        )

    dynamic_specs = (
        ("dynamic_image_product_patch_manifest.json", "records", 162, "official-cn-dynamic-batch-a"),
        ("official_cn_direct_357_product_patch.json", "items", 357, "official-cn-dynamic-direct"),
        ("remaining_dynamic_162_product_patch.json", "operations", 162, "official-cn-dynamic-remaining"),
    )
    for filename, key, count, group in dynamic_specs:
        evidence_path = dynamic_root / filename
        for index, row in enumerate(records(load_json(evidence_path), key, count, evidence_path), 1):
            add(
                row["relative_path"], source_group=group,
                authority=row.get("authority", "official-cn"),
                evidence=f"dynamic_image_recovery_audit_20260819/{filename}#{index}",
                method=row.get("action", row.get("after", "copy-official-cn")),
            )

    for relative, (authority, evidence) in PREEXISTING_VERIFIED.items():
        add(
            relative, source_group="preexisting-verified-ui", authority=authority,
            evidence=evidence, method="preexisting-reviewed-product-asset",
        )
    for relative, (authority, evidence) in RUNTIME_JSON.items():
        add(
            relative, source_group="localized-runtime-json", authority=authority,
            evidence=evidence, method="stable-key-localized-runtime-json",
        )

    actual = {item.relative_to(image_root).as_posix() for item in image_root.rglob("*") if item.is_file()}
    declared = set(entries)
    if actual != declared:
        raise ManifestError(
            "image_web product set is not exactly evidence-bound: "
            f"missing={sorted(declared - actual)[:10]} extra={sorted(actual - declared)[:10]}"
        )
    groups = Counter(row["source_group"] for row in entries.values())
    if dict(sorted(groups.items())) != dict(sorted(EXPECTED_GROUP_COUNTS.items())):
        raise ManifestError(f"source-group partition mismatch: {dict(groups)}")
    authority = Counter(row["authority"] for row in entries.values())
    rows = [entries[key] for key in sorted(entries)]
    return {
        "schema": SCHEMA, "status": "PASS",
        "scope": "only localized or authority-backed game-visible image_web PNG and JSON product assets",
        "product_root": IMAGE_ROOT.as_posix(), "entry_count": len(rows),
        "png_count": sum(row["media_type"] == "png" for row in rows),
        "json_count": sum(row["media_type"] == "json" for row in rows),
        "source_group_counts": dict(sorted(groups.items())),
        "authority_counts": dict(sorted(authority.items())),
        "partition_disjoint": True, "unmanifested_product_files": 0,
        "missing_product_files": 0, "entries": rows,
    }


def write_outputs(root: Path, manifest: dict[str, Any]) -> None:
    (root / OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    (root / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    columns = ("path", "media_type", "source_group", "authority", "method", "evidence", "bytes", "width", "height")
    lines = ["\t".join(columns)]
    for row in manifest["entries"]:
        lines.append("\t".join(str(row.get(column, "")) for column in columns))
    (root / TSV).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    groups = "\n".join(f"- `{name}`：{count} 项" for name, count in manifest["source_group_counts"].items())
    (root / README).write_text(
        "# image_web 产品闭合清单（2026-08-20）\n\n"
        f"- 产品资源：{manifest['entry_count']} 项（PNG {manifest['png_count']}，JSON {manifest['json_count']}）。\n"
        "- 仅包含已经由国服图片、Wiki/稳定键文本或已审核当前画布翻译证明具有中文化价值的文件。\n"
        "- 各来源组互不重叠；产品目录中不存在清单外文件。\n"
        "- 产品构建会逐项核对路径、大小和图片尺寸；清单外资源停止构建。\n\n"
        "## 来源分组\n\n" + groups + "\n",
        encoding="utf-8", newline="\n",
    )


def verify_manifest(root: Path) -> dict[str, Any]:
    data = load_json(root / MANIFEST)
    if data.get("schema") != SCHEMA or data.get("status") != "PASS":
        raise ManifestError("image_web manifest schema or status mismatch")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ManifestError("image_web manifest entries missing")
    declared: set[str] = set()
    groups: Counter[str] = Counter()
    for row in entries:
        if not isinstance(row, dict):
            raise ManifestError("image_web manifest row is not an object")
        relative = normalize_relative_path(row.get("relative_path"))
        expected_path = f"{IMAGE_ROOT.as_posix()}/{relative}"
        if row.get("path") != expected_path or relative in declared:
            raise ManifestError(f"image_web manifest duplicate or path mismatch: {relative}")
        declared.add(relative)
        product = root / expected_path
        if not product.is_file() or product.is_symlink():
            raise ManifestError(f"image_web product missing or linked: {expected_path}")
        raw = product.read_bytes()
        if row.get("bytes") != len(raw):
            raise ManifestError(f"image_web product size drift: {expected_path}")
        if product.suffix.casefold() == ".png":
            width, height = png_dimensions(raw)
            if row.get("width") != width or row.get("height") != height:
                raise ManifestError(f"image_web PNG geometry drift: {expected_path}")
        else:
            json.loads(raw.decode("utf-8-sig"))
        if not isinstance(row.get("source_group"), str) or not isinstance(row.get("authority"), str):
            raise ManifestError(f"image_web provenance missing: {expected_path}")
        groups[row["source_group"]] += 1
    actual = {item.relative_to(root / IMAGE_ROOT).as_posix() for item in (root / IMAGE_ROOT).rglob("*") if item.is_file()}
    if actual != declared:
        raise ManifestError(
            "image_web directory differs from manifest: "
            f"missing={sorted(declared - actual)[:10]} extra={sorted(actual - declared)[:10]}"
        )
    if data.get("entry_count") != len(entries) or data.get("source_group_counts") != dict(sorted(groups.items())):
        raise ManifestError("image_web manifest counts changed")
    if dict(sorted(groups.items())) != dict(sorted(EXPECTED_GROUP_COUNTS.items())):
        raise ManifestError("image_web source-group partition changed")
    return {
        "schema": "magireco-image-web-product-verification/v1", "status": "PASS",
        "manifest": MANIFEST.as_posix(), "entry_count": len(entries),
        "png_count": sum(row["media_type"] == "png" for row in entries),
        "json_count": sum(row["media_type"] == "json" for row in entries),
        "source_group_counts": dict(sorted(groups.items())),
        "path_set_exact": True, "sizes_exact": True, "geometry_exact": True,
        "unmanifested_product_files": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--dynamic-root", type=Path,
        default=Path(r"C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\next_round_execution_20260819\dynamic_image_recovery_audit_20260819"),
    )
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if not args.verify:
            write_outputs(root, build_manifest(root, args.dynamic_root))
        result = verify_manifest(root)
    except (ManifestError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
