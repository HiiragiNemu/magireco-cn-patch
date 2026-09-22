#!/usr/bin/env python3
"""Promote the cumulative supplement only; the frozen full JS asset is never uploaded."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path

NAMES=['cn_js_delta.zip','cn_js_delta_manifest.json','version_js_delta.json']
p=argparse.ArgumentParser();p.add_argument('--payload',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);a=p.parse_args()
repo=os.environ.get('GITHUB_REPOSITORY','HiiragiNemu/magireco-cn-patch')
if repo!='HiiragiNemu/magireco-cn-patch': raise SystemExit('Unexpected release repository')
log=[]
def run(cmd):
    v=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    log.append(dict(command=list(map(str,cmd)),exit=v.returncode,stdout=v.stdout,stderr=v.stderr))
    (a.payload/'publication-verification.json').write_text(json.dumps(log,indent=2),encoding='utf8')
    if v.returncode: raise RuntimeError(v.stderr)
    return v.stdout
def verify(folder):
    m=json.loads((folder/'version_js_delta.json').read_text());b=(folder/'cn_js_delta.zip').read_bytes()
    if len(b)!=m['size'] or hashlib.md5(b).hexdigest()!=m['md5']: raise ValueError('Supplement identity mismatch')
verify(a.payload)
try:
    for name in NAMES: run(['gh','release','upload','latest',a.payload/name,'--clobber','--repo',repo])
    with tempfile.TemporaryDirectory() as tmp:
        for name in NAMES:
            run(['gh','release','download','latest','--repo',repo,'--pattern',name,'--dir',tmp])
            if (Path(tmp)/name).read_bytes()!=(a.payload/name).read_bytes(): raise ValueError('Public asset mismatch: '+name)
        verify(Path(tmp))
except Exception as original:
    # The first publication may fail before all three assets exist. Restore every
    # prior object, and only delete new objects actually present on the release.
    current=json.loads(run(['gh','release','view','latest','--repo',repo,'--json','assets']))
    present={x['name'] for x in current['assets']}
    errors=[]
    for name in NAMES:
        try:
            if (a.previous/name).is_file(): run(['gh','release','upload','latest',a.previous/name,'--clobber','--repo',repo])
            elif name in present: run(['gh','release','delete-asset','latest',name,'--yes','--repo',repo])
        except Exception as e: errors.append(str(e))
    if errors: raise RuntimeError('Publication failed; rollback needs attention: '+repr(errors)) from original
    raise
print('PASS cumulative ZIP and last-published version identity downloaded and verified; full JS untouched')
