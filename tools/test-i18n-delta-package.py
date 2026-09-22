#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('delta', ROOT / 'i18n-delta-package.py')
delta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delta)

class DeltaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
    def zip(self, name, content):
        p = self.root / name
        with zipfile.ZipFile(p, 'w') as z:
            for k, v in content.items():
                delta.put(z, k, v.encode())
        return p
    def read(self, p):
        with zipfile.ZipFile(p) as z:
            return {n: z.read(n) for n in z.namelist() if n != delta.MANIFEST}
    def test_cumulative_skip_revert_and_unchanged_assets(self):
        base = self.zip('base.zip', {'magica/ui.js':'original', 'madomagi/font.ttf':'stable-font', 'madomagi/engine_i18n.tsv':'old'})
        first = self.zip('target1.zip', {'magica/ui.js':'first', 'madomagi/font.ttf':'stable-font', 'madomagi/engine_i18n.tsv':'old', 'magica/new.js':'added'})
        one = self.root/'d1.zip'; delta.build(base, first, one, 102, 1)
        second = self.zip('target2.zip', {'magica/ui.js':'original', 'madomagi/font.ttf':'stable-font', 'madomagi/engine_i18n.tsv':'fixed', 'magica/new.js':'added'})
        two = self.root/'d2.zip'; delta.build(base, second, two, 102, 2, one)
        self.assertNotIn('madomagi/font.ttf', self.read(two))
        self.assertEqual(self.read(two)['magica/ui.js'], b'original')
        for installed in (self.read(base), self.read(first)):
            installed.update(self.read(two)); self.assertEqual(installed, self.read(second))
        duplicate=self.root/'repeat.zip'; delta.build(base, second, duplicate, 102, 2, one)
        self.assertEqual(delta.digest(two),delta.digest(duplicate))
    def test_reject_other_baseline_version_and_deletion(self):
        base=self.zip('base.zip', {'magica/ui.js':'a'});target=self.zip('target.zip', {'magica/ui.js':'b','magica/new.js':'new'})
        one=self.root/'d1.zip';delta.build(base,target,one,102,1)
        for args in [(base,base,102,2),(base,target,103,2),(base,target,102,1)]:
            with self.assertRaises(ValueError):delta.build(args[0],args[1],self.root/'bad.zip',args[2],args[3],one)
        changed=self.zip('other.zip',{'magica/ui.js':'other'})
        with self.assertRaises(ValueError):delta.build(changed,target,self.root/'bad.zip',102,2,one)
    def test_paths_and_duplicate_members(self):
        base=self.zip('base.zip',{'magica/a':'x'})
        for name in ['../evil','/magica/a','magica/../a','C:/magica/a','magica\\a','private/a']:
            target=self.root/'bad.zip'
            with zipfile.ZipFile(target,'w') as z:
                info=zipfile.ZipInfo('magica/placeholder');info.filename=name;z.writestr(info,b'x')
            with self.subTest(name=name):
                with self.assertRaises(ValueError):delta.build(base,target,self.root/'out.zip',102,1)
        with zipfile.ZipFile(self.root/'duplicate.zip','w') as z:
            delta.put(z,'magica/a',b'a');delta.put(z,'magica/a',b'b')
        with self.assertRaises(ValueError):delta.build(base,self.root/'duplicate.zip',self.root/'out.zip',102,1)
    def test_no_changes_needs_only_manifest(self):
        base=self.zip('base.zip',{'magica/a':'x'});out=self.root/'same.zip'
        self.assertEqual(delta.build(base,base,out,102,1)['files'],0)
        self.assertEqual(self.read(out),{})

if __name__=='__main__':unittest.main(verbosity=2)
