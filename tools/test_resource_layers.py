"""Executable counterexamples for cross-package story ownership."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import build_coherent_resources as b
from resource_layers import validate, DELTA_MANIFEST, SCENARIO_PREFIX

A = SCENARIO_PREFIX + 'adv/scenario_1/100001.json'
B = SCENARIO_PREFIX + 'adv/scenario_1/100002.json'
JS = 'magica/js/main.js'


def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w') as z:
        for name, value in entries.items():
            b.cumulative.delta.put(z, name, value)


class LayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.js = self.root / 'js.zip'
        self.sc = self.root / 'scenario.zip'
        self.target = self.root / 'target.zip'
        self.delta = self.root / 'delta.zip'
        write_zip(self.js, {JS: b'keep JS unchanged'})
        write_zip(self.sc, {A: b'{"text":"new voice control"}', B: b'{"name":"correct name"}'})
        write_zip(self.target, {JS: b'keep JS unchanged', A: b'{"text":"old voice control"}', B: b'{"name":"correct name"}'})
        b.cumulative.delta.build(self.js, self.target, self.delta, 103, 21)

    def test_old_last_writer_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Last-writer scenario conflict'):
            validate(self.js, self.sc, self.delta)

    def test_coherent_last_writer_and_cached_replay(self):
        with zipfile.ZipFile(self.sc) as s:
            write_zip(self.target, {JS: b'keep JS unchanged', A: s.read(A), B: s.read(B)})
        new = self.root / 'new.zip'
        b.cumulative.delta.build(self.js, self.target, new, 103, 22, self.delta)
        report = validate(self.js, self.sc, new)
        self.assertEqual(report['scenario_overlaps_checked'], 2)
        self.assertEqual(report['conflicts'], 0)
        # Exact final bytes for full install and a later scenario reinstall.
        installed = {}
        for path in (self.sc, self.js, new, self.sc, new):
            with zipfile.ZipFile(path) as z:
                installed.update({i.filename: z.read(i) for i in z.infolist() if not i.is_dir()})
        with zipfile.ZipFile(self.sc) as z:
            self.assertEqual(installed[A], z.read(A))
            self.assertEqual(installed[B], z.read(B))
        self.assertEqual(installed[JS], b'keep JS unchanged')

    def test_undeclared_delta_file_is_rejected(self):
        with zipfile.ZipFile(self.delta, 'a') as z:
            z.writestr('magica/undeclared.js', 'not declared')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            validate(self.js, self.sc, self.delta)

    def test_wrong_frozen_js_is_rejected(self):
        write_zip(self.js, {JS: b'changed base'})
        with self.assertRaisesRegex(ValueError, 'frozen JS'):
            validate(self.js, self.sc, self.delta)

    def test_full_builder_preserves_both_old_and_new_corrections(self):
        repo = self.root / 'repo'
        repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)
        git('init', '-b', 'main')
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        git('config', 'commit.gpgsign', 'false')
        initial = {JS: b'keep JS unchanged', A: b'{"text":"old voice control"}', B: b'{"name":"old name"}'}
        for name, raw in initial.items():
            p = repo / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
        git('add', '.'); git('commit', '-m', 'fixture baseline')
        base_commit = git('rev-parse', 'HEAD').decode().strip()
        original_sc = self.root / 'original' / 'cn_scenario_update.zip'
        original_sc.parent.mkdir()
        write_zip(original_sc, {A: initial[A], B: initial[B]})
        original_sc.with_name('version_scenario.json').write_text('{"version":1}')
        config = repo / 'configures/js-delta-baseline.json'
        config.parent.mkdir()
        b.save(config, {'base_js_version': 103, 'base_js_sha256': hashlib.sha256(self.js.read_bytes()).hexdigest(),
                        'base_source_commit': base_commit, 'supplemental_product_paths': [A, B]})
        (repo / A).write_bytes(b'{"text":"new voice control"}')
        (repo / B).write_bytes(b'{"name":"correct name"}')
        git('add', '.'); git('commit', '-m', 'fixture reviewed changes')
        output = self.root / 'result'
        result = b.build(repo, 'HEAD', self.js, original_sc, self.delta, output, 2)
        self.assertEqual(result['earlier_supplement_paths_folded'], [B])
        self.assertEqual(result['new_source_paths_read'], [A])
        self.assertEqual(result['layering']['conflicts'], 0)
        with zipfile.ZipFile(output / 'cn_scenario_update.zip') as z:
            self.assertEqual(z.read(A), (repo / A).read_bytes())
            self.assertEqual(z.read(B), (repo / B).read_bytes())
        with zipfile.ZipFile(output / 'cn_js_delta.zip') as z:
            self.assertEqual(z.read(A), (repo / A).read_bytes())
            self.assertEqual(z.read(B), (repo / B).read_bytes())
        with self.assertRaisesRegex(ValueError, 'empty staging'):
            b.build(repo, 'HEAD', self.js, original_sc, self.delta, output, 3)
        repeated = self.root / 'repeated'
        again = b.build(repo, 'HEAD', self.js, output / 'cn_scenario_update.zip',
                        output / 'cn_js_delta.zip', repeated, 3)
        self.assertEqual(again['scenario_version'], 2)
        self.assertEqual(again['delta']['version'], result['delta']['version'])
        for name in ('cn_scenario_update.zip', 'cn_scenario_update_manifest.json',
                     'version_scenario.json', 'cn_js_delta.zip', 'cn_js_delta_manifest.json',
                     'version_js_delta.json'):
            self.assertEqual((repeated / name).read_bytes(), (output / name).read_bytes(), name)


if __name__ == '__main__':
    unittest.main()
