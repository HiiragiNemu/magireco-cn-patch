#!/usr/bin/env python3
"""把对照表里的译文回填进前端代码。

## 铁律：只换**整条**字面量

绝不做子串替换。这些是压缩过的 JS，字面量、标识符、正则、结构挤在一起，
子串匹配一定会误伤——把 `"チーム"` 当子串换掉，`"チーム編成一覧"` 里那三个字
也跟着变，结果是「队伍編成一覧」这种半吊子，甚至撞坏别处的标识符。

所以回填走的是**和抽取完全同一套定位逻辑**：

    JS   —— 用同一个正则找出成对引号之间的内容，内容**整体等于**原文才替换
    HTML —— 标签之间的正文、以及 placeholder/title/alt/value 四个属性，同样整体相等才换

这也意味着抽取漏掉的地方回填一定也碰不到，两边永远一致——宁可少改，不能改错。

## 拒绝会破坏结构的译文

判据不是「译文里不许有危险字符」，而是**不许引入原文没有的**，外加转义序列的
个数必须与原文一致。第一版一刀切禁反斜杠，把一批合法译文全拦了——原文形如
`…できませんでした。\\x3cbr\\x3eトップページに戻ります。`，那个 `\\x3cbr\\x3e`
是 JS 源码里写死的 `<br>`，译文当然得原样带着，否则换行就没了。

## 幂等

已经是中文的地方不会被再处理（原文匹配不上），可以反复跑。

用法：
    python3 tools/i18n-apply.py <前端根目录> <对照表.tsv> [--dry-run]
"""

import argparse
import os
import re
import sys

JS_LIT = re.compile(r'(["\'])((?:(?!\1)[^\\]|\\.)*)\1')
HTML_TEXT = re.compile(r'>([^<>{}]*)<')
HTML_ATTR = re.compile(r'((?:placeholder|title|alt|value)=")([^"]*)(")')


