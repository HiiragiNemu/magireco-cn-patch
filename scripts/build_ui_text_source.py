#!/usr/bin/env python3
"""把本仓库的 TSV 对照表生成只读审计索引（uiTextList.json）。

输出结构（供外部脚本以后统一转换成单一 JS 字典）：

    {
      "follow.a1b2c3": {
        "ja":     "フォロー数: ",
        "zhCN":   "关注数：",
        "status": "legacy-unverified-ai-assisted",
        "usedBy": ["magica/js/follow/FollowPopup.js", ...],
        "overrides": {"js/view/": "支援"}     // 可选，按路径前缀覆盖
      },
      ...
    }

键：`<首位置目录>.<ja 的 sha1 前 6 位>`——自动生成、可重复、与顺序无关；
人工可以后续把键改成语义名（如 follow.followCount），键只要求稳定唯一。

用法：
    python3 scripts/build_ui_text_source.py \
        [--tsv DIR]          本仓库 i18n/ 目录（默认脚本所在仓库的 i18n/）
        [--out PATH]         输出路径（默认本仓库 i18n/uiTextList.json）

这个 JSON 不被 Actions、Build_JS_Injector 或客户端运行时消费，也不会写入
``magica/``。迁移表来自含 AI 协作者的批次；没有逐条人工复核证据，所以任何条目
都不得标为 ``human-reviewed``。三条 v5 偏离项只作为低权重待审提案保留，不覆盖
迁移候选。
"""
import argparse
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# v5 修正中有意偏离 TSV 的条目：只保留成低权重提案，待逐条人工确认。
V5_DEVIATIONS = {
    '(オファー可能：': '　（可报价：',
    '（オファー：COMPLETE）': '　（报价：完成）',
    'メモリア保管庫': '记忆保管库',
}


def unesc(s):
    return s.replace('\\t', '\t').replace('\\n', '\n').replace('\\\\', '\\')


def load_tsv(path):
    rows = []
    with Path(path).open(encoding='utf-8-sig') as handle:
        for line_no, line in enumerate(handle, 1):
            if line.startswith('#'):
                continue
            col = line.rstrip('\r\n').split('\t')
            if len(col) >= 2 and col[1]:
                usedby = col[4].split(',') if len(col) >= 5 and col[4] else []
                rows.append((line_no, col[0], col[1], unesc(col[0]), unesc(col[1]),
                             [u.strip() for u in usedby if u.strip()]))
    return rows


def load_overrides(path):
    ov = {}
    with Path(path).open(encoding='utf-8-sig') as handle:
        for line in handle:
            if line.startswith('#'):
                continue
            col = line.rstrip('\r\n').split('\t')
            if len(col) >= 3 and col[0] and col[1] and col[2]:
                dst = '' if col[2] == '<DELETE>' else unesc(col[2])
                ov.setdefault(unesc(col[1]), {})[col[0]] = dst
    return ov


def candidate_fingerprint(ja, zh):
    return hashlib.sha256((ja + '\0' + zh).encode('utf-8')).hexdigest()


def load_lineage(path):
    with Path(path).open(encoding='utf-8-sig') as handle:
        summary = json.load(handle)
    return summary['source_tables']['frontend-strings.tsv']['translated_candidate_lineage']


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
    ap.add_argument('--tsv', type=Path, default=REPO_ROOT / 'i18n')
    ap.add_argument('--out', type=Path, default=REPO_ROOT / 'i18n' / 'uiTextList.json')
    ap.add_argument('--migration-summary', type=Path,
                    default=REPO_ROOT / 'i18n' / 'migration-source-summary.json')
    args = ap.parse_args()

    table = load_tsv(args.tsv / 'frontend-strings.tsv')
    overrides = load_overrides(args.tsv / 'overrides.tsv')
    lineage = load_lineage(args.migration_summary)

    entries = {}
    collisions = 0
    for line_no, stored_ja, stored_zh, ja, zh, usedby in table:
        evidence = lineage.get(candidate_fingerprint(stored_ja, stored_zh))
        if not evidence:
            raise SystemExit(
                f'frontend-strings.tsv:{line_no}: 译文没有迁移来源记录；'
                '请先登记为有证据的人工译文或新提案')
        batch = evidence['batch'] if isinstance(evidence, dict) else evidence
        commit = evidence.get('commit', '') if isinstance(evidence, dict) else ''
        area = area_of(usedby)
        h = hashlib.sha1(ja.encode('utf-8')).hexdigest()
        key = f'{area}.{h[:6]}'
        while key in entries:  # 极小概率碰撞就延长哈希
            h = h + h
            key = f'{area}.{h[:8]}'
            collisions += 1
        e = {
            'ja': ja,
            'zhCN': zh,
            'status': 'legacy-unverified-ai-assisted',
            'authority': 'legacy_unverified_ai_assisted',
            'source': 'i18n/frontend-strings.tsv',
            'sourceLine': line_no,
            'sourceBatch': batch,
            'sourceCommit': commit,
            'usedBy': usedby,
        }
        if ja in V5_DEVIATIONS:
            e['proposal'] = {
                'zhCN': V5_DEVIATIONS[ja],
                'status': 'needs-review',
                'authority': 'new_proposal',
                'selected': False,
            }
        if ja in overrides:
            e['overrides'] = overrides[ja]
            e['overridesStatus'] = 'legacy-unverified-ai-assisted'
        entries[key] = e

    out = dict(sorted(entries.items()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'{len(out)} 条 → {args.out}'
          f'（legacy-unverified-ai-assisted {sum(1 for e in out.values() if e["status"] == "legacy-unverified-ai-assisted")}，'
          f'待审提案 {sum(1 for e in out.values() if "proposal" in e)}，'
          f'带覆盖 {sum(1 for e in out.values() if "overrides" in e)}，'
          f'键碰撞 {collisions}）')


if __name__ == '__main__':
    main()
