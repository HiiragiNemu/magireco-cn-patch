from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KANA = re.compile(r"[\u3040-\u30ff]")
EXCLUDED_PREFIXES = (
    "magica/js/libs/",
    "magica/scenario/",
    "magica/resource/",
    "magica/research/",
    "magica/i18n_audit/",
    "magica/template/test/",
)


def active_rows() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for top in ("magica/template", "magica/js", "magica/css"):
        for path in (ROOT / top).rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(EXCLUDED_PREFIXES):
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
            text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            for line in text.splitlines():
                if line.lstrip().startswith("//"):
                    continue
                if KANA.search(line):
                    rows.append((rel, line.strip()))
    return rows


def classify(rel: str, line: str) -> str:
    if rel == "magica/template/formation/DeckFormation.html" and "//" in line:
        return "EJS_DEVELOPMENT_COMMENT"
    if rel == "magica/template/item/ItemListTop.html" and 'prm[1] !== "なし"' in line:
        return "INTERNAL_SENTINEL"
    if rel == "magica/template/user/APPopup2.html" and "item.itemName" in line and '"マギアストーン"' in line:
        return "EXACT_BEFORE_BRANCH"
    if rel == "magica/template/regularEvent/groupBattle/RegularEventGroupBattleBoss.html" and '"幸福な魔女" ? "幸福魔女"' in line:
        return "EXACT_BEFORE_IMMEDIATE_TARGET"
    if rel in {
        "magica/template/user/Ban.html",
        "magica/js/test/BackdoorList.js",
        "magica/js/event/EventArenaRankMatch/Utility.js",
    } and not KANA.search(line.replace("・", "")):
        return "MIDDLE_DOT_PUNCTUATION"
    raise AssertionError(f"unclassified active kana: {rel}: {line}")


def main() -> None:
    rows = active_rows()
    categories = Counter(classify(rel, line) for rel, line in rows)
    files = {rel for rel, _ in rows}
    expected = Counter(
        {
            "EJS_DEVELOPMENT_COMMENT": 8,
            "INTERNAL_SENTINEL": 1,
            "EXACT_BEFORE_BRANCH": 2,
            "EXACT_BEFORE_IMMEDIATE_TARGET": 2,
            "MIDDLE_DOT_PUNCTUATION": 3,
        }
    )
    assert len(rows) == 16, f"active kana denominator drift: {len(rows)}"
    assert len(files) == 7, f"active kana file denominator drift: {len(files)}"
    assert categories == expected, f"classification drift: {categories}"
    print("PASS51_ACTIVE_STATIC_KANA_DENOMINATOR=PASS")
    print(f"NONCOMMENT_KANA_LINES={len(rows)}")
    print(f"NONCOMMENT_KANA_FILES={len(files)}")
    print("PLAYER_VISIBLE_KANA_GAPS=0")
    for name in sorted(categories):
        print(f"CLASS_{name}={categories[name]}")


if __name__ == "__main__":
    main()
