#!/usr/bin/env python3
"""Promote only an already-published verified client; never mirror game resources."""
from __future__ import annotations
import argparse
import copy
import json
import os
import re
import tempfile
import time
from pathlib import Path
from mirror_release import API, APK, APK_META, CONFIG_PATH, Failure, asset_map, identity, check_monotonic, anonymous_verify

CLIENT_FIELDS = ('version', 'sha256', 'size')

def client_assets(api):
    release = api.json('releases/tags/latest')
    if release.get('draft') or release.get('prerelease'):
        raise Failure('Client release is not publicly published')
    available = asset_map(api, release)
    selected = {}
    for name in (APK, APK_META):
        item = available.get(name, {})
        if (item.get('state') != 'uploaded' or not isinstance(item.get('size'), int)
                or item['size'] <= 0 or not re.fullmatch(r'sha256:[0-9a-f]{64}', item.get('digest', ''))):
            raise Failure('Missing or incomplete verified client asset: ' + name)
        selected[name] = item
    return selected

def plan_config(current, wanted, target):
    if (not re.fullmatch(r'1\.0\.[1-9][0-9]*', str(wanted.get('version', '')))
            or not re.fullmatch(r'[0-9a-f]{64}', wanted.get('sha256', ''))
            or type(wanted.get('size')) is not int or wanted['size'] <= 0):
        raise Failure('Invalid verified client identity')
    check_monotonic(current['client'], wanted)
    result = copy.deepcopy(current)
    for key in CLIENT_FIELDS:
        result['client'][key] = wanted[key]
    result['client']['apk_url'] = 'https://github.com/' + target + '/releases/download/latest/' + APK
    # Keep live resource versions, mirrors, credits, branch policy and settings.
    # A name-only APK must never backfill an older scenario or JS publication.
    if result != current:
        result['updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    return result

def promote(source, target, work, expected_run):
    selected = client_assets(source)
    delivered = client_assets(target)
    for name in (APK, APK_META):
        if (selected[name]['size'], selected[name]['digest']) != (delivered[name]['size'], delivered[name]['digest']):
            raise Failure('Public client bytes differ from the verified publication: ' + name)
    raw_source, _ = source.file(CONFIG_PATH)
    wanted = json.loads(raw_source)['client']
    for label, api, assets in (('source', source, selected), ('public', target, delivered)):
        path = work / (label + '-client.json')
        api.download(assets[APK_META], path)
        meta = json.loads(path.read_text(encoding='utf-8'))
        if any(meta.get(k) != wanted.get(k) for k in CLIENT_FIELDS):
            raise Failure('Client metadata and source gate disagree')
        if (meta.get('publication') != 'PUBLISHED' or meta.get('source_branch') != 'main'
                or meta.get('published_from_run') != expected_run):
            raise Failure('Client metadata does not identify the accepted main build')
        if (assets[APK]['size'] != wanted['size']
                or assets[APK]['digest'] != 'sha256:' + wanted['sha256']):
            raise Failure('Client metadata does not identify the delivered APK')
    raw_current, current_sha = target.file('legacy/config.json')
    current = json.loads(raw_current)
    promoted = plan_config(current, wanted, target.repo)
    # Verify public byte reachability before the compare-and-swap gate update.
    anonymous_verify(target.repo, delivered)
    if identity(client_assets(source)) != identity(selected) or identity(client_assets(target)) != identity(delivered):
        raise Failure('Client assets changed during validation')
    latest_source, _ = source.file(CONFIG_PATH)
    if any(json.loads(latest_source)['client'].get(k) != wanted.get(k) for k in CLIENT_FIELDS):
        raise Failure('Source client identity advanced during validation')
    if promoted != current:
        import base64
        encoded = (json.dumps(promoted, ensure_ascii=False, indent=2) + '\n').encode()
        # The file SHA is mandatory. Concurrent public configuration changes
        # fail closed instead of being overwritten with this earlier snapshot.
        target.json('contents/legacy/config.json', 'PUT', {
            'message': 'fix(client): 仅发布已验证客户端并保留现有资源版本\n\n文档: 客户端发布与资源镜像生命周期隔离。\n\nCo-authored-by: Codex <noreply@openai.com>',
            'sha': current_sha, 'branch': 'main',
            'content': base64.b64encode(encoded).decode(),
        })
        anonymous_verify(target.repo, {}, encoded)
    report = {'clientVersion': wanted['version'], 'sha256': wanted['sha256'],
              'size': wanted['size'], 'sourceRun': expected_run,
              'resourceAssetsWritten': 0, 'publicConfigChanged': promoted != current}
    print('PUBLIC_CLIENT_READY', json.dumps(report), flush=True)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--expected-run', required=True, type=int)
    args = parser.parse_args()
    if args.source == args.target or args.expected_run <= 0:
        raise Failure('Invalid client publication boundary')
    source = API(args.source, os.environ.get('SOURCE_TOKEN', ''))
    target = API(args.target, os.environ.get('TARGET_TOKEN', ''))
    if not source.token or not target.token:
        raise Failure('Client publication credentials must be configured in Actions')
    with tempfile.TemporaryDirectory(prefix='client-gate-') as tmp:
        report = promote(source, target, Path(tmp), args.expected_run)
    Path('client-publication-report.json').write_text(json.dumps(report, indent=2) + '\n')

if __name__ == '__main__':
    try:
        main()
    except Failure as exc:
        raise SystemExit(str(exc))
    except Exception as exc:
        raise SystemExit('Client gate promotion failed (' + type(exc).__name__ + '); no resource mirroring was requested')
