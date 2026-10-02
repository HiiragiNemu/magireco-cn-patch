"""Small synthetic ZIP fixtures only; these tests never build real game packages."""
import copy,gzip,json,tempfile,unittest,zipfile
from pathlib import Path
from client_candidate_tools import candidate_from_source,config_with_targets,safe_path,write_isolated,verify_layers,load_packet,encoded,sha
from exact_json import apply,blob

P='madomagi/resource/scenario/json/adv/scenario_5/test.json'
Q='madomagi/resource/scenario/json/adv/scenario_5/old.json'
R='madomagi/resource/scenario/json/adv/scenario_5/parallel.json'
OLD=encoded({'story':{'group_1':[{'nameLeft':'甲','textLeft':'错误译文','chara':[{'id':1,'pos':0}]}]}})
OPS=[[['story','group_1',0,'textLeft'],'错误译文','修正译文']]
NEW=apply(OLD,OPS)
ENTRY={'path':P,'before_blob':blob(OLD),'before_sha256':sha(OLD),'after_blob':blob(NEW),'after_sha256':sha(NEW),'operations':OPS,'candidate_utf8':NEW.decode()}
CFG={'schema':'test/v1','base_js_version':103,'base_js_sha256':'a'*64,'base_source_commit':'b'*40,'supplemental_product_paths':[Q]}
PACKET={'kind':'source_bound_unreleased_story_integration','published':False,'target_count':1,'files':[ENTRY],'config_before':CFG,'preservation_guards':[{'path':Q,'sha256':sha(NEW)}]}

