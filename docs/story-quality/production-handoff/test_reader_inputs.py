import unittest,copy,json
from reader_inputs import validate_packet,classify,sha,git_blob

def fixture():
 a='{"story":{"group_1":[{"textLeft":"旧文"}]}}'.encode();b='{"story":{"group_1":[{"textLeft":"新文"}]}}'.encode();e={'path':'magireco-translate-data-master/Scenarios_full/event_story/demo/123-1.json','source_blob':git_blob(a),'source_sha256':sha(a),'candidate_blob':git_blob(b),'candidate_sha256':sha(b),'candidate_utf8':b.decode()};p={'kind':'reader_translation_inputs_not_deployment','client_manifest_sha256':'a'*64,'input_count':1,'files':[e]};return a,b,e,p
class Tests(unittest.TestCase):
 def test_valid(self):a,b,e,p=fixture();validate_packet(p)
 def test_stale_not_integrated(self):a,b,e,p=fixture();self.assertEqual(classify(a,e),'staged_only')
 def test_integrated(self):a,b,e,p=fixture();self.assertEqual(classify(b,e),'already_integrated')
 def test_third_version_rejected(self):a,b,e,p=fixture();self.assertRaises(ValueError,classify,a+b,e)
 def test_candidate_tamper(self):a,b,e,p=fixture();e['candidate_utf8']+=' ';self.assertRaises(ValueError,validate_packet,p)
 def test_wrong_baseline_hash(self):a,b,e,p=fixture();e['source_blob']='bad';self.assertRaises(ValueError,validate_packet,p)
 def test_duplicate_path(self):a,b,e,p=fixture();p['files'].append(copy.deepcopy(e));p['input_count']=2;self.assertRaises(ValueError,validate_packet,p)
 def test_traversal(self):a,b,e,p=fixture();e['path']='../a.txt';self.assertRaises(ValueError,validate_packet,p)
 def test_japanese_source_rejected(self):a,b,e,p=fixture();e['path']=e['path'].replace('magireco-translate-data-master','magireco-source-master');self.assertRaises(ValueError,validate_packet,p)
 def test_client_runtime_rejected(self):a,b,e,p=fixture();e['path']='madomagi/resource/scenario/json/adv/scenario_1/123-1.json';self.assertRaises(ValueError,validate_packet,p)
 def test_count_mismatch(self):a,b,e,p=fixture();p['input_count']=99;self.assertRaises(ValueError,validate_packet,p)
 def test_export_text_allowed(self):a,b,e,p=fixture();e['path']='website/public/data/event_story/demo/123_cn.txt';validate_packet(p)
if __name__=='__main__':unittest.main()
