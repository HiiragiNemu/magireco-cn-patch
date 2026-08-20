#!/usr/bin/env python3
"""Inventory potentially visible non-Chinese text without editing products."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from lxml import html


JP_RE = re.compile(r"[\u3040-\u30ff]")
LATIN_WORD_RE = re.compile(r"(?<![A-Za-z])[A-Za-z][A-Za-z'’.-]*(?:\s+[A-Za-z][A-Za-z'’.-]*)+")
ANY_LATIN_RE = re.compile(r"[A-Za-z]")
EJS_RE = re.compile(r"<%[\s\S]*?%>")
JS_STRING_RE = re.compile(
    r"(?P<quote>['\"])(?P<body>(?:\\.|(?!\1)[^\\\r\n])*)(?P=quote)", re.MULTILINE
)
CSS_CONTENT_RE = re.compile(
    r"\bcontent\s*:\s*(?P<quote>['\"])(?P<body>(?:\\.|(?!\1).)*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)

DISPLAY_ATTRS = ("title", "placeholder", "alt", "value", "aria-label")
UI_CONTEXT = re.compile(
    r"(?:title|content|message|label|caption|description|text|html|placeholder|"
    r"PopupClass|popup|alert|confirm|notice|toast|button|btn|displayName|shortDescription)\s*[:=]",
    re.IGNORECASE,
)
UI_CONTEXT_END = re.compile(
    r"(?:title|content|message|label|caption|description|text|html|placeholder|"
    r"PopupClass|alert|confirm|notice|toast|displayName|shortDescription)\s*[:=]\s*$|"
    r"\.(?:text|html|append|prepend)\s*\(\s*$",
    re.IGNORECASE,
)
TECHNICAL_VALUE = re.compile(
    r"^(?:https?://|/|\.\.?/|#|\.|[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+|"
    r"[A-Za-z0-9_$-]+(?:/[A-Za-z0-9_.$@%+~#?&=-]+)+|"
    r"[a-z][a-z0-9_-]*(?:\s+[a-z][a-z0-9_-]*)*)$"
)
FORMAL_RETAINED = re.compile(
    r"^(?:AP|BP|CP|CC|HP|MP|EXP|ATK|DEF|Magia|Accele|Blast|Charge|Connect|DISK|"
    r"Lv\.?|MAX|BONUS|AUTO|PLAY|LIVE2D|SD|BGM|SE|VOICE|ON|OFF|OK)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    item_id: str
    path: str
    line: int
    channel: str
    source_text: str
    language_flag: str
    classification: str
    context: str


def clean_visible(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("{{EJS}}", "")).strip()


def language_flag(value: str) -> str:
    flags: list[str] = []
    if JP_RE.search(value):
        flags.append("japanese")
    if LATIN_WORD_RE.search(value) or (ANY_LATIN_RE.search(value) and len(value) <= 24):
        flags.append("latin")
    return "+".join(flags)


def classify(value: str, *, channel: str, context: str) -> str:
    if FORMAL_RETAINED.fullmatch(value.strip()):
        return "formal-retained-review"
    if not language_flag(value):
        return "not-target"
    if channel.startswith("html-") or channel in {"css-content", "json-value"}:
        return "visible-review"
    if channel == "js-ui-literal":
        return "visible-review"
    if TECHNICAL_VALUE.fullmatch(value.strip()):
        return "technical-excluded"
    return "context-review"


def add(
    rows: list[Finding], *, rel: str, line: int, channel: str, value: str, context: str
) -> None:
    value = clean_visible(value)
    flag = language_flag(value)
    if not value or not flag:
        return
    rows.append(
        Finding(
            item_id="",
            path=rel,
            line=line,
            channel=channel,
            source_text=value,
            language_flag=flag,
            classification=classify(value, channel=channel, context=context),
            context=re.sub(r"\s+", " ", context).strip()[:600],
        )
    )


def scan_html(path: Path, rel: str, rows: list[Finding]) -> None:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    parsed_text = EJS_RE.sub("{{EJS}}", raw)
    try:
        root = html.fragment_fromstring(parsed_text, create_parent="audit-root")
    except Exception:
        for match in re.finditer(r">([^<>]+)<", parsed_text, re.DOTALL):
            add(
                rows,
                rel=rel,
                line=raw.count("\n", 0, match.start()) + 1,
                channel="html-fallback",
                value=match.group(1),
                context=match.group(1),
            )
        return
    for elem in root.iter():
        if not isinstance(elem.tag, str) or elem.tag.lower() in {"script", "style"}:
            continue
        signature = f"<{elem.tag} id={elem.get('id','')} class={elem.get('class','')}>"
        if elem.text:
            add(rows, rel=rel, line=int(elem.sourceline or 1), channel="html-text", value=elem.text, context=signature)
        for attr in DISPLAY_ATTRS:
            if attr in elem.attrib:
                add(
                    rows,
                    rel=rel,
                    line=int(elem.sourceline or 1),
                    channel=f"html-attr:{attr}",
                    value=elem.attrib[attr],
                    context=signature,
                )
        if elem.tail:
            parent = elem.getparent()
            parent_sig = (
                f"<{parent.tag} id={parent.get('id','')} class={parent.get('class','')}>"
                if parent is not None and isinstance(parent.tag, str)
                else signature
            )
            add(rows, rel=rel, line=int(elem.sourceline or 1), channel="html-text", value=elem.tail, context=parent_sig)


def scan_js(path: Path, rel: str, rows: list[Finding]) -> None:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    for match in JS_STRING_RE.finditer(raw):
        value = match.group("body")
        if not language_flag(value):
            continue
        before = raw[max(0, match.start() - 180) : match.start()]
        after = raw[match.end() : min(len(raw), match.end() + 120)]
        channel = "js-ui-literal" if UI_CONTEXT_END.search(before[-100:]) else "js-literal"
        add(
            rows,
            rel=rel,
            line=raw.count("\n", 0, match.start()) + 1,
            channel=channel,
            value=value,
            context=before + "<STRING>" + after,
        )


def scan_css(path: Path, rel: str, rows: list[Finding]) -> None:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    for match in CSS_CONTENT_RE.finditer(raw):
        add(
            rows,
            rel=rel,
            line=raw.count("\n", 0, match.start()) + 1,
            channel="css-content",
            value=match.group("body"),
            context=raw[max(0, match.start() - 180) : match.end() + 80],
        )


def walk_json(value: object, pointer: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_json(child, f"{pointer}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_json(child, f"{pointer}[{index}]")
    elif isinstance(value, str):
        yield pointer, value


def scan_json(path: Path, rel: str, rows: list[Finding]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return
    for pointer, value in walk_json(data):
        add(rows, rel=rel, line=1, channel="json-value", value=value, context=pointer)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.out.resolve()
    rows: list[Finding] = []
    skipped_generated: list[str] = []
    handlers = {".html": scan_html, ".js": scan_js, ".css": scan_css, ".json": scan_json}
    for path in sorted(root.rglob("*")):
        handler = handlers.get(path.suffix.lower())
        if handler and path.is_file():
            rel_path = path.relative_to(root)
            if rel_path.parts[0] not in {"js", "template", "css", "json", "resource"} and rel_path.as_posix() != "index.html":
                continue
            # The generated jQuery injector is assembled from the separately
            # audited runtime dictionaries.  Scanning third-party/minified
            # library bytes as UI literals creates only code false positives.
            if path.suffix.lower() == ".js" and path.stat().st_size > 2_000_000:
                skipped_generated.append(rel_path.as_posix())
                continue
            handler(path, rel_path.as_posix(), rows)
    unique: list[Finding] = []
    seen: set[tuple[str, int, str, str]] = set()
    for row in rows:
        key = (row.path, row.line, row.channel, row.source_text)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    rows = [replace(row, item_id=f"VISIBLE-{index:05d}") for index, row in enumerate(unique, 1)]
    out.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(rows[0])) if rows else list(Finding.__dataclass_fields__)
    with (out / "visible_text_inventory.tsv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    (out / "visible_text_inventory.json").write_text(
        json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.classification] = counts.get(row.classification, 0) + 1
    summary = {
        "schema": "totentanz-visible-text-inventory-v1",
        "root": str(root),
        "items": len(rows),
        "files": len({row.path for row in rows}),
        "classification_counts": dict(sorted(counts.items())),
        "skipped_generated_or_library_files": skipped_generated,
        "product_tree_writes": 0,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
