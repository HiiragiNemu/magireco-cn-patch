#!/usr/bin/env python3
"""Freeze and verify the non-translatable structure of all product HTML."""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
RESEARCH = (
    ROOT / "magica" / "research" / "totentanz-full-localization-20260817"
    / "html-structure-contract-20260819"
)
DEFAULT_CONTRACT = RESEARCH / "html_structure_contract.json"
DEFAULT_VERIFICATION = RESEARCH / "verification.json"
DEFAULT_REPORT = RESEARCH / "REPORT_CN.md"
DEFAULT_TOTENTANZ = Path(r"A:\totentanz-frontend")
DEFAULT_OLD_CN = Path(r"A:\magicaOLD")
EXPECTED_HTML_FILES = 225

TRANSLATABLE_ATTRIBUTE_VALUES = frozenset({
    "title", "placeholder", "value", "data-title",
})
STRICT_ATTRIBUTE_NAMES = frozenset({"id", "class", "href", "src", "name"})

VERSION_DIVERGENT_PATHS = frozenset({
    "magica/template/arena/ArenaCurePop.html",
    "magica/template/arena/ArenaTop.html",
    "magica/template/collection/CharaCollectionDetail.html",
    "magica/template/follow/FollowPopup.html",
    "magica/template/follow/FollowTop.html",
    "magica/template/item/ItemListTop.html",
    "magica/template/memoria/MemoriaPopup.html",
    "magica/template/mission/MissionTop.html",
    "magica/template/present/PresentList.html",
    "magica/template/quest/MainQuest.html",
    "magica/template/quest/QuestResult.html",
    "magica/template/quest/SubQuest.html",
})

EVIDENCE_FILES = (
    "tools/apply-missing-html-authority.py",
    "magica/research/totentanz-full-localization-20260817/"
    "missing-html-authority-20260819/runtime/manifest.json",
    "tools/apply-visible-closure-round6.py",
    "magica/research/totentanz-full-localization-20260817/"
    "visible-closure-round6/runtime/manifest.json",
    "tools/apply-visible-ui-localization.py",
    "magica/research/totentanz-full-localization-20260817/"
    "visible-ui/visible_ui_manifest.json",
    "magica/research/totentanz-full-localization-20260817/"
    "visible-ui-round2/html_sensitive_attributes_verification.json",
    "tools/build-final-source-exhaustion-report.py",
    "magica/research/totentanz-full-localization-20260817/"
    "final-source-exhaustion-20260819/summary.json",
    "magica/research/totentanz-full-localization-20260817/"
    "authority-source-exhaustion-round3/conditional_official_template_candidates.tsv",
    "magica/research/totentanz-full-localization-20260817/"
    "current-visible-audit/visible_text_inventory.json",
)

WORD_OR_NUMBER = re.compile(
    r"[A-Za-z_$][A-Za-z0-9_$]*|(?:\d+(?:\.\d*)?|\.\d+)"
)
MULTI_OPERATORS = (
    "===", "!==", ">>>", "**=", "=>", "==", "!=", "<=", ">=", "++",
    "--", "&&", "||", "+=", "-=", "*=", "/=", "%=", "<<", ">>",
    "**", "?.", "??",
)


def extract_ejs_tokens(text: str) -> list[tuple[int, int, str]]:
    """Find EJS blocks without treating a ``%>`` inside a JS string as close."""

    tokens: list[tuple[int, int, str]] = []
    cursor = 0
    while True:
        start = text.find("<%", cursor)
        if start < 0:
            return tokens
        index = start + 2
        while index < len(text):
            if text.startswith("//", index):
                index += 2
                while index < len(text) and text[index] not in "\r\n":
                    index += 1
                continue
            if text.startswith("/*", index):
                end_comment = text.find("*/", index + 2)
                assert end_comment >= 0, "unterminated EJS block comment"
                index = end_comment + 2
                continue
            if text[index] in "'\"`":
                quote = text[index]
                index += 1
                while index < len(text):
                    if text[index] == "\\":
                        index += 2
                        continue
                    if text[index] == quote:
                        index += 1
                        break
                    index += 1
                else:
                    raise AssertionError("unterminated EJS string literal")
                continue
            if text.startswith("%>", index):
                end = index + 2
                tokens.append((start, end, text[start:end]))
                cursor = end
                break
            index += 1
        else:
            raise AssertionError("unterminated EJS block")


