#!/usr/bin/env python3
"""Check the online resource routes without changing package identities or APK gates."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def check(config, baseline=None):
    rows = [row for row in config['mirrors'] if row.get('enabled', True)]
    by_base = {row['base']: row for row in rows}
    assert len(by_base) == len(rows), 'duplicate resource routes'
    accelerated = ['https://edgeone.assets.magireco.top/',
                   'https://esa.assets.magireco.top/']
    personal = ['https://magireco-personal-release.pages.dev/',
                'https://github.com/HiiragiNemu/magireco-cn-patch/releases/download/latest/']
    for base in accelerated + personal:
        assert base in by_base, 'missing route: ' + base
        assert 1 <= by_base[base]['chunks'] <= 16, 'invalid chunk count'
    assert min(by_base[b]['weight'] for b in accelerated) > max(by_base[b]['weight'] for b in personal), 'base CDN routes must precede personal fallbacks'
    assert by_base[personal[0]]['name'] == 'Cloudflare 中转'
    assert by_base[personal[1]]['name'] == '个人 GitHub 直连'
    if baseline is not None:
        assert {k: v for k, v in config.items() if k != 'mirrors'} == {k: v for k, v in baseline.items() if k != 'mirrors'}, 'non-routing configuration changed'
    print('PASS: EdgeOne/ESA first, personal fallbacks retained, names preserved')
    if baseline is not None:
        print('PASS: APK identity, update metadata, credits and download settings unchanged')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'configures/personal-online-config.json')
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    check(json.loads(args.config.read_text(encoding='utf-8')),
          json.loads(args.baseline.read_text(encoding='utf-8')) if args.baseline else None)
