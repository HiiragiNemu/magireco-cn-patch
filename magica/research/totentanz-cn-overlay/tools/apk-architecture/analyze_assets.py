#!/usr/bin/env python3
"""Reproduce the APK/frontend image provenance comparison used by report.md.

The script deliberately compares *logical paths* as well as byte hashes.  A
logical-path collision with different bytes is important here: it proves that
the packaged APK copy and the downloadable manifest are alternative versions
of one resource, rather than unrelated image libraries.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
TEXT_SUFFIXES = {".css", ".html", ".js", ".json"}


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def nested_root(path: Path, marker: str) -> Path:
    """Accept either the archive extraction directory or its single child."""
    if (path / marker).exists():
        return path
    children = [p for p in path.iterdir() if p.is_dir()]
    hits = [p for p in children if (p / marker).exists()]
    if len(hits) != 1:
        raise RuntimeError(f"cannot locate {marker!r} below {path}")
    return hits[0]


def files_by_relative(root: Path) -> dict[str, Path]:
    return {
        p.relative_to(root).as_posix(): p
        for p in root.rglob("*")
        if p.is_file()
    }


def image_info(path: Path) -> tuple[str, str, str]:
    """Return width, height, and a decoded RGBA hash; stay usable without PIL."""
    try:
        from PIL import Image

        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            return str(image.width), str(image.height), hashlib.sha256(rgba.tobytes()).hexdigest()
    except Exception:
        return "", "", ""


def write_csv(path: Path, rows: Iterable[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def compare_zip_products(complete: Path, callgraph: Path, out: Path) -> dict:
    pairs = [
        ("direct", complete / "01_direct_images", callgraph / "05_l2d_browser" / "assets" / "direct"),
        ("atlas_frame", complete / "02_atlas_frames", callgraph / "05_l2d_browser" / "assets" / "atlas_frames"),
    ]
    rows: list[dict] = []
    summary: dict[str, dict] = {}
    for kind, left_root, right_root in pairs:
        left, right = files_by_relative(left_root), files_by_relative(right_root)
        all_paths = sorted(set(left) | set(right))
        counts = defaultdict(int)
        for logical in all_paths:
            lp, rp = left.get(logical), right.get(logical)
            lsha = digest(lp) if lp else ""
            rsha = digest(rp) if rp else ""
            lw = lh = lpix = rw = rh = rpix = ""
            if lp and lp.suffix.lower() in IMAGE_SUFFIXES:
                lw, lh, lpix = image_info(lp)
            if rp and rp.suffix.lower() in IMAGE_SUFFIXES:
                rw, rh, rpix = image_info(rp)
            if not lp:
                status = "only_callgraph"
            elif not rp:
                status = "only_complete"
            elif lsha == rsha:
                status = "byte_identical"
            elif lpix and lpix == rpix:
                status = "decoded_pixels_identical"
            elif lw == rw and lh == rh:
                status = "same_dimensions_different_pixels"
            else:
                status = "different_dimensions_or_crop"
            counts[status] += 1
            rows.append(
                {
                    "kind": kind,
                    "logical_path": logical,
                    "complete_path": lp.as_posix() if lp else "",
                    "callgraph_path": rp.as_posix() if rp else "",
                    "complete_size": lp.stat().st_size if lp else "",
                    "callgraph_size": rp.stat().st_size if rp else "",
                    "complete_sha256": lsha,
                    "callgraph_sha256": rsha,
                    "complete_width": lw,
                    "complete_height": lh,
                    "callgraph_width": rw,
                    "callgraph_height": rh,
                    "status": status,
                }
            )
        summary[kind] = {
            "complete_files": len(left),
            "callgraph_files": len(right),
            "same_logical_paths": len(set(left) & set(right)),
            "only_complete": len(set(left) - set(right)),
            "only_callgraph": len(set(right) - set(left)),
            "status_counts": dict(sorted(counts.items())),
        }
    write_csv(
        out / "zip_asset_correspondence.csv",
        rows,
        [
            "kind",
            "logical_path",
            "complete_path",
            "callgraph_path",
            "complete_size",
            "callgraph_size",
            "complete_sha256",
            "callgraph_sha256",
            "complete_width",
            "complete_height",
            "callgraph_width",
            "callgraph_height",
            "status",
        ],
    )
    return summary


def scan_zip_image_namespaces(complete: Path, callgraph: Path, out: Path) -> dict:
    """Count runtime-looking namespaces among the image payloads in both ZIPs."""
    products = {
        "complete": [complete / "01_direct_images", complete / "02_atlas_frames"],
        "callgraph": [
            callgraph / "05_l2d_browser" / "assets" / "direct",
            callgraph / "05_l2d_browser" / "assets" / "atlas_frames",
        ],
    }
    global_names = {
        "gacha_badge.png",
        "gacha_badge_a.png",
        "global_back.png",
        "global_battle.png",
        "global_gacha.png",
        "global_memoria.png",
        "global_mission.png",
        "global_quest.png",
        "global_shop.png",
        "global_team.png",
        "global_unit.png",
    }
    result: dict[str, dict] = {}
    for product, roots in products.items():
        logical_paths = []
        for root in roots:
            logical_paths.extend(files_by_relative(root))
        normalized = [p.lower() for p in logical_paths]
        result[product] = {
            "image_payload_files": len(logical_paths),
            "resource_image_web_paths": sum(
                "/resource/image_web/" in f"/{p}" for p in normalized
            ),
            "resource_image_native_paths": sum(
                "/resource/image_native/" in f"/{p}" for p in normalized
            ),
            "global_menu_icon_basenames": sum(Path(p).name in global_names for p in normalized),
        }
    (out / "zip_image_namespace_scan.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def compare_apk_to_manifest(legacy: Path, patch: Path, out: Path) -> dict:
    records = json.loads((patch / "asset_main_cn.json").read_text(encoding="utf-8"))
    manifest = {record["path"]: record for record in records}
    apk_root = legacy / "assets"
    apk = files_by_relative(apk_root)
    common = sorted(set(apk) & set(manifest))
    rows: list[dict] = []
    for logical in common:
        p = apk[logical]
        record = manifest[logical]
        remote_size = ""
        if record.get("file_list"):
            remote_size = record["file_list"][0].get("size", "")
        apk_md5 = digest(p, "md5")
        manifest_md5 = str(record.get("md5", "")).lower()
        rows.append(
            {
                "logical_path": logical,
                "kind": "image" if p.suffix.lower() in IMAGE_SUFFIXES else "other",
                "apk_path": p.as_posix(),
                "apk_size": p.stat().st_size,
                "manifest_size": remote_size,
                "apk_md5": apk_md5,
                "manifest_md5": manifest_md5,
                "same_md5": str(apk_md5 == manifest_md5).lower(),
            }
        )
    write_csv(
        out / "apk_vs_download_manifest.csv",
        rows,
        [
            "logical_path",
            "kind",
            "apk_path",
            "apk_size",
            "manifest_size",
            "apk_md5",
            "manifest_md5",
            "same_md5",
        ],
    )
    return {
        "download_manifest_entries": len(manifest),
        "apk_assets_files": len(apk),
        "logical_path_intersection": len(common),
        "same_md5": sum(r["same_md5"] == "true" for r in rows),
        "different_md5": sum(r["same_md5"] == "false" for r in rows),
        "image_intersection": sum(r["kind"] == "image" for r in rows),
        "image_same_md5": sum(r["kind"] == "image" and r["same_md5"] == "true" for r in rows),
        "image_different_md5": sum(r["kind"] == "image" and r["same_md5"] == "false" for r in rows),
    }


def compare_frontend_images(legacy: Path, patch: Path, out: Path) -> dict:
    apk_images = [
        p
        for p in legacy.rglob("*")
        if p.is_file()
        and p.suffix.lower() in IMAGE_SUFFIXES
        and "jadx-reference" not in p.parts
    ]
    hash_to_apk: dict[str, list[str]] = defaultdict(list)
    for p in apk_images:
        hash_to_apk[digest(p)].append(p.relative_to(legacy).as_posix())
    frontend_root = patch / "magica"
    rows: list[dict] = []
    for p in sorted(frontend_root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        h = digest(p)
        rows.append(
            {
                "frontend_path": p.relative_to(patch).as_posix(),
                "size": p.stat().st_size,
                "sha256": h,
                "exact_apk_hash_matches": "|".join(hash_to_apk.get(h, [])),
            }
        )
    write_csv(
        out / "frontend_local_images.csv",
        rows,
        ["frontend_path", "size", "sha256", "exact_apk_hash_matches"],
    )
    return {
        "frontend_local_images": len(rows),
        "with_exact_apk_hash_match": sum(bool(r["exact_apk_hash_matches"]) for r in rows),
        "without_exact_apk_hash_match": sum(not r["exact_apk_hash_matches"] for r in rows),
    }


def compare_fonts(legacy: Path, patch: Path, out: Path) -> dict:
    apk_root = legacy / "assets" / "fonts"
    frontend_root = patch / "magica" / "fonts"
    apk_fonts = [p for p in apk_root.rglob("*") if p.is_file()]
    frontend_fonts = [p for p in frontend_root.rglob("*") if p.is_file()]
    rows: list[dict] = []
    for side, paths, root in (
        ("apk", apk_fonts, apk_root),
        ("frontend_hot_update", frontend_fonts, frontend_root),
    ):
        for p in sorted(paths):
            h = digest(p)
            peers = []
            other = frontend_fonts if side == "apk" else apk_fonts
            other_root = frontend_root if side == "apk" else apk_root
            for candidate in other:
                if digest(candidate) == h:
                    peers.append(candidate.relative_to(other_root).as_posix())
            rows.append(
                {
                    "side": side,
                    "path": p.relative_to(root).as_posix(),
                    "size": p.stat().st_size,
                    "sha256": h,
                    "same_hash_on_other_side": "|".join(peers),
                }
            )
    write_csv(
        out / "font_correspondence.csv",
        rows,
        ["side", "path", "size", "sha256", "same_hash_on_other_side"],
    )
    return {
        "apk_fonts": len(apk_fonts),
        "frontend_hot_update_fonts": len(frontend_fonts),
        "frontend_fonts_with_apk_hash_match": sum(
            r["side"] == "frontend_hot_update" and bool(r["same_hash_on_other_side"])
            for r in rows
        ),
    }


def inventory_global_menu_icons(
    legacy: Path, patch: Path, complete: Path, callgraph: Path, out: Path
) -> dict:
    icon_root = patch / "magica" / "resource" / "image_web" / "common" / "global"
    complete_names = {p.name for p in complete.rglob("*") if p.is_file()}
    callgraph_names = {p.name for p in callgraph.rglob("*") if p.is_file()}
    apk_hashes = {
        digest(p)
        for p in legacy.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES and "jadx-reference" not in p.parts
    }
    css = (patch / "magica" / "css" / "_common" / "common.css").read_text(encoding="utf-8")
    rows: list[dict] = []
    for p in sorted(icon_root.glob("*")):
        if not p.is_file() or p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        width, height, _ = image_info(p)
        h = digest(p)
        web_path = "/" + p.relative_to(patch).as_posix()
        rows.append(
            {
                "filename": p.name,
                "web_path": web_path,
                "size": p.stat().st_size,
                "width": width,
                "height": height,
                "sha256": h,
                "referenced_by_common_css": str(web_path in css).lower(),
                "present_by_name_in_complete_zip": str(p.name in complete_names).lower(),
                "present_by_name_in_callgraph_zip": str(p.name in callgraph_names).lower(),
                "exact_hash_in_apk": str(h in apk_hashes).lower(),
            }
        )
    write_csv(
        out / "global_menu_web_icons.csv",
        rows,
        [
            "filename",
            "web_path",
            "size",
            "width",
            "height",
            "sha256",
            "referenced_by_common_css",
            "present_by_name_in_complete_zip",
            "present_by_name_in_callgraph_zip",
            "exact_hash_in_apk",
        ],
    )
    return {
        "files": len(rows),
        "referenced_by_common_css": sum(r["referenced_by_common_css"] == "true" for r in rows),
        "present_by_name_in_complete_zip": sum(
            r["present_by_name_in_complete_zip"] == "true" for r in rows
        ),
        "present_by_name_in_callgraph_zip": sum(
            r["present_by_name_in_callgraph_zip"] == "true" for r in rows
        ),
        "exact_hash_in_apk": sum(r["exact_hash_in_apk"] == "true" for r in rows),
    }


# Conservative: only collect a complete literal URL/path.  Template-generated
# paths are separately visible through data-native* references in the sources.
WEB_REF = re.compile(r"/magica/[A-Za-z0-9_./-]+\.(?:png|jpe?g|json|js|css|html|ttf)", re.I)
NATIVE_REF = re.compile(r"(?<!/magica/)resource/image_native/[A-Za-z0-9_./-]+\.(?:png|jpe?g|json|plist|ExportJson|vfx[btj])", re.I)


def scan_frontend_references(legacy: Path, patch: Path, out: Path) -> dict:
    frontend_root = patch / "magica"
    apk_root = legacy / "assets"
    manifest_records = json.loads((patch / "asset_main_cn.json").read_text(encoding="utf-8"))
    manifest = {r["path"] for r in manifest_records}
    accum: dict[tuple[str, str], dict] = {}
    native_occurrences: list[dict] = []
    native_source_files: set[str] = set()
    for source in sorted(frontend_root.rglob("*")):
        if not source.is_file() or source.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in re.finditer(r"resource/image_native/", text):
            line = text.count("\n", 0, match.start()) + 1
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end < 0:
                line_end = len(text)
            context = text[max(line_start, match.start() - 100) : min(line_end, match.start() + 220)]
            relative = source.relative_to(patch).as_posix()
            native_source_files.add(relative)
            native_occurrences.append(
                {
                    "source": relative,
                    "line": line,
                    "context": context,
                }
            )
        for namespace, regex in (("web_magica_url", WEB_REF), ("native_bridge_path", NATIVE_REF)):
            for match in regex.finditer(text):
                ref = match.group(0)
                line = text.count("\n", 0, match.start()) + 1
                key = (namespace, ref)
                row = accum.setdefault(
                    key,
                    {
                        "namespace": namespace,
                        "reference": ref,
                        "source_count": 0,
                        "sources": [],
                        "local_magica_file": "",
                        "apk_asset_file": "",
                        "download_manifest_entry": "false",
                    },
                )
                marker = f"{source.relative_to(patch).as_posix()}:{line}"
                if marker not in row["sources"]:
                    row["sources"].append(marker)
                    row["source_count"] += 1
                if namespace == "web_magica_url":
                    local = patch / ref.lstrip("/")
                    if local.is_file():
                        row["local_magica_file"] = local.relative_to(patch).as_posix()
                else:
                    local = apk_root / ref
                    if local.is_file():
                        row["apk_asset_file"] = local.relative_to(legacy).as_posix()
                    row["download_manifest_entry"] = str(ref in manifest).lower()
    rows = []
    for row in accum.values():
        row = dict(row)
        row["sources"] = "|".join(row["sources"])
        rows.append(row)
    rows.sort(key=lambda r: (r["namespace"], r["reference"]))
    write_csv(
        out / "frontend_resource_references.csv",
        rows,
        [
            "namespace",
            "reference",
            "source_count",
            "sources",
            "local_magica_file",
            "apk_asset_file",
            "download_manifest_entry",
        ],
    )
    write_csv(
        out / "frontend_native_bridge_occurrences.csv",
        native_occurrences,
        ["source", "line", "context"],
    )
    web_rows = [r for r in rows if r["namespace"] == "web_magica_url"]
    native_rows = [r for r in rows if r["namespace"] == "native_bridge_path"]
    return {
        "literal_web_magica_urls": len(web_rows),
        "web_urls_with_local_magica_file": sum(bool(r["local_magica_file"]) for r in web_rows),
        "web_urls_without_local_magica_file": sum(not r["local_magica_file"] for r in web_rows),
        "literal_native_bridge_paths": len(native_rows),
        "native_paths_with_apk_asset": sum(bool(r["apk_asset_file"]) for r in native_rows),
        "native_paths_in_download_manifest": sum(r["download_manifest_entry"] == "true" for r in native_rows),
        "all_native_bridge_occurrences": len(native_occurrences),
        "native_bridge_source_files": len(native_source_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--complete", type=Path, default=Path("complete"))
    parser.add_argument("--callgraph", type=Path, default=Path("callgraph"))
    parser.add_argument("--legacy", type=Path, default=Path("legacy-client"))
    parser.add_argument("--patch", type=Path, default=Path("cn-patch"))
    parser.add_argument("--out", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    complete = nested_root(args.complete, "01_direct_images")
    callgraph = nested_root(args.callgraph, "05_l2d_browser")
    summary = {
        "complete_root": complete.as_posix(),
        "callgraph_root": callgraph.as_posix(),
        "zip_products": compare_zip_products(complete, callgraph, args.out),
        "zip_image_namespaces": scan_zip_image_namespaces(complete, callgraph, args.out),
        "apk_vs_download_manifest": compare_apk_to_manifest(args.legacy, args.patch, args.out),
        "frontend_local_images": compare_frontend_images(args.legacy, args.patch, args.out),
        "font_correspondence": compare_fonts(args.legacy, args.patch, args.out),
        "global_menu_web_icons": inventory_global_menu_icons(
            args.legacy, args.patch, complete, callgraph, args.out
        ),
        "frontend_resource_references": scan_frontend_references(args.legacy, args.patch, args.out),
    }
    (args.out / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
