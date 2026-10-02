"""Publish one coherent resource set to the existing latest releases.

No version-specific public Release is created. Payloads and manifests precede
version gates; after a gate opens recovery is forward-only. Unrelated assets,
including APKs, fonts in the frozen JS archive, and base/media ZIPs are untouched.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
from build_coherent_resources import build, identity, save, git, ROOT
from resource_layers import validate
from mirror_release import API, SafeRedirect, asset_map, check_monotonic

SOURCE = 'HiiragiNemu/magireco-cn-patch'
PUBLIC = 'HiiragiNemu/ProgettoMagius-1'
VERSIONS = ('version_js_delta.json', 'version_scenario.json')
PAYLOADS = ('cn_js_delta.zip', 'cn_scenario_update.zip',
            'cn_js_delta_manifest.json', 'cn_scenario_update_manifest.json', 'manifest.json')
CHANGED = PAYLOADS + VERSIONS
INPUTS = CHANGED + ('cn_js_update.zip', 'version_js.json')


def snapshot(api):
    release = api.json('releases/tags/latest')
    assets = asset_map(api, release)
    if release.get('draft') or release.get('prerelease'):
        raise ValueError('latest must be published')
    if any(n not in assets for n in INPUTS):
        raise ValueError('Missing existing publication input')
    return release, assets


def asset_identity(assets):
    return {n: (a['id'], a['size'], a.get('digest')) for n, a in assets.items()}


def matches(path, asset):
    return path.is_file() and path.stat().st_size == asset['size'] and 'sha256:' + identity(path)['sha256'] == asset['digest']


def obtain(api, asset, path, cache):
    path.parent.mkdir(parents=True, exist_ok=True)
    if matches(path, asset):
        return
    candidates = [cache / label / asset['name'] for label in
                  (api.repo.split('/')[-1], SOURCE.split('/')[-1], PUBLIC.split('/')[-1])] if cache else []
    candidate = next((p for p in candidates if matches(p, asset)), None)
    if candidate:
        shutil.copyfile(candidate, path)
    else:
        api.download(asset, path)
    if not matches(path, asset):
        raise ValueError('Downloaded input changed: ' + asset['name'])


def public_verify(url, expected, destination):
    opener = urllib.request.build_opener(SafeRedirect())
    for attempt in range(8):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Resource-Bundle-Verification', 'Accept-Encoding': 'identity'})
            with opener.open(request, timeout=120) as response, destination.open('wb') as out:
                if response.status != 200 or response.headers.get('Content-Range'):
                    raise ValueError('Not a complete public body')
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    out.write(chunk)
            if identity(destination) == expected:
                return
        except (OSError, ValueError):
            pass
        print('PUBLIC_BODY_RETRY', destination.name, attempt + 1, flush=True)
        time.sleep(5)
    raise ValueError('Ordinary anonymous URL did not converge: ' + destination.name)


def chunk_identity(path, chunk_size):
    result = []
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b''):
            result.append(hashlib.md5(chunk).hexdigest())
    return {'size': path.stat().st_size, 'chunk_size': chunk_size, 'chunks': result}


def publish_one(api, original, before, payload, work):
    release, assets = snapshot(api)
    if asset_identity(assets) != asset_identity(original):
        raise ValueError('Publication changed before replacement: ' + api.repo)
    for name in VERSIONS:
        check_monotonic(json.loads((before / name).read_bytes()), json.loads((payload / name).read_bytes()))
    modified, gate_opened = [], False
    verification = work / 'anonymous' / api.repo.split('/')[-1]
    verification.mkdir(parents=True, exist_ok=True)
    try:
        for name in CHANGED:
            path = payload / name
            if matches(path, assets[name]):
                continue
            # Recheck the full identity set before each write, including APKs and
            # media packages. A competing writer requires a new reviewed snapshot.
            current = asset_map(api, release)
            if asset_identity(current) != asset_identity(assets):
                raise ValueError('Concurrent release modification: ' + api.repo)
            modified.append(name)
            api.json('releases/assets/' + str(assets[name]['id']), 'DELETE')
            uploaded = api.upload(release, path)
            current = asset_map(api, release)
            if not matches(path, current[name]):
                raise ValueError('Uploaded bytes differ: ' + name)
            assets = current
            if name in VERSIONS:
                gate_opened = True
            public_verify(assets[name]['browser_download_url'], identity(path), verification / name)
            print('PUBLISHED_VERIFIED', api.repo, name, identity(path)['sha256'], flush=True)
        for name, old in original.items():
            if name not in CHANGED and asset_identity({name: assets[name]}) != asset_identity({name: old}):
                raise ValueError('Unrelated asset changed: ' + name)
        return {'repository': api.repo, 'modified': modified,
                'unrelated_assets_unchanged': True,
                'assets': {n: identity(payload / n) for n in CHANGED}}
    except Exception:
        # Detect a gate uploaded just before an interrupted response as well.
        current = asset_map(api, release)
        gate_opened = gate_opened or any(n in modified and matches(payload / n, current.get(n, {'size': -1})) for n in VERSIONS)
        if gate_opened:
            print('VERSION_GATE_OPEN: roll forward from saved payload; never restore an older version', flush=True)
        else:
            for name in reversed(modified):
                current = asset_map(api, release)
                if name in current:
                    api.json('releases/assets/' + str(current[name]['id']), 'DELETE')
                api.upload(release, before / name)
            print('PRE_GATE_INPUTS_RESTORED', api.repo, flush=True)
        raise


def run(work, cache=None, prepared=None, publish=False):
    token = os.environ.get('GH_TOKEN', '')
    if not token:
        raise ValueError('Authenticated repository access is required')
    work.mkdir(parents=True, exist_ok=True)
    source_commit = git(ROOT, 'rev-parse', 'HEAD').decode().strip()
    apis = [API(SOURCE, token), API(PUBLIC, token)]
    snapshots, folders = {}, {}
    for api in apis:
        release, assets = snapshot(api)
        snapshots[api.repo] = assets
        save(work / (api.repo.split('/')[-1] + '-before.json'), release | {'assets': list(assets.values())})
        folder = work / 'before' / api.repo.split('/')[-1]
        folders[api.repo] = folder
        for name in INPUTS:
            obtain(api, assets[name], folder / name, cache)
    sv = {r: json.loads((f / 'version_scenario.json').read_bytes()) for r, f in folders.items()}
    dv = {r: json.loads((f / 'version_js_delta.json').read_bytes()) for r, f in folders.items()}
    for name, versions in (('cn_scenario_update.zip', sv), ('cn_js_delta.zip', dv)):
        if versions[SOURCE]['version'] == versions[PUBLIC]['version'] and snapshots[SOURCE][name]['digest'] != snapshots[PUBLIC][name]['digest']:
            raise ValueError('Same version with conflicting package identity: ' + name)
    if snapshots[SOURCE]['cn_js_update.zip']['digest'] != snapshots[PUBLIC]['cn_js_update.zip']['digest']:
        raise ValueError('Frozen JS baselines disagree; explicit rebase required')
    scene_repo = max(sv, key=lambda r: sv[r]['version'])
    delta_repo = max(dv, key=lambda r: dv[r]['version'])
    base_js = folders[SOURCE] / 'cn_js_update.zip'
    payload = prepared or work / 'payload'
    if prepared:
        report = json.loads((payload / 'resource-bundle-report.json').read_bytes())
        # Prepared bytes remain tied to their original source tree. Only code or
        # documentation may have advanced before promotion; no product drift.
        old = report['source_commit']
        drift = git(ROOT, 'diff', '--name-only', old, source_commit, '--', 'magica', 'madomagi', 'configures/js-delta-baseline.json').strip()
        if drift:
            raise ValueError('Prepared product tree is stale')
    else:
        cfg = json.loads((ROOT / 'configures/js-delta-baseline.json').read_bytes())
        subprocess.run(['git', '-C', str(ROOT), 'fetch', '--depth=1', 'origin', cfg['base_source_commit']], check=True)
        report = build(ROOT, source_commit, base_js, folders[scene_repo] / 'cn_scenario_update.zip',
                       folders[delta_repo] / 'cn_js_delta.zip', payload, max(v['version'] for v in sv.values()) + 1)
    if identity(payload / 'cn_scenario_update.zip') != report['scenario']:
        raise ValueError('Prepared scenario identity changed')
    if identity(payload / 'cn_js_delta.zip')['sha256'] != report['delta']['sha256']:
        raise ValueError('Prepared delta identity changed')
    report['layering'] = validate(base_js, payload / 'cn_scenario_update.zip', payload / 'cn_js_delta.zip')
    # The mirror can reject future overlap regressions from two small manifests,
    # rather than redownloading half a gigabyte on every scheduled check.
    import zipfile
    from resource_layers import files, sha, DELTA_MANIFEST
    manifest_path = payload / 'cn_scenario_update_manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    with zipfile.ZipFile(payload / 'cn_scenario_update.zip') as z:
        actual = files(z)
        if set(actual) != set(manifest['files']):
            raise ValueError('Scenario sidecar inventory mismatch')
        for name, item in actual.items():
            entry = manifest['files'][name]
            if item.file_size != entry['size'] or f'{item.CRC:08x}' != entry['crc32']:
                raise ValueError('Scenario sidecar entry mismatch: ' + name)
            entry['sha256'] = sha(z, name)
    manifest['zip_sha256'] = report['scenario']['sha256']
    save(manifest_path, manifest)
    with zipfile.ZipFile(payload / 'cn_js_delta.zip') as z:
        if json.loads(z.read(DELTA_MANIFEST)) != json.loads((payload / 'cn_js_delta_manifest.json').read_bytes()):
            raise ValueError('Delta sidecar differs from its internal manifest')
    chunks = {r: json.loads((f / 'manifest.json').read_bytes()) for r, f in folders.items()}
    for name in set(chunks[SOURCE]) | set(chunks[PUBLIC]):
        if name not in ('cn_scenario_update.zip', 'cn_js_delta.zip') and chunks[SOURCE].get(name) != chunks[PUBLIC].get(name):
            raise ValueError('Unrelated chunk metadata differs: ' + name)
    new_chunks = dict(chunks[scene_repo])
    for name in ('cn_scenario_update.zip', 'cn_js_delta.zip'):
        size = new_chunks.get(name, {}).get('chunk_size', 16 * 1024 * 1024)
        new_chunks[name] = chunk_identity(payload / name, size)
    save(payload / 'manifest.json', new_chunks)
    report.update(publication_code_commit=source_commit, publication='NOT_PUBLISHED')
    save(work / 'prepared-report.json', report)
    if not publish:
        print('PREPARED_NOT_PUBLISHED', str(payload), flush=True)
        return report
    if apis[0].json('git/ref/heads/main')['object']['sha'] != source_commit:
        raise ValueError('Source main advanced before publication')
    results = []
    for api in apis:
        result = publish_one(api, snapshots[api.repo], folders[api.repo], payload, work)
        results.append(result)
        save(work / 'publication-progress.json', {'results': results})
    report.update(publication='PUBLISHED_AND_ANONYMOUSLY_VERIFIED', publications=results)
    save(work / 'publication-report.json', report)
    print('COHERENT_RESOURCES_PUBLISHED', report['scenario_version'], report['layering'], flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--cache', type=Path)
    p.add_argument('--prepared', type=Path)
    p.add_argument('--publish', action='store_true')
    a = p.parse_args()
    run(a.work, a.cache, a.prepared, a.publish)
