#!/usr/bin/env python3
"""魔纪 ADV v3 场景脚本的**流程层**分析器。

把 `madomagi/resource/scenario/json/` 全库扫一遍，产出 README 里那些数字，
并跑几条**可证伪**的检验（跳转目标必须落在同一文件的组上，等等）。
判据与结论见同目录的 README.md；这里只负责把它们跑出来。

用法：

    python3 tools/scenario-flow/analyze.py                    # 全库
    python3 tools/scenario-flow/analyze.py --root <目录>      # 指定语料根
    python3 tools/scenario-flow/analyze.py --json out.json    # 顺便存一份

退出码非 0 表示有检验没过 —— 那说明 README 里的某条结论已经不成立了。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

GROUP_RE = re.compile(r'^group_(\d+)$')
# 流程键。全库块键里只有这两个是控制流，其余都是演出/文本
SELECT = 'select'
CHANGE = 'changeGroup'
# story 直接是块数组时，段名只能我们自己起 —— 文件里没有名字
SYNTHETIC_ENTRY = '@0'


def default_root():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    return os.path.join(repo, 'madomagi', 'resource', 'scenario', 'json')


def load(path):
    """读一个场景，顺带说清它是哪种形状。

    返回 `(story, 类别)`：`story` 是 {组名: 块数组}，取不到就是 None。
    类别用来分开统计 —— 「解不开」和「形状不一样」是两回事，混在一起会让
    README 里的分母对不上。
    """
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        return None, 'not_json'
    if not isinstance(d, dict) or 'story' not in d:
        return None, 'no_story'
    story = d['story']
    if isinstance(story, dict):
        return story, 'groups'
    # 语料里有 1 个文件的 story 直接是块数组，没有组、也没有 version。
    # 当成「只有一段」处理，但段名是我们自己起的（文件里根本没有名字）。
    if isinstance(story, list):
        return {SYNTHETIC_ENTRY: story}, 'flat'
    return None, 'no_story'


def outgoing(blocks):
    """一个组往外的边，按出现顺序。"""
    out = []
    for b in blocks if isinstance(blocks, list) else []:
        if not isinstance(b, dict):
            continue
        if SELECT in b:
            for o in b[SELECT] or []:
                if isinstance(o, dict) and o.get('group'):
                    out.append(o['group'])
        if CHANGE in b:
            out.append(b[CHANGE])
    return out


def last_block(blocks):
    for b in reversed(blocks if isinstance(blocks, list) else []):
        if isinstance(b, dict):
            return b
    return None


def analyze(root):
    st = {
        'files': 0, 'not_json': 0, 'no_story': 0, 'flat_story': [], 'groups': 0, 'blocks': 0,
        'total_size': 0,
        'select_blocks': 0, 'select_files': 0, 'options': 0,
        'change_blocks': 0, 'change_files': 0,
        'options_per_select': Counter(), 'option_keys': Counter(),
        'bad_select_targets': [], 'bad_change_targets': [],
        'change_at_group_end': 0, 'change_not_at_end': [],
        'select_last_block': 0, 'select_trailing': [],
        'change_to_next_group': 0, 'change_to_further': 0, 'change_backwards': 0,
        'flow_keys_seen': Counter(),
        'per_dir': defaultdict(Counter),
        'flow_files': 0, 'flow_group_counts': Counter(),
        'cycles': [], 'self_loops': 0,
        'unreachable': [], 'unreachable_kinds': Counter(), 'nested_select_files': 0,
        'reconverge': Counter(),
        'multigroup_without_flow': defaultdict(int),
    }
    for dirpath, _dirs, names in os.walk(root):
        for name in sorted(names):
            if not name.endswith('.json'):
                continue
            path = os.path.join(dirpath, name)
            st['total_size'] += os.path.getsize(path)
            story, shape = load(path)
            if story is None:
                st[shape] += 1
                st.setdefault('%s_files' % shape, []).append(path)
                continue
            if shape == 'flat':
                st['flat_story'].append(path)
            st['files'] += 1
            rel = os.path.relpath(dirpath, root)
            top = rel.split(os.sep)[0] if rel != '.' else '.'
            sub = rel
            st['per_dir'][sub]['files'] += 1
            st['per_dir'][sub]['groups'] += len(story)
            st['groups'] += len(story)

            groups = set(story)
            edges = {}
            has_select = has_change = False
            select_groups, select_targets = set(), set()
            for g, blocks in story.items():
                blocks = blocks if isinstance(blocks, list) else []
                st['blocks'] += len(blocks)
                for i, b in enumerate(blocks):
                    if not isinstance(b, dict):
                        continue
                    for k in b:
                        if k in (SELECT, CHANGE):
                            st['flow_keys_seen'][k] += 1
                    if SELECT in b:
                        has_select = True
                        st['select_blocks'] += 1
                        select_groups.add(g)
                        opts = b[SELECT] if isinstance(b[SELECT], list) else []
                        st['options_per_select'][len(opts)] += 1
                        for o in opts:
                            st['options'] += 1
                            if isinstance(o, dict):
                                st['option_keys'].update(o.keys())
                                select_targets.add(o.get('group'))
                                if o.get('group') not in groups:
                                    st['bad_select_targets'].append((path, o.get('group')))
                        # select 是不是组里最后一个**有内容**的块
                        rest = [x for x in blocks[i + 1:] if isinstance(x, dict)]
                        if not rest:
                            st['select_last_block'] += 1
                        else:
                            st['select_trailing'].append(
                                (path, g, i, len(blocks), [sorted(x) for x in rest]))
                    if CHANGE in b:
                        has_change = True
                        st['change_blocks'] += 1
                        tgt = b[CHANGE]
                        if tgt not in groups:
                            st['bad_change_targets'].append((path, tgt))
                        if i == len(blocks) - 1:
                            st['change_at_group_end'] += 1
                        else:
                            st['change_not_at_end'].append((path, g, i, len(blocks)))
                        m, t = GROUP_RE.match(g), GROUP_RE.match(str(tgt))
                        if m and t:
                            gn, tn = int(m.group(1)), int(t.group(1))
                            if tn == gn + 1:
                                st['change_to_next_group'] += 1
                            elif tn > gn:
                                st['change_to_further'] += 1
                            else:
                                st['change_backwards'] += 1
                edges[g] = outgoing(blocks)
                if g in edges[g]:
                    st['self_loops'] += 1

            if has_select:
                st['select_files'] += 1
            if has_change:
                st['change_files'] += 1
            if has_select or has_change:
                st['flow_files'] += 1
                st['per_dir'][sub]['flow'] += 1
                st['flow_group_counts'][len(story)] += 1
                if select_groups & select_targets:
                    st['nested_select_files'] += 1
                # 可达性：从 group_1 出发
                seen, stack = set(), ['group_1']
                while stack:
                    g = stack.pop()
                    if g in seen or g not in edges:
                        continue
                    seen.add(g)
                    stack.extend(edges[g])
                miss = sorted(set(edges) - seen)
                if miss:
                    st['unreachable'].append((path, miss))
                    # 够不着的组长什么样？带 select 的话，那处 select 在可达的组里
                    # 出现过没有 —— 「重复的入口」和「另一处选项」是两回事
                    sel_of = {}
                    for g, blocks in story.items():
                        for b in blocks if isinstance(blocks, list) else []:
                            if isinstance(b, dict) and SELECT in b:
                                sel_of.setdefault(g, []).append(
                                    json.dumps(b[SELECT], ensure_ascii=False, sort_keys=True))
                    reach_sels = {x for g in seen for x in sel_of.get(g, [])}
                    for g in miss:
                        if g not in sel_of:
                            st['unreachable_kinds']['没有 select'] += 1
                        elif all(x in reach_sels for x in sel_of[g]):
                            st['unreachable_kinds']['重复了可达组里的 select'] += 1
                        else:
                            st['unreachable_kinds']['另一处不同的 select'] += 1
                # 汇合：入度大于 1 的组，就是几条支路又走到一起的地方
                indeg = Counter(v for outs in edges.values() for v in outs)
                st['reconverge'][sum(1 for _v, c in indeg.items() if c > 1)] += 1
                # 有没有环（只在带流程的文件上问，别的没有边）
                color = {}

                def dfs(u):
                    color[u] = 1
                    for v in edges.get(u, []):
                        if color.get(v) == 1:
                            st['cycles'].append((path, u, v))
                            return
                        if color.get(v) is None:
                            dfs(v)
                    color[u] = 2

                dfs('group_1')
            elif len(story) > 1:
                st['multigroup_without_flow'][sub] += 1
    return st


def report(st, root):
    p = print
    p(f'语料根：{root}')
    p(f'场景 {st["files"]} 个，组 {st["groups"]}，块 {st["blocks"]}，合计 {st["total_size"]} 字节')
    p(f'  另有 {st["not_json"]} 个 .json **根本不是 JSON**，{st["no_story"]} 个没有 story；'
      f'{len(st["flat_story"])} 个的 story 是块数组而不是组字典')
    p('')
    p('== 流程键 ==')
    p(f'  {SELECT}      {st["flow_keys_seen"][SELECT]} 处，{st["select_files"]} 个文件，'
      f'{st["options"]} 个选项')
    p(f'    每处的选项个数：{dict(sorted(st["options_per_select"].items()))}')
    p(f'    选项里的键：{dict(st["option_keys"])}')
    p(f'  {CHANGE} {st["flow_keys_seen"][CHANGE]} 处，{st["change_files"]} 个文件')
    p('')
    p('== 可证伪的检验 ==')
    checks = [
        ('所有 .json 都能解析', st['not_json'] == 0, st.get('not_json_files', [])[:3]),
        ('select 的目标组都在同一文件里', not st['bad_select_targets'], st['bad_select_targets'][:3]),
        ('changeGroup 的目标组都在同一文件里', not st['bad_change_targets'], st['bad_change_targets'][:3]),
        ('changeGroup 恒在组尾', not st['change_not_at_end'], st['change_not_at_end'][:3]),
        ('带流程的文件里没有环', not st['cycles'], st['cycles'][:3]),
        ('没有选项指向自己', st['self_loops'] == 0, st['self_loops']),
    ]
    bad = 0
    for name, okk, detail in checks:
        p(f'  [{"通过" if okk else "不通过"}] {name}' + ('' if okk else f' —— {detail}'))
        if not okk:
            bad += 1
    p(f'  select 是组里最后一个有内容的块：{st["select_last_block"]}/{st["flow_keys_seen"][SELECT]}；'
      f'其余 {len(st["select_trailing"])} 处后面只跟这些键：')
    for path, g, i, n, rest in st['select_trailing']:
        p(f'    {os.path.basename(path)} {g} 第{i}块/共{n}：{rest}')
    p('')
    p('== 语料形状记录 ==')
    p(f'  无法解析的 .json：{st["not_json"]} 个；'
      f'例如 {[os.path.basename(x) for x in st.get("not_json_files", [])[:3]]}')
    p(f'  {len(st["flat_story"])} 个的 story 是块数组：'
      f'{[os.path.basename(x) for x in st["flat_story"]]}')
    p('')
    p('== fall-through（组会不会自动落到下一组） ==')
    p(f'  changeGroup 的目标是紧邻下一组的：{st["change_to_next_group"]}；'
      f'跳更远的：{st["change_to_further"]}；往回跳的：{st["change_backwards"]}')
    p('  —— 若组会自动落下去，指向紧邻下一组的那些就是白写的。已排除。')
    p('')
    p('== 带流程的文件 ==')
    p(f'  {st["flow_files"]} 个，组数分布 {dict(sorted(st["flow_group_counts"].items()))}')
    p(f'  选项段里还有选项的：{st["nested_select_files"]} 个')
    merged = sum(n for k, n in st['reconverge'].items() if k)
    p(f'  有汇合（入度>1 的组）的文件：{merged}/{st["flow_files"]}，'
      f'汇合点个数分布 {dict(sorted(st["reconverge"].items()))}')
    p(f'  从 group_1 到不了的组：{sum(len(m) for _f, m in st["unreachable"])} 个，'
      f'分布在 {len(st["unreachable"])} 个文件；长相 {dict(st["unreachable_kinds"])}')
    p('')
    p('== 按目录 ==')
    for sub in sorted(st['per_dir']):
        c = st['per_dir'][sub]
        p(f'  {sub:24} 文件 {c["files"]:6} 组 {c["groups"]:6} 带流程 {c["flow"]:4} '
          f'多组但无流程 {st["multigroup_without_flow"][sub]}')
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=default_root(), help='场景 JSON 的根目录')
    ap.add_argument('--json', help='把统计另存一份 JSON')
    args = ap.parse_args()
    if not os.path.isdir(args.root):
        print(f'找不到语料根：{args.root}', file=sys.stderr)
        return 2
    st = analyze(args.root)
    bad = report(st, args.root)
    if args.json:
        def plain(v):
            if isinstance(v, Counter):
                return {str(k): n for k, n in v.items()}
            if isinstance(v, defaultdict):
                return {k: plain(n) for k, n in v.items()}
            return v
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump({k: plain(v) for k, v in st.items()}, f, ensure_ascii=False, indent=1)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
