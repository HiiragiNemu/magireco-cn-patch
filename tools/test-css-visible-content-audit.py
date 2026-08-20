#!/usr/bin/env python3
"""Regression checks for localized CSS-generated visible labels."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CSS_ROOT = REPO / "magica" / "css"
AUDIT_ROOT = (
    REPO
    / "magica"
    / "research"
    / "totentanz-full-localization-20260817"
    / "visible-ui"
)
MANIFEST = AUDIT_ROOT / "visible_ui_manifest.json"
REPORT = AUDIT_ROOT / "css_visible_content_audit.json"
CONNECT_SUPERSESSION = AUDIT_ROOT / "connect_supersession_ui075.json"

CONTENT_RE = re.compile(r"content\s*:\s*([\"'])(.*?)(?<!\\)\1", re.S)
KANA_RE = re.compile(r"[\u3040-\u30ff]")

# These are generated UI labels, not identifiers or source-code tokens.
FORBIDDEN_VISIBLE_VALUES = {
    "Lv",
    "LV",
    "Rank",
    "Stage",
    "Illustrator",
    "OVER",
    "Lv MAX",
    "BONUS",
    "Connect",
    "エピソードLv",
    "マギアLv",
    "マギア",
    "EXスキル",
    "コネクト",
    "条件クリアで解放",
    "最終ログイン",
    "スキルタイプ",
    "スキル",
    "アビリティタイプ",
    "アビリティ",
    "対戦相手",
    "挑戦する",
    "受け取る",
    "参加済",
    "必要GP",
    "必要撃退数",
    "到達した撃退Lv",
    "最高獲得エンブレム",
    "デイリーダメージ",
    "現在のグレード",
    "已达到的击退Lv",
}


def css_values() -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for path in sorted(CSS_ROOT.rglob("*.css")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO).as_posix()
        values.extend((rel, match.group(2)) for match in CONTENT_RE.finditer(text))
    return values


def css_braces_are_balanced(text: str) -> bool:
    """Check braces while ignoring quoted strings, escapes, and comments."""
    depth = 0
    quote: str | None = None
    escaped = False
    in_comment = False
    index = 0
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if in_comment:
            if char == "*" and following == "/":
                in_comment = False
                index += 2
                continue
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and following == "*":
            in_comment = True
            index += 2
            continue
        elif char in {"\"", "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
        index += 1
    return depth == 0 and quote is None and not in_comment


class CssVisibleContentAuditTest(unittest.TestCase):
    def test_no_kana_in_generated_visible_labels(self) -> None:
        bad = [(path, value) for path, value in css_values() if KANA_RE.search(value)]
        self.assertEqual([], bad)

    def test_no_known_unlocalized_visible_labels(self) -> None:
        bad = [
            (path, value)
            for path, value in css_values()
            if value in FORBIDDEN_VISIBLE_VALUES
        ]
        self.assertEqual([], bad)

    def test_all_css_remains_structurally_balanced(self) -> None:
        bad = []
        for path in sorted(CSS_ROOT.rglob("*.css")):
            text = path.read_text(encoding="utf-8")
            if not css_braces_are_balanced(text):
                bad.append(path.relative_to(REPO).as_posix())
        self.assertEqual([], bad)

    def test_css_manifest_items_are_path_scoped_and_reversible(self) -> None:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        css_items = [item for item in data["items"] if item["path"].startswith("magica/css/")]
        closure_items = [
            item for item in css_items if item.get("css_content_closure_20260817")
        ]
        self.assertEqual(119, len(css_items))
        self.assertEqual(110, len(closure_items))
        for item in css_items:
            if item["item_id"] in {"UI-045", "UI-046"}:
                self.assertEqual("append", item["operation"])
            else:
                self.assertEqual("replace", item["operation"])
            self.assertFalse(Path(item["path"]).is_absolute())
            self.assertNotIn("..", Path(item["path"]).parts)
            if item["operation"] == "replace":
                self.assertNotEqual(item["before"], item["after"])
                self.assertEqual(0, int(item.get("baseline_after_count", 0)))
        for item in closure_items:
            text = (REPO / item["path"]).read_text(encoding="utf-8")
            self.assertEqual(0, text.count(item["before"]), item["item_id"])
            if item["item_id"] == "UI-075":
                # The historical manifest remains immutable.  UI-075 alone is
                # superseded by the later official terminology decision.
                self.assertEqual(0, text.count(item["after"]), item["item_id"])
            else:
                self.assertEqual(1, text.count(item["after"]), item["item_id"])

    def test_ui075_connect_supersession_matches_current_product(self) -> None:
        evidence = json.loads(CONNECT_SUPERSESSION.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        history = next(item for item in manifest["items"] if item["item_id"] == "UI-075")
        current = next(item for item in report["items"] if item["item_id"] == "UI-075")
        self.assertEqual("Connect", history["target_values"][0])
        self.assertEqual("连携", evidence["superseding_target"])
        self.assertEqual(["连携"], current["target_values"])
        self.assertEqual("official-cn-terminology", current["source_tier"])

        css = (REPO / evidence["product_path"]).read_text(encoding="utf-8")
        contract = evidence["product_contract"]
        self.assertEqual(0, css.count(contract["historical_connect_rule"]))
        self.assertEqual(1, css.count(contract["primary_cn_rule"]))
        self.assertEqual(1, css.count(contract["append_override_rule"]))
        self.assertEqual(0, css.count('content:"Connect"'))
        self.assertEqual(2, css.count('content:"连携"'))
        self.assertEqual(0, current["historical_connect_rule_count_in_product"])
        self.assertEqual(1, current["primary_target_rule_count_in_product"])
        self.assertEqual(1, current["append_override_rule_count_in_product"])
        self.assertEqual(2, current["after_rule_count_in_product"])
        self.assertTrue(evidence["historical_manifest_unchanged"])
        self.assertEqual(
            "same effective value; retained as explicit cascade guard",
            evidence["append_override_reason"],
        )

    def test_audit_report_matches_product(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertTrue(report["ok"])
        self.assertEqual(0, report["counts"]["unwanted_residuals"])
        self.assertEqual(0, report["counts"]["kana_residuals"])
        self.assertEqual(110, report["counts"]["localized_rules_this_pass"])
        self.assertEqual(26, report["counts"]["localized_files_this_pass"])
        self.assertEqual(1, report["counts"]["connect_supersessions"])
        self.assertNotIn("Connect", report["policy"]["formal_terms_preserved"])
        self.assertFalse(
            any(row["value"] == "Connect" for row in report["intentional_residuals"])
        )
        self.assertEqual([], report["unwanted_residuals"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
