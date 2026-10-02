"""Read-only ADB hash audit of game resource files; never changes device access.

Requires an explicitly selected device whose existing ADB access can read the
application files. It does not root, reinstall, clear data, or write device files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from resource_layers import files, sha

ROOT = '/data/user/0/io.kamihama.totentanz/'


def audit(serial, scenario, delta, output):
    def adb(*args):
        return subprocess.check_output(['adb', '-s', serial, *args], timeout=45)
    def versions():
        raw = adb('exec-out', 'cat', ROOT + 'shared_prefs/MagiaCN.xml')
        tree = ET.fromstring(raw)
        return {n.attrib['name']: int(n.attrib['value']) for n in tree.findall('int')
                if n.attrib.get('name') in ('scenario_version', 'js_version', 'js_delta_version')}
    before = versions()
    expected = {}
    for path in (scenario, delta):
        with zipfile.ZipFile(path) as z:
            for name in files(z):
                if not re.fullmatch(r'[A-Za-z0-9_./-]+', name):
                    raise ValueError('Resource path is not safe for an ADB shell argument')
                digest = sha(z, name)
                if name in expected and expected[name] != digest:
                    raise ValueError('Audit input packages conflict: ' + name)
                expected[name] = digest
    actual = {}
    names = sorted(expected)
    for start in range(0, len(names), 64):
        group = names[start:start+64]
        text = adb('shell', 'sha256sum', *[ROOT + 'files/' + n for n in group]).decode('utf8')
        for line in text.splitlines():
            digest, path = line.split(None, 1)
            name = path.strip().removeprefix(ROOT + 'files/')
            if name not in expected or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('Unexpected resource hash response')
            actual[name] = digest
        if start % 1024 == 0:
            print('RESOURCE_HASH_AUDIT', min(start+64, len(names)), '/', len(names), flush=True)
    after = versions()
    if before != after:
        raise ValueError('Installation changed while being audited; repeat after update finishes')
    mismatches = [{'path': n, 'expected': expected[n], 'actual': actual.get(n)} for n in names if expected[n] != actual.get(n)]
    cache = adb('shell', 'sha256sum', ROOT + 'files/.cn_js_delta_cache.zip').decode().split()[0]
    delta_hash = hashlib.sha256(Path(delta).read_bytes()).hexdigest()
    report = {'serial': serial, 'versions_before': before, 'versions_after': after,
              'files_verified': len(actual), 'files_expected': len(expected),
              'mismatches': mismatches, 'cached_delta_sha256': cache,
              'expected_delta_sha256': delta_hash, 'cached_delta_matches': cache == delta_hash,
              'read_only': True}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='mismatches'}, indent=2))
    if mismatches or cache != delta_hash:
        raise SystemExit('Installed resource mismatch count: ' + str(len(mismatches)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial', required=True)
    p.add_argument('--scenario', type=Path, required=True)
    p.add_argument('--delta', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    audit(a.serial, a.scenario, a.delta, a.out)
