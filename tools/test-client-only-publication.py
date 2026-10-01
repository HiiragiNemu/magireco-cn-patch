import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import promote_verified_client as p

OLD = {'client': {'version': '1.0.198', 'sha256': 'a'*64, 'size': 12, 'apk_url': 'https://old.example/file.apk', 'note': 'retained'},
       'scenario': 3317, 'js': 103, 'delta': 21, 'updated': 'older',
       'mirrors': [{'base': 'https://current.example/', 'weight': 140}],
       'settings': {'parallel': 4}, 'credits': ['newer public translations'],
       'branch_versions': {'old': {'supported': False}}}
WANTED = {'version': '1.0.199', 'sha256': 'b'*64, 'size': 12, 'note': 'must not overwrite public note'}
ASSETS = {p.APK: {'name': p.APK, 'id': 1, 'size': 12, 'digest': 'sha256:'+'b'*64, 'state': 'uploaded'},
          p.APK_META: {'name': p.APK_META, 'id': 2, 'size': 500, 'digest': 'sha256:'+'c'*64, 'state': 'uploaded'}}

class FakeAPI:
    def __init__(self, repo, config):
        self.repo = repo
        self.config = copy.deepcopy(config)
        self.assets = copy.deepcopy(ASSETS)
        self.meta = dict(WANTED, publication='PUBLISHED', source_branch='main', published_from_run=42)
        self.writes = []
        self.downloads = []
        self.conflict = False
    def json(self, path, method='GET', data=None):
        if path == 'releases/tags/latest': return {'id': 3, 'draft': False, 'prerelease': False}
        if path.startswith('releases/3/assets?'): return list(self.assets.values())
        if method == 'PUT' and path == 'contents/legacy/config.json':
            if self.conflict: raise p.Failure('Simulated compare-and-swap conflict')
            assert data['sha'] == 'current-blob'
            self.writes.append((path, data))
            self.config = json.loads(base64.b64decode(data['content']))
            return {}
        raise AssertionError('Unexpected operation: '+method+' '+path)
    def file(self, path): return json.dumps(self.config).encode(), 'current-blob'
    def download(self, asset, target):
        assert asset['name'] == p.APK_META, 'Resource or full APK download is not part of gate promotion'
        self.downloads.append(asset['name'])
        target.write_text(json.dumps(self.meta), encoding='utf8')

def execute(source=None, target=None):
    s=source or FakeAPI('Example/Source', {'client': WANTED, 'scenario':3300})
    t=target or FakeAPI('Example/Public', OLD)
    with tempfile.TemporaryDirectory() as temp, patch.object(p, 'anonymous_verify'):
        result=p.promote(s,t,Path(temp),42)
    return s,t,result

class ClientOnly(unittest.TestCase):
    def test_newer_public_resources_are_preserved(self):
        s,t,r=execute()
        self.assertEqual(r['resourceAssetsWritten'],0)
        for key in OLD:
            if key not in ('client','updated'): self.assertEqual(t.config[key],OLD[key])
        self.assertEqual(t.config['client']['note'],'retained')
        self.assertEqual(t.config['client']['version'],'1.0.199')
        self.assertEqual(len(t.writes),1)
        self.assertEqual(t.assets,ASSETS)
    def test_planning_does_not_mutate_input(self):
        old=copy.deepcopy(OLD);want=copy.deepcopy(WANTED)
        p.plan_config(old,want,'Example/Public')
        self.assertEqual(old,OLD);self.assertEqual(want,WANTED)
    def test_idempotent_retry(self):
        s,t,_=execute();t.writes.clear()
        _,t,r=execute(s,t)
        self.assertFalse(r['publicConfigChanged']);self.assertEqual(t.writes,[])
    def test_client_downgrade_fails(self):
        old=copy.deepcopy(OLD);old['client']['version']='1.0.200'
        with self.assertRaises(p.Failure):p.plan_config(old,WANTED,'Example/Public')
    def test_same_version_different_apk_fails(self):
        old=copy.deepcopy(OLD);old['client']['version']='1.0.199'
        with self.assertRaises(p.Failure):p.plan_config(old,WANTED,'Example/Public')
    def test_invalid_identity_fails(self):
        for key,value in [('version','bad'),('sha256','no'),('size',-1),('size',True)]:
            w=dict(WANTED);w[key]=value
            with self.assertRaises(p.Failure):p.plan_config(OLD,w,'Example/Public')
    def test_public_apk_mismatch_fails(self):
        t=FakeAPI('Example/Public',OLD);t.assets[p.APK]['digest']='sha256:'+'d'*64
        with self.assertRaises(p.Failure):execute(target=t)
        self.assertEqual(t.writes,[])
    def test_metadata_mismatch_fails(self):
        t=FakeAPI('Example/Public',OLD);t.meta['sha256']='d'*64
        with self.assertRaises(p.Failure):execute(target=t)
        self.assertEqual(t.writes,[])
    def test_unapproved_run_fails(self):
        t=FakeAPI('Example/Public',OLD);t.meta['published_from_run']=41
        with self.assertRaises(p.Failure):execute(target=t)
        self.assertEqual(t.writes,[])
    def test_unpublished_metadata_fails(self):
        t=FakeAPI('Example/Public',OLD);t.meta['publication']='CANDIDATE'
        with self.assertRaises(p.Failure):execute(target=t)
        self.assertEqual(t.writes,[])
    def test_compare_and_swap_conflict_fails_without_overwrite(self):
        t=FakeAPI('Example/Public',OLD);t.conflict=True
        with self.assertRaises(p.Failure):execute(target=t)
        self.assertEqual(t.writes,[]);self.assertEqual(t.config,OLD)
    def test_workflow_only_uses_client_promotion(self):
        src=(Path(__file__).parents[1]/'.github/workflows/publish-verified-client.yml').read_text(encoding='utf8')
        self.assertIn('tools/promote_verified_client.py',src)
        self.assertNotIn('tools/mirror_release.py',src)

if __name__=='__main__':unittest.main()
