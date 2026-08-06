from __future__ import annotations

import csv
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
NEW_ROOT = HERE / "extracted" / "totentanz-frontend" / "totentanz-frontend"
OLD_ROOT = HERE / "old_cn"


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def split_selectors(prelude: str) -> list[str]:
    out, start = [], 0
    quote = None
    level = 0
    esc = False
    for i, ch in enumerate(prelude):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([":
            level += 1
        elif ch in ")]":
            level = max(0, level - 1)
        elif ch == "," and level == 0:
            out.append(norm(prelude[start:i]))
            start = i + 1
    out.append(norm(prelude[start:]))
    return [x for x in out if x]


def find_close(text: str, opening: int) -> int:
    level = 0
    quote = None
    esc = False
    for i in range(opening, len(text)):
        ch = text[i]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "{":
            level += 1
        elif ch == "}":
            level -= 1
            if level == 0:
                return i
    return len(text) - 1


def parse_rules(text: str, scope: str = "") -> dict[str, list[str]]:
    text = strip_comments(text)
    rules: dict[str, list[str]] = {}
    pos = 0
    while pos < len(text):
        opening = text.find("{", pos)
        if opening < 0:
            break
        prelude = norm(text[pos:opening])
        closing = find_close(text, opening)
        body = text[opening + 1 : closing]
        if prelude.startswith("@media") or prelude.startswith("@supports") or prelude.startswith("@layer"):
            nested_scope = f"{scope}{prelude}::"
            nested = parse_rules(body, nested_scope)
            for key, vals in nested.items():
                rules.setdefault(key, []).extend(vals)
        elif prelude.startswith("@keyframes") or prelude.startswith("@-webkit-keyframes"):
            rules.setdefault(f"{scope}{prelude}", []).append(norm(body))
        elif prelude.startswith("@font-face") or prelude.startswith("@page"):
            rules.setdefault(f"{scope}{prelude}", []).append(norm(body))
        elif prelude.startswith("@"):
            rules.setdefault(f"{scope}{prelude}", []).append(norm(body))
        else:
            for selector in split_selectors(prelude):
                rules.setdefault(f"{scope}{selector}", []).append(norm(body))
        pos = closing + 1
    return rules


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def content_strings(text: str) -> list[str]:
    vals = re.findall(r"\bcontent\s*:\s*([\"'])(.*?)\1", text, flags=re.S | re.I)
    return [v for _, v in vals if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", v)]


def main() -> None:
    paths = sorted(
        {p.relative_to(NEW_ROOT).as_posix() for p in NEW_ROOT.rglob("*.css")}
        | {p.relative_to(OLD_ROOT).as_posix() for p in OLD_ROOT.rglob("*.css")}
    )
    rows = []
    details = {}
    for rel in paths:
        np, op = NEW_ROOT / rel, OLD_ROOT / rel
        ntext = read(np) if np.exists() else ""
        otext = read(op) if op.exists() else ""
        nr = parse_rules(ntext) if ntext else {}
        or_ = parse_rules(otext) if otext else {}
        ns, os = set(nr), set(or_)
        common = ns & os
        exact = {s for s in common if nr[s] == or_[s]}
        changed = common - exact
        added, removed = ns - os, os - ns
        if np.exists() and op.exists():
            status = "shared_identical" if ntext == otext else "shared_modified"
        elif np.exists():
            status = "current_only"
        else:
            status = "old_only"
        union = len(ns | os)
        row = {
            "path": rel,
            "status": status,
            "current_rule_count": len(ns),
            "old_rule_count": len(os),
            "common_rule_count": len(common),
            "exact_rule_count": len(exact),
            "changed_rule_count": len(changed),
            "current_only_rule_count": len(added),
            "old_only_rule_count": len(removed),
            "selector_jaccard": round(len(common) / union, 6) if union else 1.0,
            "current_content_strings": " | ".join(content_strings(ntext)),
            "old_content_strings": " | ".join(content_strings(otext)),
        }
        rows.append(row)
        if added or removed or changed or row["current_content_strings"] or row["old_content_strings"]:
            details[rel] = {
                "status": status,
                "current_only_selectors": sorted(added),
                "old_only_selectors": sorted(removed),
                "changed_shared_selectors": sorted(changed),
                "current_content_strings": content_strings(ntext),
                "old_content_strings": content_strings(otext),
            }
    with (HERE / "css_diff.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (HERE / "css_diff.json").write_text(
        json.dumps({"files": rows, "details": details}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "files": len(rows),
        "current_only_selectors": sum(r["current_only_rule_count"] for r in rows),
        "old_only_selectors": sum(r["old_only_rule_count"] for r in rows),
        "changed_shared_selectors": sum(r["changed_rule_count"] for r in rows),
        "exact_shared_selectors": sum(r["exact_rule_count"] for r in rows),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
