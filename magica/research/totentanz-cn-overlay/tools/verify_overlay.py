#!/usr/bin/env python3
"""Verify overlay provenance, geometry, CSS integrity, JS syntax and HTML shape."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path


RESEARCH_REL = Path("research/totentanz-cn-overlay")
MANIFEST_REL = RESEARCH_REL / "manifests/verified_menu_overlay.json"
NEW_UI_MANIFEST_REL = RESEARCH_REL / "evidence/new-ui/manifest.json"


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


class ShapeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.tags: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        keys = ",".join(sorted(key for key, _ in attrs))
        self.tags.append(("start", f"{tag}:{keys}"))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        keys = ",".join(sorted(key for key, _ in attrs))
        self.tags.append(("empty", f"{tag}:{keys}"))

    def handle_endtag(self, tag: str) -> None:
        self.tags.append(("end", tag))


def html_shape(path: Path) -> list[tuple[str, str]]:
    parser = ShapeParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser.tags


def run(command: list[str], cwd: Path | None = None) -> dict:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "command": command,
        "exit_status": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-magica", type=Path, required=True)
    parser.add_argument("--totentanz-magica", type=Path, required=True)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()

    repo = args.repo_magica.resolve()
    current = args.totentanz_magica.resolve()
    manifest = json.loads((repo / MANIFEST_REL).read_text(encoding="utf-8"))
    errors: list[str] = []
    checks: list[dict] = []

    css = repo / manifest["common_css"]["path"]
    css_bytes = css.read_bytes()
    css_check = {
        "role": "current_ui_common_css",
        "path": str(css),
        "md5": hashlib.md5(css_bytes).hexdigest(),
        "sha256": hashlib.sha256(css_bytes).hexdigest(),
        "legacy_tail_present": "主页菜单按钮".encode("utf-8") in css_bytes,
    }
    if css_check["md5"] != manifest["common_css"]["expected_base_md5"]:
        errors.append("common.css does not match the current UI baseline MD5")
    if css_check["legacy_tail_present"]:
        errors.append("legacy background redirect tail still exists")
    checks.append(css_check)

    for item in manifest["images"]:
        baseline = current / item["target"]
        target = repo / item["target"]
        row = {
            "role": "menu_image",
            "id": item["id"],
            "text": item["text"],
            "baseline": str(baseline),
            "target": str(target),
        }
        for label, path, expected_hash in (
            ("baseline", baseline, item["baseline_sha256"]),
            ("target", target, item["output_sha256"]),
        ):
            if not path.is_file():
                errors.append(f"{label} image missing: {path}")
                continue
            actual_hash = digest(path)
            actual_size = png_size(path)
            row[f"{label}_sha256"] = actual_hash
            row[f"{label}_size"] = list(actual_size)
            if actual_hash != expected_hash:
                errors.append(f"{label} hash mismatch: {path}")
            if actual_size != (item["width"], item["height"]):
                errors.append(f"{label} geometry mismatch: {path}")
        checks.append(row)

    new_ui_manifest = json.loads((repo / NEW_UI_MANIFEST_REL).read_text(encoding="utf-8"))
    new_ui_rows: list[dict] = []
    for item in new_ui_manifest["files"]:
        baseline = current / item["path"]
        target = repo / item["path"]
        row = {"path": item["path"]}
        for label, path, expected_hash in (
            ("baseline", baseline, item["baseline_sha256"]),
            ("target", target, item["overlay_sha256"]),
        ):
            if not path.is_file():
                errors.append(f"new UI {label} missing: {path}")
                continue
            actual_hash = digest(path)
            row[f"{label}_sha256"] = actual_hash
            if actual_hash != expected_hash:
                errors.append(f"new UI {label} hash mismatch: {path}")
        new_ui_rows.append(row)
    checks.append(
        {
            "role": "current_only_ui_localization",
            "files": len(new_ui_rows),
            "records": new_ui_manifest["counts"]["records"],
            "production_records": new_ui_manifest["counts"]["production_records"],
            "test_records": new_ui_manifest["counts"]["test_records"],
            "hash_checks": new_ui_rows,
        }
    )

    node = shutil.which("node")
    js_results: list[dict] = []
    if node:
        for path in sorted(repo.rglob("*.js")):
            result = run([node, "--check", str(path)])
            js_results.append({"path": str(path), "exit_status": result["exit_status"], "stderr": result["stderr"]})
            if result["exit_status"]:
                errors.append(f"Node syntax failure: {path}")
    else:
        errors.append("node executable was not found")
    checks.append({"role": "javascript_syntax", "files": len(js_results), "failures": sum(x["exit_status"] != 0 for x in js_results)})

    html_pairs = 0
    html_failures = 0
    for path in sorted(repo.rglob("*.html")):
        rel = path.relative_to(repo)
        baseline = current / rel
        if not baseline.is_file():
            continue
        html_pairs += 1
        if html_shape(path) != html_shape(baseline):
            html_failures += 1
    checks.append({"role": "html_tag_attribute_shape", "comparable_files": html_pairs, "failures": html_failures})
    if html_failures:
        errors.append(f"HTML tag/attribute shape drift in {html_failures} comparable files")

    record = {
        "schema_version": 1,
        "status": "pass" if not errors else "fail",
        "inputs": {"repo_magica": str(repo), "totentanz_magica": str(current)},
        "checks": checks,
        "errors": errors,
    }
    rendered = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
