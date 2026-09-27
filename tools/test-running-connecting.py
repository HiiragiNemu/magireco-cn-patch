"""Regression: Web Connecting stays separate from native running Loading.

The historical filename is retained as the existing workflow entry point.
"""
import argparse, hashlib, json, struct
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
a = p.parse_args()
path = 'magica/resource/image_web/common/global/connecting.png'
b = (a.root / path).read_bytes()
assert hashlib.sha256(b).hexdigest() == '4bb87d745a258efa579b7e42cc0f536b537ebdd27b41c5558048482117c71120', 'Web Connecting was replaced by running Loading'
assert b[:8] == b'\x89PNG\r\n\x1a\n'
assert struct.unpack('>II', b[16:24]) == (334, 54)
n = 8
chunks = []
while n < len(b):
    size = struct.unpack('>I', b[n:n+4])[0]
    chunks.append(b[n+4:n+8])
    n += size + 12
assert n == len(b) and chunks[-1] == b'IEND'
assert not set(chunks) & {b'acTL', b'fcTL', b'fdAT'}, 'Web Connecting must not use the running APNG'
m = json.loads((a.root / 'magica/i18n_audit/web_image_cn_authority_20260924/manifest.json').read_text('utf8'))
assert m['userRequestedRestorations'] == []
assert m['loadingSeparation']['nativeLoadingPreserved'] == 'assets/package/loading/'
assert next(x for x in m['originalCnImages'] if x['path'] == path)['sha256'] == hashlib.sha256(b).hexdigest()
print('PASS exact original Web Connecting; native running Loading remains a separate resource path')
