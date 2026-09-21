#!/usr/bin/env python3
"""Fail closed if WebView can still load legacy US/JP font carriers."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parent.parent
css = (root / "magica/css/_common/fonts.css").read_text(encoding="utf-8")
base = (root / "magica/js/_common/base.js").read_text(encoding="utf-8")
common = (root / "magica/css/_common/common.css").read_text(encoding="utf-8")

expected = {
    "koruri": "TTZhiHeiGB3-W4.ttf",
    "motoya": "TTZhiHeiGB3-W4.ttf",
    "mbm": "TTDaYuanGB3.ttf",
    "MagiReco CN Medium": "TTDaYuanGB3.ttf",
}
problems = []
for family, filename in expected.items():
    fam = re.escape(family)
    pattern = (
        r"@font-face\s*\{[^}]*font-family\s*:\s*[\"']?"
        + fam +
        r"[\"']?[^}]*src\s*:\s*url\([^)]*/"
        + re.escape(filename) +
        r"\)"
    )
    if not re.search(pattern, css, re.I | re.S):
        problems.append(f"{family} 没有固定路由到 {filename}")

for needle in ("data:font/ttf;base64", "String(a.motoya)", "String(a.mbm)"):
    if needle in base:
        problems.append(f"base.js 仍可注入旧字体载体: {needle}")

if "fontDataGet=function" not in base:
    problems.append("base.js 缺少 fontDataGet 回调，可能破坏 native bridge")
if "ignore legacy US/JP base64 carriers" not in base:
    problems.append("fontDataGet 没有明确进入 CN 固定字体模式")


# 使用链也必须正确：普通 UI 继承 body 的 koruri/motoya（两者都落 TTZhiHei）；
# 剧情/对白 .serifFont 必须优先 mbm/MagiReco CN Medium，绝不能再把 koruri 放首位。
if not re.search(r"body\s*\{[^}]*font-family\s*:\s*koruri\s*,\s*motoya\s*,\s*sans-serif", common, re.I | re.S):
    problems.append("body 普通 UI 字体链漂移：必须是 koruri,motoya,sans-serif")
if not re.search(r"\.serifFont\s*\{[^}]*font-family\s*:\s*mbm\s*,\s*[\"']MagiReco CN Medium[\"']\s*,\s*sans-serif", common, re.I | re.S):
    problems.append("serifFont 剧情字体链漂移：必须优先 mbm / MagiReco CN Medium")
if re.search(r"\.serifFont\s*\{[^}]*font-family\s*:\s*koruri\b", common, re.I | re.S):
    problems.append("serifFont 仍把 koruri 放在首位，会把剧情错误路由到 TTZhiHei")

for name in ("TTZhiHeiGB3-W4.ttf", "TTDaYuanGB3.ttf"):
    p = root / "magica/fonts" / name
    if not p.is_file():
        problems.append(f"缺少 Web 字体文件 {p.relative_to(root)}")

if problems:
    print("Web 字体路由检查未通过：", file=sys.stderr)
    for p in problems:
        print("  ✗ " + p, file=sys.stderr)
    raise SystemExit(1)

print("Web 字体路由已封闭：UI=TTZhiHei；剧情/ADV=TTDaYuan；legacy base64 字体注入已禁用。")
