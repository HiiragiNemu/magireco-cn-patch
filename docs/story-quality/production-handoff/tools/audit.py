"""Read-only current-source, translation-scope and deployed Reader audit. No publication."""
from pathlib import Path
import sys, subprocess, json, gzip, hashlib, csv, io, datetime, urllib.request, time, collections
W=Path(__file__).resolve().parent;ROOT=W.parent;R=ROOT/'repo';PREV=ROOT/'semantic-batch17-ai-only-held-20261003';P='A:/StoryQuality-20260930-1739/patch.git';G='A:/StoryQuality-20260930-1739/public.git'
sys.path.insert(0,str(PREV))
from checkpoint import guard
from exact_json import apply,blob

def git(repo,*args):
 cmd=['git',*(['--git-dir='+{'patch':P,'public':G}[repo]] if repo!='reader' else ['-C',str(R)]),*args]
 cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
 if cp.returncode:raise RuntimeError(cp.stderr.decode(errors='replace'))
 return cp.stdout

def tree(repo,ref):
 d={}
 for row in git(repo,'ls-tree','-rz',ref).split(b'\0'):
  if row:m,p=row.split(b'\t',1);d[p.decode()]=m.split()[2].decode()
 return d

def enc(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def save(n,x):
 p=W/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(enc(x))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(n):return json.loads((W/n).read_bytes())
def get(url,name):
 errors=[]
 for a in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Story-Production-Readiness-Audit','Accept-Encoding':'identity'}),timeout=40) as res:raw=res.read();status=res.status
   (W/name).parent.mkdir(parents=True,exist_ok=True);(W/name).write_bytes(raw)
   return {'url':url,'status':status,'sha256':sha(raw),'bytes':len(raw),'saved':name,'attempts':a+1,'prior_errors':errors}
  except Exception as exc:errors.append(str(exc));time.sleep(a+1)
 return {'url':url,'errors':errors,'status':None}

def main():
 guard();refs={};trees={}
 for repo in ('reader','patch','public'):
  git(repo,'fetch','origin','main');refs[repo]=git(repo,'rev-parse','FETCH_HEAD').decode().strip();trees[repo]=tree(repo,refs[repo]);save(repo+'-tree.json',trees[repo])
 save('bases.json',refs)
 paths={
  'ready.json':'docs/story-quality/client-integration/READY.json',
  'scope-status.tsv':'docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/scope-status.tsv',
  'remaining-status-summary.json':'docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/remaining-status-summary.json',
  'unreleased-summary.json':'docs/story-quality/contributions/unreleased-summary.json',
  'active-candidate-generations.json':'docs/story-quality/contributions/active-candidate-generations.json',
 }
 for n,p in paths.items():
  if p not in trees['patch']:
   candidates=[x for x in trees['patch'] if x.endswith('/'+n) and 'batch17' in x]
   assert len(candidates)==1,(n,candidates);p=candidates[0];paths[n]=p
  (W/n).write_bytes(git('patch','show',refs['patch']+':'+p))
 ready=read('ready.json');kit=W/'client-kit';kit.mkdir(exist_ok=True)
 for n,h in ready['files'].items():
  raw=git('patch','show',refs['patch']+':docs/story-quality/client-integration/'+n);assert sha(raw)==h,n;(kit/n).write_bytes(raw)
 (kit/'READY.json').write_bytes((W/'ready.json').read_bytes());packet=json.loads(gzip.decompress((kit/'integration-manifest.json.gz').read_bytes()));assert sha((kit/'integration-manifest.json.gz').read_bytes())==ready['manifest_sha256']
 active={x['reader_path']:x for x in read('active-candidate-generations.json')['files']};assert len(active)==ready['targets']==361
 rows=list(csv.DictReader(io.StringIO((W/'scope-status.tsv').read_text(encoding='utf8')),delimiter='\t'));save('scope-columns.json',{'columns':list(rows[0]),'sample':rows[0]})
 statuses=collections.Counter(x['status'] for x in rows);assert len(rows)==len({x.get('reader_path',x.get('path')) for x in rows})==1079
 oldtree=json.loads((PREV/'reader-tree.json').read_bytes());cn=lambda p:p.startswith('magireco-translate-data-master/Scenarios_full/') and p.endswith('.json')
 oldcn={p:h for p,h in oldtree.items() if cn(p)};newcn={p:h for p,h in trees['reader'].items() if cn(p)}
 changes=[p for p in oldcn.keys()|newcn.keys() if oldcn.get(p)!=newcn.get(p)]
 candidate_states=[];reader_entries=[]
 for e in packet['files']:
  p=e['reader_path'];a=active[p];raw=git('reader','show',refs['reader']+':'+p);candidate=apply(raw,e['operations']);assert blob(candidate)==a['current_reader_candidate_blob'],p
  out=W/'reader-inputs'/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(candidate)
  reader_entries.append({'path':p,'source_blob':blob(raw),'source_sha256':sha(raw),'candidate_blob':blob(candidate),'candidate_sha256':sha(candidate),'operations':e['operations'],'candidate_utf8':candidate.decode('utf8'),'player_path':e['path'],'player_candidate_blob':e['after_blob'],'player_candidate_sha256':e['after_sha256']})
  candidate_states.append({'path':p,'current_blob':blob(raw),'candidate_blob':blob(candidate),'state':'same_bytes_no_change_required' if raw==candidate else 'not_integrated','player_state':'same_bytes_no_change_required' if trees['patch'][e['path']]==e['after_blob'] else 'not_integrated'})
 save('reader-candidates.json',{'client_manifest_sha256':ready['manifest_sha256'],'reader_base':refs['reader'],'published':False,'runtime_applied':False,'files':reader_entries});save('candidate-integration-status.json',candidate_states)
 exportpath='docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/cumulative-reader-exports.json.gz'
 assert exportpath in trees['patch'];raw=git('patch','show',refs['patch']+':'+exportpath);(W/'cumulative-reader-exports.json.gz').write_bytes(raw);exports=json.loads(gzip.decompress(raw));assert len(exports['files'])==240
 for p,e in exports['files'].items():
  assert trees['reader'][p]==e['source_blob'],p;b=e['candidate_utf8'].encode();assert blob(b)==e['candidate_blob'] and sha(b)==e['candidate_sha256'];f=W/'reader-inputs'/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
 urls=[('https://magireader.pages.dev/adv-release-build.json','live/build.json'),('https://magireader.pages.dev/api/adv/release','live/adv.json'),('https://magireader.pages.dev/api/proofreading/config','live/config.json'),('https://magireader.pages.dev/story_index.json','live/story_index.json'),('https://magireader.pages.dev/search_index_manifest.magireco.json','live/search-manifest.json'),('https://magireco-personal-release.pages.dev/version_scenario.json','live/scenario-version.json'),('https://magireco-personal-release.pages.dev/version_js_delta.json','live/delta-version.json')]
 results=[get(u,n) for u,n in urls];save('live-http.json',results);assert all(x['status']==200 for x in results),results
 index=read('live/story_index.json');mapping=collections.defaultdict(list)
 for story in index:
  for i,p in enumerate(story.get('json_sources_cn',[])):mapping[p].append({'story_id':story['id'],'index':i})
 save('reader-target-routes.json',{p:mapping[p] for p in active})
 checks=[]
 for prefix in ('512710-1_','513510-1','710044-1','521110-9_','420131-1'):
  matches=[e for e in reader_entries if Path(e['path']).stem.startswith(prefix) and mapping[e['path']]]
  if not matches:continue
  e=matches[0];m=mapping[e['path']][0];url='https://magireader.pages.dev/api/story-json/'+urllib.parse.quote(str(m['story_id']),safe='')+'/cn/'+str(m['index']);item=get(url,'live/body-'+Path(e['path']).name)
  if item['status']==200:
   raw=(W/item['saved']).read_bytes();item.update(path=e['path'],matches_current_unintegrated_source=sha(raw)==e['source_sha256'],matches_final_candidate=sha(raw)==e['candidate_sha256'],expected_final_sha256=e['candidate_sha256'])
  checks.append(item)
 save('live-body-checks.json',checks)
 receipt_paths=[p for p in trees['patch'] if 'CLIENT_RECEIPT' in p.upper() and 'history/' not in p]
 summary={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'references':refs,'ready_manifest_sha256':ready['manifest_sha256'],'scope_counts':dict(statuses),'scope_total':1079,'known_first_review_pending':read('remaining-status-summary.json')['actionable_first_review_pending'],'known_residual_pending_fields':read('remaining-status-summary.json')['identified_residual_review_pending_fields'],'cn_inventory_count':len(newcn),'cn_inventory_changes_since_last_source_audit':changes,'reader_candidate_states':dict(collections.Counter(x['state'] for x in candidate_states)),'client_candidate_states':dict(collections.Counter(x['player_state'] for x in candidate_states)),'exports_ready':len(exports['files']),'source_bound_reader_inputs':len(reader_entries)+len(exports['files']),'client_receipt_paths':receipt_paths,'live_reader_source':read('live/build.json')['source_revision'],'live_reader_deployment':read('live/adv.json')['deployment'],'live_reader_story_count':len(index),'mapped_targets':sum(bool(mapping[p]) for p in active),'unmapped_targets':[p for p in active if not mapping[p]],'live_body_checks':checks,'published':False,'runtime_modified':False,'index_rebuilt_for_candidates':False}
 save('audit-summary.json',summary);save('canonical-paths.json',paths);guard();print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
