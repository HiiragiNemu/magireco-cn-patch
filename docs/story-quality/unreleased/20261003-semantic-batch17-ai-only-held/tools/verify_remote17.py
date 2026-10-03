"""Independent readback of active/past ledgers, actual remote READY and unchanged production paths."""
from pathlib import Path
import sys,json,gzip,csv,io,hashlib,datetime,urllib.request,time
W=Path(__file__).resolve().parent;sys.path[:0]=[str(W),str(W.parent/'semantic-batch03-20261001')]
from checkpoint import guard,enc
from initialize import git,tree
from census import Store
from client_candidate_tools import preflight
from current_ready_gate import check
from recover_held import inspect

def load(n):return json.loads((W/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def tab(b):return list(csv.DictReader(io.StringIO(b.decode()),delimiter='\t'))
def main():
 guard();rec=load('final-document-commit.json');pointers=load('pointer-final.json');heads={};trees={}
 for repo in ('reader','patch','public'):
  git(repo,'fetch','origin','main');heads[repo]=git(repo,'rev-parse','FETCH_HEAD').decode().strip();trees[repo]=tree(repo,heads[repo])
 ps=Store(patch=True);rs=Store();cur=trees['patch'];root='docs/story-quality/contributions/';kit='docs/story-quality/client-integration/'
 for p,h in rec['files'].items():assert sha(ps.get(cur[p]))==h,p
 for p,h in pointers['reader_hashes'].items():assert sha(rs.get(trees['reader'][p]))==h,p
 for p,h in load('prior-doc-hashes.json').items():assert cur.get(p)==h,p
 oldpt=load('patch-tree.json');oldpub={p:h for p,h in oldpt.items() if p.startswith(root) and not p.startswith(root+'unreleased-') and p not in (root+'README.md',root+'pending-status-with-unreleased.tsv',root+'active-candidate-generations.json')}
 for p,h in oldpub.items():assert cur.get(p)==h,p
 published=json.loads(ps.get(cur[root+'summary.json']));assert published['confirmed_ai_fully_reviewed']==694 and published['confirmed_ai_pending']==385 and published['legacy_unique_registered_ids']==498
 summary=json.loads(ps.get(cur[root+'unreleased-summary.json']));assert summary['unique_pending_targets_prepared']==361 and summary['combined_text_address_changes']==11226 and summary['this_batch_new']==0 and summary['this_batch_new_body_changes']==824 and summary['pending_targets_needing_ai_review']==0 and summary['protected_or_previously_resolved_pending_exceptions']==24
 ready=json.loads(ps.get(cur[kit+'READY.json']));assert ready['manifest_sha256']==rec['manifest_sha256'] and ready['targets']==361 and ready['field_changes']==11226 and not ready['published']
 for name,h in ready['files'].items():assert sha(ps.get(cur[kit+name]))==h,name
 raw=ps.get(cur[ready['manifest']]);assert sha(raw)==ready['manifest_sha256'];packet=json.loads(gzip.decompress(raw));oldpacket=json.loads(gzip.decompress((W/'prior-integration-manifest.json.gz').read_bytes()));oldentries={e['path']:e for e in oldpacket['files']};amended=0
 for e in packet['files']:
  old=oldentries[e['path']];assert e['operations'][:len(old['operations'])]==old['operations']
  if e!=old:amended+=1
 assert amended==235 and sum(len(e['operations']) for e in packet['files'])==11226
 fields=json.loads(gzip.decompress(ps.get(cur[root+'unreleased-field-changes.json.gz'])))['records'];oldfields=json.loads(gzip.decompress((W/'prior-unreleased-field-changes.json.gz').read_bytes()))['records'];assert fields[:10402]==oldfields and len(fields)==11226
 ops={(e['path'],tuple(a)):(b,c) for e in packet['files'] for a,b,c in e['operations']};assert len(ops)==11226
 for r in fields:assert ops[r['player_path'],tuple(r['address'])]==(r['before'],r['after'])
 rows=tab(ps.get(cur[root+'unreleased-scripts.tsv']));oldrows=tab((W/'prior-unreleased-scripts.tsv').read_bytes());assert len(rows)==361 and sum(a!=b for a,b in zip(rows,oldrows))==235
 base=load('baseline-census.json');jpmap={s['path']:s['jp_path'] for s in base['scripts']}
 for r in rows:
  assert trees['reader'][r['reader_path']]==r['source_cn_blob'],r['reader_path']
  assert trees['reader'][jpmap[r['reader_path']]]==r['source_jp_blob']
 for e in packet['files']:assert cur[e['path']]==e['before_blob'],e['path']
 assert cur['configures/js-delta-baseline.json']==oldpt['configures/js-delta-baseline.json']
 staged,pre=preflight('A:/StoryQuality-20260930-1739/patch.git',heads['patch'],packet);assert len(staged)==362 and len(json.loads(staged['configures/js-delta-baseline.json'])['supplemental_product_paths'])==489
 for p,h in rec['snapshot_files'].items():assert sha(ps.get(cur[p]))==h,p
 meta=rec['recovery'];doc,digest=inspect(ps.get(cur[meta['path']]),meta['sha256']);assert len(doc['files'])==meta['files']
 exports=json.loads(gzip.decompress(ps.get(cur['docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/cumulative-reader-exports.json.gz'])));assert len(exports['files'])==240
 for path,f in exports['files'].items():
  assert trees['reader'][path]==f['source_blob'];assert sha(rs.get(f['source_blob']))==f['source_sha256'];assert sha(f['candidate_utf8'].encode())==f['candidate_sha256']
 for repo in ('reader','public'):
  assert not any(p.startswith(('docs/story-quality/contributions/','docs/story-quality/unreleased/','docs/story-quality/client-integration/')) for p in trees[repo]),repo
 own_commits=[]
 for repo in ('reader','patch'):
  lines=git(repo,'log','--format=%H%x09%s',load('bases.json')[repo]+'..'+heads[repo]).decode().splitlines()
  for line in lines:
   c,msg=line.split('\t',1)
   if 'held-batch17' not in msg:continue
   names=[x.decode() for x in git(repo,'diff-tree','--no-commit-id','--name-only','-r','-z',c).split(b'\0') if x]
   assert all(p.startswith('docs/story-quality/') or p=='STORY_QUALITY_HANDOFF.md' for p in names) and '[skip ci]' in msg
   if repo=='reader':assert set(names)<={'STORY_QUALITY_HANDOFF.md','docs/story-quality/CONTINUATION.md','docs/story-quality/CONTINUATION_STATE.json'}
   own_commits.append({'repo':repo,'commit':c,'paths':len(names),'runtime_paths':0})
 remaining=json.loads(ps.get(cur['docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/remaining-status-summary.json']))
 assert remaining['historical_source_pool']==1079 and remaining['actionable_first_review_pending']==0 and remaining['identified_residual_review_pending_fields']==0 and remaining['identified_residual_review_pending_scripts']==0 and remaining['validated_unpublished_targets']==361
 scope_raw=ps.get(cur['docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/scope-status.tsv'])
 assert sha(scope_raw)==remaining['scope_status_tsv_sha256'] and len(tab(scope_raw))==1079
 cov=json.loads(ps.get(cur['docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/sweep-completion-validation.json']))
 ledger_raw=gzip.decompress(ps.get(cur['docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/sweep-review-ledger.json.gz']))
 assert sha(ledger_raw)==cov['ledger_sha256'] and cov['reviewed_fields']==6372 and cov['corrected_fields']==824 and cov['pending_fields']==0
 oldrt=load('reader-tree.json');source_prefixes=('magireco-translate-data-master/Scenarios_full/','magireco-source-master/Scenarios_full/')
 audited=lambda tr:{p:h for p,h in tr.items() if p.startswith(source_prefixes) and p.endswith('.json')}
 assert audited(oldrt)==audited(trees['reader']),'Source inventory changed after audit; refresh before reporting remaining counts'
 for path in ['manifests/authoritative_scenario_variant_repairs.v1.json','manifests/authoritative_scenario_runtime_repairs.v1.json','docs/reader-availability-local-20260929.json']:
  assert oldrt[path]==trees['reader'][path],'Protection source changed'
 assert not any(p.startswith(kit+'CLIENT_RECEIPT') for p in cur),'Client publication receipt appeared; reconcile'
 ps.close();rs.close()
 fresh=check('A:/StoryQuality-20260930-1739/patch.git',W/'client-kit/integration-manifest.json.gz',ready['manifest_sha256']);assert fresh['passed']
 try:check('A:/StoryQuality-20260930-1739/patch.git',W/'prior-integration-manifest.json.gz',rec['previous_manifest_sha256'])
 except ValueError as e:stale=str(e);assert 'Superseded candidate manifest' in stale
 else:raise AssertionError('Same-count stale361 manifest passed current remote gate')
 live=[]
 for url in ['https://magireco-personal-release.pages.dev/version_scenario.json','https://magireco-personal-release.pages.dev/version_js_delta.json','https://github.com/HiiragiNemu/ProgettoMagius-1/releases/download/latest/version_scenario.json','https://magireader.pages.dev/adv-release-build.json','https://magireader.pages.dev/api/adv/release']:
  row={'url':url}
  for attempt in range(2):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Held-Batch17-Readback','Accept-Encoding':'identity'}),timeout=25) as r:data=r.read();row.update(status=r.status,data=json.loads(data),sha256=sha(data));break
   except Exception as error:row['error']=str(error);time.sleep(1)
  live.append(row)
 guard();result={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':True,'heads':heads,'cn_patch_document_hashes_verified':len(rec['files']),'reader_pointer_hashes_verified':3,'historical_published_files_preserved':len(oldpub),'old_snapshot_files_verified':len(rec['snapshot_files']),'old_fields_preserved':10402,'new_fields':824,'total_fields':11226,'existing_candidates_amended':235,'total_candidates':361,'new_full_review_count':0,'all_runtime_sources_still_unapplied':True,'current_READY_gate':fresh,'old_361_manifest_rejected':stale,'same_count_freshness_check_tested_against_real_remote':True,'old694_385_published_ledger_preserved':True,'old498_registered_ids_preserved':True,'exemptions24_preserved':True,'current_delta_proposal_paths':489,'original_delta_production_config_preserved':True,'reader_export_files':240,'reader_and_public_cumulative_copies':0,'recovery_files':meta['files'],'recovery_sha256':digest,'own_doc_only_commits':own_commits,'client_receipt_received':False,'publication_performed':False,'deployment_performed':False,'live_readback_complete':all(r.get('status')==200 for r in live),'live':live,'original_worktree_state_preserved':True}
 result.update(remaining_counts=remaining,residual_sweep_remote_verified=True,residual_fields_reviewed=6372,residual_fields_corrected=824,remaining_scope_files_verified=1079,source_json_inventory_and_protection_unchanged_since_origin_audit=True)
 (W/'final-verification.json').write_bytes(enc(result));print('FINAL_READBACK',json.dumps({k:result[k] for k in ['heads','cn_patch_document_hashes_verified','old_fields_preserved','new_fields','total_fields','total_candidates','new_full_review_count','recovery_files','live_readback_complete']},ensure_ascii=False));print('LIVE',json.dumps([{'url':r['url'],'status':r.get('status'),'version':r.get('data',{}).get('version'),'source_revision':r.get('data',{}).get('source_revision')} for r in live]));print('OLD361_REJECTED',stale)
if __name__=='__main__':main()
