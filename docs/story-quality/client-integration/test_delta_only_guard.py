"""Synthetic overlay regressions; no real game archive is produced by these tests."""
import copy,json,tempfile,unittest,zipfile,warnings
from pathlib import Path
from delta_only_guard import PREFIX,META,SCHEMA,blob,sha,inventory,validate_delta,verify_maps
A=PREFIX+'adv/scenario_7/new.json';B=PREFIX+'adv/scenario_1/preserved.json';J='magica/js/existing.js'
def row(b):return {'blob':blob(b),'sha256':sha(b),'size':len(b)}
def fixture():
 old_a=row(b'{"text":"old"}');new_a=row(b'{"text":"corrected"}');b=row(b'{"repair":true}');j=row(b'approved existing fix')
 expected={A:new_a,B:b,J:j};base_sha='a'*64
 plan={'full_js_sha256':base_sha,'base_js_version':103,'previous_delta_version':22,'required_delta_paths':[A,B,J],'source_product_blobs':{p:r['blob'] for p,r in expected.items()},'final_source_expectations':{p:r['blob'] for p,r in expected.items()},'frozen_overlay':{A:old_a,B:b,J:row(b'old js')}}
 m={'schema':SCHEMA,'version':23,'base_js_version':103,'base_js_sha256':base_sha,'entries':[{'path':p,'sha256':r['sha256'],'size':r['size']} for p,r in expected.items()]}
 new={'metadata':m,'files':dict(expected)|{META:row(json.dumps(m).encode())}}
 return plan,new
class DeltaOnly(unittest.TestCase):
 def test_new_delta_may_deliberately_override_unchanged_scenario(self):
  p,n=fixture();self.assertNotEqual(p['frozen_overlay'][A]['blob'],n['files'][A]['blob']);self.assertTrue(verify_maps(p,n)['passed'])
 def test_old_delta_relabelled_new_version_is_rejected(self):
  p,n=fixture();n['files'][A]=p['frozen_overlay'][A];r=n['metadata']['entries'][0];r.update(sha256=n['files'][A]['sha256'],size=n['files'][A]['size']);self.assertRaisesRegex(ValueError,'Stale delta',verify_maps,p,n)
 def test_omitted_new_target_rejected(self):
  p,n=fixture();del n['files'][A];n['metadata']['entries']=n['metadata']['entries'][1:];self.assertRaisesRegex(ValueError,'omitted',verify_maps,p,n)
 def test_omitted_old_story_repair_rejected(self):
  p,n=fixture();del n['files'][B];n['metadata']['entries']=[e for e in n['metadata']['entries'] if e['path']!=B];self.assertRaisesRegex(ValueError,'omitted',verify_maps,p,n)
 def test_omitted_nonstory_old_fix_rejected(self):
  p,n=fixture();del n['files'][J];n['metadata']['entries']=[e for e in n['metadata']['entries'] if e['path']!=J];self.assertRaisesRegex(ValueError,'omitted',verify_maps,p,n)
 def test_same_version_rejected(self):
  p,n=fixture();n['metadata']['version']=22;self.assertRaisesRegex(ValueError,'advance',verify_maps,p,n)
 def test_smaller_version_rejected(self):
  p,n=fixture();n['metadata']['version']=21;self.assertRaisesRegex(ValueError,'advance',verify_maps,p,n)
 def test_wrong_base_sha_rejected(self):
  p,n=fixture();n['metadata']['base_js_sha256']='b'*64;self.assertRaisesRegex(ValueError,'baseline',verify_maps,p,n)
 def test_wrong_base_version_rejected(self):
  p,n=fixture();n['metadata']['base_js_version']=102;self.assertRaisesRegex(ValueError,'baseline',verify_maps,p,n)
 def test_manifest_payload_hash_mismatch_rejected(self):
  p,n=fixture();n['metadata']['entries'][0]['sha256']='c'*64;self.assertRaisesRegex(ValueError,'payload',verify_maps,p,n)
 def test_hidden_extra_file_rejected(self):
  p,n=fixture();n['files']['magica/js/extra.js']=row(b'extra');self.assertRaisesRegex(ValueError,'inventory',verify_maps,p,n)
 def test_duplicate_manifest_path_rejected(self):
  p,n=fixture();n['metadata']['entries'].append(n['metadata']['entries'][0]);self.assertRaisesRegex(ValueError,'Duplicate',verify_maps,p,n)
 def test_declared_unapproved_payload_rejected(self):
  p,n=fixture();x='magica/js/extra.js';r=row(b'extra');n['files'][x]=r;n['metadata']['entries'].append(dict(path=x,sha256=r['sha256'],size=r['size']));self.assertRaisesRegex(ValueError,'Unapproved',verify_maps,p,n)
 def test_current_source_not_old_delta_is_authority(self):
  p,n=fixture();p['source_product_blobs'][J]=blob(b'later fix');self.assertRaisesRegex(ValueError,'Stale delta',verify_maps,p,n)
 def test_unsupplied_new_baseline_difference_rejected(self):
  p,n=fixture();x=PREFIX+'another.json';p['final_source_expectations'][x]=blob(b'new');self.assertRaisesRegex(ValueError,'Final baseline',verify_maps,p,n)
 def test_skipped_updates_and_latest_replay_converge(self):
  p,n=fixture();r=verify_maps(p,n);self.assertTrue(r['cumulative_previous_paths_preserved']);self.assertFalse(r['actual_device_test_performed'])
 def test_removed_added_file_not_silently_omitted(self):
  p,n=fixture();p['required_delta_paths'].append('magica/js/retired.js');self.assertRaisesRegex(ValueError,'omitted',verify_maps,p,n)
 def test_zip_valid_binary_hash(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'fixture.zip'
   with zipfile.ZipFile(f,'w') as z:z.writestr(A,b'fixture')
   self.assertEqual(inventory(f)['files'][A],row(b'fixture'))
 def test_zip_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'fixture.zip'
   with zipfile.ZipFile(f,'w') as z:z.writestr('magica/../bad.js',b'bad')
   self.assertRaisesRegex(ValueError,'Unsafe',inventory,f)
 def test_zip_duplicate_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'fixture.zip'
   with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    with zipfile.ZipFile(f,'w') as z:z.writestr(A,b'one');z.writestr(A,b'two')
   self.assertRaisesRegex(ValueError,'Duplicate',inventory,f)
 def test_zip_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'fixture.zip';i=zipfile.ZipInfo(A);i.external_attr=0o120777<<16
   with zipfile.ZipFile(f,'w') as z:z.writestr(i,b'target')
   self.assertRaisesRegex(ValueError,'symlink',inventory,f)
if __name__=='__main__':unittest.main()
