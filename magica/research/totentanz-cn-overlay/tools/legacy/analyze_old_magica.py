from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE / "extracted"
ARCHIVE = Path(r"A:\magicaOLD.7z")

TEXT_EXTENSIONS = {".js", ".html", ".css", ".json", ".txt", ".py"}
HASH_CHUNK = 4 * 1024 * 1024

# Characters that strongly indicate Simplified Chinese rather than merely CJK
# ideographs shared with Japanese. This is deliberately only a signal, not a
# full language detector.
SIMPLIFIED_SIGNAL = set(
    "这为国录发后个们时无与从见将门间东叶乐开关长当万过进还请认让仅两并"
    "层边对实计设线页签钮显击删择务队礼镜结忆录继绑码输载译适龄"
)

HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
HIRAGANA_RE = re.compile(r"[\u3040-\u309f]")
KATAKANA_RE = re.compile(r"[\u30a0-\u30ff\u31f0-\u31ff]")
TEXT_REF_RE = re.compile(r"text!([A-Za-z0-9_./-]+\.(?:html|css|json))")
MAGICA_REF_RE = re.compile(
    r"(?:https?://[^\s\"']+)?/magica/[A-Za-z0-9_./%{}<>=-]+", re.I
)
DEFINE_ARRAY_RE = re.compile(r"define\s*\(\s*\[([^\]]*)\]", re.S)
JS_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)


def stream_hashes(path: Path) -> tuple[str, str]:
    sha = hashlib.sha256()
    md5 = hashlib.md5()
    with path.open("rb") as fh:
        while True:
            block = fh.read(HASH_CHUNK)
            if not block:
                break
            sha.update(block)
            md5.update(block)
    return sha.hexdigest(), md5.hexdigest()


def png_size(data: bytes) -> tuple[int | None, int | None]:
    if len(data) >= 24 and data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    return None, None


def decode_text(data: bytes) -> tuple[str | None, str | None]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "shift_jis"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    return None, None


def classify(path: str, ext: str, text: str | None, zh_signal_count: int) -> tuple[str, str, str]:
    lower = path.lower()
    if path == "index.html":
        return "bootstrap", "bootstrap_review", "Diff and port loader changes; do not replace the new document wholesale."
    if path in {
        "js/_common/baseConfig.js",
        "js/_common/help.js",
        "js/_common/base.js",
        "js/_common/backboneCommon.js",
        "js/_common/router.js",
    }:
        return "bootstrap_support", "bootstrap_review", "Runtime loader/style/template behavior; merge only compatible hooks."
    if path == "js/system/replacement.js":
        return "cache_manifest", "metadata_only", "Cache-busting fingerprint table, not a translation dictionary."
    if lower.startswith("js/libs/"):
        return "third_party_library", "exclude", "Third-party runtime library; reuse the current frontend version."
    if lower.startswith("js/system/"):
        return "runtime_mapping", "compatibility_review", "Endpoint/cache/release mapping; port only when current routes require it."
    if lower.startswith("js/test/") or lower.startswith("template/test/") or lower.startswith("css/test/"):
        return "test_fixture", "exclude", "Test/backdoor surface, not normal UI localization."
    if lower.startswith("js/") and ext in {".js", ".json"}:
        tier = "high_text" if zh_signal_count else "logic_review"
        return "ui_module", tier, "Chinese UI literals live in page/view modules; transplant literals against current logic."
    if lower.startswith("template/"):
        tier = "high_text" if zh_signal_count else "template_review"
        return "ui_template", tier, "Chinese visible markup lives at the same text! template path; structurally merge into current template."
    if lower.startswith("css/"):
        return "stylesheet", "preserve_new_css", "Treat old CSS as layout/font reference only; keep current UI CSS by default."
    if lower.startswith("resource/image_web/"):
        return "web_image", "visual_review", "Web-layer image; inspect for baked-in Chinese before path-preserving replacement."
    if lower.startswith("resource/"):
        return "web_media", "visual_review", "Web-layer static media referenced below /magica/resource/."
    if lower.startswith("json/"):
        return "offline_json_fixture", "exclude_bulk", "Used by file:/// local mode; online mode requests /magica/api."
    if lower.startswith("api/"):
        return "captured_api_fixture", "exclude_bulk", "Captured/server fixture data, not a static UI overlay."
    if ext in {".txt", ".py"}:
        return "archive_auxiliary", "exclude", "Inventory/helper material bundled with the archive."
    return "other", "review", "Unclassified archive member."


