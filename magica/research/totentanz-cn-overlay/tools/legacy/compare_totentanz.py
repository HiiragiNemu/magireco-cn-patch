from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
import tarfile
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
OLD_ROOT = HERE / "extracted"
TAR_PATH = Path(r"A:\totentanz-frontend.tar")
PREFIX = "totentanz-frontend/totentanz-frontend/"

SIMPLIFIED_SIGNAL = set(
    "这为国录发后个们时无与从见将门间东叶乐开关长当万过进还请认让仅两并"
    "层边对实计设线页签钮显击删择务队礼镜结忆录继绑码输载译适龄"
)

TEXT_REF_RE = re.compile(r"text!([A-Za-z0-9_./-]+\.(?:html|css|json))")
DEFINE_ARRAY_RE = re.compile(r"define\s*\(\s*\[([^\]]*)\]", re.S)
TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9:_-]*)\b")


CURATED_GLOBAL = {
    # Old root menu: verified visually from side-by-side contact sheet.
    "resource/image_web/common/global/global_gacha.png": ("true_simplified_cn", "扭蛋"),
    "resource/image_web/common/global/global_memoria.png": ("true_simplified_cn", "记忆结晶"),
    "resource/image_web/common/global/global_mission.png": ("true_simplified_cn", "任务"),
    "resource/image_web/common/global/global_shop.png": ("true_cn", "商店"),
    "resource/image_web/common/global/global_team.png": ("true_simplified_cn", "队伍"),
    "resource/image_web/common/global/global_unit.png": ("shared_han_ambiguous", "魔法少女"),
    "resource/image_web/common/global/global_quest.png": ("true_simplified_cn", "剧情"),
    "resource/image_web/common/global/global_battle.png": ("true_simplified_cn", "镜界"),
    "resource/image_web/common/global/global_home.png": ("neutral_latin", "HOME"),
    "resource/image_web/common/global/global_patrol_a.png": ("japanese_residue", "パトロール"),
    "resource/image_web/common/global/global_accomplish.png": ("japanese_residue", "バトルミュージアム"),
    "resource/image_web/common/global/global_extermination.png": ("japanese_residue", "殲滅戦"),
    "resource/image_web/common/global/global_scene0.png": ("neutral_latin", "Scene0"),
    "resource/image_web/common/global/global_kimochi.png": ("japanese_residue", "キモチ戦"),
    "resource/image_web/common/global/global_kimochi_a.png": ("japanese_residue", "キモチ戦"),
    # Old update2 suite: visually verified as Japanese; do not treat it as a
    # Chinese source merely because the paths match.
    "resource/image_web/common/global/update2/global_gacha.png": ("japanese_residue", "ガチャ"),
    "resource/image_web/common/global/update2/global_memoria.png": ("japanese_residue", "メモリア"),
    "resource/image_web/common/global/update2/global_mission.png": ("japanese_residue", "ミッション"),
    "resource/image_web/common/global/update2/global_shop.png": ("japanese_residue", "ショップ"),
    "resource/image_web/common/global/update2/global_team.png": ("japanese_residue", "チーム"),
    "resource/image_web/common/global/update2/global_unit.png": ("shared_han_ambiguous", "魔法少女"),
}


def png_size(data: bytes) -> tuple[int | None, int | None]:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    return None, None


def decode(data: bytes) -> str | None:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "shift_jis"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return None


def language_counts(text: str | None) -> dict[str, int]:
    result = {"han": 0, "hiragana": 0, "katakana": 0, "simplified_signal": 0}
    if text is None:
        return result
    counts = Counter(text)
    for char, count in counts.items():
        cp = ord(char)
        if 0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF:
            result["han"] += count
        elif 0x3040 <= cp <= 0x309F:
            result["hiragana"] += count
        elif 0x30A0 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF:
            result["katakana"] += count
    result["simplified_signal"] = sum(counts.get(ch, 0) for ch in SIMPLIFIED_SIGNAL)
    return result


