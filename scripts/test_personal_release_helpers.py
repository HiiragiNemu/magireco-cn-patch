import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from reuse_unchanged_package import reuse, content_digest
from refresh_finalized_record import record, NAMES


class Helpers(unittest.TestCase):
    def test_git_line_endings_only_for_utf8_text(self):
        self.assertEqual(content_digest('a.json', b'{\r\n}\r\n'),content_digest('a.json', b'{\n}\n'))
        self.assertNotEqual(content_digest('a.png', b'a\r\n'),content_digest('a.png', b'a\n'))
        self.assertNotEqual(content_digest('a.json', b'{"text":"a"}'),content_digest('a.json', b'{"text":"b"}'))

    def test_reuse_ignores_zip_timestamp_but_not_product_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td)/'candidate.zip', Path(td)/'baseline.zip'
            for p, year in [(a, 2026), (b, 2025)]:
                with zipfile.ZipFile(p, 'w') as z:
                    z.writestr(zipfile.ZipInfo('a.json', (year,1,1,0,0,0)), b'{}')
            self.assertNotEqual(a.read_bytes(), b.read_bytes())
            self.assertTrue(reuse(a,b)); self.assertEqual(a.read_bytes(),b.read_bytes())
            with zipfile.ZipFile(a,'w') as z: z.writestr('a.json',b'{"new":true}')
            self.assertFalse(reuse(a,b))

    def test_source_bound_record_and_rejection_cases(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            objects = {'manifest.json': {}}
            for scope in ['js','scenario']:
                objects[f'version_{scope}.json'] = dict(version=1,size=7,md5='a'*32)
                objects[f'cn_{scope}_update_manifest.json'] = dict(version=1,zip_size=7,zip_md5='a'*32,files={'test.json':{}})
            release = dict(tag_name='latest',assets=[])
            for name in NAMES:
                body = json.dumps(objects[name]).encode() if name.endswith('.json') else b'fixture'
                (root/name).write_bytes(body)
                release['assets'].append(dict(name=name,size=len(body),digest='sha256:'+hashlib.sha256(body).hexdigest()))
            previous = dict(files={},publication_hold=False)
            new = record(previous,release,root,'a'*40)
            self.assertEqual(set(new['files']),set(NAMES))
            self.assertEqual(record(new,release,root,'b'*40),new)
            with self.assertRaises(ValueError): record(dict(previous,publication_hold=True),release,root,'a'*40)
            with self.assertRaises(ValueError): record(previous,dict(release,tag_name='other'),root,'a'*40)


if __name__ == '__main__': unittest.main(verbosity=2)
