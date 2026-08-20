#!/usr/bin/env python3
"""i18n-package.py 的包边界与 engine-only 回归测试。"""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).with_name('i18n-package.py')
ENGINE_MEMBER = 'madomagi/engine_i18n.tsv'
REPAIR_PREFIX = 'madomagi/resource/image_native/'
REPO_ENGINE = SCRIPT.parent.parent / ENGINE_MEMBER


class I18nPackageTest(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            check=False,
        )

    @staticmethod
    def write_engine(path, value='戻る\t返回\n'):
        Path(path).write_text('# ja<TAB>zhCN\n' + value, encoding='utf-8', newline='\n')

    @staticmethod
    def make_polluted_base(path):
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('magica/js/old.js', b'old')
            archive.writestr(ENGINE_MEMBER, '戻る\t旧译\n'.encode('utf-8'))
            archive.writestr('madomagi/resource/scenario/json/1001.json', b'{}')
            archive.writestr('unexpected-root.txt', b'not-js-package-data')
            archive.writestr('magica/research/notes.tsv', b'audit-only')
            archive.writestr('magica/i18n_audit/report.json', b'{}')

    def test_engine_only_replaces_table_and_preserves_magica(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'base.zip'
            engine = root / 'engine_i18n.tsv'
            output = root / 'cn_js_update.zip'
            self.make_polluted_base(base)
            self.write_engine(engine)

            result = self.run_tool('--base', base, '--engine', engine, '-o', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertEqual(len(names), len(set(names)))
                self.assertEqual(
                    archive.read(ENGINE_MEMBER), engine.read_bytes(),
                    '包内 engine 表必须逐字节等于权威源',
                )
                self.assertEqual(archive.read('magica/js/old.js'), b'old')
                self.assertNotIn('madomagi/resource/scenario/json/1001.json', names)
                self.assertNotIn('unexpected-root.txt', names)
                self.assertNotIn('magica/research/notes.tsv', names)
                self.assertNotIn('magica/i18n_audit/report.json', names)
                self.assertTrue(all(
                    name.startswith('magica/') or name == ENGINE_MEMBER
                    or name.startswith(REPAIR_PREFIX)
                    for name in names
                ))
                self.assertEqual(
                    91, sum(name.startswith(REPAIR_PREFIX) for name in names)
                )

    def test_default_engine_is_repository_authority_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'base.zip'
            output = root / 'cn_js_update.zip'
            with zipfile.ZipFile(base, 'w') as archive:
                archive.writestr('magica/js/old.js', b'old')

            result = self.run_tool('--base', base, '-o', output)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read(ENGINE_MEMBER), REPO_ENGINE.read_bytes())

    def test_frontend_overlay_and_add_keep_parallel_root_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'base.zip'
            engine = root / 'engine_i18n.tsv'
            magica = root / 'magica'
            changed = root / 'changed.txt'
            extra = root / 'icon.png'
            output = root / 'cn_js_update.zip'
            self.make_polluted_base(base)
            self.write_engine(engine)
            (magica / 'js').mkdir(parents=True)
            (magica / 'js' / 'new.js').write_text('新', encoding='utf-8')
            changed.write_text('js/new.js\n', encoding='utf-8')
            extra.write_bytes(b'png')

            result = self.run_tool(
                magica, changed, '--base', base, '--engine', engine,
                '--add', f'{extra}=resource/image_web/icon.png', '-o', output,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read('magica/js/new.js'), '新'.encode('utf-8'))
                self.assertEqual(archive.read('magica/resource/image_web/icon.png'), b'png')
                self.assertEqual(archive.read(ENGINE_MEMBER), engine.read_bytes())

    def test_engine_only_without_base_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            engine = root / 'engine_i18n.tsv'
            output = root / 'cn_js_update.zip'
            self.write_engine(engine)
            result = self.run_tool('--engine', engine, '-o', output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('--base', result.stderr)
            self.assertFalse(output.exists())

    def test_audit_or_research_overlay_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'base.zip'
            engine = root / 'engine_i18n.tsv'
            magica = root / 'magica'
            changed = root / 'changed.txt'
            output = root / 'cn_js_update.zip'
            with zipfile.ZipFile(base, 'w') as archive:
                archive.writestr('magica/js/old.js', b'old')
            self.write_engine(engine)
            (magica / 'i18n_audit').mkdir(parents=True)
            (magica / 'i18n_audit' / 'report.json').write_text('{}', encoding='utf-8')
            changed.write_text('i18n_audit/report.json\n', encoding='utf-8')

            result = self.run_tool(
                magica, changed, '--base', base, '--engine', engine, '-o', output,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('不得进入运行时包', result.stderr)
            self.assertFalse(output.exists())

    def test_malformed_engine_table_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'base.zip'
            engine = root / 'engine_i18n.tsv'
            output = root / 'cn_js_update.zip'
            self.make_polluted_base(base)
            engine.write_text('缺少制表符\n', encoding='utf-8')
            result = self.run_tool('--base', base, '--engine', engine, '-o', output)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('缺少 TAB', result.stderr)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
