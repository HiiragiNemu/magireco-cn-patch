#!/usr/bin/env python3
"""从前端代码里抽出所有日文字面量，生成可审阅的对照表。

## 为什么要有这一步

游戏界面上的文字不只住在 `/magica/resource` 里。那棵树只有图片/图集/剧本，
而弹窗按钮、教程引导语、错误提示这些**硬编码在前端代码里**：

    js/_common/nativeCommand.js   83 处
    js/util/TutorialUtil.js       56 处
    js/top/TopPage.js             22 处
    …

现有的 `cn_js_update.zip` 只覆盖了 `js/libs/` 下的**数据表**（角色名、道具名、
章节标题、技能描述），一个页面代码文件都没有。所以「角色名是中文、按钮还是
日文」。

## 为什么不直接改代码

这些是压缩过的 JS，直接在里面做正则替换风险很高——字面量和结构混在一起，
改错一个引号整页就废。而且这事有前科：早先有人拿代码硬汉化，效果不好还直接
推了上去。

所以流程拆成三步，每一步都能单独审、单独回滚：

    1. 抽取（本脚本）  → 唯一串 + 出现位置，落成 TSV
    2. 翻译（人/模型） → 只填 TSV 的第二列，不碰代码
    3. 回填（i18n-apply.py）→ 按 TSV 做**整串精确替换**，不用正则猜边界

## 判据

- 默认**只认假名**（平假名 / 片假名）。汉字中日共用，拿它当判据会把已经汉化好
  的中文串一起抓回来。
- `--cjk` 打开后连**纯汉字**的串一起抓（`選択` `戦闘` `確認` `設定` 这类，
  只认假名时一条都抓不到）。之所以敢这么抓：**上游那棵树本来就全是日文**，
  里面不存在中文，除非是我们自己回填进去的。为了不把自己的译文抓回来，
  该模式会跳过「已经作为译文出现在对照表里」的串——所以对已汉化的树重跑也安全。
- JS 只扫**字符串字面量**（成对引号内），不扫注释与标识符。
- HTML 扫标签之间的正文，外加 placeholder/title/alt/value 四个常见属性。

用法：
    python3 tools/i18n-extract.py <前端根目录> [-o out.tsv]

前端根目录指含 `js/` 与 `template/` 的那一层（从设备上
`/data/data/<pkg>/files/magica/` 取，或从上游按 replacement.js 的清单拉）。
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict

KANA = re.compile(r'[\u3040-\u30ff]')
CJK  = re.compile(r'[\u4e00-\u9fff]')

# 这些目录/文件默认排除，理由各不相同，都写在这里免得以后有人纳闷：
#   test / Backdoor —— 调试页，要 window.isDebug 为真才注册路由，玩家看不到
#   RulePopup / LawPopup / Terms / ConsentRules —— 利用条款与法律文本，
#     不该机器翻译，需要人自己定稿
DEFAULT_SKIP = re.compile(
    r'(^|/)(test)/|Backdoor|RulePopup|LawPopup|Terms|ConsentRules', re.I)


def js_literals(text):
    """JS 里的字符串字面量。只取成对引号之间的内容。"""
    out = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
    out += re.findall(r"'((?:[^'\\]|\\.)*)'", text)
    return out


def html_texts(text):
    """HTML 里的可见文字：标签之间的正文 + 四个常见属性。"""
    out = re.findall(r'>([^<>{}]*)<', text)
    out += re.findall(r'(?:placeholder|title|alt|value)="([^"]*)"', text)
    return out


# 法条 / 条款相关的关键词。命中即标「法条勿动」，不参与翻译。
#
# 两个理由（由维护者定的，写在这儿免得以后有人手痒去填）：
#   1. 这游戏官方已经停运两年以上，运营方不再维护这些条文；
#   2. 更要紧的是——**这本来就不是我们能翻译的东西**。利用条款、特定商取引法
#      表示、资金结算法表示、未成年人同意告知，都是有法律效力的文本，翻译等于
#      重新表述，出了偏差是给自己惹麻烦。原文照旧留着，反而是最稳妥的。
#
# 按**内容**匹配而不只按文件名：真机抽取时发现有 4 条法条串散落在
# PurchasePopup.js / TopPage.js / Ban.html / PurchaseTemps.html 这些普通 UI
# 文件里，光靠文件名的黑名单挡不住。
LEGAL = re.compile(
    r'利用規約|規約|特定商取引|資金決済|プライバシー|個人情報|著作権|免責'
    r'|禁止事項|第\d+条|運営会社|消費者|返金|未成年|法令|責任を負')


def risk_of(s):
    """给这条串标个风险等级，提醒译者哪些不能照字面翻。

    抽出来的东西不都是「一句完整的话」。踩过的坑长这样：

      "あと" / "まで" / "を"     ——**拼接碎片**。代码里是 "あと"+n+"回"，
                                   照字面译成「还有」再拼上数字就成了
                                   「还有3回」这种半通不通的东西，而且中文
                                   的语序跟日文不一样，碎片根本对不上。
      "<p class=...>…</p>"       ——**带标签的 HTML 片段**。译文里必须原样
                                   保留标签与类名，改错一个字符整块就废。
      "%s／%s"、"{0}"            ——**带占位符**。占位符不能动、顺序可能要调。

    这三类都必须回到代码里看上下文再决定怎么处理，不能丢给批量翻译。

    法条相关的另有一档「法条勿动」，理由见 LEGAL 上面那段。
    """
    if LEGAL.search(s):
        return '法条勿动'
    if re.search(r'<[a-zA-Z/!]', s):
        return 'HTML片段'
    if re.search(r'%[sd]|\{\d\}|\$\{', s):
        return '含占位符'
    # 极短**且纯假名**：多半是接在数字/名字前后的碎片（を / まで / あと）。
    # 必须加「纯假名」这个条件——只看长度会把「閉じる」「変更」这类完整词也
    # 判成碎片（第一版就是这么误伤的，95 处的「閉じる」被挡在批量之外）。
    if len(s) <= 3 and re.fullmatch(r'[぀-ヿ]+', s):
        return '疑似碎片'
    # 单个汉字：--cjk 打开后冒出来的一类量词/序数碎片（個 位 月 日 分 人 第 問），
    # 代码里是 n + "個" 这种拼法。界限画在「单字」而不是「两字以内」——
    # 「決定」「合計」「報酬」都是两字的完整词，一并挡掉又是一次误伤。
    if len(s) == 1 and CJK.fullmatch(s):
        return '疑似碎片'
    return ''


def scan(root, skip, cjk=False, known_translations=None):
    """返回 {原文: [出现位置…]}，位置形如 rel/path。"""
    hits = defaultdict(list)
    scanned = 0
    known = known_translations or set()
    for cur, _dirs, files in os.walk(root):
        for name in sorted(files):
            path = os.path.join(cur, name)
            rel = os.path.relpath(path, root)
            if skip and skip.search(rel):
                continue
            if not (name.endswith('.js') or name.endswith('.html')):
                continue
            try:
                text = open(path, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            scanned += 1
            cands = html_texts(text) if name.endswith('.html') else js_literals(text)
            for s in cands:
                s = s.strip()
                if not s:
                    continue
                if s in known:
                    # 我们自己回填进去的译文，任何模式下都不该再被当成待翻内容。
                    # 假名分支也要查：中点「・」(U+30FB) 落在假名区间里，
                    # 而译文「数据转移・关联」正好含它——只在汉字分支查的话，
                    # 这一条每次重抽都会漏回来。
                    continue
                if KANA.search(s):
                    hits[s].append(rel)
                elif cjk and CJK.search(s):
                    # 纯汉字：上游树里这就是日文。跳过 known 是为了不把我们
                    # 自己回填进去的译文当成待翻内容再抓一遍。
                    hits[s].append(rel)
    return hits, scanned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', help='含 js/ 与 template/ 的前端根目录')
    ap.add_argument('-o', '--out', default='frontend-strings.tsv')
    ap.add_argument('--all', action='store_true',
                    help='连调试页与条款一起抽（默认排除）')
    ap.add_argument('--cjk', action='store_true',
                    help='连纯汉字的日文串一起抓（只对未汉化的上游树使用）')
    ap.add_argument('--overrides',
                    help='按文件的覆盖表；--cjk 下要靠它把那些译文也排除在外')
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print('目录不存在: ' + args.root, file=sys.stderr)
        return 2

    # 先读一遍已有译文：--cjk 模式要靠它把我们自己的产出排除在外。
    #
    # ⚠ 两处都踩过：
    #   · 译文列在表里是**转义存**的（\\x3cbr\\x3e），而文件里是未转义的形态，
    #     不还原就对不上，重抽会把自己的译文当成待翻内容再抓一遍；
    #   · 按文件的覆盖表里也有译文（如「辅助」），同样要算进来。
    # 修之前对已汉化的树重抽会多出 304 条，其中 303 条是我们自己的产出。
    def unesc(x):
        return x.replace('\\t', '\t').replace('\\n', '\n').replace('\\\\', '\\')

    prior = {}
    known = set()
    if os.path.exists(args.out):
        for line in open(args.out, encoding='utf-8'):
            if line.startswith('#'):
                continue
            c = line.rstrip('\n').split('\t')
            if len(c) >= 2 and c[1]:
                prior[c[0]] = c[1]
                # 自映射（译文与原文相同，如「魔法少女」）不算「我们的产出」——
                # 算进去的话，下次重抽会连原文一起挡掉，那一行就凭空消失了。
                if c[1] != c[0]:
                    known.add(unesc(c[1]))
    if args.overrides and os.path.exists(args.overrides):
        for line in open(args.overrides, encoding='utf-8'):
            if line.startswith('#'):
                continue
            c = line.rstrip('\n').split('\t')
            if len(c) >= 3 and c[2]:
                known.add(unesc(c[2]))
    hits, scanned = scan(args.root, None if args.all else DEFAULT_SKIP,
                         cjk=args.cjk, known_translations=known)
    freq = Counter({s: len(v) for s, v in hits.items()})

    # 增量合并：已有译文必须留住。
    # 上游改一个文件就得重抽一次，如果每次都覆盖，前面翻好的全没了——这种工具
    # 只要坑人一次，后面就没人敢再跑它。
    existing = {}
    if os.path.exists(args.out):
        for line in open(args.out, encoding='utf-8'):
            if line.startswith('#'):
                continue
            col = line.rstrip('\n').split('\t')
            if len(col) >= 2 and col[1]:
                existing[col[0]] = col[1]
        if existing:
            print('沿用已有译文 %d 条' % len(existing))

    with open(args.out, 'w', encoding='utf-8') as f:
        # 第二列留空给译文；第三列是风险标记；第四列出现次数（排优先级）；第五列出处
        f.write('# 原文\t译文\t风险\t出现次数\t出现于\n')
        for s, n in freq.most_common():
            where = ','.join(sorted(set(hits[s]))[:3])
            if len(set(hits[s])) > 3:
                where += ',…共%d处' % len(set(hits[s]))
            # TSV：原文里的制表符与换行要转义，否则列会错位
            esc = s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')
            r = risk_of(s)
            # 法条一律不给译文，即使表里以前填过——按维护者的规定，这类原文照旧
            tr = '' if r == '法条勿动' else existing.get(esc, '')
            f.write('%s\t%s\t%s\t%d\t%s\n' % (esc, tr, r, n, where))

    total = sum(freq.values())
    print('扫描 %d 个文件，日文串 %d 处，去重后 %d 条 → %s'
          % (scanned, total, len(freq), args.out))
    short = sum(1 for s in freq if len(s) <= 12)
    print('  其中 ≤12 字（按钮/标签类）%d 条，占 %.0f%%'
          % (short, 100.0 * short / max(1, len(freq))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