def parse_manifest() -> dict[str, str]:
    path = ROOT / "js/system/replacement.js"
    source = path.read_text("utf-8")
    match = re.fullmatch(r"\s*window\.fileTimeStamp\s*=\s*(\{.*\})\s*;?\s*", source, re.S)
    if not match:
        raise RuntimeError("replacement.js is not a pure window.fileTimeStamp object")
    return json.loads(match.group(1))


def parse_module_map() -> list[dict[str, str]]:
    source = (ROOT / "js/_common/baseConfig.js").read_text("utf-8")
    result: list[dict[str, str]] = []
    black_start = source.index("window.pathBlackList")
    white_start = source.index("window.pathWhiteList")
    black = source[black_start:white_start]
    white = source[white_start:source.index("window.shieldInput")]
    pair_re = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*:\s*['\"]([^'\"]+)['\"]", re.M)
    for kind, block in (("persistent_blacklist", black), ("page_whitelist", white)):
        for module_id, module_path in pair_re.findall(block):
            js_path = module_path + ("" if module_path.endswith(".js") else ".js")
            result.append(
                {
                    "map_kind": kind,
                    "module_id": module_id,
                    "module_path": module_path,
                    "resolved_path": js_path,
                    "exists": str((ROOT / js_path).is_file()).lower(),
                }
            )
    return result


def text_stats(text: str | None) -> tuple[int, int, int, int, int]:
    if text is None:
        return 0, 0, 0, 0, 0
    # One frequency pass is much faster than dozens of full scans for the very
    # large captured JSON fixtures.
    counts = Counter(text)
    han = 0
    hira = 0
    kata = 0
    for char, count in counts.items():
        cp = ord(char)
        if 0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF:
            han += count
        elif 0x3040 <= cp <= 0x309F:
            hira += count
        elif 0x30A0 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF:
            kata += count
    zh = sum(counts.get(ch, 0) for ch in SIMPLIFIED_SIGNAL)
    return han, hira, kata, zh, text.count("\n") + 1


def extract_dependencies(text: str | None) -> tuple[list[str], list[str]]:
    if not text:
        return [], []
    text_refs = sorted(set(TEXT_REF_RE.findall(text)))
    deps: list[str] = []
    match = DEFINE_ARRAY_RE.search(text)
    if match:
        deps = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
    return deps, text_refs


def emit_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_context(text: str, start: int, end: int, radius: int = 90) -> str:
    value = text[max(0, start - radius) : min(len(text), end + radius)]
    return re.sub(r"\s+", " ", value).strip()


def extract_localizable(path: str, text: str) -> list[dict]:
    ext = Path(path).suffix.lower()
    if ext not in {".js", ".html"}:
        return []
    found: list[tuple[int, int, str, str]] = []
    if ext == ".js":
        for match in JS_STRING_RE.finditer(text):
            value = match.group(0)[1:-1]
            if HAN_RE.search(value):
                found.append((match.start() + 1, match.end() - 1, value, "js_string"))
    else:
        # Visible text nodes, including text embedded inside script templates.
        for match in re.finditer(r">([^<>]+)<", text, re.S):
            value = match.group(1)
            if HAN_RE.search(value):
                found.append((match.start(1), match.end(1), value, "html_text"))
        # Chinese attribute values can also be visible/accessibility text.
        for match in re.finditer(r"[A-Za-z_:][-\w:.]*\s*=\s*(['\"])(.*?)\1", text, re.S):
            value = match.group(2)
            if HAN_RE.search(value):
                found.append((match.start(2), match.end(2), value, "html_attribute"))
    result: list[dict] = []
    seen = set()
    for start, end, value, kind in sorted(found):
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned or len(cleaned) > 1000:
            continue
        key = (start, end, cleaned, kind)
        if key in seen:
            continue
        seen.add(key)
        han, hira, kata, zh, _ = text_stats(cleaned)
        result.append(
            {
                "path": path,
                "kind": kind,
                "line": text.count("\n", 0, start) + 1,
                "offset": start,
                "text": cleaned,
                "han_count": han,
                "hiragana_count": hira,
                "katakana_count": kata,
                "simplified_signal_count": zh,
                "context": safe_context(text, start, end),
            }
        )
    return result


