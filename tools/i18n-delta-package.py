#!/usr/bin/env python3
"""Build a cumulative JS supplement against an unchanged published full JS package.

The target is a complete desired JS ZIP. Previous touched paths remain in the
supplement even when reverted to baseline, so clients skipping versions converge.
Removal of an added file needs an installer delete transaction and is rejected.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

MANIFEST = 'magica/.cn_js_delta.json'
SCHEMA = 'magireco-cn-js-delta/v1'

def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def members(z):
    result = {}
    for info in z.infolist():
        if info.is_dir():
            continue
        name = info.filename
        p = PurePosixPath(name)
        if (info.orig_filename != name or p.is_absolute() or '\\' in name or ':' in name
                or any(s in ('', '.', '..') for s in name.split('/'))
                or p.parts[0] not in ('magica', 'madomagi')
                or (info.external_attr >> 16) & 0o170000 == 0o120000):
            raise ValueError('Invalid product member: ' + name)
        if name in result:
            raise ValueError('Duplicate product member: ' + name)
        result[name] = info
    return result

def bytes_hash(z, name):
    h = hashlib.sha256()
    with z.open(name) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def put(z, name, data):
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    z.writestr(info, data, compresslevel=9)

def build(base, target, out, base_version, version, previous=None):
    base, target, out = map(Path, (base, target, out))
    if base_version <= 0 or version <= 0:
        raise ValueError('Versions must be positive')
    if out.resolve() in {p.resolve() for p in (base, target, *([Path(previous)] if previous else []))}:
        raise ValueError('Output must not overwrite an input')
    base_sha = digest(base)
    touched = set()
    with zipfile.ZipFile(base) as bz, zipfile.ZipFile(target) as tz:
        bm, tm = members(bz), members(tz)
        if MANIFEST in bm or MANIFEST in tm:
            raise ValueError('Full baseline and target must not contain delta metadata')
        if previous:
            with zipfile.ZipFile(previous) as pz:
                pm = members(pz)
                meta = json.loads(pz.read(MANIFEST))
                if (meta.get('schema') != SCHEMA or meta.get('base_js_version') != base_version
                        or meta.get('base_js_sha256') != base_sha):
                    raise ValueError('Previous supplement belongs to a different baseline')
                if meta['version'] >= version:
                    raise ValueError('Version must exceed previous supplement')
                declared = {row['path']: row for row in meta['entries']}
                if len(declared) != len(meta['entries']) or set(pm) != set(declared) | {MANIFEST}:
                    raise ValueError('Previous supplement inventory mismatch')
                for name, row in declared.items():
                    if pm[name].file_size != row['size'] or bytes_hash(pz, name) != row['sha256']:
                        raise ValueError('Previous supplement content mismatch: ' + name)
                touched.update(declared)
        missing = (set(bm) | touched) - set(tm)
        if missing:
            raise ValueError('Deletion requires installer support: ' + ', '.join(sorted(missing)))
        for name, info in tm.items():
            if name not in bm or info.file_size != bm[name].file_size or bytes_hash(tz, name) != bytes_hash(bz, name):
                touched.add(name)
        entries = [dict(path=n, size=tm[n].file_size, sha256=bytes_hash(tz, n)) for n in sorted(touched)]
        meta = dict(schema=SCHEMA, version=version, base_js_version=base_version,
                    base_js_sha256=base_sha, target_js_sha256=digest(target), entries=entries)
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, 'w') as dz:
            for row in entries:
                put(dz, row['path'], tz.read(row['path']))
            put(dz, MANIFEST, json.dumps(meta, ensure_ascii=False, indent=2).encode('utf-8'))
    # Reopen final package and verify every carried file, not only its archive hash.
    with zipfile.ZipFile(out) as dz:
        if dz.testzip() is not None:
            raise ValueError('Delta ZIP CRC check failed')
        if set(members(dz)) != touched | {MANIFEST}:
            raise ValueError('Delta output inventory mismatch')
        for row in entries:
            if bytes_hash(dz, row['path']) != row['sha256']:
                raise ValueError('Delta output content mismatch')
    version_meta = dict(version=version, size=out.stat().st_size, md5=digest(out, 'md5'),
                        base_js_version=base_version, base_js_sha256=base_sha)
    out.with_name('version_js_delta.json').write_text(json.dumps(version_meta, indent=2) + '\n', encoding='utf-8')
    out.with_name('cn_js_delta_manifest.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return dict(files=len(entries), delta_bytes=out.stat().st_size, target_bytes=target.stat().st_size,
                base_js_version=base_version, version=version, sha256=digest(out))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'target', 'out'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--previous', type=Path)
    p.add_argument('--base-version', type=int, required=True)
    p.add_argument('--version', type=int, required=True)
    a = p.parse_args()
    print(json.dumps(build(a.base, a.target, a.out, a.base_version, a.version, a.previous), indent=2))

if __name__ == '__main__':
    main()
