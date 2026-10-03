import copy
import hashlib
import unittest
from sweep_contract import encoded, validate_coverage


def fixture():
    source = [{'sweep_id': i, 'id': 'a', 'ordinal': i, 'address': ['story','g',i,'textLeft'], 'jp': '日本語'+str(i), 'cn': '旧译'+str(i)} for i in range(2)]
    rows = [{'sweep_id': i, 'id': 'a', 'ordinal': i, 'address': x['address'], 'japanese': x['jp'], 'prior_candidate': x['cn'], 'disposition': 'retain' if i == 0 else 'correct', 'after': x['cn'] if i == 0 else '新译', 'rationale': '已对照原文'} for i,x in enumerate(source)]
    part = {'slice_sha256': hashlib.sha256(encoded(source)).hexdigest(), 'rows': rows}
    return source, [part]


class SweepCoverageTests(unittest.TestCase):
    def test_exact_complete_set(self):
        s,p=fixture();r=validate_coverage(s,p);self.assertEqual((r['reviewed_fields'],r['corrected_fields'],r['retained_fields'],r['pending_fields']),(2,1,1,0))
    def test_missing_rows_rejected(self):
        s,p=fixture();p[0]['rows']=p[0]['rows'][:1];p[0]['slice_sha256']=hashlib.sha256(encoded(s[:1])).hexdigest()
        with self.assertRaises(ValueError):validate_coverage(s,p)
    def test_incomplete_can_only_be_reported_incomplete(self):
        s,p=fixture();p[0]['rows']=p[0]['rows'][:1];p[0]['slice_sha256']=hashlib.sha256(encoded(s[:1])).hexdigest();r=validate_coverage(s,p,False);self.assertEqual(r['pending_fields'],1);self.assertFalse(r['passed'])
    def test_duplicate_slice_rejected(self):
        s,p=fixture()
        with self.assertRaises(ValueError):validate_coverage(s,p+p)
    def test_source_hash_rejected(self):
        s,p=fixture();p[0]['slice_sha256']='0'*64
        with self.assertRaises(ValueError):validate_coverage(s,p)
    def test_moved_address_rejected(self):
        s,p=fixture();p=copy.deepcopy(p);p[0]['rows'][0]['address'][2]=42
        with self.assertRaises(ValueError):validate_coverage(s,p)
    def test_japanese_drift_rejected(self):
        s,p=fixture();p[0]['rows'][1]['japanese']='別の台詞'
        with self.assertRaises(ValueError):validate_coverage(s,p)
    def test_candidate_text_drift_rejected(self):
        s,p=fixture();p[0]['rows'][1]['prior_candidate']='未知版本'
        with self.assertRaises(ValueError):validate_coverage(s,p)
    def test_changed_retained_text_rejected(self):
        s,p=fixture();p[0]['rows'][0]['after']='擅自修改'
        with self.assertRaises(ValueError):validate_coverage(s,p)
    def test_missing_rationale_rejected(self):
        s,p=fixture();p[0]['rows'][1]['rationale']=''
        with self.assertRaises(ValueError):validate_coverage(s,p)


if __name__ == '__main__': unittest.main()
