"""Read public Reader endpoints and compare actual final-main bytes; no deployment mutation."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import sys,json,gzip,hashlib,collections,urllib.request,urllib.parse,time,datetime
W=Path(__file__).resolve().parent;S=W/'reader';PUB=S/'website/.pages-deploy';REV=(W/'source-revision.txt').read_text().strip();BASE='https://magireader.pages.dev';sys.path.insert(0,str(W));from integrate import save,sha

def public_json(path):
 with urllib.request.urlopen(urllib.request.Request(BASE+path,headers={'Accept-Encoding':'identity','User-Agent':'Reader-Final-Translation-Verification'}),timeout=45) as r:return json.load(r)
def make_plan():
 packet=json.loads(gzip.decompress((W/'kit/docs/story-quality/production-handoff/reader-input-manifest.json.gz').read_bytes()))
 idx=json.loads((PUB/'story_index.json').read_bytes());routes=collections.defaultdict(list);checks={};covered={}
 for st in idx:
  for lang in ['cn','jp']:
   for i,p in enumerate(st.get('json_sources_'+lang,[])):routes[p].append('/api/story-json/'+urllib.parse.quote(str(st['id']),safe='')+'/'+lang+'/'+str(i))
 def add(path,f,kind,source=None):
  raw=f.read_bytes();e={'path':path,'bytes':len(raw),'sha256':sha(raw),'kind':kind}
  if path in checks:assert checks[path]['sha256']==e['sha256']
  else:checks[path]=e
  if source:covered[source]=path
 for e in packet['files']:
  p=e['path']
  if p.endswith('.json'):
   assert routes[p]
   for route in routes[p]:add(route,S/p,'final_reviewed_json',p)
  elif p.startswith('website/public/'):add('/'+p.removeprefix('website/public/'),S/p,'final_reviewed_export',p)
 prior=json.loads(Path(r'D:\magia\deliveries\reader-ui-production-20261003\online-verification-targets.json').read_bytes())
 sources=set(prior['prior_authorized_source_paths'])|{p for p in prior['changed_paths'] if p.startswith('magireco-translate-data-master/') and p.endswith('.json')}
 sources|={r['target_path'] for r in json.loads((S/'manifests/authoritative_scenario_runtime_repairs.v1.json').read_bytes())['entries']}
 for st in idx:
  if st.get('category')=='main_story' and '第II部' in st.get('folder',''):
   sources.update(st.get('json_sources_cn',[]))
   if st.get('path_cn'):add(st['path_cn'],PUB/st['path_cn'].lstrip('/'),'act2_export')
 missing=[]
 for p in sorted(sources):
  if p in covered:continue
  if p.endswith('.json'):
   if routes[p]:add(routes[p][0],S/p,'preserved_source_json',p)
   else:missing.append(p)
  elif p.endswith('.txt'):
   rel=Path(p.split('Scenarios_full/',1)[1]);dest='/data/'+(rel.parent/(rel.stem+'_cn.txt')).as_posix();local=PUB/dest.lstrip('/')
   assert local.is_file() and local.read_bytes()==(S/p).read_bytes(),p
   add(dest,local,'protected_human_export',p)
 for name in ['story_index.json','story_ids.json','story_voice_index.generated.json','story-voice/103105.json','adv-release-build.json','data/machine_translation_manifest.generated.json','search_index_manifest.magireco.json','search_index_manifest.exedra.json']:
  if (PUB/name).is_file():add('/'+name,PUB/name,'index_or_manifest')
 for folder,kind in [('story-json-catalog/v1','catalog_shard'),('story-json-packs','source_pack'),('search-chunks','search_chunk')]:
  for f in sorted((PUB/folder).rglob('*')):
   if f.is_file():add('/'+f.relative_to(PUB).as_posix(),f,kind)
 for st in idx:
  if st.get('category') in ['Scene0主线','exedra_main'] and st.get('json_sources_cn'):
   p=st['json_sources_cn'][0];add(routes[p][0],S/p,'other_game_regression');break
 protected=prior['prior_authorized_source_paths'];assert set(protected)<=set(covered),[p for p in protected if p not in covered]
 plan={'source_revision':REV,'checks':list(checks.values()),'final_targets':361,'authorized_196_all_covered':True,'unindexed_prior_paths_not_public':missing,'categories':dict(collections.Counter(x['kind'] for x in checks.values()))};save('online-plan.json',plan);return plan

def check(e):
 url=BASE+urllib.parse.quote(e['path'],safe='/:?=&%');errors=[]
 for attempt in range(3):
  try:
   start=time.monotonic()
   with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept-Encoding':'gzip','User-Agent':'Reader-Final-Translation-Verification'}),timeout=45) as r:
    data=r.read(max(e['bytes']*2,16*1024*1024)+1);data=gzip.decompress(data) if r.headers.get('Content-Encoding')=='gzip' else data
    assert r.status==200 and not r.headers.get('Content-Range'),'Incomplete response'
    assert sha(data)==e['sha256'] and len(data)==e['bytes'],'Content differs from rebuilt main'
    source=r.headers.get('X-Reader-Source-Revision')
    if e['path'].startswith('/api/story-json/'):assert source==REV,'Wrong serving revision'
    return {**e,'ok':True,'attempts':attempt+1,'earlier_errors':errors,'source_revision':source,'seconds':round(time.monotonic()-start,3)}
  except Exception as exc:
   errors.append(str(exc))
   if attempt<2:time.sleep(attempt+1)
 return {**e,'ok':False,'errors':errors}

def main():
 if sys.argv[-1]=='plan':p=make_plan();print('ONLINE_PLAN',len(p['checks']),p['categories']);return
 p=json.loads((W/'online-plan.json').read_bytes());assert p['source_revision']==REV
 live=public_json('/adv-release-build.json');assert live['source_revision']==REV,'New deployment is not live yet'
 results=[]
 with ThreadPoolExecutor(max_workers=6) as pool:
  futures=[pool.submit(check,e) for e in p['checks']]
  for f in as_completed(futures):
   results.append(f.result())
   if len(results)%100==0:save('online-progress.json',{'source_revision':REV,'results':results});print('VERIFIED',len(results),'/',len(futures),'ERRORS',sum(not r['ok'] for r in results),flush=True)
 assert public_json('/adv-release-build.json')['source_revision']==REV
 output={'source_revision':REV,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'total':len(results),'passed':sum(r['ok'] for r in results),'failed':sum(not r['ok'] for r in results),'retries':sum(r.get('attempts',1)>1 for r in results),'authorized_196_all_covered':p['authorized_196_all_covered'],'categories':p['categories'],'results':results}
 save('online-verification.json',output);print('ONLINE_RESULT',json.dumps({k:v for k,v in output.items() if k!='results'},ensure_ascii=False))
 if output['failed']:print('FAILURES',json.dumps([r for r in results if not r['ok']],ensure_ascii=False));raise SystemExit(1)
 statuses=[]
 for url in ['/api/adv/release','/api/proofreading/config','/api/proofreading/machine-status']:
  d=public_json(url)
  if url=='/api/proofreading/config':assert d['source_revision']==REV,url
  statuses.append({'path':url,'data':d,'matches_expected_revision':d.get('source_revision')==REV})
 save('public-status-prepromotion.json',statuses)
if __name__=='__main__':main()
