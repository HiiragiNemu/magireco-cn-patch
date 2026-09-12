"""Full HTTP body verification for the personal publication endpoint."""
import hashlib,json,pathlib,urllib.request,concurrent.futures,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE='https://magireco-personal-release.pages.dev/'
EXPECTED=json.loads((ROOT/'configures/finalized-localization-assets.json').read_text(encoding='utf-8'))
def verify(name):
 row=EXPECTED['files'][name]
 q=urllib.request.Request(BASE+name+'?verify='+str(time.time_ns()),headers={'User-Agent':'MadeInMagius-Release-Verify','Accept-Encoding':'identity'})
 h=hashlib.sha256();size=0
 with urllib.request.urlopen(q,timeout=120) as f:
  assert f.status==200,(name,f.status)
  while b:=f.read(4*1024*1024):h.update(b);size+=len(b)
 assert size==row['bytes'] and h.hexdigest()==row['sha256'],(name,size,h.hexdigest())
 print('HTTP_FULL_BODY_PASS',name,flush=True);return dict(name=name,bytes=size,sha256=h.hexdigest(),status='PASS')
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(verify,EXPECTED['files']))
 pathlib.Path('personal-live-verification.json').write_text(json.dumps(dict(status='PASS',source_commit=EXPECTED['source_commit'],objects=rows),indent=2),encoding='utf-8')