class ClientIntegrationTests(unittest.TestCase):
 def test_exact_candidate(self):self.assertEqual(candidate_from_source(OLD,ENTRY),(NEW,'staged_only'))
 def test_idempotent(self):self.assertEqual(candidate_from_source(NEW,ENTRY),(NEW,'already_integrated'))
 def test_parallel_runtime_change_blocks(self):
  with self.assertRaises(ValueError):candidate_from_source(OLD.replace(b'"id": 1',b'"id": 2'),ENTRY)
 def test_wrong_after_hash_blocks(self):
  e=copy.deepcopy(ENTRY);e['after_sha256']='f'*64
  with self.assertRaises(ValueError):candidate_from_source(OLD,e)
 def test_actor_change_not_translation(self):
  e=copy.deepcopy(ENTRY);e['operations'].append([['story','group_1',0,'chara',0,'id'],1,2])
  with self.assertRaises(ValueError):candidate_from_source(OLD,e)
 def test_config_union_preserves_original_order(self):
  self.assertEqual(json.loads(config_with_targets(encoded(CFG),PACKET))['supplemental_product_paths'],[Q,P])
 def test_config_parallel_addition_preserved(self):
  c=copy.deepcopy(CFG);c['supplemental_product_paths'].append(R);c['new_policy']={'keep':True};result=json.loads(config_with_targets(encoded(c),PACKET));self.assertEqual(result['supplemental_product_paths'],[Q,R,P]);self.assertEqual(result['new_policy'],c['new_policy'])
 def test_existing_owned_path_removal_blocks(self):
  c=copy.deepcopy(CFG);c['supplemental_product_paths']=[]
  with self.assertRaises(ValueError):config_with_targets(encoded(c),PACKET)
 def test_baseline_drift_blocks(self):
  c=copy.deepcopy(CFG);c['base_js_version']=104
  with self.assertRaises(ValueError):config_with_targets(encoded(c),PACKET)
 def test_config_idempotent_bytes(self):
  c=copy.deepcopy(CFG);c['supplemental_product_paths'].append(P);raw=encoded(c);self.assertEqual(config_with_targets(raw,PACKET),raw)
 def test_config_duplicate_rejected(self):
  c=copy.deepcopy(CFG);c['supplemental_product_paths']=[Q,Q]
  with self.assertRaises(ValueError):config_with_targets(encoded(c),PACKET)
 def test_traversal_rejected(self):
  for p in ['../file','/absolute','C:/file','a\\b','a//b','a/./b']:
   with self.subTest(p=p),self.assertRaises(ValueError):safe_path(p)
 def test_output_existing_blocked(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):write_isolated({P:NEW},Path(t))
 def test_output_under_git_blocked(self):
  with tempfile.TemporaryDirectory() as t:
   (Path(t)/'.git').mkdir()
   with self.assertRaises(ValueError):write_isolated({P:NEW},Path(t)/'new')
 def test_isolated_output(self):
  with tempfile.TemporaryDirectory() as t:
   dest=Path(t)/'new';write_isolated({P:NEW},dest);self.assertEqual((dest/P).read_bytes(),NEW)
 def zipped(self,root,name,entries):
  p=root/name
  with zipfile.ZipFile(p,'w') as z:
   for key,value in entries:z.writestr(key,value)
  return p
 def run_layers(self,scenario=None,delta=None,full=None,base=None):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=self.zipped(r,'s.zip',scenario if scenario is not None else [(P,NEW),(Q,NEW)]);d=self.zipped(r,'d.zip',delta if delta is not None else [(P,NEW),(Q,NEW)]);f=self.zipped(r,'f.zip',full if full is not None else [('unrelated.js',b'old javascript')]);b=self.zipped(r,'b.zip',base if base is not None else [(P,OLD),(Q,OLD)])
   return verify_layers(PACKET,s,d,f,[b])
 def test_correct_final_layer_and_cache_replay(self):
  r=self.run_layers();self.assertTrue(r['passed']);self.assertEqual(r['reviewed_targets_in_both_packages'],1);self.assertEqual(r['final_layer_hash_checks'],4);self.assertFalse(r['device_test_performed'])
 def test_stale_delta_rejected_even_version_new(self):
  with self.assertRaises(ValueError):self.run_layers(delta=[(P,OLD),(Q,NEW),('version.json',b'{"version":99999}')])
 def test_missing_delta_target_rejected(self):
  with self.assertRaises(ValueError):self.run_layers(delta=[(Q,NEW)])
 def test_stale_scenario_rejected(self):
  with self.assertRaises(ValueError):self.run_layers(scenario=[(P,OLD),(Q,NEW)])
 def test_old_published_correction_regression_blocks(self):
  with self.assertRaises(ValueError):self.run_layers(scenario=[(P,NEW),(Q,OLD)],delta=[(P,NEW),(Q,OLD)])
 def test_full_js_late_overlay_regression_blocks(self):
  with self.assertRaises(ValueError):self.run_layers(full=[(P,OLD)])
 def test_delta_scenario_extra_overlap_mismatch_blocks(self):
  with self.assertRaises(ValueError):self.run_layers(delta=[(P,NEW),(Q,NEW),(R,OLD)])
 def test_duplicate_zip_entry_blocks(self):
  import warnings
  with warnings.catch_warnings():
   warnings.simplefilter('ignore',UserWarning)
   with self.assertRaises(ValueError):self.run_layers(delta=[(P,NEW),(P,OLD),(Q,NEW)])
 def test_zip_traversal_blocks(self):
  with self.assertRaises(ValueError):self.run_layers(delta=[(P,NEW),(Q,NEW),('../bad',b'x')])
 def test_old_supplemental_ownership_required(self):
  with self.assertRaises(ValueError):self.run_layers(delta=[(P,NEW)])
 def test_manifest_hash_required(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'m.gz';raw=gzip.compress(encoded(PACKET));p.write_bytes(raw)
   with self.assertRaises(ValueError):load_packet(p,'0'*64)
   self.assertEqual(load_packet(p,sha(raw))['target_count'],1)
 def test_manifest_payload_tampering_blocks(self):
  with tempfile.TemporaryDirectory() as t:
   m=copy.deepcopy(PACKET);m['files'][0]['candidate_utf8']='tampered';p=Path(t)/'m.gz';raw=gzip.compress(encoded(m));p.write_bytes(raw)
   with self.assertRaises(ValueError):load_packet(p,sha(raw))
 def test_duplicate_manifest_target_blocks(self):
  with tempfile.TemporaryDirectory() as t:
   m=copy.deepcopy(PACKET);m['files'].append(copy.deepcopy(ENTRY));m['target_count']=2;p=Path(t)/'m.gz';raw=gzip.compress(encoded(m));p.write_bytes(raw)
   with self.assertRaises(ValueError):load_packet(p,sha(raw))

if __name__=='__main__':unittest.main()
