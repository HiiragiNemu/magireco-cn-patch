"""The accepted local gacha fix must be present in distributable product paths."""
import argparse,hashlib,json,gzip,plistlib,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--manifest',type=Path);a=p.parse_args()
m=json.loads((a.manifest or a.root/'magica/i18n_audit/gacha_public_repair_20260926/manifest.json').read_text('utf8'))
assert len(m['files'])==45
errors=[]
for row in m['files']:
    f=a.root/row['path']
    if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest()!=row['sha256']: errors.append(row['path'])
for name in errors: print('FAIL '+name)
assert not errors, f'{len(errors)} gacha resources missing or stale'
d=a.root/'madomagi/resource/image_native/scene/gacha_v2'
scene=json.loads(gzip.decompress((d/'Gacha.ExportJson.gz').read_bytes()))
# These two result atlases are absent from both the published static archive and
# the accepted device snapshot; they are not part of this static scene repair.
result_atlases={'Gacha_item00.png','Gacha_item01.png'}
for name in scene['config_file_path']+scene['config_png_path']:
    assert name in result_atlases or (d/name).is_file(),name
for f in d.glob('*.plist'): plistlib.loads(f.read_bytes())
for f in d.glob('*.vfxj'):
    v=json.loads(f.read_bytes())
    for group in v['spark_gear_data']:
        for effect in group['ef_list']: assert (d/effect['name']).is_file(),effect['name']
print('PASS 45 accepted gacha resources, static animation/atlas/effect dependencies; 2 result atlas names excluded')
