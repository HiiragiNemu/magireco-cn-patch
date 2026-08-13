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
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path

JS_LIT = re.compile(r'(["\'])((?:(?!\1)[^\\]|\\.)*)\1')
HTML_TEXT = re.compile(r'>([^<>{}]*)<')
HTML_ATTR = re.compile(r'((?:placeholder|title|alt|value)=")([^"]*)(")')

EFFECTIVE_COLUMNS = (
    "key", "scope", "path_prefix", "source_text", "selected_cn", "authority",
    "weight", "source_file", "source_line", "source_batch", "evidence",
)
CANONICAL_INPUTS = (
    "frontend-strings.tsv", "glossary.tsv", "overrides.tsv", "fragments.tsv",
    "reviewed-candidates.tsv",
)


class EffectiveGateError(ValueError):
    """The canonical authority view is missing, stale, or structurally invalid."""


def normalized_lf_bytes(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def normalized_sha256(path):
    return hashlib.sha256(normalized_lf_bytes(path)).hexdigest()


def decode_cell(value):
    """Decode the literal escaping convention used by frontend-strings.tsv."""
    return value.replace('\\t', '\t').replace('\\n', '\n').replace('\\\\', '\\')


def canonical_i18n_dir(table_path):
    """Return the canonical maintenance directory, or None for an ad-hoc table.

    The two contract files identify the migrated authority dataset.  Detection
    does not depend on generated files: deleting them must still fail closed.
    """
    table_path = Path(table_path).resolve()
    parent = table_path.parent
    if (
        table_path.name == "frontend-strings.tsv"
        and (parent / "authority-policy.json").is_file()
        and (parent / "migration-source-summary.json").is_file()
    ):
        return parent
    return None


def source_keys(path):
    keys = set()
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if not row or row[0].startswith("#"):
                continue
            if row[0]:
                keys.add(decode_cell(row[0]))
    return keys


def _require_hash(record, label):
    if not isinstance(record, dict):
        raise EffectiveGateError("effective 摘要缺少 %s" % label)
    value = record.get("normalized_lf_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", str(value)):
        raise EffectiveGateError("effective 摘要的 %s 哈希无效" % label)
    return value


def _verify_bound_file(path, record, label):
    path = Path(path)
    if not path.is_file():
        raise EffectiveGateError("缺少 effective 绑定文件：%s" % path)
    expected = _require_hash(record, label)
    actual = normalized_sha256(path)
    if actual != expected:
        raise EffectiveGateError(
            "%s 已变化，effective 视图陈旧（expected %s, got %s）"
            % (label, expected, actual)
        )


def load_verified_effective(table_path):
    """Load the fresh canonical effective overlay.

    This is intentionally strict.  The raw migrated four-table snapshot remains
    untouched for provenance, but applying its canonical frontend table is only
    allowed when the generated selection is cryptographically bound to all five
    current authority inputs, both policy contracts, the producer code, and the
    exact effective output.
    """
    i18n_dir = canonical_i18n_dir(table_path)
    if i18n_dir is None:
        return None

    generated = i18n_dir / "generated"
    effective_path = generated / "effective.tsv"
    summary_path = generated / "summary.json"
    if not summary_path.is_file():
        raise EffectiveGateError("缺少 canonical effective 摘要：%s" % summary_path)
    if not effective_path.is_file():
        raise EffectiveGateError("缺少 canonical effective 表：%s" % effective_path)
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EffectiveGateError("canonical effective 摘要不可读：%s" % exc) from exc

    if summary.get("schema_version") != 1:
        raise EffectiveGateError("canonical effective 摘要 schema_version 不受支持")
    if summary.get("result") != "pass" or summary.get("fatal_equal_weight_conflicts") != 0:
        raise EffectiveGateError("canonical effective 审计未通过或仍有同权重冲突")
    if (
        summary.get("mode") != "audit-only"
        or summary.get("product_tree_writes") != 0
        or summary.get("magica_consumed") is not False
        or summary.get("runtime_consumed") is not False
    ):
        raise EffectiveGateError("canonical effective 摘要违反只读生成合同")

    input_tables = summary.get("input_tables")
    if not isinstance(input_tables, dict):
        raise EffectiveGateError("canonical effective 摘要缺少 input_tables")
    for name in CANONICAL_INPUTS:
        _verify_bound_file(i18n_dir / name, input_tables.get(name), "input_tables.%s" % name)

    contracts = summary.get("input_contracts")
    if not isinstance(contracts, dict):
        raise EffectiveGateError("canonical effective 摘要缺少 input_contracts")
    for name in ("authority-policy.json", "migration-source-summary.json"):
        _verify_bound_file(i18n_dir / name, contracts.get(name), "input_contracts.%s" % name)

    producer_path = Path(__file__).resolve().with_name("i18n-build-effective.py")
    producer = summary.get("producer")
    if not isinstance(producer, dict) or producer.get("path") != "tools/i18n-build-effective.py":
        raise EffectiveGateError("canonical effective 摘要缺少固定 producer 身份")
    _verify_bound_file(producer_path, producer, "producer")

    outputs = summary.get("generated_outputs")
    if not isinstance(outputs, dict):
        raise EffectiveGateError("canonical effective 摘要缺少 generated_outputs")
    effective_record = outputs.get("effective.tsv")
    _verify_bound_file(effective_path, effective_record, "generated_outputs.effective.tsv")

    allowed_sources = source_keys(table_path)
    overlay = {}
    row_count = 0
    with effective_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != EFFECTIVE_COLUMNS:
            raise EffectiveGateError("canonical effective.tsv 表头不匹配")
        seen_keys = set()
        for row in reader:
            row_count += 1
            key = row["key"]
            if not key or key in seen_keys:
                raise EffectiveGateError("canonical effective.tsv 存在空键或重复键")
            seen_keys.add(key)
            if row["scope"] != "global" or row["path_prefix"]:
                continue
            src = decode_cell(row["source_text"])
            if src not in allowed_sources:
                continue
            dst = decode_cell(row["selected_cn"])
            if not dst:
                raise EffectiveGateError("canonical effective.tsv 为原文 %r 选择了空译文" % src)
            why = unsafe_reason(src, dst)
            if why:
                raise EffectiveGateError(
                    "canonical effective.tsv 的 %r 会破坏结构：%s" % (src, why)
                )
            if src in overlay and overlay[src] != dst:
                raise EffectiveGateError("canonical effective.tsv 对原文 %r 给出多个目标" % src)
            overlay[src] = dst

    if row_count != summary.get("effective_rows"):
        raise EffectiveGateError(
            "canonical effective.tsv 行数与摘要不一致（expected %r, got %d）"
            % (summary.get("effective_rows"), row_count)
        )
    if not isinstance(effective_record, dict) or row_count != effective_record.get("data_rows"):
        raise EffectiveGateError("canonical effective.tsv 行数与输出绑定不一致")
    if not overlay:
        raise EffectiveGateError("canonical effective.tsv 未覆盖 frontend-strings.tsv 的任何原文")
    return overlay


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
            src = decode_cell(col[0])
            dst = decode_cell(col[1])
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
    try:
        effective_overlay = load_verified_effective(args.table)
    except EffectiveGateError as exc:
        print('✘ canonical effective 权威门失败：%s' % exc, file=sys.stderr)
        return 2
    if effective_overlay is not None:
        changed_authority = sum(
            source not in table or table[source] != target
            for source, target in effective_overlay.items()
        )
        filled_authority = sum(source not in table for source in effective_overlay)
        table.update(effective_overlay)
        print(
            '✔ canonical effective 已验证：命中原始主表 %d 条，权威覆盖 %d 条（补全 %d 条）'
            % (len(effective_overlay), changed_authority, filled_authority)
        )
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
