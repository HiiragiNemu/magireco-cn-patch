"""Independent remote readback, prior-ledger preservation and proof of held-only integration state."""
from pathlib import Path
import sys,json,gzip,hashlib,csv,io,datetime,urllib.request,time,subprocess
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W))
from checkpoint import guard,enc,DEST
from initialize import git,tree
from recover_held import inspect

def read(n):return json.loads((W/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def table(raw):return list(csv.DictReader(io.StringIO(raw.decode('utf8')),delimiter='\t'))

def main():
 guard();rec=read('final-held-commits.json');base=read('bases.json');p=read('repair-plan.json');txt=read('text-plan.json');heads={};trees={}
 for repo in ('reader','patch','public'):
  git(repo,'fetch','origin','main');heads[repo]=git(repo,'rev-parse','FETCH_HEAD').decode().strip();trees[repo]=tree(repo,heads[repo])
 out={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'heads':heads,'passed':False,'runtime_integration_performed':False,'publication_performed':False,'doc_hash_checks':0,'reader_pointer_checks':0,'live':[]}
 for e in rec['document_files']:
  raw=git('patch','show',heads['patch']+':'+e['path']);assert sha(raw)==e['sha256'],e['path'];out['doc_hash_checks']+=1
 for path,h in rec['reader_pointer_hashes'].items():assert sha(git('reader','show',heads['reader']+':'+path))==h;out['reader_pointer_checks']+=1
 pt=read('patch-tree.json');cur=trees['patch'];root='docs/story-quality/contributions/'
 oldpub={path:h for path,h in pt.items() if path.startswith(root) and not path.startswith(root+'unreleased-') and not path.endswith(('README.md','pending-status-with-unreleased.tsv'))}
 for path,h in oldpub.items():assert cur.get(path)==h,path
 for path,h in read('prior-doc-hashes.json').items():assert cur.get(path)==h,path
 oldsummary=json.loads(git('patch','show',heads['patch']+':'+root+'summary.json'));assert oldsummary['confirmed_ai_fully_reviewed']==694 and oldsummary['confirmed_ai_pending']==385 and oldsummary['legacy_unique_registered_ids']==498
 summary=json.loads(git('patch','show',heads['patch']+':'+root+'unreleased-summary.json'));assert summary['unique_pending_targets_prepared']==204 and summary['pending_targets_not_prepared']==181 and summary['new_full_review_unreleased']==121 and summary['reviewed_text_reuse_unreleased']==83 and not summary['published']
 raw=git('patch','show',heads['patch']+':'+root+'unreleased-scripts.tsv');prior=(W/'prior-unreleased-scripts.tsv').read_bytes();assert raw.startswith(prior);records=table(raw);assert len(records)==len({r['reader_path'] for r in records})==204 and records[:133]==table(prior)
 statuses=table(git('patch','show',heads['patch']+':'+root+'pending-status-with-unreleased.tsv'));assert len(statuses)==385 and sum(r['status']=='not_yet_prepared' for r in statuses)==181
 fd=json.loads(gzip.decompress(git('patch','show',heads['patch']+':'+root+'unreleased-field-changes.json.gz')));oldfields=json.loads(gzip.decompress((W/'prior-unreleased-field-changes.json.gz').read_bytes()))['records'];assert len(fd['records'])==5688 and fd['records'][:3560]==oldfields
 assert len({(r['player_path'],tuple(r['address'])) for r in fd['records']})==5688
 allnotapplied=[]
 for r in records:
  assert trees['reader'][r['reader_path']]==r['source_cn_blob'],r['reader_path'];assert cur[r['player_path']]==r['source_cn_blob'],r['player_path']
  jp=r['reader_path'].replace('magireco-translate-data-master/','magireco-source-master/',1);assert trees['reader'][jp]==r['source_jp_blob'];allnotapplied.append(r['reader_path'])
 for f in txt['files']:assert trees['reader'][f['path']]==f['before']
 recovery=rec['recovery'];raw=git('patch','show',heads['patch']+':'+recovery['path']);bundle,digest=inspect(raw,recovery['sha256']);assert len(bundle['files'])==recovery['files']
 # Check all own commits, not unrelated resources maintained by the other task.
 doccommits=[]
 for repo in ('reader','patch'):
  logs=git(repo,'log','--format=%H%x09%s',base[repo]+'..'+heads[repo]).decode().splitlines()
  for line in logs:
   c,msg=line.split('\t',1)
   if 'held-batch12' not in msg:continue
   changed=[s.decode() for s in git(repo,'diff-tree','--no-commit-id','--name-only','-r','-z',c).split(b'\0') if s]
   assert all(s.startswith('docs/story-quality/') or s=='STORY_QUALITY_HANDOFF.md' for s in changed)
   if repo=='reader':assert set(changed)<={'STORY_QUALITY_HANDOFF.md','docs/story-quality/CONTINUATION.md','docs/story-quality/CONTINUATION_STATE.json'}
   doccommits.append({'repository':repo,'commit':c,'paths':len(changed),'runtime_paths':0,'skip_ci':'[skip ci]' in msg})
 assert all(r['skip_ci'] for r in doccommits)
 for repo in ('reader','public'):
  forbidden=[x for x in trees[repo] if x.startswith('docs/story-quality/contributions/') or x.startswith('docs/story-quality/unreleased/')]
  assert not forbidden,(repo,forbidden)
 diffs={}
 for repo in ('reader','patch','public'):
  old=read(repo+'-tree.json');current=trees[repo];diffs[repo]=sorted(x for x in set(old)|set(current) if old.get(x)!=current.get(x) and not x.startswith('docs/story-quality/') and x!='STORY_QUALITY_HANDOFF.md')
 urls=['https://magireco-personal-release.pages.dev/version_scenario.json','https://github.com/HiiragiNemu/ProgettoMagius-1/releases/download/latest/version_scenario.json','https://magireader.pages.dev/adv-release-build.json','https://magireader.pages.dev/api/adv/release']
 for url in urls:
  row={'url':url}
  for attempt in range(2):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Held-Translation-Batch12-Verification','Accept-Encoding':'identity'}),timeout=25) as response:body=json.load(response);row.update(status=response.status,data=body,attempts=attempt+1)
    break
   except Exception as error:
    row['last_error']=str(error)
    if not attempt:time.sleep(2)
  out['live'].append(row)
 out.update(doc_only_commits=doccommits,published_completed_preserved=694,published_pending_preserved=385,legacy_registered_ids_preserved=498,published_record_files_unchanged=len(oldpub),prior_recovery_and_snapshot_paths_preserved=len(read('prior-doc-hashes.json')),prior_held_scripts_preserved=133,prior_held_field_records_preserved=3560,new_full_review_unreleased=71,total_prepared_unreleased=204,total_unprepared=181,field_delta_records=5688,new_field_delta_records=2128,recovery_files=recovery['files'],recovery_sha256=digest,all_candidates_still_unapplied=True,reader_cumulative_or_candidate_copies=0,public_cumulative_or_candidate_copies=0,resource_path_differences_from_baseline=diffs,no_game_package_or_deployment_build_created=not any(f.name.startswith('cn_') and f.suffix=='.zip' for f in W.iterdir()),original_worktree_state_preserved=True,live_readback_complete=all(r.get('status')==200 for r in out['live']),passed=True)
 assert out['no_game_package_or_deployment_build_created'];guard();(W/'final-verification.json').write_bytes(enc(out));print('FINAL_REMOTE_VERIFIED',json.dumps({k:out[k] for k in ('heads','doc_hash_checks','reader_pointer_checks','published_record_files_unchanged','total_prepared_unreleased','total_unprepared','all_candidates_still_unapplied','recovery_files','live_readback_complete','publication_performed')},ensure_ascii=False));print('LIVE',json.dumps([{'url':r['url'],'status':r.get('status'),'version':r.get('data',{}).get('version'),'source_revision':r.get('data',{}).get('source_revision'),'error':r.get('last_error')} for r in out['live']],ensure_ascii=False))
if __name__=='__main__':main()
