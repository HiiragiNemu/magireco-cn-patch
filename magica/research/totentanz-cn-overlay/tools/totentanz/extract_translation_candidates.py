from __future__ import annotations

import csv
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from analyze_css import content_strings, parse_rules


HERE = Path(__file__).resolve().parent
NEW_ROOT = HERE / "extracted" / "totentanz-frontend" / "totentanz-frontend"
OLD_ROOT = HERE / "old_cn"
EAST_ASIAN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
KANA = re.compile(r"[\u3040-\u30ff]")
CJK = re.compile(r"[\u3400-\u9fff]")
JS_STRING = re.compile(r'(?P<q>[\"\'])(?P<body>(?:\\.|(?!\1).)*?)(?P=q)', re.S)


def human(s: str) -> bool:
    s = s.strip()
    if not EAST_ASIAN.search(s):
        return False
    if len(s) > 500:
        return False
    # Most resource/module paths contain a slash and no whitespace/punctuation.
    if "/" in s and not re.search(r"[。！？、，：；\s]", s):
        return False
    return True


def js_tokens(text: str) -> list[str]:
    return [m.group("body") for m in JS_STRING.finditer(text)]


def html_tokens(text: str) -> list[str]:
    vals = []
    for s in re.findall(r">([^<>]+)<", text, flags=re.S):
        s = re.sub(r"<%.*?%>", "", s, flags=re.S)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            vals.append(s)
    for s in re.findall(r"\b(?:title|placeholder|alt|value)=[\"']([^\"']+)[\"']", text, flags=re.I):
        if s.strip():
            vals.append(s.strip())
    return vals


def paired_replacements(current: list[str], old: list[str]) -> list[tuple[str, str, str, str]]:
    out = []
    sm = SequenceMatcher(None, current, old, autojunk=False)
    opcodes = sm.get_opcodes()
    for idx, (tag, i1, i2, j1, j2) in enumerate(opcodes):
        if tag != "replace" or i2 - i1 != j2 - j1 or i2 == i1 or i2 - i1 > 12:
            continue
        anchored_before = idx > 0 and opcodes[idx - 1][0] == "equal"
        anchored_after = idx + 1 < len(opcodes) and opcodes[idx + 1][0] == "equal"
        span = i2 - i1
        for a, b in zip(current[i1:i2], old[j1:j2]):
            if a == b or not human(a) or not human(b):
                continue
            # Desired direction is Japanese/current -> Chinese/old. Retain a
            # few mixed strings but require the old side to not add kana.
            if len(KANA.findall(b)) > len(KANA.findall(a)):
                continue
            if anchored_before and anchored_after and span <= 4:
                conf = "high"
                evidence = "equal literal anchors on both sides"
            elif (anchored_before or anchored_after) and span <= 6:
                conf = "review"
                evidence = "one equal literal anchor and equal replacement arity"
            else:
                continue
            guards = semantic_guards(a, b)
            if guards:
                conf = "review"
                evidence += "; " + "; ".join(guards)
            out.append((a, b, conf, evidence))
    return out


def unescape_markup(s: str) -> str:
    return (
        s.replace("\\x3c", "<").replace("\\x3e", ">").replace("\\x3d", "=")
        .replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u003d", "=")
    )


def semantic_guards(current: str, old: str) -> list[str]:
    guards = []
    c, o = unescape_markup(current), unescape_markup(old)
    cplain = unicodedata.normalize("NFKC", re.sub(r"<[^>]*>", "", c))
    oplain = unicodedata.normalize("NFKC", re.sub(r"<[^>]*>", "", o))
    if re.findall(r"\d+(?:\.\d+)?", cplain) != re.findall(r"\d+(?:\.\d+)?", oplain):
        guards.append("numeric tokens differ")
    ctags = [x.lower() for x in re.findall(r"</?([a-z][\w-]*)\b", c, flags=re.I)]
    otags = [x.lower() for x in re.findall(r"</?([a-z][\w-]*)\b", o, flags=re.I)]
    if ctags != otags:
        guards.append("embedded markup skeleton differs")
    cph = re.findall(r"%(?:\d+\$)?[sdif]|\{\{.*?\}\}|\$\{.*?\}", current)
    oph = re.findall(r"%(?:\d+\$)?[sdif]|\{\{.*?\}\}|\$\{.*?\}", old)
    if cph != oph:
        guards.append("placeholder tokens differ")
    return guards


