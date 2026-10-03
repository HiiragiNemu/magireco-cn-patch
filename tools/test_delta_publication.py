"""Offline tests of the current two-repository delta-only publication boundary."""
import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import publish_delta_only as p
from test_coherent_publication import FakeAPI
from resource_layers import validate_manifest_layers, SCENARIO_PREFIX


class DeltaPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.payload=self.root/'payload';self.payload.mkdir();self.folders={}
        self.old={n:('old-'+n).encode() for n in p.CHANGED}
        self.old[p.GATES[0]]=b'{"version":23,"size":12,"md5":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
        self.old.update({'cn_scenario_update.zip':b'fixed3323','cn_js_update.zip':b'fixed103',
            'cn_scenario_update_manifest.json':b'{}','version_scenario.json':b'{"version":3323}',
            'version_js.json':b'{"version":103}','client.apk':b'fixedapk'})
        self.new={n:('new-'+n).encode() for n in p.PAYLOADS}
        self.new[p.GATES[0]]=b'{"version":24,"size":14,"md5":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}'
        for n,b in self.new.items():(self.payload/n).write_bytes(b)
        self.apis=[];self.originals={};self.order=[]
        for repo in (p.SOURCE,p.PUBLIC):
            api=FakeAPI(self.old);api.repo=repo;self.apis.append(api);self.originals[repo]=api.assets()
            folder=self.root/repo.split('/')[-1];folder.mkdir();self.folders[repo]=folder
            for n,b in self.old.items():(folder/n).write_bytes(b)
            original=api.upload
            def upload(release,path,api=api,original=original):
                self.order.append((api.repo,path.name));return original(release,path)
            api.upload=upload
        self.mock=patch.object(p,'public_verify',return_value=None);self.mock.start();self.addCleanup(self.mock.stop)
    def run_publish(self):return p.publish_all(self.apis,self.originals,self.folders,self.payload,self.root)
    def test_both_data_sets_precede_first_gate(self):
        r=self.run_publish();self.assertTrue(r['passed'])
        self.assertEqual(self.order[:6],[(r,n) for r in (p.SOURCE,p.PUBLIC) for n in p.PAYLOADS])
        for api in self.apis:
            for n,b in self.old.items():
                if n not in p.CHANGED:self.assertEqual(api.contents[n],b);self.assertEqual(api.ids[n],self.originals[api.repo][n]['id'])
    def test_pre_gate_error_restores_both(self):
        self.apis[1].fail_name=p.PAYLOADS[1]
        with self.assertRaises(RuntimeError):self.run_publish()
        for api in self.apis:self.assertEqual(api.contents,self.old)
    def test_lost_gate_ack_never_restores_old(self):
        self.apis[0].fail_name=p.GATES[0];self.apis[0].fail_after_upload=True
        with self.assertRaises(RuntimeError):self.run_publish()
        self.assertEqual(self.apis[0].contents[p.GATES[0]],self.new[p.GATES[0]])
        for api in self.apis:
            for n in p.PAYLOADS:self.assertEqual(api.contents[n],self.new[n])
        self.assertEqual(json.loads((self.root/'publication-recovery.json').read_bytes())['action'],'ROLL_FORWARD_ONLY')
    def test_changed_release_rejected_before_write(self):
        self.apis[1].contents['client.apk']=b'newer unrelated build'
        with self.assertRaises(ValueError):self.run_publish()
        self.assertEqual(self.order,[])
    def test_version_rollback_rejected(self):
        (self.payload/p.GATES[0]).write_text('{"version":22}')
        with self.assertRaises(Exception):self.run_publish()
        self.assertEqual(self.order,[])
    def test_full_baselines_never_in_write_allowlist(self):
        self.assertEqual(set(p.CHANGED),{'cn_js_delta.zip','cn_js_delta_manifest.json','manifest.json','version_js_delta.json'})
    def test_private_source_authenticated_public_target_anonymous(self):
        source=self.apis[0];source.private=True;reads=[]
        def download(asset,dest):
            reads.append(asset['name']);dest.write_bytes(source.contents[asset['name']])
        source.download=download
        self.run_publish();self.assertEqual(reads,list(p.CHANGED))

class PrivateAccessTests(unittest.TestCase):
    def test_git_credential_is_scoped_and_restored(self):
        import os
        from source_access import authenticated_source_git
        old=dict(os.environ)
        with authenticated_source_git('fixture-not-a-secret'):
            i=int(old.get('GIT_CONFIG_COUNT','0'))
            self.assertEqual(os.environ['GIT_CONFIG_KEY_'+str(i)],'http.https://github.com/HiiragiNemu/magireco-cn-patch/.extraheader')
        self.assertEqual(dict(os.environ),old)


class AuthorityTests(unittest.TestCase):
    def test_new_story_differs_from_frozen_but_matches_authority(self):
        path=SCENARIO_PREFIX+'adv/a.json';entry=dict(path=path,size=3,sha256='b'*64)
        meta={'cn_js_delta_manifest.json':{'version':24,'entries':[entry],'source_authority':{'mode':'delta_only_cumulative'}},
            'cn_scenario_update_manifest.json':dict(version=3323,zip_size=5,zip_sha256='c'*64,files={path:dict(size=3,sha256='a'*64)}),
            'version_js_delta.json':{'version':24},'version_scenario.json':{'version':3323}}
        assets={'cn_scenario_update.zip':dict(size=5,digest='sha256:'+'c'*64)}
        with self.assertRaises(ValueError):validate_manifest_layers(meta,assets)
        self.assertEqual(validate_manifest_layers(meta,assets,{path:dict(size=3,sha256='b'*64)}),1)
        with self.assertRaises(ValueError):validate_manifest_layers(meta,assets,{path:dict(size=3,sha256='a'*64)})


if __name__=='__main__':unittest.main()
