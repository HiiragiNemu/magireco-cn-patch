"""Stage coherent active ledgers and immutable prior evidence, then commit CN patch documents only."""
from pathlib import Path
import sys,json,gzip,csv,io,collections,hashlib,datetime,re,shutil
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W))
from checkpoint import guard,commit,git,tree,enc,DEST,BATCH
from exact_json import apply,blob
from client_candidate_tools import preflight

def load(n):return json.loads((W/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def table(b):return list(csv.DictReader(io.StringIO(b.decode('utf8')),delimiter='\t'))
def tsv(rows,keys):
 o=io.StringIO(newline='');wr=csv.DictWriter(o,fieldnames=keys,delimiter='\t',lineterminator='\n',extrasaction='raise');wr.writeheader();wr.writerows(rows);return o.getvalue().encode()
def main():
 guard();assert not (W/'final-document-commit.json').exists(),'Already finalized; perform independent readback'
 ready=load('client-kit/READY.json');packet=json.loads(gzip.decompress((W/'client-kit/integration-manifest.json.gz').read_bytes()));proof=load('amendment-proof.json');gens=load('candidate-generations.json');validation=load('amendment-validation.json');parser=load('parser-validation.json');export=load('cumulative-reader-exports-metadata.json');txt=load('text-plan.json');origin=load('origin-refresh-summary.json');now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 assert validation['passed'] and parser['passed'] and len(parser['files'])==235 and export['passed'] and not txt['holds'] and not txt['missing']
 test=(W/'tests-final-87.log').read_bytes();assert b'Ran 87 tests' in test and b'\nOK' in test and b'FAILED' not in test
 for r in parser['files']:
  for folder,key in [('prior-stage','before_sha256'),('stage','after_sha256')]:assert sha((W/folder/'reader'/r['path']).read_bytes())==r[key]
 assert sha((W/'cumulative-reader-exports.json.gz').read_bytes())==export['sha256']
 olddoc=json.loads(gzip.decompress((W/'prior-unreleased-field-changes.json.gz').read_bytes()));oldfields=olddoc['records'];newfields=load('new-field-records.json');combined=oldfields+newfields;assert len(oldfields)==10402 and len(newfields)==824 and len(combined)==11226 and combined[:10402]==oldfields
 entries={e['path']:e for e in packet['files']};ops={(e['path'],tuple(a)):(b,c) for e in packet['files'] for a,b,c in e['operations']}
 assert len(ops)==len(combined)==11226
 for r in combined:assert ops[r['player_path'],tuple(r['address'])]==(r['before'],r['after'])
 originaltsv=(W/'prior-unreleased-scripts.tsv').read_bytes();rows=table(originaltsv);oldrows=table(originaltsv);gm={r['player_path']:r for r in gens}
 for r in rows:
  e=entries[r['player_path']];r['candidate_blob']=e['after_blob'];r['body_changes']=str(sum(a[-1]!='textSelect' for a,b,c in e['operations']));r['choice_changes']=str(sum(a[-1]=='textSelect' for a,b,c in e['operations']))
  if 'player_candidate_blob' in r:r['player_candidate_blob']=e['after_blob']
  # Preserve the separately based MVD Reader candidate; its player image bytes are intentionally distinct.
  if r['player_path'] not in gm:
   old=next(x for x in oldrows if x['player_path']==r['player_path']);r.clear();r.update(old)
 assert len(rows)==361 and sum(a!=b for a,b in zip(rows,oldrows))==235
 oldstatus=table((W/'prior-pending-status-with-unreleased.tsv').read_bytes());status=[dict(x) for x in oldstatus];changedmap={r['reader_path']:r for r in rows if r['player_path'] in gm}
 for r in status:
  if r['reader_path'] in changedmap:r['candidate_blob']=changedmap[r['reader_path']]['candidate_blob']
 assert len(status)==385 and sum(a!=b for a,b in zip(status,oldstatus))==235
 prior=load('prior-unreleased-summary.json');summary=dict(prior);summary.update(schema=5,updated_at=now,batch=BATCH,entry=DEST+'README.md',previous_prepared=361,this_batch_new=0,this_batch_new_body_changes=824,this_batch_body_fields_reviewed=0,fresh_body_fields_corrected=prior['fresh_body_fields_corrected']+824,combined_text_address_changes=11226,txt_files_prepared=export['files'],txt_physical_span_edits=export['current_unique_span_operations'],residual_amended_candidate_files=235,residual_recheck_added_fields=824,new_full_review_count_this_batch=0,field_candidate_blob_is_historical_review_generation=True,active_candidate_versions='docs/story-quality/contributions/active-candidate-generations.json',current_origin_audit=DEST+'origin-refresh-summary.json',next_action='Continue targeted QA of residual machine fields or provenance-only sources; do not translate exempt human text. Client must pin latest manifest SHA, integrate same-source Scenario/delta and return receipt. Reader integration remains a separate unpublished gate.')
 summary['batches']=list(prior['batches'])+[{'batch':BATCH,'canonical_entry':DEST+'README.md','kind':'targeted_residual_machine_amendment','new_full_review':0,'exact_source_reuse':0,'prepared_targets':0,'existing_targets_amended':235,'fresh_body_changes':824,'choice_changes':0,'reuse_sync_changes':0,'published':False}]
 assert summary['new_full_review_unreleased']==278 and summary['reviewed_text_reuse_unreleased']==83 and summary['fresh_body_fields_corrected']==9091
 sweep=load('sweep-completion-validation.json');remaining=load('remaining-status-summary.json')
 assert sweep['passed'] and sweep['source_fields']==sweep['reviewed_fields']==6372 and sweep['corrected_fields']==824 and sweep['amended_scripts']==235 and sweep['pending_fields']==0
 assert remaining['actionable_first_review_pending']==0 and remaining['validated_unpublished_targets']==361
 summary.update(residual_machine_fields_reviewed_this_batch=6372,residual_machine_fields_corrected_this_batch=824,residual_machine_fields_retained_this_batch=5548,residual_review_remaining_fields=0,residual_review_remaining_scripts=0,remaining_scope_summary=DEST+'remaining-status-summary.json',remaining_scope_paths=DEST+'scope-status.tsv',next_action='All first-review tasks and this frozen residual sweep are accounted for. Wait for client integration/release receipt for 361 targets; investigate new confirmed machine defects only, never retranslate the 24 human/prior-review exemptions. No publication in this window.')
 fielddoc=dict(olddoc);fielddoc.update(schema=2,records=combined,new_body_changes=olddoc['new_body_changes']+824,batches=summary['batches'],generation_note='Each field record candidate_blob is immutable evidence of the candidate generation when that decision was made. Resolve current candidate bytes with active-candidate-generations.json and the current READY packet; do not rewrite historical records just to make their metadata match the latest whole-file blob.')
 generations=[]
 for r in rows:
  historical=sorted({x['candidate_blob'] for x in combined if x['player_path']==r['player_path']})
  generations.append({'reader_path':r['reader_path'],'player_path':r['player_path'],'current_reader_candidate_blob':r['candidate_blob'],'current_player_candidate_blob':entries[r['player_path']]['after_blob'],'current_player_sha256':entries[r['player_path']]['after_sha256'],'historical_decision_candidate_blobs':historical,'active_manifest_sha256':ready['manifest_sha256']})
 validation.update(validated_at=now,tests_passed=87,test_groups={'translation_contract':23,'append_only_amendment':16,'client_overlay':28,'remote_ready_freshness':10,'residual_coverage':10},test_log_sha256=sha(test),actual_reader_parser_files=235,parser_proof_sha256=sha((W/'parser-validation.json').read_bytes()),new_full_story_count=0,all_old_field_values_and_order_preserved=True,active_tsv_candidate_generations_updated=235,cumulative_export=export,source_audit=origin,client_preflight=load('client-preflight.json'),production_build_run=False,website_qa_run=False,game_device_test_run=False)
 (W/'validation.json').write_bytes(enc(validation));(W/'unreleased-summary.json').write_bytes(enc(summary));(W/'active-candidate-generations.json').write_bytes(enc({'schema':1,'files':generations}));(W/'active-unreleased-scripts.tsv').write_bytes(tsv(rows,list(rows[0])))
 counts=collections.Counter(r['script_id'] for r in proof);tbl='\n'.join('| '+sid+' | '+str(n)+' |' for sid,n in counts.items())
 report=(W/'report17-base.md').read_text(encoding='utf8').format(timestamp=now,manifest_sha256=ready['manifest_sha256'],previous_manifest_sha256=ready['supersedes_manifest_sha256'],script_table=tbl)
 (W/'Reader_AI_Held_Batch17_20261003.md').write_text(report,encoding='utf8')
 # Recovery document: text only, no credentials/font/model/game ZIP binary.
 shutil.copyfile(W.parent/'semantic-batch15-ai-only-held-20261003'/'recover_held.py',W/'recover_held.py');from recover_held import inspect
 bundle={}
 def include(p,name):
  data=p.read_bytes();text=data.decode('utf8');assert text.encode()==data;bundle[name]={'utf8':text,'bytes':len(data),'sha256':sha(data)}
 for p in W.iterdir():
  if p.is_file() and p.suffix in ('.py','.cjs','.json','.tsv','.md','.log') and p.name not in ('reader-tree.json','patch-tree.json','public-tree.json','baseline-census.json','baseline-contributions.json','initial-status-z.bin','final-document-commit.json'):include(p,p.name)
 for folder in ['originals','prior-stage','stage','japanese','sweep-reviews']:
  for p in (W/folder).rglob('*'):
   if p.is_file():include(p,p.relative_to(W).as_posix())
 packed=gzip.compress(enc({'schema':1,'kind':'held_translation_recovery_document_not_game_package','published':False,'release_version':None,'batch':BATCH,'files':bundle,'previous_packet_sha256':ready['supersedes_manifest_sha256'],'current_packet_sha256':ready['manifest_sha256'],'instructions':'Materialize only to a fresh isolated directory. The immutable prior packet is in client-integration/history; all latest candidates in active READY. Never use historical field candidate_blob as an active whole-file hash without checking active-candidate-generations.'}),mtime=0);doc,digest=inspect(packed);assert len(doc['files'])==len(bundle);(W/'held-recovery.json.gz').write_bytes(packed);meta={'path':DEST+'held-recovery.json.gz','sha256':digest,'bytes':len(packed),'files':len(bundle),'not_game_package':True};(W/'recovery-metadata.json').write_bytes(enc(meta))
 git('patch','fetch','origin','main');head=git('patch','rev-parse','FETCH_HEAD').decode().strip();cur=tree('patch',head);root='docs/story-quality/contributions/';kitroot='docs/story-quality/client-integration/';assert git('patch','show',head+':'+kitroot+'READY.json')==(W/'prior-client-ready.json').read_bytes()
 assert not any(p.startswith(kitroot+'CLIENT_RECEIPT') for p in cur),'Client receipt appeared; reconcile release state first'
 assert git('patch','show',head+':'+root+'unreleased-scripts.tsv')==originaltsv
 preflight('A:/StoryQuality-20260930-1739/patch.git',head,packet)
 files={DEST+'README.md':report.encode(),DEST+'validation.json':enc(validation),DEST+'held-recovery.json.gz':packed,DEST+'recovery-metadata.json':enc(meta),DEST+'recover_held.py':(W/'recover_held.py').read_bytes(),DEST+'amendment-proof.json.gz':gzip.compress(enc(proof),mtime=0),DEST+'amendment-decisions.json':(W/'amendment-decisions.json').read_bytes(),DEST+'candidate-generations.json':enc(gens),DEST+'origin-refresh-summary.json':enc(origin),DEST+'origin-refresh-ledger.json.gz':(W/'origin-refresh-ledger.json.gz').read_bytes(),DEST+'cumulative-reader-exports.json.gz':(W/'cumulative-reader-exports.json.gz').read_bytes(),DEST+'cumulative-reader-exports-metadata.json':enc(export),DEST+'parser-validation.json':(W/'parser-validation.json').read_bytes(),DEST+'tests-final-87.log.json':enc({'log_utf8':test.decode('utf8'),'sha256':sha(test),'tests':87,'passed':True}),root+'unreleased-summary.json':enc(summary),root+'unreleased-scripts.tsv':tsv(rows,list(rows[0])),root+'pending-status-with-unreleased.tsv':tsv(status,list(status[0])),root+'unreleased-field-changes.json.gz':gzip.compress(enc(fielddoc),mtime=0),root+'active-candidate-generations.json':enc({'schema':1,'files':generations})}
 files.update({DEST+'sweep-completion-validation.json':(W/'sweep-completion-validation.json').read_bytes(),DEST+'sweep-review-ledger.json.gz':gzip.compress((W/'sweep-review-ledger.json').read_bytes(),mtime=0),DEST+'sweep-source-set.json.gz':gzip.compress((W/'sweep-set.json').read_bytes(),mtime=0),DEST+'remaining-status-summary.json':(W/'remaining-status-summary.json').read_bytes(),DEST+'scope-status.tsv':(W/'scope-status.tsv').read_bytes(),DEST+'inherited-display-restoration-proof.json':(W/'inherited-display-restoration-proof.json').read_bytes()})
 for name in ('sweep_contract.py','test_sweep_contract.py','validate_completion17.py','sweep17.py'):
  files[DEST+'tools/'+name]=(W/name).read_bytes()
 progress=load('progress.json');progress.update(stage='validated_held_amendments_client_ready',checkpoint='第17批235既有候选追加824字段；361目标、11226字段，来源分账不变，87测试和235真实解析通过；仅文档，未整合/发布',validation=DEST+'validation.json',client_ready=kitroot+'READY.json',updated_at=now);files[DEST+'progress.json']=enc(progress);(W/'progress.json').write_bytes(enc(progress))
 oldhist=kitroot+'history/'+ready['supersedes_manifest_sha256']+'/'
 snapshot={}
 for path in cur:
  if path.startswith(kitroot) and '/' not in path.removeprefix(kitroot):
   name=path.removeprefix(kitroot);raw=git('patch','show',head+':'+path);dest=oldhist+name
   if dest in cur:assert git('patch','show',head+':'+dest)==raw
   files[dest]=raw;snapshot[dest]=sha(raw)
 for n in ['unreleased-summary.json','unreleased-scripts.tsv','unreleased-field-changes.json.gz','pending-status-with-unreleased.tsv']:
  data=git('patch','show',head+':'+root+n);files[oldhist+'ledger-snapshot/'+n]=data;snapshot[oldhist+'ledger-snapshot/'+n]=sha(data)
 files[oldhist+'SNAPSHOT.json']=enc({'source_commit':head,'files':snapshot,'superseded_by_manifest_sha256':ready['manifest_sha256'],'immutable':True,'published':False})
 for p in (W/'client-kit').iterdir():
  if p.is_file():files[kitroot+p.name]=p.read_bytes()
 for n in ['amendment_contract.py','test_amendment_contract.py','build_amendments.py','merge_reader_exports.py','prepare_client17.py','finalize_records17.py']:
  files[DEST+'tools/'+n]=(W/n).read_bytes()
 files[kitroot+'source-before-integration-block.json']=(W/'unintegrated-source-negative-check.json').read_bytes();files[kitroot+'current-package-negative-check.json']=(W/'old-package-negative-check.json').read_bytes();files[kitroot+'client-test-evidence.json']=enc({'client_overlay_tests':28,'new_current_READY_tests':10,'residual_coverage_tests':10,'full_batch_tests':87,'passed':True,'log_sha256':sha(test),'device_test':False,'new_packages_tested':False})
 oldreadme=git('patch','show',head+':'+root+'README.md').decode();files[root+'README.md']=(f'<!-- HELD-BATCH17-AMENDMENTS -->\n## 第17批：361目标不变，追加824处漏改机翻\n\n235个既有候选已改进，累计11226字段。旧10402记录的值/顺序保留；活动候选版本在active-candidate-generations.json，旧361行索引快照在客户端history/{ready["supersedes_manifest_sha256"]}/ledger-snapshot/。不是新增824篇或新增235篇；694发布账、361未发布目标、24已核销来源项不变。\n\n[本批记录](../unreleased/{BATCH}/README.md)；[客户端最新READY](../client-integration/READY.json)，整合前必须使用current_ready_gate.py与远端main核对SHA，不只比较目标数。运行资源和发布均未改动。\n<!-- /HELD-BATCH17-AMENDMENTS -->\n\n'+oldreadme).encode()
 expected={p:cur.get(p) for p in files};frozen=load('patch-tree.json')
 for n in ['summary.json','ledger.json.gz']:expected[root+n]=frozen[root+n]
 for p,h in load('prior-doc-hashes.json').items():assert cur.get(p)==h,p
 result=commit('patch',files,'held-batch17 validated residual amendments and current READY gate',expected_old=expected)
 receipt={'patch':result,'files':{p:sha(b) for p,b in files.items()},'snapshot_files':snapshot,'recovery':meta,'manifest_sha256':ready['manifest_sha256'],'previous_manifest_sha256':ready['supersedes_manifest_sha256'],'counts':{'targets':361,'fields':11226,'amended_existing_targets':235,'new_fields':824,'new_completed_stories':0},'runtime_changed':False,'published':False};(W/'final-document-commit.json').write_bytes(enc(receipt));guard();print('CN_PATCH_FINAL',result,'RECOVERY',meta,'DOC_FILES',len(files))
if __name__=='__main__':main()
