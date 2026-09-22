#!/usr/bin/env python3
"""Overlay Git product changes onto the frozen JS archive, then build a cumulative small ZIP."""
import argparse, hashlib, importlib.util, json, shutil, subprocess, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('delta', ROOT/'tools/i18n-delta-package.py')
delta = importlib.util.module_from_spec(spec); spec.loader.exec_module(delta)

def product(name):
    if name.startswith(('magica/research/', 'magica/i18n_audit/')): return False
    return name.startswith('magica/') or name.startswith('madomagi/resource/image_native/') or name in (
        'madomagi/engine_i18n.tsv', 'madomagi/repair_manifest.json')

def build(repo, base, config, out, previous=None, ref='HEAD'):
    repo, base, out = map(Path, (repo, base, out)); out.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(Path(config).read_text(encoding='utf8'))
    if delta.digest(base) != cfg['base_js_sha256']: raise ValueError('Frozen JS archive changed')
    def git(*args): return subprocess.check_output(['git','-C',str(repo),*args])
    source = git('rev-parse', ref).decode().strip()
    changes = [n.decode('utf8') for n in git('diff','--name-only','--no-renames','-z',cfg['base_source_commit'],source).split(b'\0') if n]
    changes = sorted(n for n in changes if product(n))
    blobs = {}
    for name in changes:
        # Removal is not an overwrite. Do not silently erase or leave a stale layer.
        blobs[name] = git('show', source+':'+name)
    target = out/'target.zip'
    with zipfile.ZipFile(base) as bz, zipfile.ZipFile(target,'w') as tz:
        known = set(delta.members(bz))
        for info in bz.infolist():
            tz.writestr(info, blobs.get(info.filename, bz.read(info.filename)))
        for name in sorted(set(blobs)-known): delta.put(tz,name,blobs[name])
    previous_version = 0
    if previous:
        with zipfile.ZipFile(previous) as z: previous_version = json.loads(z.read(delta.MANIFEST))['version']
    result = delta.build(base,target,out/'cn_js_delta.zip',cfg['base_js_version'],previous_version+1,previous)
    if previous:
        with zipfile.ZipFile(previous) as pz, zipfile.ZipFile(out/'cn_js_delta.zip') as nz:
            old = json.loads(pz.read(delta.MANIFEST)); new = json.loads(nz.read(delta.MANIFEST))
        if old['entries'] == new['entries']:
            shutil.copyfile(previous,out/'cn_js_delta.zip')
            meta = dict(version=old['version'],size=Path(previous).stat().st_size,md5=delta.digest(previous,'md5'),
                        base_js_version=cfg['base_js_version'],base_js_sha256=cfg['base_js_sha256'])
            (out/'version_js_delta.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
            (out/'cn_js_delta_manifest.json').write_text(json.dumps(old,indent=2)+'\n',encoding='utf8')
            result.update(version=old['version'],sha256=delta.digest(previous),delta_bytes=Path(previous).stat().st_size,unchanged=True)
    result.update(source_commit=source,changed_product_paths=changes)
    (out/'build-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=ROOT)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--config',type=Path,default=ROOT/'configures/js-delta-baseline.json')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--previous',type=Path)
    a=p.parse_args(); print(json.dumps(build(a.repo,a.base,a.config,a.out,a.previous),ensure_ascii=False,indent=2))
