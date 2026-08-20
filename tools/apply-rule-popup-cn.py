#!/usr/bin/env python3
"""Apply the reviewed Simplified Chinese translation of RulePopup.html."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import tempfile
from pathlib import Path


REPO_DEFAULT = Path(__file__).resolve().parents[1]
SOURCE_DEFAULT = Path(r"A:\totentanz-frontend\template\etc\RulePopup.html")
AUDIT_REL = Path(
    "magica/research/totentanz-full-localization-20260817/"
    "rule-popup-cn-20260819"
)
INPUT_REL = AUDIT_REL / "input"
STATE_REL = AUDIT_REL / "runtime"
PRODUCT_REL = Path("magica/template/etc/RulePopup.html")
EXPECTED_SOURCE_BYTES = 29770
EXPECTED_SOURCE_LINES = 173
EXPECTED_TRANSLATION_ROWS = 146
EXPECTED_IDS = ["rulesBase", "rulePolicyLink", "ruleLinkAdjust"]
EXPECTED_URLS = [
    "https://www.aniplex.co.jp/help/privacy.html",
    "https://www.adjust.com/ja/terms/privacy-policy/",
]
PRESERVED_TOKENS = [
    "Sauce Labs Inc.",
    "Backtrace",
    "Adjust",
    "Pnote",
]
SOURCE_TO_FINAL_TERMS = {
    "株式会社アニプレックス": "Aniplex股份有限公司",
    "著作権法": "《著作权法》",
    "資金決済法": "《资金结算法》",
    "個人情報の保護に関する法律": "《个人信息保护法》",
    "日本法": "日本法律",
    "前払式支払手段": "预付式支付手段",
    "東京地方裁判所": "东京地方法院",
    "adjust株式会社": "adjust股份有限公司",
    "株式会社セガ": "世嘉股份有限公司",
}
FORBIDDEN_JAPANESE_TERMS = [
    "株式会社アニプレックス",
    "著作権法",
    "資金決済法",
    "個人情報の保護に関する法律",
    "前払式支払手段",
    "東京地方裁判所",
    "adjust株式会社",
    "株式会社セガ",
    "セガ公司",
]
PURE_STRUCTURE_LINES = {
    '<div id="rulesBase">',
    '<div class="popupScrollWrap rulesPop">',
    "</div>",
    "<br>",
}


def clean_text(data: bytes) -> str:
    return data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def tag_tokens(text: str) -> list[str]:
    return re.findall(r"<[^>]*>", text)


def ejs_tokens(text: str) -> list[str]:
    return re.findall(r"<%[\s\S]*?%>", text)


def dom_ids(text: str) -> list[str]:
    return [match.group(2) for match in re.finditer(r"\bid=([\"'])(.*?)\1", text)]


def urls(text: str) -> list[str]:
    return re.findall(r"https?://[^<\s]+", text)


def load_translation_rows(path: Path) -> dict[int, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != ["line_no", "final_html"]:
            raise ValueError("translation table columns changed")
        rows: dict[int, str] = {}
        for row in reader:
            line_no = int(row["line_no"])
            final = row["final_html"]
            if line_no in rows:
                raise ValueError(f"duplicate translation line: {line_no}")
            if not final or final != final.strip() or "\r" in final or "\n" in final or "\t" in final:
                raise ValueError(f"invalid translated line: {line_no}")
            rows[line_no] = final
    if len(rows) != EXPECTED_TRANSLATION_ROWS:
        raise ValueError(f"translation row count changed: {len(rows)}")
    return rows


def build_translation(source: str, rows: dict[int, str]) -> tuple[str, list[dict]]:
    source_lines = source.splitlines()
    if len(source_lines) != EXPECTED_SOURCE_LINES:
        raise ValueError(f"source line count changed: {len(source_lines)}")
    visible_lines = {
        index
        for index, line in enumerate(source_lines, 1)
        if line.strip() and line.strip() not in PURE_STRUCTURE_LINES
    }
    if set(rows) != visible_lines:
        raise ValueError(
            f"translation coverage changed: missing={sorted(visible_lines-set(rows))}, "
            f"extra={sorted(set(rows)-visible_lines)}"
        )
    output: list[str] = []
    records: list[dict] = []
    for index, line in enumerate(source_lines, 1):
        if index not in rows:
            output.append(line)
            continue
        leading = line[: len(line) - len(line.lstrip())]
        source_html = line.strip()
        final_html = rows[index]
        output.append(leading + final_html)
        records.append(
            {
                "line_no": index,
                "source_html": source_html,
                "final_html": final_html,
                "operation": "preserve-exact" if source_html == final_html else "translate-line",
                "source_tier": "root-reviewed-translation",
            }
        )
    translated = "\n".join(output) + "\n"
    validate_structure(source, translated)
    return translated, records


def validate_structure(source: str, translated: str) -> None:
    if tag_tokens(source) != tag_tokens(translated):
        raise ValueError("HTML tag sequence changed")
    if ejs_tokens(source) != ejs_tokens(translated):
        raise ValueError("EJS token sequence changed")
    if dom_ids(source) != EXPECTED_IDS or dom_ids(translated) != EXPECTED_IDS:
        raise ValueError("DOM id contract changed")
    if urls(source) != EXPECTED_URLS or urls(translated) != EXPECTED_URLS:
        raise ValueError("URL contract changed")
    if len(source.splitlines()) != len(translated.splitlines()):
        raise ValueError("HTML line structure changed")
    for token in PRESERVED_TOKENS:
        if source.count(token) != translated.count(token):
            raise ValueError(f"preserved Latin token count changed: {token}")
    for source_term, final_term in SOURCE_TO_FINAL_TERMS.items():
        source_count = source.count(source_term)
        if source_count < 1 or translated.count(final_term) != source_count:
            raise ValueError(f"required legal/name translation count changed: {source_term} -> {final_term}")
    for token in FORBIDDEN_JAPANESE_TERMS:
        if token in translated:
            raise ValueError(f"visible Japanese legal/name term remains: {token}")
    if re.search(r"日本法(?!律)", translated):
        raise ValueError("visible Japanese legal name remains: 日本法")
    residue = sorted(set(re.findall(r"[\u3040-\u30ff]+", translated)))
    if residue:
        raise ValueError(f"unexpected Japanese kana remains: {residue}")


def comparison_tsv(records: list[dict]) -> bytes:
    fields = ["line_no", "source_html", "final_html", "operation", "source_tier"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue().encode("utf-8")


def prepare(repo: Path, source_path: Path, input_dir: Path, state: Path) -> dict:
    product = repo / PRODUCT_REL
    if product.exists():
        raise ValueError(f"refusing to replace existing product file: {product}")
    source_bytes = source_path.read_bytes()
    mirror_bytes = (input_dir / "RulePopup.ja.html").read_bytes()
    if len(source_bytes) != EXPECTED_SOURCE_BYTES or source_bytes != mirror_bytes:
        raise ValueError("A: current source differs from the reviewed source mirror")
    source = clean_text(source_bytes)
    rows = load_translation_rows(input_dir / "reviewed_translation_lines.tsv")
    translated, records = build_translation(source, rows)
    source_state = state / "source" / "RulePopup.ja.html"
    prepared_state = state / "prepared" / "RulePopup.html"
    write_atomic(source_state, source.encode("utf-8"))
    write_atomic(prepared_state, translated.encode("utf-8"))
    manifest = {
        "schema": 1,
        "scope": "rule-popup-current-structure-simplified-chinese",
        "product_path": str(PRODUCT_REL).replace("\\", "/"),
        "structure_source": str(source_path),
        "source_mirror": str((input_dir / "RulePopup.ja.html").relative_to(repo)).replace("\\", "/"),
        "translation_input": str((input_dir / "reviewed_translation_lines.tsv").relative_to(repo)).replace("\\", "/"),
        "source_tier": "root-reviewed-translation",
        "official_chinese": False,
        "source_bytes": len(source_bytes),
        "prepared_bytes": len(translated.encode("utf-8")),
        "source_lines": len(source.splitlines()),
        "translation_records": len(records),
        "translated_records": sum(row["operation"] == "translate-line" for row in records),
        "preserved_records": sum(row["operation"] == "preserve-exact" for row in records),
        "tag_tokens": len(tag_tokens(source)),
        "ejs_tokens": len(ejs_tokens(source)),
        "dom_ids": EXPECTED_IDS,
        "urls": EXPECTED_URLS,
        "preserved_latin_tokens": {token: source.count(token) for token in PRESERVED_TOKENS},
        "legal_name_translations": {
            source_term: {
                "final_cn": final_term,
                "count": source.count(source_term),
            }
            for source_term, final_term in SOURCE_TO_FINAL_TERMS.items()
        },
        "source_state_path": str(source_state.relative_to(repo)).replace("\\", "/"),
        "prepared_state_path": str(prepared_state.relative_to(repo)).replace("\\", "/"),
    }
    rollback = {
        "schema": 1,
        "operation": "remove-created-file-after-exact-byte-gate",
        "product_path": manifest["product_path"],
        "expected_bytes_path": manifest["prepared_state_path"],
        "before_state": "absent",
    }
    write_atomic(state / "manifest.json", json_bytes(manifest))
    write_atomic(state / "comparison.tsv", comparison_tsv(records))
    write_atomic(state / "rollback.json", json_bytes(rollback))
    return manifest


def load_and_validate(repo: Path, state: Path) -> tuple[dict, bytes]:
    manifest = json.loads((state / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("product_path") != str(PRODUCT_REL).replace("\\", "/"):
        raise ValueError("manifest product scope changed")
    source = (repo / manifest["source_state_path"]).read_text(encoding="utf-8")
    prepared_path = repo / manifest["prepared_state_path"]
    prepared = prepared_path.read_text(encoding="utf-8")
    input_dir = repo / INPUT_REL
    rows = load_translation_rows(input_dir / "reviewed_translation_lines.tsv")
    rebuilt, _ = build_translation(source, rows)
    if rebuilt != prepared:
        raise ValueError("prepared RulePopup drifted from reviewed translation")
    return manifest, prepared_path.read_bytes()


def apply(repo: Path, state: Path, fail_after_write: bool = False) -> dict:
    manifest, prepared = load_and_validate(repo, state)
    product = repo / manifest["product_path"]
    if product.exists():
        raise ValueError("RulePopup product already exists")
    try:
        write_atomic(product, prepared)
        if fail_after_write:
            raise RuntimeError("synthetic apply failure")
    except Exception:
        product.unlink(missing_ok=True)
        raise
    record = {"operation": "apply", "created_files": 1, "result": "passed"}
    write_atomic(state / "apply-record.json", json_bytes(record))
    return record


def verify(repo: Path, state: Path) -> dict:
    manifest, prepared = load_and_validate(repo, state)
    product = repo / manifest["product_path"]
    if not product.is_file() or product.read_bytes() != prepared:
        raise ValueError("RulePopup product differs from reviewed prepared bytes")
    source = (repo / manifest["source_state_path"]).read_text(encoding="utf-8")
    translated = product.read_text(encoding="utf-8")
    validate_structure(source, translated)
    report = {
        "result": "passed",
        "checked_files": 1,
        "translation_records": manifest["translation_records"],
        "translated_records": manifest["translated_records"],
        "preserved_records": manifest["preserved_records"],
        "tag_tokens_preserved": manifest["tag_tokens"],
        "dom_ids_preserved": manifest["dom_ids"],
        "urls_preserved": manifest["urls"],
        "unexpected_kana_records": 0,
    }
    write_atomic(state / "verification.json", json_bytes(report))
    return report


def rollback(repo: Path, state: Path, fail_after_remove: bool = False) -> dict:
    manifest, prepared = load_and_validate(repo, state)
    product = repo / manifest["product_path"]
    if not product.is_file() or product.read_bytes() != prepared:
        raise ValueError("rollback gate failed for RulePopup product")
    previous = product.read_bytes()
    try:
        product.unlink()
        if fail_after_remove:
            raise RuntimeError("synthetic rollback failure")
    except Exception:
        write_atomic(product, previous)
        raise
    record = {"operation": "rollback", "removed_files": 1, "result": "passed"}
    write_atomic(state / "rollback-record.json", json_bytes(record))
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--verify", action="store_true")
    modes.add_argument("--rollback", action="store_true")
    parser.add_argument("--repo", type=Path, default=REPO_DEFAULT)
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--synthetic-fail-after-write", action="store_true")
    parser.add_argument("--synthetic-fail-after-remove", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    input_dir = args.input_dir.resolve() if args.input_dir else repo / INPUT_REL
    state = args.state.resolve() if args.state else repo / STATE_REL
    if args.prepare:
        result = prepare(repo, args.source.resolve(), input_dir, state)
    elif args.apply:
        result = apply(repo, state, args.synthetic_fail_after_write)
    elif args.verify:
        result = verify(repo, state)
    else:
        result = rollback(repo, state, args.synthetic_fail_after_remove)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