def dependencies(text: str | None) -> tuple[list[str], list[str]]:
    if not text:
        return [], []
    text_refs = sorted(set(TEXT_REF_RE.findall(text)))
    match = DEFINE_ARRAY_RE.search(text)
    deps = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)) if match else []
    return deps, text_refs


def tag_signature(text: str | None) -> tuple[int, str]:
    tags = [tag.lower() for tag in TAG_RE.findall(text or "")]
    return len(tags), hashlib.sha256("\n".join(tags).encode()).hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def literal_class(row: dict) -> tuple[str, str]:
    zh = int(row.get("simplified_signal_count", 0))
    kana = int(row.get("hiragana_count", 0)) + int(row.get("katakana_count", 0))
    han = int(row.get("han_count", 0))
    if zh and kana:
        return "mixed_cn_japanese", "Review per literal; copy only the Chinese semantic fragment."
    if zh:
        return "strong_simplified_cn", "Authoritative Chinese wording candidate; transplant the literal/text node only."
    if kana:
        return "japanese_residue", "Reject as a Chinese source."
    if han:
        return "shared_han_ambiguous", "Manual semantic review; Han alone does not prove Chinese localization."
    return "non_cjk", "Not a Chinese text source."


def main() -> None:
    old_inventory = json.loads((HERE / "inventory.json").read_text("utf-8"))
    old_by_path = {row["path"]: row for row in old_inventory}
    needed = {
        path
        for path in old_by_path
        if Path(path).suffix.lower() in {".png", ".jpg", ".js", ".html", ".css"}
        or path == "index.html"
    }

    new_data: dict[str, bytes] = {}
    tar_paths: set[str] = set()
    with tarfile.open(TAR_PATH, "r:") as tf:
        for member in tf:
            if not member.isfile() or not member.name.startswith(PREFIX):
                continue
            rel = member.name[len(PREFIX) :]
            tar_paths.add(rel)
            if rel not in needed:
                continue
            source = tf.extractfile(member)
            if source is not None:
                new_data[rel] = source.read()

    comparisons: list[dict] = []
    text_candidates: list[dict] = []
    png_candidates: list[dict] = []
    for rel in sorted(needed):
        old = old_by_path[rel]
        current = new_data.get(rel)
        ext = Path(rel).suffix.lower()
        old_path = OLD_ROOT / rel
        old_bytes = old_path.read_bytes()
        old_w, old_h = png_size(old_bytes)
        new_w, new_h = png_size(current or b"")
        new_hash = hashlib.sha256(current).hexdigest() if current is not None else ""
        same_bytes = current is not None and new_hash == old["sha256"]
        same_geometry = (
            current is not None
            and old_w is not None
            and new_w is not None
            and (old_w, old_h) == (new_w, new_h)
        )
        row = {
            "path": rel,
            "extension": ext,
            "old_size": old["size"],
            "totentanz_exists": current is not None,
            "totentanz_size": len(current) if current is not None else "",
            "old_sha256": old["sha256"],
            "totentanz_sha256": new_hash,
            "same_bytes": same_bytes,
            "old_width": old_w if old_w is not None else "",
            "old_height": old_h if old_h is not None else "",
            "totentanz_width": new_w if new_w is not None else "",
            "totentanz_height": new_h if new_h is not None else "",
            "same_geometry": same_geometry,
        }
        comparisons.append(row)

        if ext in {".js", ".html"} and current is not None:
            old_text = decode(old_bytes)
            new_text = decode(current)
            old_l = language_counts(old_text)
            new_l = language_counts(new_text)
            old_deps, old_refs = dependencies(old_text)
            new_deps, new_refs = dependencies(new_text)
            old_tag_count, old_tag_hash = tag_signature(old_text if ext == ".html" else None)
            new_tag_count, new_tag_hash = tag_signature(new_text if ext == ".html" else None)
            source_eligible = old.get("injection_tier") not in {"exclude", "exclude_bulk", "metadata_only"}
            if source_eligible and (
                old_l["simplified_signal"]
                or (old_l["han"] >= 4 and not old_l["hiragana"] + old_l["katakana"])
            ):
                if old_l["simplified_signal"] and old_l["hiragana"] + old_l["katakana"]:
                    language_class = "file_mixed_cn_japanese"
                elif old_l["simplified_signal"]:
                    language_class = "file_strong_cn"
                else:
                    language_class = "file_shared_han_ambiguous"
                text_candidates.append(
                    {
                        **row,
                        "old_role": old["role"],
                        "old_injection_tier": old["injection_tier"],
                        "old_han_count": old_l["han"],
                        "old_hiragana_count": old_l["hiragana"],
                        "old_katakana_count": old_l["katakana"],
                        "old_simplified_signal_count": old_l["simplified_signal"],
                        "totentanz_han_count": new_l["han"],
                        "totentanz_hiragana_count": new_l["hiragana"],
                        "totentanz_katakana_count": new_l["katakana"],
                        "totentanz_simplified_signal_count": new_l["simplified_signal"],
                        "old_language_class": language_class,
                        "define_dependencies_equal": old_deps == new_deps,
                        "text_refs_equal": old_refs == new_refs,
                        "old_html_tag_count": old_tag_count if ext == ".html" else "",
                        "totentanz_html_tag_count": new_tag_count if ext == ".html" else "",
                        "html_tag_signature_equal": (old_tag_hash == new_tag_hash) if ext == ".html" else "",
                        "authority_guidance": "Transplant verified Chinese literals/text nodes into the current file; same path is not permission to overwrite current logic or markup.",
                    }
                )

        if ext == ".png" and current is not None:
            visual_class, visible_text = CURATED_GLOBAL.get(rel, ("unreviewed_visual", ""))
            if same_bytes:
                guidance = "Identical bytes; no localization delta."
            elif visual_class in {"true_cn", "true_simplified_cn"} and same_geometry:
                guidance = "High-confidence path-and-geometry-compatible Chinese asset; copy only after confirming current CSS uses this exact path and box."
            elif visual_class in {"true_cn", "true_simplified_cn"}:
                guidance = "Chinese source but geometry changed; redraw/transplant text into the current canvas instead of copying the old PNG."
            elif visual_class in {"japanese_residue", "shared_han_ambiguous", "neutral_latin"}:
                guidance = "Not an authoritative Chinese asset; do not copy as localization."
            else:
                guidance = "Same path/geometry is only a compatibility signal; manual visual language review is required."
            png_candidates.append(
                {
                    **row,
                    "visual_language_class": visual_class,
                    "visible_text": visible_text,
                    "copy_guidance": guidance,
                }
            )

    literals = json.loads((HERE / "localizable_strings.json").read_text("utf-8"))
    literal_rows: list[dict] = []
    for row in literals:
        language_class, guidance = literal_class(row)
        source = old_by_path.get(row["path"], {})
        source_eligible = (
            row["path"] in new_data
            and source.get("injection_tier") not in {"exclude", "exclude_bulk", "metadata_only"}
        )
        literal_rows.append(
            {
                **row,
                "language_class": language_class,
                "totentanz_same_path": row["path"] in new_data,
                "old_role": source.get("role", ""),
                "old_injection_tier": source.get("injection_tier", ""),
                "source_eligible": source_eligible,
                "authority_guidance": guidance,
            }
        )

    old_reference_counts = {path: 0 for path in CURATED_GLOBAL}
    current_reference_counts = {path: 0 for path in CURATED_GLOBAL}
    for rel, old in old_by_path.items():
        if Path(rel).suffix.lower() not in {".js", ".html", ".css"}:
            continue
        if old.get("role") == "cache_manifest":
            continue
        old_text = decode((OLD_ROOT / rel).read_bytes()) or ""
        current_text = decode(new_data.get(rel, b"")) or ""
        for asset_path in CURATED_GLOBAL:
            old_reference_counts[asset_path] += old_text.count(asset_path)
            current_reference_counts[asset_path] += current_text.count(asset_path)
    for row in png_candidates:
        if row["path"] in CURATED_GLOBAL:
            row["old_text_reference_count"] = old_reference_counts[row["path"]]
            row["totentanz_comparable_text_reference_count"] = current_reference_counts[row["path"]]
            row["reference_caveat"] = "Totentanz css/_common is absent from the tar, so current runtime selection cannot be proven from this tar alone."
        else:
            row["old_text_reference_count"] = ""
            row["totentanz_comparable_text_reference_count"] = ""
            row["reference_caveat"] = ""

    curated_rows = [row for row in png_candidates if row["path"] in CURATED_GLOBAL]
    strong_png = [
        row
        for row in png_candidates
        if row["visual_language_class"] in {"true_cn", "true_simplified_cn"} and row["same_geometry"]
    ]
    strong_literals = [
        row
        for row in literal_rows
        if row["language_class"] == "strong_simplified_cn" and row["source_eligible"]
    ]

    old_module_rows = json.loads((HERE / "module_path_map.json").read_text("utf-8"))
    old_module_map = {row["module_id"]: row["module_path"] for row in old_module_rows}
    current_base_config = decode(new_data.get("js/_common/baseConfig.js", b"")) or ""
    current_pair_block = current_base_config.split("requireNoCash", 1)[0]
    current_module_map = dict(
        re.findall(r'([A-Za-z_$][\w$]*):"([A-Za-z0-9_./-]+)"', current_pair_block)
    )
    module_map_comparison: list[dict] = []
    for module_id in sorted(set(old_module_map) | set(current_module_map)):
        old_path = old_module_map.get(module_id, "")
        current_path = current_module_map.get(module_id, "")
        if old_path and current_path:
            status = "same" if old_path == current_path else "changed"
        elif old_path:
            status = "old_only"
        else:
            status = "totentanz_only"
        module_map_comparison.append(
            {
                "module_id": module_id,
                "old_module_path": old_path,
                "totentanz_module_path": current_path,
                "status": status,
            }
        )

    current_index = decode(new_data.get("index.html", b"")) or ""
    index_dependencies: list[dict] = []
    for attr, url in re.findall(r'\b(src|href)\s*=\s*["\']([^"\']+)["\']', current_index, re.I):
        if not url.startswith("/magica/"):
            continue
        rel = url.split("?", 1)[0][len("/magica/") :]
        index_dependencies.append(
            {
                "attribute": attr.lower(),
                "url": url,
                "relative_path": rel,
                "present_in_totentanz_tar": rel in tar_paths,
                "present_in_old_tree": (OLD_ROOT / rel).is_file(),
            }
        )

    outputs = {
        "old_vs_totentanz_inventory": comparisons,
        "authoritative_text_candidates": text_candidates,
        "web_png_geometry_candidates": png_candidates,
        "curated_global_icons": curated_rows,
        "strong_cn_png_candidates": strong_png,
        "text_literal_authority": literal_rows,
        "strong_cn_text_literals": strong_literals,
        "module_map_comparison": module_map_comparison,
        "totentanz_index_dependencies": index_dependencies,
    }
    for name, rows in outputs.items():
        (HERE / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        csv_rows = []
        for source in rows:
            value = dict(source)
            for key, item in list(value.items()):
                if isinstance(item, list):
                    value[key] = ";".join(str(v) for v in item)
            csv_rows.append(value)
        write_csv(HERE / f"{name}.csv", csv_rows)

    summary = {
        "old_paths_considered": len(needed),
        "same_path_count": len(new_data),
        "text_authority_file_candidates": len(text_candidates),
        "png_same_path_count": len(png_candidates),
        "png_same_geometry_count": sum(row["same_geometry"] for row in png_candidates),
        "curated_global_icon_count": len(curated_rows),
        "strong_cn_same_geometry_png_count": len(strong_png),
        "text_literal_records": len(literal_rows),
        "strong_cn_text_literal_count": len(strong_literals),
        "literal_language_counts": dict(Counter(row["language_class"] for row in literal_rows)),
        "module_map_status_counts": dict(Counter(row["status"] for row in module_map_comparison)),
        "totentanz_index_dependency_count": len(index_dependencies),
        "totentanz_index_dependencies_missing_from_tar": sum(
            not row["present_in_totentanz_tar"] for row in index_dependencies
        ),
    }
    (HERE / "comparison_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
