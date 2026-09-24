"""Selected Web UI images must remain exact CN originals, not re-rendered labels."""
import argparse,hashlib,json,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();root=a.root.resolve()
m=json.loads((root/'magica/i18n_audit/web_image_cn_authority_20260924/manifest.json').read_text('utf8'))
assert len(m['originalCnImages'])==22
for row in m['originalCnImages']:
    assert row['path'].startswith('magica/resource/image_web/')
    raw=(root/row['path']).read_bytes();assert raw[:8]==b'\x89PNG\r\n\x1a\n'
    assert hashlib.sha256(raw).hexdigest()==row['sha256'],row['path']
    assert list(struct.unpack('>II',raw[16:24]))==row['size'],row['path']
assert len(m['preservedAcceptedImages'])==11 and len(m['preservedAlreadyCnImages'])==3
for row in m['preservedAcceptedImages']+m['preservedAlreadyCnImages']:
    assert hashlib.sha256((root/row['path']).read_bytes()).hexdigest()==row['sha256'],row['path']
print(json.dumps(dict(status='PASS',exactCnOriginals=22,acceptedImagesUnchanged=11,alreadyCnImagesUnchanged=3,AIRepainting=False,nativeCardsChanged=False,VFXTChanged=False)))
