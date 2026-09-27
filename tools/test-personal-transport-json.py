"""Accept formatting only; pin original metadata and reject changed values/ZIPs."""
from pathlib import Path
import hashlib,importlib.util,json,tempfile
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('verify_live',root/'distribution/personal/verify_live.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);value={'version':20,'files':[{'size':33,'sha256':'a'*64}]}
 original=(json.dumps(value,indent=2)+'\n').encode();compact=json.dumps(value,separators=(',',':')).encode()
 row={'bytes':len(original),'sha256':hashlib.sha256(original).hexdigest()}
 mod.EXPECTED={'files':{'test.json':row,'test.zip':row}}
 (p/'test.json').write_bytes(original)
 def check(name,b):return mod.verify_identity(name,len(b),hashlib.sha256(b).hexdigest(),b,p)
 assert check('test.json',original)=='byte-exact'
 assert check('test.json',compact)=='json-equivalent-pinned-source'
 assert check('test.zip',original)=='byte-exact'
 def reject(name,b):
  try:check(name,b)
  except (AssertionError,ValueError):return
  raise AssertionError('unexpected accepted changed content')
 reject('test.json',compact.replace(b'20',b'19',1))
 reject('test.json',b'not-json')
 reject('test.zip',compact)
 (p/'test.json').write_bytes(compact)
 reject('test.json',compact)
print('PASS 7 transport checks: formatting accepted; changed metadata, unpinned source and binary rejected')
