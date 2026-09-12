"""Record the seven promoted Release fingerprints after successful publication."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

REPO = 'HiiragiNemu/magireco-cn-patch'
NAMES = ['cn_js_update.zip', 'cn_scenario_update.zip',
         'cn_js_update_manifest.json', 'cn_scenario_update_manifest.json',
         'manifest.json', 'version_js.json', 'version_scenario.json']
EXCLUDED = 'madomagi/resource/image_native/memoria/'


def record(previous, release, payload, source_commit):
    if previous.get('publication_hold'):
        raise ValueError('Publication is on hold')
    if release.get('tag_name') != 'latest':
        raise ValueError('Expected exact latest tag')
    assets = {a['name']: a for a in release['assets']}
    files = {}
    for name in NAMES:
        asset = assets[name]
        digest = asset.get('digest', '')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
            raise ValueError('Missing GitHub asset digest: ' + name)
        files[name] = {'bytes': asset['size'], 'sha256': digest[7:]}
        if name.endswith('.json'):
            b = (payload / name).read_bytes()
            if len(b) != asset['size'] or hashlib.sha256(b).hexdigest() != digest[7:]:
                raise ValueError('Metadata body mismatch: ' + name)
    for scope in ('js', 'scenario'):
        version = json.loads((payload / f'version_{scope}.json').read_bytes())
        manifest = json.loads((payload / f'cn_{scope}_update_manifest.json').read_bytes())
        if not (version['version'] == manifest['version']
                and version['size'] == manifest['zip_size'] == files[f'cn_{scope}_update.zip']['bytes']
                and version['md5'] == manifest['zip_md5']):
            raise ValueError('Version / ZIP / manifest mismatch: ' + scope)
        if any(n.startswith(EXCLUDED) for n in manifest['files']):
            raise ValueError('Memoria is excluded')
    if files == previous['files']:
        return previous
    if not re.fullmatch(r'[0-9a-f]{40}', source_commit):
        raise ValueError('Expected exact source commit')
    return dict(previous, files=files, source_commit=source_commit)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-commit', required=True)
    args = p.parse_args()
    release = json.loads(subprocess.check_output(['gh', 'api', f'repos/{REPO}/releases/tags/latest']))
    payload = Path('_finalized_metadata')
    payload.mkdir(exist_ok=True)
    command = ['gh', 'release', 'download', 'latest', '--repo', REPO, '--dir', str(payload), '--clobber']
    for name in NAMES:
        if name.endswith('.json'):
            command += ['--pattern', name]
    subprocess.run(command, check=True)
    path = Path('configures/finalized-localization-assets.json')
    previous = json.loads(path.read_bytes())
    result = record(previous, release, payload, args.source_commit)
    if result != previous:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('FINALIZED_SEVEN_FINGERPRINTS_RECORDED')
