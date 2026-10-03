"""Final remote/source/live verification and append-only client coordination; no game publishing."""
from pathlib import Path
import sys,json,gzip,subprocess,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from integrate import R,P,run,tree,save,enc,sha
from record_progress import commit_docs
from verify_live import public_json
C='docs/story-quality/client-integration/';H='docs/story-quality/production-handoff/';D='docs/story-quality/reader-final-20261003/';Q='docs/story-quality/contributions/'
REV=(W/'source-revision.txt').read_text().strip()
def get(repo,ref,p):return run(repo,'show',ref+':'+p)
def main():
 assert not (W/'final-independent-verification.json').exists(),'Finalized; read existing receipt'
 rec=json.loads((W/'final-delivery-commits.json').read_bytes());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 run(P,'fetch','origin','main');ph=run(P,'rev-parse','FETCH_HEAD').decode().strip();pt=tree(P,ph)
 run(R,'fetch','origin','main');rh=run(R,'rev-parse','FETCH_HEAD').decode().strip();rt=tree(R,rh)
 for p,h in rec['patch_document_hashes'].items():assert sha(get(P,ph,p))==h,p
 for p,h in rec['reader_pointer_hashes'].items():assert sha(get(R,rh,p))==h,p
 for p,h in rec['old_contribution_paths_preserved'].items():assert pt[p][1]==h,p
 packet=json.loads(gzip.decompress(get(P,ph,C+'integration-manifest.json.gz')));assert len(packet['files'])==361
 for e in packet['files']:assert pt[e['path']][1]==e['before_blob'],e['path']
 inputs=json.loads(gzip.decompress(get(P,ph,H+'reader-input-manifest.json.gz')))
 for e in inputs['files']:assert rt[e['path']][1]==e['candidate_blob'],e['path']
 old=json.loads((W/'original-worktree-state.json').read_bytes())
 assert run(R,'status','--porcelain=v1','-z').hex()==old['status'] and sha(run(R,'diff','--binary'))==old['diff'] and sha(run(R,'diff','--cached','--binary'))==old['cached']
 live={p:public_json(p) for p in ['/adv-release-build.json','/api/adv/release','/api/proofreading/config']}
 assert all(x.get('source_revision')==REV for x in live.values())
 assert live['/api/adv/release']['deployment']=='https://2086f41c.magireader.pages.dev'
 require_empty=[p for p in rt if p.startswith(('docs/story-quality/contributions/','docs/story-quality/client-integration/','docs/story-quality/unreleased/','docs/story-quality/production-handoff/'))];assert not require_empty,require_empty
 cp=subprocess.run(['gh','api','repos/HiiragiNemu/ProgettoMagius-1/git/trees/main?recursive=1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120);assert cp.returncode==0
 public=json.loads(cp.stdout);assert not public.get('truncated');assert not any(e['path'].startswith(('docs/story-quality/contributions/','docs/story-quality/unreleased/','docs/story-quality/client-integration/')) for e in public['tree'])
 ready=json.loads(get(P,ph,C+'READY.json'));policy=get(P,ph,ready['publication_policy_path']);assert sha(policy)==ready['publication_policy_sha256']==rec['release_policy_sha256'];assert json.loads(policy)['mode']=='delta_only_cumulative'
 for n,h in ready['files'].items():assert sha(get(P,ph,C+n))==h,n
 cli=json.loads((W/'delta-only-cli-plan.log').read_text(encoding='utf8'));assert cli['required_delta_paths']==596 and cli['required_scenario_paths']==489 and not cli['production_ready']
 tests=(W/'delta-only-final-tests.log').read_text(encoding='utf8');assert 'Ran 21 tests' in tests and '\nOK' in tests
 # The policy-aware CLI was exercised against current remote policy and fixed archives.
 files={C+'delta_only_guard.py':(W/'delta_only_guard.py').read_bytes(),C+'delta-only-cli-execution.json':enc({'passed':True,'command':'delta_only_guard.py plan; current remote policy and canonical baseline-lock hashes checked','result':cli,'published':False,'actual_new_package_tested':False}),D+'tools/delta_only_guard.py':(W/'delta_only_guard.py').read_bytes(),D+'tools/verify_closeout.py':Path(__file__).read_bytes(),D+'voice-verification.json':(W/'voice-verification.json').read_bytes()}
 ready['files']['delta_only_guard.py']=sha(files[C+'delta_only_guard.py']);ready['files']['delta-only-cli-execution.json']=sha(files[C+'delta-only-cli-execution.json']);files[C+'READY.json']=enc(ready)
 prod=json.loads(get(P,ph,H+'READY.json'));prod.update(deployed_asset_manifest=D+'deployment-file-hashes.json.gz',deployed_asset_manifest_sha256=sha(get(P,ph,D+'deployment-file-hashes.json.gz')),deployed_data_verification=D+'data-verification.json',local_deployed_build_root=str(W/'reader'),preintegration_data_product_manifest_is_historical=True);files[H+'READY.json']=enc(prod)
 # Preserve every earlier cross-window pointer verbatim as a suffix.
 ptr=Path(r'D:\magia\deliveries\resource-integrity-20261002-src\.build\finish-20261003\TRANSLATION_WINDOW_HANDOFF.md');assert ptr.is_file();oldptr=ptr.read_bytes()
 note=f'''<!-- READER-DEPLOYED-DELTA-ONLY-20261003 -->\nReader最终校订稿已经正式部署，源码{REV}，部署2086f41c，正文/数据生产/ADV已验收。维护者最新要求游戏以后只更新累计JS delta，不再共同重发Scenario。请读取CN patch main的 docs/story-quality/client-integration/DELTA_ONLY_HANDOFF.md、release-policy.json和READY.json，交付提交{rec['patch']['commit']}。\n内容manifest仍为{rec['client_manifest_sha256']}；361目标/11226字段未改变。当前至少489剧情+107既有非剧情载荷，必须全部按最新整合Git刷新，不能复用旧delta落后正文。新delta_only_guard允许新delta覆盖冻结Scenario3323，但对14340最终路径逐项核对权威源；原JS103和完整Scenario原文件/版本保持。旧生产流程仍会共同重打Scenario，必须先适配delta-only并保留串行锁/防回退/安装事务；不要直接触发旧发布器。旧缓存21/22不得在新delta后异步回写。\n本窗口未写游戏运行源或发包。实际新delta/元数据/设备与缓存重放通过后，请留带当前manifest和政策SHA的CLIENT_RECEIPT；此指针写入不表示你已阅读或已经发布。\n<!-- /READER-DEPLOYED-DELTA-ONLY-20261003 -->\n\n'''.encode()
 assert b'READER-DEPLOYED-DELTA-ONLY-20261003' not in oldptr
 ptr.write_bytes(note+oldptr);assert ptr.read_bytes().endswith(oldptr)
 pointer={'path':str(ptr),'sha256':sha(ptr.read_bytes()),'previous_sha256':sha(oldptr),'previous_text_preserved':True,'reader_source_revision':REV,'policy_sha256':rec['release_policy_sha256'],'client_acknowledged':False,'client_runtime_or_workflow_changed':False};files[C+'reader-deployed-delta-only-pointer.json']=enc(pointer)
 result={'passed':True,'verified_at':now,'reader_source_revision':REV,'reader_deployment_id':rec['reader_deployment_id'],'reader_main':rh,'patch_main_before_final_proof':ph,'reader_inputs_verified':len(inputs['files']),'client_targets_still_pending':len(packet['files']),'patch_documents_verified':len(rec['patch_document_hashes']),'reader_pointers_verified':len(rec['reader_pointer_hashes']),'old_contribution_paths_preserved':len(rec['old_contribution_paths_preserved']),'client_manifest_unchanged':True,'policy_sha256':rec['release_policy_sha256'],'reader_cumulative_copies':0,'public_cumulative_copies':0,'original_reader_worktree_preserved':True,'all_three_live_reader_revisions_match':True,'live_reader_and_adv':live,'delta_only_cli_passed':True,'delta_only_tests':21,'game_package_published_by_this_task':False,'client_pointer':pointer}
 files[D+'final-independent-verification.json']=enc(result)
 close=commit_docs(P,files,'reader-final-live-proof-and-delta-only-policy-gate',expected={p:pt.get(p,(None,None))[1] for p in files})
 for p,b in files.items():assert get(P,close['commit'],p)==b
 fresh=json.loads(get(P,close['commit'],C+'READY.json'))
 for p,h in fresh['files'].items():assert sha(get(P,close['commit'],C+p))==h,p
 result['final_proof_commit']=close['commit'];save('final-independent-verification.json',result);save('final-close-commit.json',close)
 report=W/'Reader_Deployed_Delta_Only_Handoff_20261003.md';report.write_text(report.read_text(encoding='utf8')+'\n最终独立读回记录：CN patch `'+close['commit']+'`。新验收器还会核对远端当前发布政策和本地基线锁的身份；真实CLI已执行。\n',encoding='utf8')
 print('FINAL_VERIFIED',json.dumps({k:v for k,v in result.items() if k not in ['live_reader_and_adv','client_pointer']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
