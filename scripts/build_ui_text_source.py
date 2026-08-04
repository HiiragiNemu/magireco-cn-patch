#!/usr/bin/env python3
"""把 legacy-client 的 TSV 对照表升级为下一代 JSON 翻译源（uiTextList.json）。

输出结构（供外部脚本以后统一转换成单一 JS 字典）：

    {
      "follow.a1b2c3": {
        "ja":     "フォロー数: ",
        "zhCN":   "关注数：",
        "status": "human-reviewed",          // 或 needs-review
        "usedBy": ["magica/js/follow/FollowPopup.js", ...],
        "overrides": {"js/view/": "支援"}     // 可选，按路径前缀覆盖
      },
      ...
    }

键：`<首位置目录>.<ja 的 sha1 前 6 位>`——自动生成、可重复、与顺序无关；
人工可以后续把键改成语义名（如 follow.followCount），键只要求稳定唯一。

用法：
    python3 scripts/build_ui_text_source.py \
        [--tsv DIR]          legacy-client 的 i18n/ 目录（默认 ../magirecocn-legacy-client/i18n）
        [--out PATH]         输出路径（默认 i18n/uiTextList.json）
"""
import argparse
import hashlib
import json
import os

# v5 修正中有意偏离 TSV 的条目：zhCN 以 v5 产物为准，标 needs-review 待贡献者确认
V5_DEVIATIONS = {
    '(オファー可能：': ('　（可报价：', 'needs-review'),
    '（オファー：COMPLETE）': ('　（报价：完成）', 'needs-review'),
    'メモリア保管庫': ('记忆保管库', 'needs-review'),  # Wiki 用语：记忆保管库
}


def unesc(s):
    return s.replace('\\t', '\t').replace('\\n', '\n').replace('\\\\', '\\')


def load_tsv(path):
    rows = []
    for line in open(path, encoding='utf-8'):
        if line.startswith('#'):
            continue
        col = line.rstrip('\n').split('\t')
        if len(col) >= 2 and col[1]:
            usedby = col[4].split(',') if len(col) >= 5 and col[4] else []
            rows.append((unesc(col[0]), unesc(col[1]),
                         [u.strip() for u in usedby if u.strip()]))
    return rows


def load_overrides(path):
    ov = {}
    for line in open(path, encoding='utf-8'):
        if line.startswith('#'):
            continue
        col = line.rstrip('\n').split('\t')
        if len(col) >= 3 and col[0] and col[1] and col[2]:
            dst = '' if col[2] == '<DELETE>' else unesc(col[2])
            ov.setdefault(unesc(col[1]), {})[col[0]] = dst
    return ov


def area_of(usedby):
    """取首位置的路径段当键前缀：js/follow/…→follow，template/top/…→top"""
    if not usedby:
        return 'misc'
    parts = usedby[0].replace('\\', '/').split('/')
    for p in parts:
        if p not in ('js', 'template', 'magica') and '.' not in p:
            return p
    return 'misc'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tsv', default='/root/magirecocn-legacy-client/i18n')
    ap.add_argument('--out', default='/root/magireco-cn-patch/i18n/uiTextList.json')
    args = ap.parse_args()

    table = load_tsv(os.path.join(args.tsv, 'frontend-strings.tsv'))
    overrides = load_overrides(os.path.join(args.tsv, 'overrides.tsv'))

    entries = {}
    collisions = 0
    for ja, zh, usedby in table:
        if ja in V5_DEVIATIONS:
            zh, status = V5_DEVIATIONS[ja]
        else:
            status = 'human-reviewed'
        area = area_of(usedby)
        h = hashlib.sha1(ja.encode('utf-8')).hexdigest()
        key = f'{area}.{h[:6]}'
        while key in entries:  # 极小概率碰撞就延长哈希
            h = h + h
            key = f'{area}.{h[:8]}'
            collisions += 1
        e = {'ja': ja, 'zhCN': zh, 'status': status, 'usedBy': usedby}
        if ja in overrides:
            e['overrides'] = overrides[ja]
        entries[key] = e

    out = dict(sorted(entries.items()))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'{len(out)} 条 → {args.out}'
          f'（needs-review {sum(1 for e in out.values() if e["status"] != "human-reviewed")}，'
          f'带覆盖 {sum(1 for e in out.values() if "overrides" in e)}，'
          f'键碰撞 {collisions}）')


if __name__ == '__main__':
    main()
