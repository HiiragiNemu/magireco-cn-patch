"""Publication policy tests; network transport is replaced by an in-memory API."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import publish_coherent_resources as p
from resource_layers import validate_manifest_layers, SCENARIO_PREFIX


class FakeAPI:
    repo = p.PUBLIC
    def __init__(self, contents):
        self.contents = dict(contents)
        self.ids = {n: i + 1 for i, n in enumerate(contents)}
        self.next_id = 100
        self.writes = []
        self.fail_name = None
        self.fail_after_upload = False
    def assets(self):
        return {n: {'id': self.ids[n], 'name': n, 'size': len(v), 'digest': 'sha256:' + hashlib.sha256(v).hexdigest(),
                    'browser_download_url': 'https://github.com/example/repo/releases/download/latest/' + n}
                for n, v in self.contents.items()}
    def json(self, path, method='GET', data=None):
        if path == 'releases/tags/latest':
            return {'id': 1, 'draft': False, 'prerelease': False}
        if path.startswith('releases/1/assets?'):
            return list(self.assets().values())
        if method == 'DELETE':
            number = int(path.rsplit('/', 1)[1])
            name = next(n for n, i in self.ids.items() if i == number)
            self.writes.append(('delete', name)); del self.contents[name]; del self.ids[name]
            return None
        raise AssertionError(path)
    def upload(self, release, path):
        name = path.name
        fail = name == self.fail_name
        if fail:
            self.fail_name = None
        if fail and not self.fail_after_upload:
            raise RuntimeError('injected pre-gate failure')
        self.contents[name] = path.read_bytes(); self.next_id += 1; self.ids[name] = self.next_id
        self.writes.append(('upload', name))
        if fail:
            raise RuntimeError('injected lost upload acknowledgement')
        return self.assets()[name]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name); self.before = self.root / 'before'; self.payload = self.root / 'payload'
        self.before.mkdir(); self.payload.mkdir()
        self.old = {n: ('old-' + n).encode() for n in p.CHANGED}
        self.new = {n: ('new-' + n).encode() for n in p.CHANGED}
        for n in p.VERSIONS:
            self.old[n] = json.dumps({'version': 1, 'size': 12, 'md5': 'a'*32}).encode()
            self.new[n] = json.dumps({'version': 2, 'size': 14, 'md5': 'b'*32}).encode()
        self.old['client.apk'] = b'unchanged reviewed APK'
        self.old['cn_js_update.zip'] = b'unchanged frozen JS'
        self.old['version_js.json'] = b'{"version":103}'
        for n, raw in self.old.items(): (self.before / n).write_bytes(raw)
        for n, raw in self.new.items(): (self.payload / n).write_bytes(raw)
        self.api = FakeAPI(self.old)
        self.original = self.api.assets()
        self.verify = patch.object(p, 'public_verify', return_value=None)
        self.verify.start(); self.addCleanup(self.verify.stop)
    def publish(self):
        return p.publish_one(self.api, self.original, self.before, self.payload, self.root)
    def test_payloads_precede_gates_and_static_assets_unchanged(self):
        result = self.publish()
        writes = [n for action, n in self.api.writes if action == 'upload']
        self.assertEqual(writes, list(p.CHANGED))
        self.assertEqual(self.api.contents['client.apk'], self.old['client.apk'])
        self.assertEqual(self.api.ids['client.apk'], self.original['client.apk']['id'])
        self.assertTrue(result['unrelated_assets_unchanged'])
    def test_pre_gate_failure_restores_originals(self):
        self.api.fail_name = 'cn_scenario_update.zip'
        with self.assertRaises(RuntimeError): self.publish()
        self.assertEqual(self.api.contents, self.old)
    def test_lost_version_acknowledgement_never_rolls_back(self):
        self.api.fail_name = p.VERSIONS[0]; self.api.fail_after_upload = True
        with self.assertRaises(RuntimeError): self.publish()
        self.assertEqual(self.api.contents[p.VERSIONS[0]], self.new[p.VERSIONS[0]])
        for n in p.PAYLOADS: self.assertEqual(self.api.contents[n], self.new[n])
        self.assertEqual(self.api.contents['client.apk'], self.old['client.apk'])
    def test_downgrade_rejected_before_writing(self):
        (self.payload / p.VERSIONS[0]).write_text('{"version":0}')
        with self.assertRaises(Exception): self.publish()
        self.assertFalse(self.api.writes)
    def test_concurrent_change_rejected_before_writing(self):
        self.api.contents['client.apk'] = b'newer APK from another publisher'
        with self.assertRaisesRegex(ValueError, 'changed before'): self.publish()
        self.assertFalse(self.api.writes)
    def test_idempotent_publication_does_not_replace_assets(self):
        for n in p.CHANGED: (self.payload / n).write_bytes(self.old[n])
        self.publish()
        self.assertFalse(self.api.writes)
    def test_manifest_guard_is_bound_to_full_scenario(self):
        name = SCENARIO_PREFIX + 'adv/a.json'
        assets = {'cn_scenario_update.zip': {'digest': 'sha256:' + 'b'*64, 'size': 12}}
        meta = {'cn_js_delta_manifest.json': {'version': 22, 'entries': [{'path': name, 'size': 5, 'sha256': 'a'*64}]},
                'cn_scenario_update_manifest.json': {'zip_sha256': 'b'*64, 'zip_size': 12, 'version': 3323,
                    'files': {name: {'size': 5, 'sha256': 'a'*64}}},
                'version_scenario.json': {'version': 3323}, 'version_js_delta.json': {'version': 22}}
        self.assertEqual(validate_manifest_layers(meta, assets), 1)
        meta['cn_scenario_update_manifest.json']['files'][name]['sha256'] = 'c'*64
        with self.assertRaisesRegex(ValueError, 'Last-writer'): validate_manifest_layers(meta, assets)
        meta['cn_scenario_update_manifest.json']['zip_sha256'] = 'd'*64
        with self.assertRaisesRegex(ValueError, 'identity'): validate_manifest_layers(meta, assets)


if __name__ == '__main__': unittest.main()
