"""Independent readback of held-only documentation, unchanged runtime data and live release pointers."""
from pathlib import Path
import sys,json,gzip,hashlib,csv,io,datetime,urllib.request,time,subprocess
W=Path(__file__).resolve().parent;R=W.parent/'repo';sys.path.insert(0,str(W));from checkpoint import guard,git,tree,enc,DEST
from recover_held import inspect

def read(n):return json.loads((W/n).read_bytes())
def obj(repo,ref,path):return json.loads(git(repo,'show',ref+':'+path))
def main():
 guard();rec=read('final-held-commits.json');base=read('bases.json');p=read('repair-plan.json');t=read('text-plan.json');out={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'heads':{},'doc_hash_checks':0,'publication_performed':False,'runtime_integration_performed':False,'live':[],'doc_only_commits':[]}
 current={}
 for repo in ['reader','patch']:
  git(repo,'fetch','origin','main');h=git(repo,'rev-parse','FETCH_HEAD').decode().strip();current[repo]=tree(repo,h);out['heads'][repo]=h
  logs=git(repo,'log','--format=%H%x09%s',base[repo]+'..'+h).decode().splitlines()
  for row in logs:
   c,msg=row.split('\t',1)
   if 'held-batch11' not in msg:continue
   changed=[x.decode() for x in git(repo,'diff-tree','--no-commit-id','--name-only','-r','-z',c).split(b'\0') if x]
   assert all(x.startswith('docs/story-quality/') or x=='STORY_QUALITY_HANDOFF.md' for x in changed),(repo,c,changed)
   out['doc_only_commits'].append({'repository':repo,'commit':c,'paths':len(changed),'runtime_paths':0})
 ph=out['heads']['patch'];root='docs/story-quality/contributions/'
 for item in rec['document_files']:
  raw=git('patch','show',ph+':'+item['path']);assert hashlib.sha256(raw).hexdigest()==item['sha256'],item['path'];out['doc_hash_checks']+=1
 assert current['patch'][root+'summary.json']==rec['published_summary_unchanged_blob'] and current['patch'][root+'ledger.json.gz']==rec['published_ledger_unchanged_blob']
 old=read('patch-tree.json');preserved=[x for x in old if x.startswith(root) and x!=root+'README.md']
 assert all(current['patch'].get(x)==old[x] for x in preserved)
 original_summary=obj('patch',ph,root+'summary.json');assert original_summary['confirmed_ai_fully_reviewed']==694 and original_summary['confirmed_ai_pending']==385 and original_summary['legacy_unique_registered_ids']==498
 s=obj('patch',ph,root+'unreleased-summary.json');rows=list(csv.DictReader(io.StringIO(git('patch','show',ph+':'+root+'unreleased-scripts.tsv').decode()),delimiter='\t'));pending=list(csv.DictReader(io.StringIO(git('patch','show',ph+':'+root+'pending-status-with-unreleased.tsv').decode()),delimiter='\t'))
 assert len(rows)==len({r['reader_path'] for r in rows})==133 and len(pending)==385
 assert sum(r['mode']=='fresh_full_review' for r in rows)==50 and sum(r['mode']=='exact_reviewed_text_reuse' for r in rows)==83 and sum(r['status']=='not_yet_prepared' for r in pending)==252
 assert sum(int(r['body_changes']) for r in rows if r['mode']=='fresh_full_review')==1425 and sum(int(r['body_changes']) for r in rows if r['mode']=='exact_reviewed_text_reuse')==2121 and sum(int(r['choice_changes']) for r in rows)==14
 fields=json.loads(gzip.decompress(git('patch','show',ph+':'+root+'unreleased-field-changes.json.gz')));assert len(fields['records'])==3560 and not fields['published']
 raw=git('patch','show',ph+':'+rec['recovery']['path']);bundle,digest=inspect(raw,rec['recovery']['sha256']);assert len(bundle['files'])==1835
 out.update(published_completed_preserved=694,published_pending_preserved=385,legacy_registered_ids_preserved=498,published_record_files_unchanged=len(preserved),new_full_review_unreleased=50,exact_source_reuse_unreleased=83,prepared_unique_targets=133,remaining_not_prepared=252,choice_corrections=14,field_delta_records=3560,recovery_files=1835,recovery_sha256=digest)
 for path,h in p['inputs'].items():assert current['reader'].get(path)==h,('Reader source drift',path)
 for path,h in t['inputs'].items():assert current['reader'].get(path)==h,('TXT source drift',path)
 for spec in p['runtime_files']:assert current['patch'].get(spec['path'])==spec['before'],('Player source unexpectedly applied',spec['path'])
 for spec in p['reader_files']:assert current['reader'].get(spec['path'])==spec['before'],('Reader source unexpectedly applied',spec['path'])
 out['all_candidates_still_unapplied']=True
 forbidden=[path for path in current['reader'] if path.startswith(DEST) or '/contributions/' in path or path.endswith('ai-only-census.json.gz')];assert not forbidden;out['reader_cumulative_or_candidate_copies']=0
 pg='A:/StoryQuality-20260930-1739/public.git';subprocess.run(['git','--git-dir='+pg,'fetch','origin','main'],cwd=R,check=True,capture_output=True,timeout=90);pub=subprocess.check_output(['git','--git-dir='+pg,'rev-parse','FETCH_HEAD'],cwd=R).decode().strip();out['heads']['public']=pub
 pubpaths=subprocess.check_output(['git','--git-dir='+pg,'ls-tree','-rz','--name-only',pub],cwd=R).decode().split('\0');assert not [x for x in pubpaths if x.startswith(DEST) or x.startswith(root)];out['public_cumulative_or_candidate_copies']=0;out['public_head_unchanged_from_baseline']=pub==base['public']
 out['resource_path_differences_from_baseline']={}
 for repo in ['reader','patch']:
  prior=read(repo+'-tree.json');out['resource_path_differences_from_baseline'][repo]=[x for x in set(prior)|set(current[repo]) if prior.get(x)!=current[repo].get(x) and not x.startswith('docs/story-quality/') and x!='STORY_QUALITY_HANDOFF.md']
  # Other authorized audit work may advance unrelated resources; never overwrite or attribute it to this batch.
 baseline={x['url']:x for x in read('live-baseline.json')['observations']}
 for url,b in baseline.items():
  last=None
  for attempt in range(3):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Held-Translation-Readback-No-Publication','Accept-Encoding':'identity'}),timeout=45) as r: data=json.load(r);status=r.status
    break
   except Exception as e:
    last=str(e)
    if attempt==2:raise
    time.sleep(2)
  check={'url':url,'status':status,'attempts':attempt+1}
  if 'version_scenario' in url:
   check['version']=data['version'];check['size']=data['size'];check['md5']=data['md5'];check['unchanged_from_baseline']=data==b['data']
  else:
   check['source_revision']=data['source_revision'];check['unchanged_from_baseline']=data['source_revision']==b['data']['source_revision']
   if 'deployment' in data:check['deployment']=data['deployment'];check['unchanged_from_baseline']=check['unchanged_from_baseline'] and data['deployment']==b['data']['deployment']
  out['live'].append(check)
 assert not list(W.glob('cn_*.zip')) and not (W/'delivery').exists();out['no_game_package_or_deployment_build_created']=True;guard();out['original_worktree_state_preserved']=True;out['passed']=True;(W/'final-verification.json').write_bytes(enc(out));print('HELD_FINAL_INDEPENDENT_PASS',json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