def load_table(path):
    """读对照表，返回 {原文: 译文}。只取填了译文的行。"""
    table = {}
    bad = []
    with open(path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            if line.startswith('#'):
                continue
            col = line.rstrip('\n').split('\t')
            if len(col) < 2 or not col[1]:
                continue
            src = col[0].replace('\\t', '\t').replace('\\n', '\n').replace('\\\\', '\\')
            dst = col[1].replace('\\t', '\t').replace('\\n', '\n').replace('\\\\', '\\')
            why = unsafe_reason(src, dst)
            if why:
                bad.append((lineno, src, dst, why))
                continue
            table[src] = dst
    return table, bad


def unsafe_reason(src, dst):
    """译文若会破坏结构就说明原因，安全则返回 None。

    判据不是「译文里不许有危险字符」，而是**不许引入原文没有的**。

    第一版是一刀切禁反斜杠，结果把一批合法译文全拦了：原文形如
    `…できませんでした。\\x3cbr\\x3eトップページに戻ります。`——那个
    `\\x3cbr\\x3e` 是 JS 源码里写死的 `<br>` 转义，译文当然也得原样带着它，
    否则换行就没了。

    所以逐类比对：引号、反斜杠、尖括号，只有在**原文里也有**时才准出现。
    这样既拦得住手滑引入的破坏性字符，又不挡合法的原样保留。
    """
    for ch, name in (('"', '双引号'), ("'", '单引号'),
                     ('\\', '反斜杠'), ('<', '左尖括号'), ('>', '右尖括号')):
        if ch in dst and ch not in src:
            return '译文引入了原文没有的%s' % name
    # 转义序列的个数也要对得上：少一个 \x3cbr\x3e 就少一个换行，
    # 多一个则可能拼出意料之外的标签
    for esc in (r'\x3c', r'\x3e', r'\x26', r'\n', r'\t'):
        if src.count(esc) != dst.count(esc):
            return '转义序列 %s 的个数与原文不一致（原文 %d，译文 %d）' % (
                esc, src.count(esc), dst.count(esc))
    return None


def apply_js(text, table, stat):
    def repl(m):
        quote, body = m.group(1), m.group(2)
        if body in table:
            stat[body] = stat.get(body, 0) + 1
            return quote + table[body] + quote
        return m.group(0)
    return JS_LIT.sub(repl, text)


def apply_html(text, table, stat):
    def repl_text(m):
        body = m.group(1)
        key = body.strip()
        if key in table:
            stat[key] = stat.get(key, 0) + 1
            # 保留原有的前后空白，只换文字本身
            return '>' + body.replace(key, table[key]) + '<'
        return m.group(0)

    def repl_attr(m):
        head, body, tail = m.group(1), m.group(2), m.group(3)
        if body in table:
            stat[body] = stat.get(body, 0) + 1
            return head + table[body] + tail
        return m.group(0)

    text = HTML_TEXT.sub(repl_text, text)
    return HTML_ATTR.sub(repl_attr, text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', help='含 js/ 与 template/ 的前端根目录')
    ap.add_argument('table', help='对照表 TSV')
    ap.add_argument('--overrides', help='按文件的译文覆盖表（见 i18n/overrides.tsv）')
    ap.add_argument('--dry-run', action='store_true', help='只报告，不落盘')
    ap.add_argument('--out', help='改动文件的清单落到这个文件（供打包用）')
    args = ap.parse_args()

    table, bad = load_table(args.table)
    if bad:
        print('✘ 以下译文会破坏结构（引入了原文没有的字符，或转义个数对不上），请先改掉：',
              file=sys.stderr)
        for lineno, src, dst, why in bad[:20]:
            print('   第%d行  %s → %s' % (lineno, src[:26], dst[:26]), file=sys.stderr)
            print('           %s' % why, file=sys.stderr)
        return 1
    if not table:
        print('对照表里没有已填写的译文', file=sys.stderr)
        return 1
    print('对照表 %d 条译文' % len(table))

    # 按文件的覆盖：同一原文在不同界面含义不同时用它。
    # 例：サポート 在 charaType 映射里是角色类型「辅助」，在好友支援语境里是
    # 「支援」——包里恰好一半一半，全局表按精确原文索引表达不了，硬选一个必错一半。
    #
    # 译文列写 <DELETE> 表示**显式删除**：该原文在这些文件里替换成空串。
    # 用于中文里没有对应物的助词(如 ShopTop 购买完成弹窗里「Xを<br>已购买。」
    # 的 を)——注意与「译文留空=未翻译」区分,留空的行永远不会被处理。
    overrides = []
    if args.overrides and os.path.isfile(args.overrides):
        for line in open(args.overrides, encoding='utf-8'):
            if line.startswith('#'):
                continue
            col = line.rstrip('\n').split('\t')
            if len(col) >= 3 and col[0] and col[1] and col[2]:
                dst = '' if col[2] == '<DELETE>' else col[2]
                overrides.append((col[0], col[1], dst))
        print('按文件的覆盖 %d 条' % len(overrides))

    stat = {}
    changed = []
    for cur, _dirs, files in os.walk(args.root):
        for name in sorted(files):
            if not (name.endswith('.js') or name.endswith('.html')):
                continue
            path = os.path.join(cur, name)
            try:
                orig = open(path, encoding='utf-8', errors='strict').read()
            except (OSError, UnicodeDecodeError):
                continue
            rel = os.path.relpath(path, args.root).replace(os.sep, '/')
            eff = table
            hit = [(s_, d_) for pre, s_, d_ in overrides if rel.startswith(pre)]
            if hit:
                eff = dict(table)
                eff.update(hit)
            new = apply_html(orig, eff, stat) if name.endswith('.html') \
                else apply_js(orig, eff, stat)
            if new != orig:
                changed.append(rel)
                if not args.dry_run:
                    open(path, 'w', encoding='utf-8').write(new)

    total = sum(stat.values())
    print('%s %d 个文件，替换 %d 处（命中 %d 条不同译文）'
          % ('将改动' if args.dry_run else '已改动', len(changed), total, len(stat)))
    unused = [s for s in table if s not in stat]
    if unused:
        # 不算错：抽取时排除过调试页与条款，那些文件不在回填范围内
        print('  对照表里有 %d 条没用上（多半来自被排除的文件）' % len(unused))
    if args.out and not args.dry_run:
        open(args.out, 'w', encoding='utf-8').write('\n'.join(sorted(changed)) + '\n')
        print('  改动清单 → %s' % args.out)

    # ── 改完必须验语法 ──
    # 「整条字面量替换」在设计上不该破坏结构，但设计对不等于实现对：正则、
    # 模板串、转义序列里都可能藏着让人意外的引号配对。这些文件是要发到玩家
    # 机器上的，一个语法错就是整页白屏，而白屏在真机上排查一轮要一整天
    # （本轮已经为白屏耗掉两轮往返）。有 node 就必须过一遍。
    if not args.dry_run and changed:
        rc = syntax_check([f for f in changed if f.endswith('.js')], args.root)
        if rc != 0:
            return rc
    return 0


def syntax_check(js_files, root):
    """用 node --check 逐个验 JS。没有 node 就明说跳过，不假装通过。"""
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        print('  ⚠ 找不到 node，跳过语法检查——发包前请务必自行验一遍')
        return 0
    bad = []
    for rel in js_files:
        p = os.path.join(root, rel)
        r = subprocess.run([node, '--check', p], capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((rel, (r.stderr or '').strip().splitlines()[:2]))
    if bad:
        print('✘ 语法检查未通过 %d 个：' % len(bad), file=sys.stderr)
        for rel, err in bad[:10]:
            print('   %s' % rel, file=sys.stderr)
            for line in err:
                print('     %s' % line, file=sys.stderr)
        return 1
    print('  ✔ 语法检查通过（%d 个 JS）' % len(js_files))
    return 0


if __name__ == '__main__':
    sys.exit(main())
