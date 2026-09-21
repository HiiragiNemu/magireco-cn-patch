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


# WebView 不是 ADV 渲染器：普通页面、角色页、记忆结晶、主页气泡、活动 UI 等
# 一律使用 TTZhiHei。真正 ADV/剧情由 native Story* / RaidScrollView 语义路由
# 到 TTDaYuan；不能再把通用 .serifFont 误当成“剧情”。
if not re.search(r"body\s*\{[^}]*font-family\s*:\s*koruri\s*,\s*motoya\s*,\s*sans-serif", common, re.I | re.S):
    problems.append("body 普通 UI 字体链漂移：必须是 koruri,motoya,sans-serif")
if not re.search(r"\.serifFont\s*\{[^}]*font-family\s*:\s*koruri\s*,\s*motoya\s*,\s*sans-serif", common, re.I | re.S):
    problems.append("serifFont 是通用 Web UI 类，必须走 koruri/motoya -> TTZhiHei")

css_root = root / "magica/css"
for css_path in css_root.rglob("*.css"):
    if css_path.name == "fonts.css":
        continue
    css_text = css_path.read_text(encoding="utf-8")
    if re.search(r"font-family\s*:[^;}]*\bmbm\b", css_text, re.I):
        problems.append(f"普通 Web CSS 仍直接选择 mbm/TTDaYuan: {css_path.relative_to(root)}")
    if "MagiReco CN Medium" in css_text:
        problems.append(f"普通 Web CSS 仍直接选择 MagiReco CN Medium/TTDaYuan: {css_path.relative_to(root)}")

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
