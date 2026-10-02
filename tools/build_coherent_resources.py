"""Build scenario and its cumulative compatibility layer from one pinned tree.

Unchanged archive entries are reused only when their Git blob matches the source.
This preserves earlier supplemental corrections without overwriting later story
work. No story text is rewritten or inferred by this builder.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time
import zipfile
from resource_layers import SCENARIO_PREFIX, files, validate

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cumulative', ROOT / 'tools/build-cumulative-js-delta.py')
cumulative = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cumulative)


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(repo), *args])


def blob(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def identity(path: Path) -> dict:
    return {'size': path.stat().st_size, 'sha256': cumulative.delta.digest(path),
            'md5': cumulative.delta.digest(path, 'md5')}


def build(repo: Path, ref: str, base_js: Path, previous_scenario: Path,
          previous_delta: Path, out: Path, scenario_version: int) -> dict:
    repo, base_js, previous_scenario, previous_delta, out = map(
        Path, (repo, base_js, previous_scenario, previous_delta, out))
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output must be an empty staging directory')
    out.mkdir(parents=True, exist_ok=True)
    source = git(repo, 'rev-parse', ref).decode().strip()
    tree = {}
    for item in git(repo, 'ls-tree', '-rz', source, '--', SCENARIO_PREFIX).split(b'\0'):
        if not item:
            continue
        attr, name = item.split(b'\t', 1)
        mode, kind, digest = attr.decode().split()
        if mode != '100644' or kind != 'blob':
            raise ValueError('Non-regular scenario source')
        tree[name.decode('utf8')] = digest
    if not tree:
        raise ValueError('Empty scenario source tree')
    previous_version_path = previous_scenario.with_name('version_scenario.json')
    if previous_version_path.exists():
        previous_version = json.loads(previous_version_path.read_bytes())['version']
        if scenario_version <= previous_version:
            raise ValueError('Scenario version must increase')
    changed, recovered, from_git = [], [], []
    scenario_path = out / 'cn_scenario_update.zip'
    with zipfile.ZipFile(previous_scenario) as old, zipfile.ZipFile(previous_delta) as delta:
        old_files, delta_files = files(old), files(delta)
        if set(old_files) - set(tree):
            raise ValueError('Source deletion needs an explicit reviewed migration')
        with zipfile.ZipFile(scenario_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as new:
            for name in sorted(tree):
                raw = old.read(name) if name in old_files else None
                if raw is None or blob(raw) != tree[name]:
                    changed.append(name)
                    alternate = delta.read(name) if name in delta_files else None
                    if alternate is not None and blob(alternate) == tree[name]:
                        raw = alternate
                        recovered.append(name)
                    else:
                        raw = git(repo, 'show', source + ':' + name)
                        from_git.append(name)
                if blob(raw) != tree[name]:
                    raise ValueError('Scenario source identity mismatch: ' + name)
                cumulative.delta.put(new, name, raw)
    if not changed and previous_version_path.exists():
        shutil.copyfile(previous_scenario, scenario_path)
        scenario_version = previous_version
    with zipfile.ZipFile(scenario_path) as z:
        if z.testzip() is not None:
            raise ValueError('Scenario CRC verification failed')
        if set(files(z)) != set(tree):
            raise ValueError('Scenario inventory changed')
        for name, digest in tree.items():
            if blob(z.read(name)) != digest:
                raise ValueError('Final scenario source mismatch: ' + name)
        sid = identity(scenario_path)
        manifest = {'schema': 1, 'package': 'cn_scenario_update', 'version': scenario_version,
                    'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'zip_size': sid['size'], 'zip_md5': sid['md5'], 'file_count': len(tree),
                    'total_size': sum(i.file_size for i in files(z).values()),
                    'cleanup_prefixes': [SCENARIO_PREFIX],
                    'files': {n: {'size': i.file_size, 'crc32': f'{i.CRC:08x}'} for n, i in files(z).items()}}
    previous_manifest_path = previous_scenario.with_name('cn_scenario_update_manifest.json')
    if not changed and previous_manifest_path.exists():
        prior_manifest = json.loads(previous_manifest_path.read_bytes())
        if (prior_manifest.get('zip_size') == sid['size'] and prior_manifest.get('zip_md5') == sid['md5']
                and prior_manifest.get('version') == scenario_version
                and set(prior_manifest.get('files', {})) == set(tree)):
            manifest = prior_manifest
    save(out / 'cn_scenario_update_manifest.json', manifest)
    save(out / 'version_scenario.json', {'version': scenario_version, 'size': sid['size'], 'md5': sid['md5']})
    delta_result = cumulative.build(repo, base_js, repo / 'configures/js-delta-baseline.json',
                                    out / 'delta-build', previous_delta, source, reuse=[scenario_path])
    for name in ('cn_js_delta.zip', 'cn_js_delta_manifest.json', 'version_js_delta.json'):
        shutil.copyfile(out / 'delta-build' / name, out / name)
    layers = validate(base_js, scenario_path, out / 'cn_js_delta.zip')
    with zipfile.ZipFile(previous_delta) as old, zipfile.ZipFile(out / 'cn_js_delta.zip') as new:
        om, nm = files(old), files(new)
        delta_changed = sorted(n for n in set(om) | set(nm)
                               if n not in om or n not in nm or old.read(n) != new.read(n))
    report = {'schema': 1, 'source_commit': source, 'scenario_version': scenario_version,
              'scenario': sid, 'scenario_source_files': len(tree), 'scenario_changed_paths': changed,
              'earlier_supplement_paths_folded': recovered, 'new_source_paths_read': from_git,
              'delta': delta_result, 'delta_changed_paths': delta_changed, 'layering': layers,
              'full_js_unchanged': True, 'publication': 'NOT_PUBLISHED'}
    save(out / 'resource-bundle-report.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=ROOT)
    p.add_argument('--ref', default='HEAD')
    p.add_argument('--js', type=Path, required=True)
    p.add_argument('--scenario', type=Path, required=True)
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--scenario-version', type=int, required=True)
    a = p.parse_args()
    result = build(a.repo, a.ref, a.js, a.scenario, a.delta, a.out, a.scenario_version)
    print(json.dumps({k: v for k, v in result.items() if k not in
                      ('scenario_changed_paths', 'earlier_supplement_paths_folded', 'delta')}, indent=2))