def main() -> None:
    if not ROOT.is_dir():
        raise SystemExit(f"missing extraction root: {ROOT}")

    manifest = parse_manifest()
    module_map = parse_module_map()
    files = sorted((p for p in ROOT.rglob("*") if p.is_file()), key=lambda p: p.relative_to(ROOT).as_posix())

    inventory: list[dict] = []
    localizable: list[dict] = []
    dependencies: list[dict] = []
    actual_paths = set()

    for index, path in enumerate(files, 1):
        rel = path.relative_to(ROOT).as_posix()
        actual_paths.add(rel)
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()
        ext = path.suffix.lower()
        text = None
        encoding = None
        # The 280 MB under api/ and json/ is captured/offline response data and
        # is not a static UI overlay candidate. Hash and inventory it, but avoid
        # expensive per-character language scans there. JSON co-located under
        # js/ remains scanned because modules can load it directly.
        text_scan_skipped = rel.startswith("api/") or rel.startswith("json/")
        if (ext in TEXT_EXTENSIONS or rel == "index.html") and not text_scan_skipped:
            text, encoding = decode_text(data)
        han, hira, kata, zh_signal, line_count = text_stats(text)
        deps, text_refs = extract_dependencies(text if ext == ".js" else None)
        magica_refs = (
            sorted(set(MAGICA_REF_RE.findall(text or "")))
            if ext in {".js", ".html", ".css"}
            else []
        )
        width, height = png_size(data)
        token = manifest.get(rel)
        if token is None:
            manifest_status = "unlisted"
        elif token == md5[8:24]:
            manifest_status = "listed_match"
        else:
            manifest_status = "listed_mismatch"
        role, tier, reason = classify(rel, ext, text, zh_signal)
        row = {
            "path": rel,
            "top_level": rel.split("/", 1)[0],
            "extension": ext,
            "size": len(data),
            "mtime_local": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            "sha256": sha256,
            "md5": md5,
            "md5_middle16": md5[8:24],
            "replacement_token": token or "",
            "replacement_status": manifest_status,
            "role": role,
            "injection_tier": tier,
            "candidate_reason": reason,
            "text_encoding": encoding or "",
            "text_scan_skipped": text_scan_skipped,
            "line_count": line_count if text is not None else "",
            "han_count": han,
            "hiragana_count": hira,
            "katakana_count": kata,
            "simplified_signal_count": zh_signal,
            "likely_chinese_text": bool(zh_signal or (han >= 4 and not (hira or kata))),
            "define_dependency_count": len(deps),
            "define_dependencies": deps,
            "text_ref_count": len(text_refs),
            "text_refs": text_refs,
            "magica_ref_count": len(magica_refs),
            "magica_refs": magica_refs,
            "native_key_count": (text or "").count("data-nativeimgkey") + (text or "").count("data-nativebgkey"),
            "png_width": width if width is not None else "",
            "png_height": height if height is not None else "",
        }
        inventory.append(row)
        if ext == ".js":
            dependencies.append(
                {
                    "path": rel,
                    "dependencies": deps,
                    "text_refs": text_refs,
                    "missing_text_refs": [ref for ref in text_refs if not (ROOT / ref).is_file()],
                }
            )
        if text is not None:
            localizable.extend(extract_localizable(rel, text))
        if index % 1000 == 0:
            (HERE / "progress.log").write_text(f"scanned {index}/{len(files)}\n", "utf-8")
            print(f"scanned {index}/{len(files)}", file=sys.stderr, flush=True)

    manifest_audit: list[dict] = []
    inv_by_path = {row["path"]: row for row in inventory}
    for rel, token in sorted(manifest.items()):
        row = inv_by_path.get(rel)
        manifest_audit.append(
            {
                "path": rel,
                "replacement_token": token,
                "actual_exists": bool(row),
                "actual_md5_middle16": row["md5_middle16"] if row else "",
                "status": row["replacement_status"] if row else "listed_missing",
                "actual_size": row["size"] if row else "",
            }
        )

    candidates = [
        row
        for row in inventory
        if row["injection_tier"]
        in {
            "bootstrap_review",
            "high_text",
            "logic_review",
            "template_review",
            "visual_review",
            "compatibility_review",
        }
    ]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version,
        "archive": {
            "path": str(ARCHIVE),
            "size": ARCHIVE.stat().st_size,
            "sha256": stream_hashes(ARCHIVE)[0],
        },
        "extracted": {
            "root": str(ROOT),
            "files": len(inventory),
            "bytes": sum(row["size"] for row in inventory),
        },
        "counts_by_extension": dict(Counter(row["extension"] for row in inventory)),
        "bytes_by_top_level": dict(
            sorted(
                (
                    key,
                    sum(row["size"] for row in inventory if row["top_level"] == key),
                )
                for key in {row["top_level"] for row in inventory}
            )
        ),
        "counts_by_role": dict(Counter(row["role"] for row in inventory)),
        "counts_by_injection_tier": dict(Counter(row["injection_tier"] for row in inventory)),
        "language_file_counts": {
            "han_nonzero": sum(bool(row["han_count"]) for row in inventory),
            "simplified_signal_nonzero": sum(bool(row["simplified_signal_count"]) for row in inventory),
            "hiragana_nonzero": sum(bool(row["hiragana_count"]) for row in inventory),
            "katakana_nonzero": sum(bool(row["katakana_count"]) for row in inventory),
        },
        "replacement_manifest": {
            "entries": len(manifest),
            "listed_match": sum(row["status"] == "listed_match" for row in manifest_audit),
            "listed_mismatch": sum(row["status"] == "listed_mismatch" for row in manifest_audit),
            "listed_missing": sum(row["status"] == "listed_missing" for row in manifest_audit),
            "actual_unlisted": sum(row["replacement_status"] == "unlisted" for row in inventory),
            "status_by_extension": {
                ext: dict(Counter(row["status"] for row in manifest_audit if Path(row["path"]).suffix.lower() == ext))
                for ext in sorted({Path(row["path"]).suffix.lower() for row in manifest_audit})
            },
        },
        "module_path_map_entries": len(module_map),
        "dependency_records": len(dependencies),
        "localizable_string_records": len(localizable),
        "candidate_files": len(candidates),
    }

    csv_inventory = []
    for row in inventory:
        copy = dict(row)
        for field in ("define_dependencies", "text_refs", "magica_refs"):
            copy[field] = ";".join(copy[field])
        csv_inventory.append(copy)
    csv_candidates = []
    for row in candidates:
        copy = dict(row)
        for field in ("define_dependencies", "text_refs", "magica_refs"):
            copy[field] = ";".join(copy[field])
        csv_candidates.append(copy)

    (HERE / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), "utf-8")
    emit_csv(HERE / "inventory.csv", csv_inventory)
    (HERE / "candidate_inventory.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), "utf-8")
    emit_csv(HERE / "candidate_inventory.csv", csv_candidates)
    (HERE / "replacement_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    emit_csv(HERE / "replacement_manifest_audit.csv", manifest_audit)
    (HERE / "module_path_map.json").write_text(json.dumps(module_map, ensure_ascii=False, indent=2), "utf-8")
    emit_csv(HERE / "module_path_map.csv", module_map)
    (HERE / "dependencies.json").write_text(json.dumps(dependencies, ensure_ascii=False, indent=2), "utf-8")
    (HERE / "localizable_strings.json").write_text(json.dumps(localizable, ensure_ascii=False, indent=2), "utf-8")
    emit_csv(HERE / "localizable_strings.csv", localizable)
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
