"""Read-only baseline freeze for translation-only work; no release/deploy capabilities."""
from pathlib import Path
import subprocess,json,gzip,datetime,hashlib,collections,urllib.request,sys
W=Path(__file__).resolve().parent;ROOT=W.parent;R=ROOT/'repo';P='A:/StoryQuality-20260930-1739/patch.git';G='A:/StoryQuality-20260930-1739/public.git'
def git(repo,*args):
 return subprocess.check_output(['git',*(['--git-dir='+({'patch':P,'public':G}[repo])] if repo!='reader' else []),*args],cwd=R,timeout=120)
def tree(repo,ref):
 out={}
 for row in git(repo,'ls-tree','-rz',ref).split(b'\0'):
  if row:
   m,p=row.split(b'\t',1);out[p.decode()]=m.split()[2].decode()
 return out
def save(n,o):(W/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
 assert not (W/'bases.json').exists(),'Do not replace frozen baseline'
 refs={x:git(x,'rev-parse','origin/main' if x=='reader' else 'FETCH_HEAD').decode().strip() for x in ['reader','patch','public']}
 assert refs['reader']==git('reader','rev-parse','HEAD').decode().strip()
 for repo,ref in refs.items():save(repo+'-tree.json',tree(repo,ref))
 census=json.loads(gzip.decompress(git('patch','show',refs['patch']+':docs/story-quality/20261002-ai-only-census.json.gz')));save('baseline-census.json',census)
 cs=json.loads(git('patch','show',refs['patch']+':docs/story-quality/contributions/summary.json'));save('baseline-contributions.json',cs)
 assert len(census['scripts'])==1079 and sum(x['complete'] for x in census['scripts'])==694 and cs['confirmed_ai_pending']==385
 for name,args in [('initial-diff.bin',('diff','--binary')),('initial-staged.bin',('diff','--cached','--binary')),('initial-status-z.bin',('status','--porcelain=v1','-z'))]:(W/name).write_bytes(git('reader',*args))
 dirty=git('reader','diff','--name-only','-z').decode().split('\0');save('dirty-tracked-hashes.json',{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in dirty if p})
 # Snapshot all untracked files as well, without exposing user content.
 untracked=git('reader','ls-files','--others','--exclude-standard','-z').decode().split('\0');save('untracked-hashes.json',{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in untracked if p and (R/p).is_file()})
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();save('bases.json',refs|{'frozen_at':now,'task_id':'tsk_e9584d2518500246'})
 observed=[]
 for url in ['https://magireco-personal-release.pages.dev/version_scenario.json','https://github.com/HiiragiNemu/ProgettoMagius-1/releases/download/latest/version_scenario.json','https://magireader.pages.dev/adv-release-build.json','https://magireader.pages.dev/api/adv/release']:
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AI-Translation-Held-Batch-Audit','Accept-Encoding':'identity'}),timeout=45) as res: obj=json.load(res);observed.append({'url':url,'status':res.status,'data':obj})
  except Exception as e:observed.append({'url':url,'error':type(e).__name__+': '+str(e)})
 save('live-baseline.json',{'observed_at':now,'observations':observed,'no_release_mutation':True})
 rt=json.loads((W/'reader-tree.json').read_bytes());allrows=census['scripts'];done=collections.defaultdict(list)
 for row in allrows:
  assert rt[row['path']]==row['current_blob'] and rt[row['jp_path']]==row['jp_blob'],row['path']
  if row['complete']:done[row['jp_blob']].append(row)
 duplicates=[]
 for row in allrows:
  if not row['complete'] and row['jp_blob'] in done:duplicates.append({'target':row,'proven_reviewed_donors':done[row['jp_blob']]})
 save('exact-japanese-reuse-candidates.json',duplicates)
 save('progress.json',{'batch':'20261002-semantic-batch11-ai-only-held','task_id':'tsk_e9584d2518500246','stage':'source_frozen','publication_prohibited':True,'resource_source_writes_prohibited_during_audit':True,'target_version':None,'published_baseline_version':cs['last_published_scenario_version'],'published_completed':694,'published_pending':385,'reviewed':[],'reused':[],'checkpoint':'Frozen source and canonical CN patch ledger; pending translations are kept outside live resource paths and no release/deployment performed'})
 print('BASES',json.dumps(refs));print('LIVE',json.dumps(observed,ensure_ascii=False));print('REUSE_CANDIDATES',len(duplicates),[(Path(x['target']['path']).stem,[Path(z['path']).stem for z in x['proven_reviewed_donors']]) for x in duplicates])
 q=census['next_full_chapter_queue']['queue'];print('NEXT_QUEUE',len(q))
 for x in q[:50]:print(json.dumps({k:v for k,v in x.items() if k not in ['sources','paths','script_paths']},ensure_ascii=False)[:1600])
if __name__=='__main__':main()