def run_git(root: Path, *args: str, text: bool = True):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="strict" if text else None,
        check=False,
    )
    if result.returncode:
        stderr = result.stderr if text else result.stderr.decode("utf-8", "replace")
        raise AssertionError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout


def normalize_ejs_control(token: str) -> list[str]:
    """Keep EJS/JavaScript control syntax while discarding comments and strings."""

    assert token.startswith("<%") and token.endswith("%>")
    body = token[2:-2]
    output: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char.isspace():
            index += 1
            continue
        if body.startswith("//", index):
            index += 2
            while index < len(body) and body[index] not in "\r\n":
                index += 1
            continue
        if body.startswith("/*", index):
            end = body.find("*/", index + 2)
            assert end >= 0, "unterminated EJS block comment"
            index = end + 2
            continue
        if char in "'\"`":
            quote = char
            index += 1
            while index < len(body):
                if body[index] == "\\":
                    index += 2
                    continue
                if body[index] == quote:
                    index += 1
                    break
                index += 1
            else:
                raise AssertionError("unterminated EJS string literal")
            output.append("__STRING__")
            continue
        match = WORD_OR_NUMBER.match(body, index)
        if match:
            output.append(match.group(0))
            index = match.end()
            continue
        operator = next(
            (candidate for candidate in MULTI_OPERATORS
             if body.startswith(candidate, index)),
            None,
        )
        if operator:
            output.append(operator)
            index += len(operator)
            continue
        output.append(char)
        index += 1
    return output


class StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.events: list[list[object]] = []

    @staticmethod
    def structural_attributes(
        attributes: list[tuple[str, str | None]],
    ) -> list[list[str]]:
        selected: list[list[str]] = []
        for raw_name, raw_value in attributes:
            name = raw_name.lower()
            value = "" if raw_value is None else raw_value
            structural = name in STRICT_ATTRIBUTE_NAMES or name.startswith("data-")
            translatable = name in TRANSLATABLE_ATTRIBUTE_VALUES
            if not (structural or translatable):
                continue
            selected.append([
                name,
                "__TRANSLATABLE_ATTRIBUTE_VALUE__" if translatable else value,
            ])
        return sorted(selected)

    def handle_starttag(self, tag, attrs):
        self.events.append([
            "start", tag.lower(), self.structural_attributes(attrs),
        ])

    def handle_startendtag(self, tag, attrs):
        self.events.append([
            "startend", tag.lower(), self.structural_attributes(attrs),
        ])

    def handle_endtag(self, tag):
        self.events.append(["end", tag.lower()])

    def handle_decl(self, decl):
        self.events.append(["decl", " ".join(decl.split()).lower()])


def structure_signature(raw: bytes) -> dict[str, object]:
    text = raw.decode("utf-8-sig")
    spans = extract_ejs_tokens(text)
    tokens = [token for _start, _end, token in spans]
    pieces: list[str] = []
    cursor = 0
    for index, (start, end, _token) in enumerate(spans):
        pieces.extend((text[cursor:start], f"__EJS_{index}__"))
        cursor = end
    pieces.append(text[cursor:])
    parser_text = "".join(pieces)
    parser = StructureParser()
    parser.feed(parser_text)
    parser.close()
    return {
        "tag_events": parser.events,
        "ejs_control": [normalize_ejs_control(token) for token in tokens],
    }


def source_evidence_for(root: Path, product_path: str) -> list[str]:
    basename = Path(product_path).name
    evidence: list[str] = []
    for relative in EVIDENCE_FILES:
        path = root / relative
        assert path.is_file(), f"missing structure evidence: {relative}"
        # Always bind the two structural aggregate checks.  Path-specific apply
        # tools/manifests are added only when they name this exact template.
        aggregate = relative.endswith((
            "html_sensitive_attributes_verification.json",
            "final-source-exhaustion-20260819/summary.json",
            "conditional_official_template_candidates.tsv",
            "current-visible-audit/visible_text_inventory.json",
        ))
        if aggregate or basename in path.read_text(encoding="utf-8-sig", errors="replace"):
            evidence.append(relative)
    return evidence


def product_paths(root: Path) -> list[str]:
    template = root / "magica/template"
    return sorted(
        path.relative_to(root).as_posix()
        for path in template.rglob("*.html")
        if path.is_file()
    )


