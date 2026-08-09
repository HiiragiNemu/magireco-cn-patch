#!/usr/bin/env python3
"""从中文 Wiki 的术语模板里提取日→中对照表。

## 来源

`magireco-wiki-data` 是 magireco.moe 中文 Wiki 的完整镜像。站方有一份成文的
[[magirecowiki:翻译规范]]，其中把实际对照表托管在几个模板里：

    Template:效果中文    Buff/Debuff 与战斗效果（最大的一份）
    Template:素材中文    道具、素材、货币
    Template:记忆中文    记忆结晶名
    Template:声优中文 / 画师中文 / 学校中文 / 原案监修中文

格式统一是 MediaWiki 的 `#switch`：

    {{ #switch: {{{1}}}
    | ガチャチケット = 扭蛋券
    | サポートPt = 支援Pt
    | ミラーズコイン = -{zh-cn:镜币; zh-tw:鏡像幣;}-
    }}

## 为什么要用它而不是自己译

站方的规范写得很清楚：「除非原翻译品质不佳或不够准确，禁止无故修改已长期使用
的译名」。玩家认的是这套词，我们自己另起一套只会造成割裂。实测我凭印象翻的
第一批里就有踩空的——`サポートPt` 官方作「支援Pt」而非「支援点数」，
`ガチャチケット` 作「扭蛋券」而非「抽卡券」。

## 简繁

模板里用 MediaWiki 的 LanguageConverter 语法 `-{zh-cn:简; zh-tw:繁;}-` 标注
地区词。本脚本只取 zh-cn（本项目面向简体），没有分歧的原样取用。

用法：
    python3 tools/i18n-glossary.py <magireco-wiki-data 路径> [-o glossary.tsv]
"""

import argparse
import glob
import gzip
import json
import os
import re
import sys

# 值里可能出现的地区词标记：-{zh-cn:简; zh-tw:繁;}- 或 -{zh:通用; zh-cn:简;}-
CONV = re.compile(r'-\{([^}]*)\}-')


def pick_zh_cn(value):
    """把 LanguageConverter 标记归一成简体单值。"""
    def repl(m):
        body = m.group(1)
        if ':' not in body:
            return body                      # -{原样输出}-，不做转换
        variants = {}
        for part in body.split(';'):
            part = part.strip()
            if not part or ':' not in part:
                continue
            k, v = part.split(':', 1)
            variants[k.strip()] = v.strip()
        # 优先级：zh-cn > zh-hans > zh > 第一个
        for k in ('zh-cn', 'zh-hans', 'zh'):
            if k in variants:
                return variants[k]
        return next(iter(variants.values()), '')
    return CONV.sub(repl, value).strip()


def parse_switch(text):
    """从 #switch 正文里抠出 {日文: 中文}。

    两种写法都要认：
      · 分行写（效果中文/素材中文那样，每行一个 `| 日 = 中`）
      · 挤在一行（角色类型那样，`|ヒール=治疗|バランス=均衡|…`）
    只处理分行的话，角色类型那张表会整个漏掉——而它恰好是界面上「均衡/攻击/
    防御/辅助/极限/究极」这些天天见的词。
    """
    out = {}
    # 先把挤在一行的拆开：只在「|键=值」这种形态处断，避免误伤值里的竖线
    for m in re.finditer(r'\|\s*([^|=\n{}]{1,40}?)\s*=\s*([^|\n{}]{1,60})', text):
        k, v = m.group(1).strip(), pick_zh_cn(m.group(2).strip())
        if not k or not v or k.startswith('#') or v.startswith('#'):
            continue
        if '{{' in v or '[[' in v or '&#' in v:
            continue
        out.setdefault(k, v)
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('|') or '=' not in line:
            continue
        # 去掉行内注释，否则译文里会混进 <!-- … -->
        line = re.sub(r'<!--.*?-->', '', line)
        body = line[1:]
        # 只在第一个 = 处切；#switch 的默认分支写成 "| #default = …"，跳过
        key, val = body.split('=', 1)
        key, val = key.strip(), pick_zh_cn(val.strip())
        if not key or not val or key.startswith('#') or key.startswith('{'):
            continue
        # 值里若还残留模板/参数/实体语法，说明这条不是纯文本映射，跳过。
        # `&#10;` 这一条尤其要拦：角色类型模板里第一个 #switch 是鼠标悬停的
        # 提示浮层（「バランス&#10;攻击时获得MP：90%…」），真正的译名在最后一个
        # #switch 里。不拦的话行式解析会用提示文本把译名覆盖掉。
        if '{{' in val or '}}' in val or '[[' in val or '&#' in val:
            continue
        out.setdefault(key, val)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('wiki', help='magireco-wiki-data 仓库路径')
    ap.add_argument('-o', '--out', default='i18n/glossary.tsv')
    args = ap.parse_args()

    arch = os.path.join(args.wiki, 'data', 'archive', 'templates.jsonl.gz')
    if not os.path.isfile(arch):
        print('找不到 %s' % arch, file=sys.stderr)
        return 2

    # 这几个模板是规范点名的对照表来源
    WANT = re.compile(r'^Template:((效果|素材|记忆|声优|画师|学校|原案监修)中文|角色类型)$')
    glossary = {}
    per = {}
    with gzip.open(arch, 'rt', encoding='utf-8') as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            title = o.get('title', '')
            if not WANT.match(title):
                continue
            body = o.get('text') or o.get('wikitext') or o.get('content') or ''
            m = parse_switch(body)
            per[title] = len(m)
            # 先到先得：与站方「禁止无故修改已长期使用的译名」的原则一致，
            # 同一个词在多张表里出现时不互相覆盖
            for k, v in m.items():
                # 译文与原文相同的条目没有意义（模板里确实有，例如
                # 角色类型第一个 #switch 的「ラストコネクト = ラストコネクト」），
                # 留着只会在回填时做一次无用替换
                if k == v:
                    continue
                glossary.setdefault(k, v)

    # ── 第二个来源：重定向 ──
    #
    # 站内把日文原词做成重定向指向中文条目，这本身就是一份权威对照：
    #     ドッペル → 魔女化身      ミラーズ → 镜界
    # 而且是**系统名词**这一层，恰好是上面那几张模板（效果/素材/记忆）覆盖不到、
    # 却又最常出现在界面上的词。实测我凭印象把 ドッペル 译成「分身」就是错的。
    idx = os.path.join(args.wiki, 'data', 'pages_index.json')
    n_redir = 0
    if os.path.isfile(idx):
        for it in json.load(open(idx, encoding='utf-8')):
            if not isinstance(it, dict):
                continue
            src, dst = it.get('title', ''), it.get('redirectTo') or ''
            # 只要「日文原词 → 中文条目」这个方向：源含假名、目标不含
            if not src or not dst:
                continue
            if not re.search(r'[぀-ヿ]', src):
                continue
            if re.search(r'[぀-ヿ]', dst):
                continue
            if ':' in src or '/' in src:      # 跳过命名空间页与子页
                continue
            if src not in glossary:
                glossary[src] = dst
                n_redir += 1
    if n_redir:
        print('  %-24s %d 条' % ('（重定向：日文→中文条目）', n_redir))

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write('# 日文\t中文\n')
        for k in sorted(glossary):
            f.write('%s\t%s\n' % (k, glossary[k]))

    for t in sorted(per):
        print('  %-24s %d 条' % (t, per[t]))
    print('合计 %d 条 → %s' % (len(glossary), args.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
