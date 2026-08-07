#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把新一轮译文合并进现有译文——**新版权威，但不许把已翻的东西退回去**。

## 为什么不能直接整包覆盖

每一轮 LLM 重译（pass6、batch11 这种）覆盖的是同一批文件，但覆盖率不是单调的：
新一轮往往在 A 处译得更好、在 B 处却漏译，于是整包覆盖会把 B 处**退回日文**。

实测把 v3 直接盖上去的后果：

  · 29 个前端文件里假名反而变多，合计 1520 个字符退回日文；
  · `js/libs/*.json` 那 23 张数据表里 **11735 处字段**退回日文
    （道具名、记忆结晶名、关卡标题、商店条目……条目一个没少，但内容退了）。

所以要做的是**合并**，不是覆盖：新版权威，只在「新版没译、旧版译了」的地方保留旧版。

## 判据：什么叫「新版没译、旧版译了」

对每一个可比较的字符串单元，取旧值 o、新值 v：

  1. 新版没有这个单元        → 用 o
  2. o == v                  → 用 v
  3. v 的**假名比 o 多**              → 用 o（新版把它退回日文了；比数量而不是
                                          比有无，才能覆盖「旧版译了一半」的情况）
  4. v 是**纯 ASCII 且含字母**而 o 里有汉字 → 用 o（新版把它退回英文了）
  5. 其余                    → 用 v（新版权威）

第 3 条为什么用假名而不是「有没有汉字」：中日文都用汉字，假名才是「这段没被翻译」
的可靠信号。两边都有假名时（比如专有名词「キモチ」）走第 5 条，仍以新版为准。

## 怎么切成「字符串单元」

  · **JSON 数据表**：按主键索引成 {id: 条目}，再逐字段比。
  · **JS**：把字符串字面量抠出来，剩下的部分当骨架。骨架一致（实测 196 个里 194 个
    一致）说明两版结构相同，字面量可以按位置一一对应地合并。
  · **HTML 模板**：按 `<...>` 切成「标签 / 文本段」交替序列。标签序列一致
    （实测 181 个里 167 个一致）就逐文本段合并。
  · 以上都对不上的少数文件，退回 difflib 的 token 级对齐，只在 `replace` 块上
    套同一套判据；`insert`/`delete` 一律听新版的——那是结构变化，不是译文差异。

用法：
    python3 scripts/merge_translations.py --old <旧包.zip|目录> --new magica --report
    python3 scripts/merge_translations.py --old <旧包.zip|目录> --new magica --write
