"""Full HTTP body verification for the personal publication endpoint."""
import hashlib,json,pathlib,urllib.request,concurrent.futures,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE='https://magireco-personal-release.pages.dev/'
EXPECTED=json.loads((ROOT/'configures/finalized-localization-assets.json').read_text(encoding='utf-8'))
def verify_identity(name,size,digest,body=None,payload=ROOT/'payload'):
 row=EXPECTED['files'][name]
 if size==row['bytes'] and digest==row['sha256']: return 'byte-exact'
 # Pages validates JSON and reserializes it. Validate the pinned original bytes
 # first, then compare complete JSON values; ZIP bodies remain byte-exact.
 assert name.endswith('.json') and body is not None,(name,size,digest)
 original=(payload/name).read_bytes()
 assert len(original)==row['bytes'] and hashlib.sha256(original).hexdigest()==row['sha256'],('unverified reference',name)
 assert json.loads(body)==json.loads(original),('metadata changed',name)
 return 'json-equivalent-pinned-source'

def verify(name):
 row=EXPECTED['files'][name]
 q=urllib.request.Request(BASE+name+'?verify='+str(time.time_ns()),headers={'User-Agent':'MadeInMagius-Release-Verify','Accept-Encoding':'identity'})
 h=hashlib.sha256();size=0;chunks=[] if name.endswith('.json') else None
 with urllib.request.urlopen(q,timeout=120) as f:
  assert f.status==200,(name,f.status)
  while b:=f.read(4*1024*1024):
   h.update(b);size+=len(b)
   if chunks is not None:chunks.append(b)
 mode=verify_identity(name,size,h.hexdigest(),b''.join(chunks) if chunks is not None else None)
 print('HTTP_FULL_BODY_PASS',name,flush=True);return dict(name=name,bytes=size,sha256=h.hexdigest(),status='PASS',comparison=mode)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(verify,EXPECTED['files']))
 pathlib.Path('personal-live-verification.json').write_text(json.dumps(dict(status='PASS',source_commit=EXPECTED['source_commit'],objects=rows),indent=2),encoding='utf-8')

