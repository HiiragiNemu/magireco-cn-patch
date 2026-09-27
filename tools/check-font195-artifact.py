#!/usr/bin/env python3
"""Check the shipped native aliases, not merely the presence of unused TTFs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROUND_SHA = 'a6adbd53d4d061c54a210194d800fafd989f656a6bd5334843fc069c08ed8f48'
SANS_SHA = 'fa0710a050e8c0c73623d482be4d25a4aed23a8d2fb6056fad79fd98de22289e'
ROUND_NAMES = ('TTDaYuanGB3.ttf', 'MTF4a5kp.ttf', 'mbm_20160902.ttf')
FORBIDDEN = {
    '1fe1fdc28cc7347e26099bf2fb54b85370617acd91efc6e63903cf3c33a62541',
    'c69dea79d5b33864bbda85645641d5208790f8c394a291992e898a3753dd71d3',
    '51383ac04bf0835445a0de382c07e6467f43991c6a51cf13a4327cad51f58b03',
}

def verify(apk: Path) -> dict:
    reviewed = ROOT / '.reviewed-fonts/magica'
    manifest = json.loads((reviewed/'font-licenses/font194-manifest.json').read_text(encoding='utf8'))
    assert manifest['version'] == '1.0.194', 'Unexpected verified font generation'
    round_data = (reviewed/'fonts/TTDaYuanGB3.ttf').read_bytes()
    assert hashlib.sha256(round_data).hexdigest() == ROUND_SHA
    record = dict(version='1.0.195', font_source_version='1.0.194', fonts={},
                  native_round_aliases=list(ROUND_NAMES), font_routing_changed=False,
                  download_priority_changed=False, migration_release='1.0.196',
                  device_visual_acceptance='pending maintainer')
    with zipfile.ZipFile(apk) as z, tempfile.TemporaryDirectory() as tmp:
        names = z.namelist()
        assert len(names) == len(set(names)), 'Duplicate APK entries'
        for name in ROUND_NAMES:
            assert z.read('assets/fonts/'+name) == round_data, 'Native round alias NOT replaced: '+name
        assert hashlib.sha256(z.read('assets/fonts/TTZhiHeiGB3-W4.ttf')).hexdigest() == SANS_SHA
        root = Path(tmp)
        for name in names:
            if name.startswith('assets/fonts/') and not name.endswith('/'):
                assert len(Path(name).parts) == 3, 'Unexpected font subdirectory'
                p = root/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(z.read(name))
            if name.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                data = z.read(name)
                h = hashlib.sha256(data).hexdigest()
                assert h not in FORBIDDEN, 'Old font bytes remain: '+name
                for word in ('Tensentype JiaLiDaYuan', 'Tensentype ZhiHei', '腾祥嘉丽大圆', '腾祥智黑'):
                    assert word.encode('utf-16-be') not in data and word.encode('utf8') not in data, name
                record['fonts'][name] = dict(size=len(data), sha256=h)
        for name, row in manifest['fonts'].items():
            data = z.read('assets/fonts/'+name)
            assert len(data) == row['size'] and hashlib.sha256(data).hexdigest() == row['sha256'], name
        licenses = [p for p in (reviewed/'font-licenses').iterdir() if p.is_file()]
        assert len(licenses) >= 8
        for p in licenses:
            assert z.read('assets/font-licenses/'+p.name) == p.read_bytes(), 'License mismatch: '+p.name
        subprocess.run([sys.executable, str(ROOT/'tools/check-fonts.py'), '--tree', str(root)],
                       check=True, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        record['license_files_verified'] = len(licenses)
        record['required_characters_per_round_alias'] = len(manifest['fonts']['TTDaYuanGB3.ttf']['required_coverage'])
        record['all_registered_fonts_passed'] = True
    record['apk_size'] = apk.stat().st_size
    record['apk_sha256'] = hashlib.sha256(apk.read_bytes()).hexdigest()
    return record

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    args = parser.parse_args()
    report = verify(args.apk)
    output = ROOT/'.build/font195-apk-verification.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print('PASS_FINAL_195_NATIVE_ROUND_ALIASES', json.dumps(report, ensure_ascii=False))