"""

import argparse
import difflib
import io
import json
import os
import re
import sys
import zipfile

KANA = re.compile(r'[぀-ヿｦ-ﾟ]')      # 平假名 / 片假名 / 半角片假名
CJK  = re.compile(r'[一-鿿㐀-䶿]')      # 汉字
LATIN = re.compile(r'[A-Za-z]')

STR_JS   = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
TAG_HTML = re.compile(r'(<[^>]*>)')
TOKEN    = re.compile(r'[^\x00-\x7f]+|[A-Za-z0-9_]+|\s+|.')

# 「这个字符串是拿来比较的，不是拿来显示的」——这种一律不还原旧译文。
# 例：APPopup2.html 里 `item.itemName === "マギアストーン"`。旧版把它译成了
# 「Magia 石材」，但 itemList 里根本没有 MAGIA_STONE 这个条目，运行时字典不会
# 改写 item.itemName，于是这个分支永远不成立——旧版那处是**bug**，v3 保留日文
# 才是对的。显示文案该还原，判据键不该动，两者只能靠上下文区分。
# 引号可能被切成独立 token，所以两侧都要容忍一个引号
CMP_BEFORE = re.compile(
    r'(===?|!==?|\bcase\b|indexOf\s*\(|includes\s*\(|switch\s*\()\s*["\']?\s*$')
CMP_AFTER  = re.compile(r'^\s*["\']?\s*(===?|!==?)')


def is_cmp(before, after):
    return bool(CMP_BEFORE.search(before[-24:])) or bool(CMP_AFTER.match(after[:8]))


def pick(o, v, before='', after=''):
    """核心判据。返回该采用的那个值，外加是否「保住了旧译文」。"""
    if v is None:
        return o, o is not None
    if o is None or o == v:
        return v, False
    if is_cmp(before, after):
        return v, False        # 比较用的字符串，听 v3 的
    # 新版退回日文：比的是假名**数量**而不是有无。
    # 有无只能抓住「旧版全译、新版全没译」；实测更常见的是旧版译了一半、新版
    # 整句都是日文——两边都有假名，按有无判就会放它过去。数量能一起覆盖两种。
    if len(KANA.findall(v)) > len(KANA.findall(o)):
        return o, True
    # 新版退回英文
    if LATIN.search(v) and not re.search(r'[^\x00-\x7f]', v) and CJK.search(o):
        return o, True
    return v, False


# ---------------------------------------------------------------- JSON

PRIMARY_KEYS = ('cardId', 'charaId', 'charaNo', 'chapterId', 'giftId', 'itemCode',
                'itemId', 'pieceId', 'enemyId', 'patrolAreaId', 'shopItemId',
                'formationSheetId', 'sectionId', 'eventId', 'storyIds',
                'arenaBattleFreeRankClass', 'skillId', 'magiaId', 'id')


def key_of(item):
    if not isinstance(item, dict):
        return None
    for k in PRIMARY_KEYS:
        if k in item:
            return str(item[k])
    return None


def merge_json(old_raw, new_raw):
    """返回 (合并后的 bytes, 保住的字段数)。结构一律沿用新版。"""
    o = json.loads(old_raw)
    v = json.loads(new_raw)
    kept = 0

    def merge_item(oi, vi):
        nonlocal kept
        if not isinstance(oi, dict) or not isinstance(vi, dict):
            return vi
        out = dict(vi)
        for f, ov in oi.items():
            if not isinstance(ov, str):
                continue
            chosen, k = pick(ov, vi.get(f))
            if k:
                out[f] = chosen
                kept += 1
        return out

    if isinstance(v, list):
        oidx = {}
        for it in (o if isinstance(o, list) else []):
            k = key_of(it)
            if k is not None:
                oidx[k] = it
        merged = []
        for it in v:
            k = key_of(it)
            merged.append(merge_item(oidx[k], it) if (k is not None and k in oidx) else it)
        out = merged
    elif isinstance(v, dict):
        out = {}
        for k, it in v.items():
            out[k] = merge_item(o.get(k), it) if isinstance(o, dict) else it
    else:
        return new_raw, 0
    return json.dumps(out, ensure_ascii=False, indent=1).encode('utf-8'), kept


# ---------------------------------------------------------------- 文本

def split_js(s):
    """→ (骨架, 字面量列表)"""
    lits = STR_JS.findall(s)
    skel = STR_JS.split(s)
    return skel, lits


def join_js(skel, lits):
    out = [skel[0]]
    for i, l in enumerate(lits):
        out.append(l)
        out.append(skel[i + 1])
    return ''.join(out)


def merge_inline(o, v):
    """合并一个 HTML 文本段。段内可能混着 <% %> 模板代码，所以仍要按 token 对齐
    并逐块判断比较上下文，不能整段一刀切。返回 (文本, 保住的块数)。"""
    if o == v:
        return v, 0
    ot, vt = TOKEN.findall(o), TOKEN.findall(v)
    sm = difflib.SequenceMatcher(None, ot, vt, autojunk=False)
    buf, kept = [], 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            before = ''.join(vt[max(0, j1 - 12):j1])
            after  = ''.join(vt[j2:j2 + 6])
            chosen, k = pick(''.join(ot[i1:i2]), ''.join(vt[j1:j2]), before, after)
            buf.append(chosen)
            if k:
                kept += 1
        elif tag == 'equal':
            buf.append(''.join(vt[j1:j2]))
        else:
            buf.append(''.join(vt[j1:j2]))
    return ''.join(buf), kept


def merge_text(o, v, is_html):
    """返回 (合并后文本, 保住的单元数, 用了哪种对齐)。"""
    kept = 0
    if is_html:
        op, vp = TAG_HTML.split(o), TAG_HTML.split(v)
        if len(op) == len(vp) and all(op[i] == vp[i] for i in range(1, len(op), 2)):
            out = list(vp)
            for i in range(0, len(vp), 2):          # 偶数下标是文本段
                # 文本段里可能整段就是 <% ... %> 模板代码，比较上下文要在段内找
                chosen, k = merge_inline(op[i], vp[i])
                if k:
                    out[i] = chosen
                    kept += k
            return ''.join(out), kept, 'tag'
    else:
        oskel, olits = split_js(o)
        vskel, vlits = split_js(v)
        if oskel == vskel and len(olits) == len(vlits):
            out = list(vlits)
            for i in range(len(vlits)):
                chosen, k = pick(olits[i], vlits[i], vskel[i], vskel[i + 1])
                if k:
                    out[i] = chosen
                    kept += 1
            return join_js(vskel, out), kept, 'literal'

    # 兜底：token 级对齐，只在 replace 块上套判据
    ot, vt = TOKEN.findall(o), TOKEN.findall(v)
    sm = difflib.SequenceMatcher(None, ot, vt, autojunk=False)
    buf = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            buf.append(''.join(vt[j1:j2]))
        elif tag == 'replace':
            before = ''.join(vt[max(0, j1 - 12):j1])
            after  = ''.join(vt[j2:j2 + 6])
            chosen, k = pick(''.join(ot[i1:i2]), ''.join(vt[j1:j2]), before, after)
            buf.append(chosen)
            if k:
                kept += 1
        else:
            # insert / delete 是结构变化，一律听新版的
            buf.append(''.join(vt[j1:j2]))
    return ''.join(buf), kept, 'token'


# ---------------------------------------------------------------- 主流程

class Source(object):
    """旧译文来源：zip 或目录，统一成 read(rel) -> bytes|None。"""
    def __init__(self, path):
        self.zip = zipfile.ZipFile(path) if zipfile.is_zipfile(path) else None
        self.dir = None if self.zip else path
        self.names = (set(n for n in self.zip.namelist() if not n.endswith('/'))
                      if self.zip else None)

    def read(self, rel):
        if self.zip:
            name = 'magica/' + rel
            return self.zip.read(name) if name in self.names else None
        p = os.path.join(self.dir, rel)
        return open(p, 'rb').read() if os.path.isfile(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', required=True, help='旧译文：cn_js_update.zip 或解开的目录')
    ap.add_argument('--new', default='magica', help='新译文所在目录（就地合并）')
    ap.add_argument('--write', action='store_true', help='真的写回；不给就只报告')
    ap.add_argument('--report', action='store_true')
    args = ap.parse_args()

    src = Source(args.old)
    total_kept = 0
    changed = []
    for dirpath, _, files in os.walk(args.new):
        for f in sorted(files):
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, args.new).replace(os.sep, '/')
            if rel.endswith('jquery-3.7.1.min.js'):
                continue                     # 注入产物，由 Build_JS_Injector.py 生成
            # 只合并有译文的三类。CSS 里没有译文，跑一遍 token 对齐纯属拿正确性
            # 换零收益——`magica/css/` 那 188 个文件是原样复刻服务端的，一个字节
            # 都不能动（见 check_css_freeze.py）。
            if not rel.endswith(('.js', '.html', '.json')):
                continue
            old_raw = src.read(rel)
            if old_raw is None:
                continue
            new_raw = open(p, 'rb').read()
            if old_raw == new_raw:
                continue
            try:
                if rel.endswith('.json'):
                    merged, kept = merge_json(old_raw, new_raw)
                    how = 'json'
                else:
                    merged_s, kept, how = merge_text(
                        old_raw.decode('utf-8'), new_raw.decode('utf-8'),
                        rel.endswith('.html'))
                    merged = merged_s.encode('utf-8')
            except Exception as e:
                sys.stderr.write('  ⚠ %s 合并失败，保留新版：%s\n' % (rel, e))
                continue
            if kept:
                total_kept += kept
                changed.append((rel, kept, how))
                if args.write and merged != new_raw:
                    with open(p, 'wb') as fh:
                        fh.write(merged)

    changed.sort(key=lambda r: -r[1])
    print('从旧译文里救回 %d 处，涉及 %d 个文件' % (total_kept, len(changed)))
    if args.report:
        for rel, kept, how in changed[:40]:
            print('  %6d  [%-7s] %s' % (kept, how, rel))
        if len(changed) > 40:
            print('  …还有 %d 个文件' % (len(changed) - 40))
    if not args.write:
        print('\n（只是报告；加 --write 才真的写回）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
