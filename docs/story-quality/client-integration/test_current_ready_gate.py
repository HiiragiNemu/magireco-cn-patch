import unittest,hashlib,json,tempfile
from pathlib import Path
from unittest.mock import patch
from current_ready_gate import validate_identity,check,CANONICAL
DATA=b'candidate bytes';HASH=hashlib.sha256(DATA).hexdigest();REF='a'*40

def ready():return {'canonical_repository':CANONICAL,'manifest_sha256':HASH,'targets':361,'field_changes':10402,'ready_for_client_integration':True}
class Freshness(unittest.TestCase):
 def test_current_identity(self):self.assertTrue(validate_identity(REF,ready(),HASH,DATA)['passed'])
 def test_same_count_old_manifest_rejected(self):
  r=ready();r['manifest_sha256']='b'*64;r['targets']=361
  with self.assertRaisesRegex(ValueError,'Superseded'):validate_identity(REF,r,HASH,DATA)
 def test_wrong_local_bytes_rejected(self):
  with self.assertRaisesRegex(ValueError,'bytes'):validate_identity(REF,ready(),HASH,DATA+b'old')
 def test_wrong_authority(self):
  r=ready();r['canonical_repository']='another/repo'
  with self.assertRaisesRegex(ValueError,'authority'):validate_identity(REF,r,HASH,DATA)
 def test_not_ready(self):
  r=ready();r['ready_for_client_integration']=False
  with self.assertRaisesRegex(ValueError,'not ready'):validate_identity(REF,r,HASH,DATA)
 def test_bad_hash(self):
  with self.assertRaisesRegex(ValueError,'SHA'):validate_identity(REF,ready(),'latest',DATA)
 def test_bad_remote_ref(self):
  with self.assertRaisesRegex(ValueError,'revision'):validate_identity('main',ready(),HASH,DATA)
 def test_remote_moves_during_read(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'manifest.gz';p.write_bytes(DATA)
   responses=[('https://github.com/'+CANONICAL+'.git').encode(),(REF+'\trefs/heads/main\n').encode(),json.dumps(ready()).encode(),('b'*40+'\trefs/heads/main\n').encode()]
   with patch('current_ready_gate.git',side_effect=responses):
    with self.assertRaisesRegex(ValueError,'moved'):check(d,p,HASH)
 def test_old_local_objects_do_not_fallback(self):
  responses=[('https://github.com/'+CANONICAL+'.git').encode(),(REF+'\trefs/heads/main\n').encode(),RuntimeError('missing object')]
  with patch('current_ready_gate.git',side_effect=responses):
   with self.assertRaisesRegex(ValueError,'refresh main'):check('repo','no-use.gz',HASH)
 def test_noncanonical_origin_rejected(self):
  with patch('current_ready_gate.git',return_value=b'https://github.com/another/repo.git'):
   with self.assertRaisesRegex(ValueError,'canonical'):check('repo','no-use.gz',HASH)
if __name__=='__main__':unittest.main()
