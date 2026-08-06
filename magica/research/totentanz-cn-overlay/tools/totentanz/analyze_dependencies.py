from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
NEW_ROOT = HERE / "extracted" / "totentanz-frontend" / "totentanz-frontend"
OLD_ROOT = HERE / "old_cn"
TEXT_EXTS = {".html", ".js", ".css"}


def status(rel: str) -> str:
    n, o = NEW_ROOT / rel, OLD_ROOT / rel
    if n.is_file() and o.is_file():
        return "present_both"
    if n.is_file():
        return "current_only"
    if o.is_file():
        return "old_only"
    return "absent_both"


def add_ref(rows: list[dict], source: str, kind: str, raw: str, rel: str, dynamic: bool = False) -> None:
    rel = rel.lstrip("/")
    if rel.startswith("magica/"):
        rel = rel[len("magica/") :]
    rows.append(
        {
            "source_file": source,
            "reference_kind": kind,
            "raw_reference": raw,
            "resolved_path": rel,
            "dynamic": dynamic,
            "availability": "dynamic" if dynamic else status(rel),
        }
    )


def main() -> None:
    rows: list[dict] = []
    index = (NEW_ROOT / "index.html").read_text(encoding="utf-8-sig")
    for m in re.finditer(r"(?:src|href)=[\"'](/magica/[^\"']+)[\"']", index):
        raw = m.group(1)
        clean = raw.split("?", 1)[0]
        add_ref(rows, "index.html", "index_static", raw, clean)

    # RequireJS dependencies use text!template/... and text!css/...; direct
    # module IDs under js/... omit .js. Dynamic concatenations are retained as
    # prefixes but excluded from availability assertions.
    dep_re = re.compile(r"(?P<prefix>text!)?(?P<path>(?:template|css|js)/[A-Za-z0-9_./-]+)")
    for p in sorted(NEW_ROOT.rglob("*.js")):
        rel_src = p.relative_to(NEW_ROOT).as_posix()
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        for m in dep_re.finditer(text):
            raw = m.group(0)
            rel = m.group("path")
            # Ignore path-like snippets from URLs or assignments unless they
            # are dependencies/resources with a recognized extension/prefix.
            if rel.startswith("js/") and not rel.endswith(".js"):
                rel += ".js"
            dynamic = rel.endswith("/") or (m.end() < len(text) and text[m.end() : m.end() + 4].lstrip().startswith("+"))
            if not dynamic and Path(rel).suffix.lower() not in {".js", ".html", ".css", ".json"}:
                continue
            add_ref(rows, rel_src, "require_dependency", raw, rel, dynamic)

    # De-duplicate identical references from the same source.
    unique = []
    seen = set()
    for row in rows:
        key = tuple(row.values())
        if key not in seen:
            seen.add(key)
            unique.append(row)
    rows = unique
    with (HERE / "dependency_audit.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # Parse the current baseConfig mapping as a separate route/module inventory.
    cfg = (NEW_ROOT / "js/_common/baseConfig.js").read_text(encoding="utf-8-sig")
    map_rows = []
    for key, path in re.findall(r'([A-Za-z_$][\w$]*):"(js/[^"]+)"', cfg):
        rel = path if path.endswith(".js") else path + ".js"
        map_rows.append({"module": key, "mapped_path": rel, "availability": status(rel)})
    # Stable unique-by-module+path.
    map_rows = list({(r["module"], r["mapped_path"]): r for r in map_rows}.values())
    map_rows.sort(key=lambda r: (r["mapped_path"], r["module"]))
    with (HERE / "require_map.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(map_rows[0]))
        w.writeheader()
        w.writerows(map_rows)

    payload = {
        "summary": {
            "references": len(rows),
            "reference_availability": dict(Counter(r["availability"] for r in rows)),
            "require_mappings": len(map_rows),
            "require_map_availability": dict(Counter(r["availability"] for r in map_rows)),
        },
        "references": rows,
        "require_map": map_rows,
    }
    (HERE / "dependency_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