def select_reference(
    root: Path,
    product_path: str,
    head: str,
    head_paths: set[str],
    totentanz: Path,
    old_cn: Path,
) -> tuple[str, str, bytes]:
    relative = product_path.removeprefix("magica/")
    current_us = totentanz / Path(relative)
    if current_us.is_file():
        return "totentanz-current-us", str(current_us.resolve()), current_us.read_bytes()
    if product_path in head_paths:
        locator = f"git:{head}:{product_path}"
        return (
            "git-head-baseline",
            locator,
            run_git(root, "show", f"{head}:{product_path}", text=False),
        )
    old_path = old_cn / Path(relative)
    if old_path.is_file():
        return "magicaOLD", str(old_path.resolve()), old_path.read_bytes()
    raise AssertionError(f"no structure source for {product_path}")


def build_contract(
    root: Path,
    totentanz: Path = DEFAULT_TOTENTANZ,
    old_cn: Path = DEFAULT_OLD_CN,
) -> dict[str, object]:
    root = root.resolve()
    paths = product_paths(root)
    assert len(paths) == EXPECTED_HTML_FILES, len(paths)
    head = run_git(root, "rev-parse", "HEAD").strip()
    head_paths = set(
        run_git(root, "ls-tree", "-r", "--name-only", head, "--", "magica/template")
        .splitlines()
    )

    entries: list[dict[str, object]] = []
    source_counts: Counter[str] = Counter()
    strict_matches = 0
    for product_path in paths:
        kind, locator, reference_raw = select_reference(
            root, product_path, head, head_paths, totentanz, old_cn
        )
        product_raw = (root / product_path).read_bytes()
        product_structure = structure_signature(product_raw)
        reference_structure = structure_signature(reference_raw)
        divergent = product_path in VERSION_DIVERGENT_PATHS
        if divergent:
            assert kind == "magicaOLD", (
                f"version-divergent path unexpectedly has a newer source: {product_path}"
            )
            assert product_structure != reference_structure, (
                f"version-divergent path no longer differs: {product_path}"
            )
            entry = {
                "path": product_path,
                "source_kind": "version-divergent-frozen-product",
                "source_locator": product_path,
                "reference_source_kind": "magicaOLD-cn-text-only",
                "reference_source_locator": locator,
                "reference_structure_equal": False,
                "frozen_structure": product_structure,
                "translation_evidence": source_evidence_for(root, product_path),
            }
        else:
            assert product_structure == reference_structure, (
                f"HTML structure drift: {product_path} ({kind}: {locator})"
            )
            strict_matches += 1
            entry = {
                "path": product_path,
                "source_kind": kind,
                "source_locator": locator,
                "reference_structure_equal": True,
                "frozen_structure": reference_structure,
            }
        source_counts[entry["source_kind"]] += 1
        entries.append(entry)

    assert strict_matches == EXPECTED_HTML_FILES - len(VERSION_DIVERGENT_PATHS)
    return {
        "schema": "magireco-cn-html-structure-contract/v1",
        "status": "PASS",
        "product_scope": "magica/template/**/*.html",
        "file_count": len(entries),
        "git_head": head,
        "source_priority": [
            str(totentanz.resolve()),
            "git HEAD same path",
            str(old_cn.resolve()),
        ],
        "comparison": {
            "visible_text": "ignored",
            "ejs": "comments removed; quoted strings normalized; control tokens strict",
            "strict_attributes": ["id", "class", "href", "src", "name", "data-*"],
            "translatable_attribute_values": sorted(TRANSLATABLE_ATTRIBUTE_VALUES),
            "translatable_data_attributes": ["data-title"],
        },
        "strict_source_matches": strict_matches,
        "version_divergent_frozen_product": len(VERSION_DIVERGENT_PATHS),
        "source_kind_counts": dict(sorted(source_counts.items())),
        "entries": entries,
    }


def raw_from_locator(root: Path, locator: str) -> bytes:
    if locator.startswith("git:"):
        _prefix, commit, product_path = locator.split(":", 2)
        return run_git(root, "show", f"{commit}:{product_path}", text=False)
    path = Path(locator)
    assert path.is_file(), f"missing frozen source: {locator}"
    return path.read_bytes()


