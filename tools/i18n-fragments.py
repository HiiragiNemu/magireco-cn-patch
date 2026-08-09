#!/usr/bin/env python3
"""片段级补丁：跨节点整段改写，解决整串替换机制够不到的语序问题。

## 为什么有这一步

整串回填（i18n-apply.py）的铁律是「只换整条字面量」，这在大多数时候是对的，
但有三类日文句式整条替换永远翻不通：

    Xを N個 使用して Yします。  —— 宾语前置,道具名变量在助词**之前**,
                                  中文必须「使用 N 个 X」
    cが それぞれ N アップ       —— 「数+动」,数值变量夹在动词**之前**,
                                  中文必须「提升 N」
    Xを<br>購入しました。        —— 助词在中文里没有对应物,要的是**删除**

这些语境里变量夹在助词与谓语之间,中文语序必须把谓语挪到变量的另一侧。
与其手改压缩 JS / 模板(会被流水线重跑冲掉),不如把整段改写也做成表驱动:
可审、可回滚、可重跑。

## 在流水线里的位置

    i18n-extract.py   抽取 → 对照表
    (人/模型)         填 i18n/frontend-strings.tsv
    i18n-apply.py     整串回填(含 overrides 与 <DELETE>)
    i18n-fragments.py 片段补丁(本步)  ← 跑在回填**之后**,匹配的是
    i18n-package.py   打包              「邻居已汉化、只剩语序残留」的文本

## 安全规则

- 每条补丁必须**至少精确命中一次**;命中 0 次即整体报错退出(非零)。
  上游文本一变补丁就该响,悄悄跳过是最坏的失败方式。
- 替换前后,模板占位符(<% … %>)与 HTML 标签必须各自是同一个多重集合
  ——只许挪位置,不许增删。
- 转义序列(\\x3c 等)的个数替换前后必须一致(同 i18n-apply 的判据)。
- 改动到的 JS 文件过 node --check;没有 node 就明说跳过,不假装通过。

用法:
    python3 tools/i18n-fragments.py <前端根目录> <片段表.tsv> [--dry-run]
"""

import argparse
import os
import re
import sys

PLACEHOLDER = re.compile(r'<%.*?%>')
TAG = re.compile(r'</?[a-zA-Z][^>]*>')
ESCAPES = (r'\x3c', r'\x3e', r'\x26', r'\n', r'\t')


def unesc(x):
    # 与 i18n-apply.load_table 同一套转义约定
    return x.replace('\\t', '\t').replace('\\n', '\n').replace('\\\\', '\\')


def load(path):
    """读片段表,返回 [(前缀, 原始片段, 替换片段, 行号)]。格式/校验错误直接退出。"""
    frags = []
    bad = []
    with open(path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            if line.startswith('#') or not line.strip():
                continue
            col = line.rstrip('\n').split('\t')
            if len(col) < 3 or not col[0] or not col[1] or not col[2]:
                bad.append((lineno, '格式不对:需要 文件前缀⇥原始片段⇥替换片段'))
                continue
            pre, src, dst = col[0], unesc(col[1]), unesc(col[2])
            if src == dst:
                bad.append((lineno, '原始片段与替换片段相同'))
                continue
            if sorted(PLACEHOLDER.findall(src)) != sorted(PLACEHOLDER.findall(dst)):
                bad.append((lineno, '模板占位符的多重集合不一致'))
                continue
            if sorted(TAG.findall(src)) != sorted(TAG.findall(dst)):
                bad.append((lineno, 'HTML 标签的多重集合不一致'))
                continue
            for e in ESCAPES:
                if src.count(e) != dst.count(e):
                    bad.append((lineno, '转义序列 %s 的个数不一致' % e))
                    break
            else:
                frags.append((pre, src, dst, lineno))
    for lineno, why in bad:
        print('✗ 片段表第 %d 行:%s' % (lineno, why), file=sys.stderr)
    if bad:
        sys.exit(2)
    return frags


def syntax_check(js_files, root):
    """用 node --check 逐个验 JS。没有 node 就明说跳过,不假装通过。"""
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        print('  ⚠ 找不到 node,跳过语法检查——发包前请务必自行验一遍')
        return 0
    bad = []
    for rel in js_files:
        r = subprocess.run([node, '--check', os.path.join(root, rel)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((rel, (r.stderr or '').strip().splitlines()[:2]))
    if bad:
        for rel, err in bad:
            print('  ✗ 语法检查未过:%s: %s' % (rel, err), file=sys.stderr)
        return 1
    if js_files:
        print('  ✔ 语法检查通过(%d 个 JS)' % len(js_files))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', help='含 js/ 与 template/ 的前端根目录')
    ap.add_argument('fragments', help='片段表 TSV(见 i18n/fragments.tsv)')
    ap.add_argument('--dry-run', action='store_true', help='只报告,不落盘')
    args = ap.parse_args()

    frags = load(args.fragments)
    print('片段补丁 %d 条' % len(frags))

    # 每条补丁各自记账:{行号: (前缀, 命中数)}
    ledger = {lineno: [pre, 0] for pre, _s, _d, lineno in frags}
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
            new = orig
            for pre, src, dst, lineno in frags:
                if not rel.startswith(pre):
                    continue
                n = new.count(src)
                if n:
                    ledger[lineno][1] += n
                    if n > 1:
                        print('  ⚠ 第 %d 行补丁在 %s 命中 %d 次,全部替换'
                              % (lineno, rel, n))
                    new = new.replace(src, dst)
            if new != orig:
                changed.append(rel)
                if not args.dry_run:
                    open(path, 'w', encoding='utf-8').write(new)

    stale = [(lineno, pre) for lineno, (pre, n) in ledger.items() if n == 0]
    for lineno, pre in stale:
        print('✗ 第 %d 行补丁命中 0 次(前缀 %s)——上游文本已变或回填顺序不对,'
              '补丁失效,拒绝继续' % (lineno, pre), file=sys.stderr)
    if stale:
        return 1

    print('%s %d 个文件' % ('将改动' if args.dry_run else '已改动', len(changed)))
    for rel in changed:
        print('   ', rel)

    if not args.dry_run and changed:
        return syntax_check([f for f in changed if f.endswith('.js')], args.root)
    return 0


if __name__ == '__main__':
    sys.exit(main())
