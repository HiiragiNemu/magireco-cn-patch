from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError


HERE = Path(__file__).resolve().parent
NEW_ROOT = HERE / "extracted" / "totentanz-frontend" / "totentanz-frontend"
OLD_ROOT = HERE / "old_cn"
TEXTISH = re.compile(
    r"(?:^|[/_.-])(btn|button|title|text|txt|label|logo|menu|tab|header|footer|caption|"
    r"message|notice|help|rule|howto|global|mission|quest|gacha|shop|team|unit|memoria|"
    r"formation|result|reward|badge|name|status|guide|tutorial|popup|select|confirm|clear|"
    r"complete|lock|unlock|story|event|campaign|arena|collection|login)(?:[/_.-]|$)",
    re.I,
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rgba(path: Path) -> tuple[Image.Image, np.ndarray]:
    im = Image.open(path).convert("RGBA")
    return im, np.asarray(im, dtype=np.int16)


def dhash(im: Image.Image) -> np.ndarray:
    # Alpha-composite over neutral gray so transparent RGB garbage is ignored.
    bg = Image.new("RGBA", im.size, (127, 127, 127, 255))
    flat = Image.alpha_composite(bg, im).convert("L").resize((17, 16), Image.Resampling.LANCZOS)
    a = np.asarray(flat)
    return a[:, 1:] > a[:, :-1]


def metrics(src: Path, dst: Path) -> dict:
    try:
        si, s = rgba(src)
        di, d = rgba(dst)
    except (UnidentifiedImageError, OSError) as exc:
        return {"same_dimensions": False, "decode_error": str(exc)}
    result = {
        "source_width": si.width,
        "source_height": si.height,
        "target_width": di.width,
        "target_height": di.height,
        "same_dimensions": si.size == di.size,
    }
    if si.size != di.size:
        return result
    sa = s[:, :, 3:4].astype(np.float32) / 255.0
    da = d[:, :, 3:4].astype(np.float32) / 255.0
    sp = s[:, :, :3].astype(np.float32) * sa
    dp = d[:, :, :3].astype(np.float32) * da
    alpha_delta = np.abs(s[:, :, 3] - d[:, :, 3])
    visible_delta = np.max(np.abs(sp - dp), axis=2)
    changed = (visible_delta > 2.0) | (alpha_delta > 2)
    result.update(
        {
            "visible_change_ratio": round(float(changed.mean()), 6),
            "visible_identical_ratio": round(float(1.0 - changed.mean()), 6),
            "alpha_change_ratio": round(float((alpha_delta > 2).mean()), 6),
            "visual_mae": round(float((np.abs(sp - dp).mean() + alpha_delta.mean()) / 2.0), 6),
            "dhash_distance": round(float(np.not_equal(dhash(si), dhash(di)).mean()), 6),
        }
    )
    return result


def classify(rel: str, m: dict) -> tuple[str, str]:
    if rel.startswith("resource/image_web/common/global/update2/global_"):
        return "reject", "reserved for manual update2 menu audit; legacy files are JP or dimension-incompatible"
    if m.get("decode_error"):
        return "reject", "one or both PNG files could not be decoded"
    if not m["same_dimensions"]:
        return "reject", "pixel dimensions differ"
    if m["visible_change_ratio"] <= 0.001:
        return "noop", "rendered pixels are effectively identical"
    textish = bool(TEXTISH.search(rel))
    if (
        textish
        and m["visible_identical_ratio"] >= 0.72
        and m["alpha_change_ratio"] <= 0.035
        and m["visual_mae"] <= 7.0
        and m["dhash_distance"] <= 0.14
    ):
        return "high", "same path/dimensions; mostly identical rendered pixels; text-oriented path"
    if (
        textish
        and m["visible_identical_ratio"] >= 0.55
        and m["alpha_change_ratio"] <= 0.07
        and m["visual_mae"] <= 14.0
        and m["dhash_distance"] <= 0.22
    ):
        return "review", "same path/dimensions and structurally close; visual review required"
    return "reject", "difference is too broad or path is not text-oriented"


def write_tsv(path: Path, rows: list[dict]) -> None:
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = [
        "source", "target", "source_sha256", "target_sha256", "confidence", "reason"
        ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def build_row(rel: str, src: Path, dst: Path, kind: str = "same_path") -> dict:
    m = metrics(src, dst)
    conf, reason = classify(rel, m)
    return {
        "source": src.relative_to(OLD_ROOT).as_posix(),
        "target": dst.relative_to(NEW_ROOT).as_posix(),
        "mapping_kind": kind,
        "source_bytes": src.stat().st_size,
        "target_bytes": dst.stat().st_size,
        "source_sha256": digest(src),
        "target_sha256": digest(dst),
        **m,
        "confidence": conf,
        "reason": reason,
    }


def main() -> None:
    menu_only = "--menu-only" in sys.argv
    if menu_only:
        high = json.loads((HERE / "safe_copy_map.json").read_text(encoding="utf-8"))
        review = json.loads((HERE / "review_copy_map.json").read_text(encoding="utf-8"))
        modified_pngs = [None] * 6631
        all_rows = [None] * (len(high) + len(review))
    else:
        inv = json.loads((HERE / "inventory.json").read_text(encoding="utf-8"))
        modified_pngs = [
            e["path"] for e in inv["entries"] if e["extension"] == ".png" and e["status"] == "shared_modified"
        ]
        all_rows = []
        for i, rel in enumerate(modified_pngs, 1):
            all_rows.append(build_row(rel, OLD_ROOT / rel, NEW_ROOT / rel))
            if i % 1000 == 0:
                print(f"measured {i}/{len(modified_pngs)}")
        high = [r for r in all_rows if r["confidence"] == "high"]
        review = [r for r in all_rows if r["confidence"] == "review"]
        write_tsv(HERE / "safe_copy_map.tsv", high)
        write_tsv(HERE / "review_copy_map.tsv", review)
        (HERE / "safe_copy_map.json").write_text(json.dumps(high, ensure_ascii=False, indent=2), encoding="utf-8")
        (HERE / "review_copy_map.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    menu_names = [
        "global_unit.png", "global_memoria.png", "global_team.png",
        "global_gacha.png", "global_mission.png", "global_shop.png",
    ]
    menu_rows = []
    for name in menu_names:
        target_rel = f"resource/image_web/common/global/update2/{name}"
        for source_rel, kind in (
            (target_rel, "same_path"),
            (f"resource/image_web/common/global/{name}", "old_root_to_current_update2"),
        ):
            row = build_row(target_rel, OLD_ROOT / source_rel, NEW_ROOT / target_rel, kind)
            # Keep source relative path exact after build_row's target-based classifier.
            row["source"] = source_rel
            menu_rows.append(row)
    write_tsv(HERE / "global_update2_audit.tsv", menu_rows)
    (HERE / "global_update2_audit.json").write_text(
        json.dumps(menu_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "modified_pngs_measured": len(modified_pngs),
        "high_confidence_same_path_candidates": len(high),
        "review_same_path_candidates": len(review),
        "rejected_or_noop": len(modified_pngs) - len(high) - len(review),
    }
    (HERE / "resource_map_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