def main() -> None:
    rows = []
    for ext, extractor, kind in (("*.js", js_tokens, "js_literal"), ("*.html", html_tokens, "html_text")):
        for np in sorted(NEW_ROOT.rglob(ext)):
            rel = np.relative_to(NEW_ROOT)
            op = OLD_ROOT / rel
            if not op.is_file():
                continue
            nt = extractor(np.read_text(encoding="utf-8-sig", errors="replace"))
            ot = extractor(op.read_text(encoding="utf-8-sig", errors="replace"))
            for cur, old, conf, evidence in paired_replacements(nt, ot):
                rows.append(
                    {
                        "path": rel.as_posix(),
                        "kind": kind,
                        "current_text": cur,
                        "legacy_cn_text": old,
                        "confidence": conf,
                        "evidence": evidence,
                    }
                )
    for np in sorted(NEW_ROOT.rglob("*.css")):
        rel = np.relative_to(NEW_ROOT)
        op = OLD_ROOT / rel
        if not op.is_file():
            continue
        nr = parse_rules(np.read_text(encoding="utf-8-sig", errors="replace"))
        or_ = parse_rules(op.read_text(encoding="utf-8-sig", errors="replace"))
        for selector in sorted(set(nr) & set(or_)):
            nc = content_strings(";".join(nr[selector]))
            oc = content_strings(";".join(or_[selector]))
            if len(nc) != len(oc):
                continue
            for cur, old in zip(nc, oc):
                if cur == old or not human(cur) or not human(old):
                    continue
                guards = semantic_guards(cur, old)
                rows.append(
                    {
                        "path": rel.as_posix(),
                        "kind": "css_content",
                        "current_text": cur,
                        "legacy_cn_text": old,
                        "confidence": "review" if guards else "high",
                        "evidence": "same CSS selector: " + selector + ("; " + "; ".join(guards) if guards else ""),
                    }
                )

    # Stable dedupe without losing evidence order.
    unique, seen = [], set()
    for row in rows:
        key = (row["path"], row["kind"], row["current_text"], row["legacy_cn_text"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    rows = unique
    with (HERE / "translation_candidates.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (HERE / "translation_candidates.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    inventory = json.loads((HERE / "inventory.json").read_text(encoding="utf-8"))
    current_only = {e["path"] for e in inventory["entries"] if e["status"] == "current_only"}
    new_ui_rows = []
    for rel_s in sorted(current_only):
        p = NEW_ROOT / rel_s
        if p.suffix == ".js":
            vals, kind = js_tokens(p.read_text(encoding="utf-8-sig", errors="replace")), "js_literal"
        elif p.suffix == ".html":
            vals, kind = html_tokens(p.read_text(encoding="utf-8-sig", errors="replace")), "html_text"
        elif p.suffix == ".css":
            vals, kind = content_strings(p.read_text(encoding="utf-8-sig", errors="replace")), "css_content"
        else:
            continue
        seen_vals = set()
        for val in vals:
            if human(val) and val not in seen_vals:
                seen_vals.add(val)
                new_ui_rows.append({
                    "path": rel_s,
                    "kind": kind,
                    "source_text": val,
                    "cn_text": "",
                    "status": "manual_translation_required",
                })
    with (HERE / "new_ui_strings.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(new_ui_rows[0]))
        w.writeheader()
        w.writerows(new_ui_rows)
    (HERE / "new_ui_strings.json").write_text(
        json.dumps(new_ui_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "total": len(rows),
        "high": sum(r["confidence"] == "high" for r in rows),
        "review": sum(r["confidence"] == "review" for r in rows),
        "files": len({r["path"] for r in rows}),
        "new_ui_manual_strings": len(new_ui_rows),
        "new_ui_files_with_strings": len({r["path"] for r in new_ui_rows}),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
