import unittest,copy,json
from exact_json import apply,blob
from amendment_contract import amend,sha

def sample():
 src=b'{"story":{"group_1":[{"nameRight":"Name","textRight":"old","chara":[{"id":1}]},{"textRight":"[se:1]machine userName","item":[{"base64":"KEEPME"}]}]}}'
 ops=[[['story','group_1',0,'textRight'],'old','reviewed']];prior=apply(src,ops)
 entry={'before_blob':blob(src),'before_sha256':sha(src),'after_blob':blob(prior),'after_sha256':sha(prior),'candidate_utf8':prior.decode(),'operations':ops}
 d={'address':['story','group_1',1,'textRight'],'before':'[se:1]machine userName','after':'[se:1]correct userName','japanese':'test source','import_chinese':'[se:1]machine userName','prior_candidate_text':'[se:1]machine userName','unchanged_imported_machine_field':True,'machine_types':['fallback'],'rationale':'source-bound semantic correction','protected':False}
 return src,entry,d
class Contract(unittest.TestCase):
 def test_append_and_reverse(self):
  src,e,d=sample();n,o=amend(e,src,[d]);self.assertEqual(n['operations'][:1],e['operations']);self.assertEqual(len(n['operations']),2);self.assertEqual(apply(n['candidate_utf8'].encode(),[[a,y,x] for a,x,y in o]),e['candidate_utf8'].encode())
 def test_original_inputs_not_mutated(self):
  src,e,d=sample();a=copy.deepcopy(e);b=copy.deepcopy(d);amend(e,src,[d]);self.assertEqual(e,a);self.assertEqual(d,b)
 def test_images_and_actor_retained(self):
  src,e,d=sample();n,_=amend(e,src,[d]);j=json.loads(n['candidate_utf8']);self.assertEqual(j['story']['group_1'][1]['item'][0]['base64'],'KEEPME');self.assertEqual(j['story']['group_1'][0]['chara'][0]['id'],1)
 def test_source_third_version_rejected(self):
  src,e,d=sample()
  with self.assertRaises(ValueError):amend(e,src+b' ',[d])
 def test_candidate_tampering_rejected(self):
  src,e,d=sample();e['candidate_utf8']+=' '
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_earlier_operation_cannot_be_overwritten(self):
  src,e,d=sample();d['address']=['story','group_1',0,'textRight']
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_duplicate_address_rejected(self):
  src,e,d=sample()
  with self.assertRaises(ValueError):amend(e,src,[d,d])
 def test_unverified_source_rejected(self):
  src,e,d=sample();d['unchanged_imported_machine_field']=False
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_no_log_proof_rejected(self):
  src,e,d=sample();d['machine_types']=[]
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_protected_field_rejected(self):
  src,e,d=sample();d['protected']=True
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_import_mismatch_rejected(self):
  src,e,d=sample();d['import_chinese']='different'
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_semantic_reason_missing_rejected(self):
  src,e,d=sample();d['rationale']=''
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_changing_effect_rejected(self):
  src,e,d=sample();d['after']='[se:2]correct userName'
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_changing_placeholder_rejected(self):
  src,e,d=sample();d['after']='[se:1]correct'
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_noop_amendment_rejected(self):
  src,e,d=sample();d['after']=d['before']
  with self.assertRaises(ValueError):amend(e,src,[d])
 def test_speaker_edit_rejected(self):
  src,e,d=sample();d.update(address=['story','group_1',0,'nameRight'],before='Name',import_chinese='Name',prior_candidate_text='Name',after='New')
  with self.assertRaises(ValueError):amend(e,src,[d])
if __name__=='__main__':unittest.main()