def verify_contract(
    root: Path,
    contract: dict[str, object],
    expected_file_count: int = EXPECTED_HTML_FILES,
    version_divergent_paths: frozenset[str] = VERSION_DIVERGENT_PATHS,
    verify_external_sources: bool = True,
) -> dict[str, object]:
    root = root.resolve()
    assert contract.get("schema") == "magireco-cn-html-structure-contract/v1"
    entries = contract.get("entries")
    assert isinstance(entries, list)
    assert contract.get("file_count") == expected_file_count == len(entries)
    expected_paths = [entry["path"] for entry in entries]
    assert expected_paths == sorted(expected_paths)
    assert len(expected_paths) == len(set(expected_paths))
    assert product_paths(root) == expected_paths, "HTML product path set drift"

    source_counts: Counter[str] = Counter()
    strict_matches = 0
    frozen_matches = 0
    for entry in entries:
        product_path = entry["path"]
        actual = structure_signature((root / product_path).read_bytes())
        assert actual == entry["frozen_structure"], (
            f"frozen HTML structure drift: {product_path}"
        )
        kind = entry["source_kind"]
        source_counts[kind] += 1
        if kind == "version-divergent-frozen-product":
            assert product_path in version_divergent_paths
            assert entry.get("reference_source_kind") == "magicaOLD-cn-text-only"
            reference = entry.get("reference_source_locator")
            assert isinstance(reference, str)
            evidence = entry.get("translation_evidence")
            assert isinstance(evidence, list) and evidence
            if verify_external_sources:
                assert Path(reference).is_file(), f"missing CN text reference: {reference}"
                for relative in evidence:
                    assert (root / relative).is_file(), (
                        f"missing translation evidence: {relative}"
                    )
            frozen_matches += 1
        else:
            if verify_external_sources:
                source_raw = raw_from_locator(root, entry["source_locator"])
                assert structure_signature(source_raw) == entry["frozen_structure"], (
                    f"frozen source structure drift: {product_path}"
                )
            strict_matches += 1

    assert set(version_divergent_paths) == {
        entry["path"] for entry in entries
        if entry["source_kind"] == "version-divergent-frozen-product"
    }
    assert strict_matches == expected_file_count - len(version_divergent_paths)
    assert frozen_matches == len(version_divergent_paths)
    assert dict(sorted(source_counts.items())) == contract["source_kind_counts"]
    return {
        "schema": "magireco-cn-html-structure-verification/v1",
        "status": "PASS",
        "html_files": len(entries),
        "source_path_missing": 0,
        "strict_source_structure_matches": strict_matches,
        "version_divergent_frozen_product": frozen_matches,
        "product_structure_drift": 0,
        "source_structure_drift": 0,
        "external_sources_verified": verify_external_sources,
        "source_kind_counts": dict(sorted(source_counts.items())),
        "version_divergent_paths": sorted(version_divergent_paths),
        "translatable_data_attributes": ["data-title"],
    }


def render_report(verification: dict[str, object]) -> str:
    counts = verification["source_kind_counts"]
    paths = "\n".join(
        f"- `{path}`" for path in verification["version_divergent_paths"]
    )
    return f"""# HTML 冻结结构合同

## 结论

- 产品 HTML：{verification['html_files']} 个
- 严格与逐路径结构源一致：{verification['strict_source_structure_matches']} 个
- 版本差异、冻结最终产品结构：{verification['version_divergent_frozen_product']} 个
- 源路径缺失：{verification['source_path_missing']}
- 产品结构漂移：{verification['product_structure_drift']}
- 源结构漂移：{verification['source_structure_drift']}
- 来源分布：`{json.dumps(counts, ensure_ascii=False, sort_keys=True)}`

只忽略可见文字，以及 `title`、`placeholder`、`value`、`data-title`
的可翻译值；标签序列、EJS 控制骨架和其余敏感属性严格比较。

## 12 个版本差异模板

这些模板仅把旧国服文件作为中文参考，不声称旧结构等于当前结构；当前最终
产品结构已独立冻结，后续任一标签、敏感属性或 EJS 控制骨架改变都会失败。

{paths}
"""


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--totentanz", type=Path, default=DEFAULT_TOTENTANZ)
    parser.add_argument("--old-cn", type=Path, default=DEFAULT_OLD_CN)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--verification", type=Path, default=DEFAULT_VERIFICATION)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
    else:
        contract = build_contract(args.root, args.totentanz, args.old_cn)
        write_json(args.contract, contract)
    # ``--verify`` reopens the committed, byte-frozen contract and therefore
    # must remain usable after the acquisition drives have been retired.  A
    # fresh build still verifies every external source before freezing it.
    verification = verify_contract(
        args.root,
        contract,
        verify_external_sources=not args.verify,
    )
    write_json(args.verification, verification)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(verification), encoding="utf-8", newline="\n")
    sys.stdout.buffer.write(
        (json.dumps(verification, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
