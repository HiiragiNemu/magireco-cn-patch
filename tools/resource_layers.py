"""Validate final cross-package content, not independent version counters.

Scenario JSON is authoritative in the full scenario archive. A cumulative
last-writer overlay may carry the same paths for old clients, but the bytes must
be identical. This also makes a cached overlay replay after reinstall safe.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile

SCENARIO_PREFIX = 'madomagi/resource/scenario/json/'
DELTA_MANIFEST = 'magica/.cn_js_delta.json'


def files(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    result = {}
    for item in archive.infolist():
        if item.is_dir():
            continue
        name = item.filename
        if (name != item.orig_filename or '\\' in name or ':' in name
                or any(c in name for c in ('\0', '\r', '\n'))
                or any(p in ('', '.', '..') for p in name.split('/'))
                or not name.startswith(('madomagi/', 'magica/'))
                or (item.external_attr >> 16) & 0o170000 == 0o120000
                or name in result):
            raise ValueError('Invalid or duplicate product path: ' + name)
        result[name] = item
    return result


def sha(archive: zipfile.ZipFile, name: str) -> str:
    h = hashlib.sha256()
    with archive.open(name) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate(full_js: Path, scenario: Path, delta: Path) -> dict:
    with zipfile.ZipFile(full_js) as j, zipfile.ZipFile(scenario) as s, zipfile.ZipFile(delta) as d:
        jm, sm, dm = files(j), files(s), files(d)
        if not sm or any(not n.startswith(SCENARIO_PREFIX) for n in sm):
            raise ValueError('Scenario inventory has an unexpected owner')
        m = json.loads(d.read(DELTA_MANIFEST))
        if m.get('schema') != 'magireco-cn-js-delta/v1':
            raise ValueError('Unexpected supplement schema')
        entries = m.get('entries', [])
        declared = {x['path']: x for x in entries}
        if len(declared) != len(entries) or set(dm) != set(declared) | {DELTA_MANIFEST}:
            raise ValueError('Supplement inventory is not exact')
        for name, item in declared.items():
            if dm[name].file_size != item['size'] or sha(d, name) != item['sha256']:
                raise ValueError('Supplement entry identity mismatch: ' + name)
        if hashlib.sha256(Path(full_js).read_bytes()).hexdigest() != m['base_js_sha256']:
            raise ValueError('Supplement does not match frozen JS archive')
        conflicts = []
        overlapping = []
        for label, archive, names in (('js', j, jm), ('delta', d, dm)):
            for name in sorted(n for n in names if n.startswith(SCENARIO_PREFIX)):
                overlapping.append(name)
                if name not in sm or sha(s, name) != sha(archive, name):
                    conflicts.append({'layer': label, 'path': name})
        if conflicts:
            raise ValueError('Last-writer scenario conflict: ' + json.dumps(conflicts, ensure_ascii=False))
        return {'scenario_files': len(sm), 'js_files': len(jm), 'delta_files': len(dm),
                'scenario_overlaps_checked': len(overlapping), 'conflicts': 0,
                'install_order': ['scenario', 'js', 'delta'],
                'cached_delta_replay_safe_for_scenario': True}


def validate_manifest_layers(metadata: dict, assets: dict, authority: dict | None = None) -> int:
    """Cheap publication guard, with manifests bound to the ZIP descriptors."""
    delta = metadata.get('cn_js_delta_manifest.json', {})
    paths = [e for e in delta.get('entries', []) if e['path'].startswith(SCENARIO_PREFIX)]
    if not paths:
        return 0
    scene = metadata.get('cn_scenario_update_manifest.json', {})
    if (scene.get('zip_sha256') != assets['cn_scenario_update.zip']['digest'][7:]
            or scene.get('zip_size') != assets['cn_scenario_update.zip']['size']
            or scene.get('version') != metadata['version_scenario.json']['version']
            or delta.get('version') != metadata['version_js_delta.json']['version']):
        raise ValueError('Scenario/delta manifest identity is missing or inconsistent')
    known = scene.get('files', {})
    if delta.get('source_authority', {}).get('mode') == 'delta_only_cumulative':
        if authority is None:
            raise ValueError('Current Git source authority is required for cumulative publication')
        known = authority
    for entry in paths:
        other = known.get(entry['path'], {})
        if other.get('size') != entry['size'] or other.get('sha256') != entry['sha256']:
            raise ValueError('Last-writer scenario conflict: ' + entry['path'])
    return len(paths)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--js', type=Path, required=True)
    p.add_argument('--scenario', type=Path, required=True)
    p.add_argument('--delta', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(validate(a.js, a.scenario, a.delta), indent=2))
