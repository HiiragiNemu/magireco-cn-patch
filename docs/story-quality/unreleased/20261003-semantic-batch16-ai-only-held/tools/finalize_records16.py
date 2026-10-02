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
 assert validation['passed'] and parser['passed'] and len(parser['files'])==30 and export['passed'] and not txt['holds'] and not txt['missing']
 test=(W/'tests-final.log').read_bytes();assert b'Ran 77 tests' in test and b'\nOK' in test and b'FAILED' not in test
 for r in parser['files']:
  for folder,key in [('prior-stage','before_sha256'),('stage','after_sha256')]:assert sha((W/folder/'reader'/r['path']).read_bytes())==r[key]
 assert sha((W/'cumulative-reader-exports.json.gz').read_bytes())==export['sha256']
 olddoc=json.loads(gzip.decompress((W/'prior-unreleased-field-changes.json.gz').read_bytes()));oldfields=olddoc['records'];newfields=load('new-field-records.json');combined=oldfields+newfields;assert len(oldfields)==10312 and len(newfields)==90 and len(combined)==10402 and combined[:10312]==oldfields
 entries={e['path']:e for e in packet['files']};ops={(e['path'],tuple(a)):(b,c) for e in packet['files'] for a,b,c in e['operations']}
 assert len(ops)==len(combined)==10402
 for r in combined:assert ops[r['player_path'],tuple(r['address'])]==(r['before'],r['after'])
 originaltsv=(W/'prior-unreleased-scripts.tsv').read_bytes();rows=table(originaltsv);oldrows=table(originaltsv);gm={r['player_path']:r for r in gens}
 for r in rows:
  e=entries[r['player_path']];r['candidate_blob']=e['after_blob'];r['body_changes']=str(sum(a[-1]!='textSelect' for a,b,c in e['operations']));r['choice_changes']=str(sum(a[-1]=='textSelect' for a,b,c in e['operations']))
  if 'player_candidate_blob' in r:r['player_candidate_blob']=e['after_blob']
  # Preserve the separately based MVD Reader candidate; its player image bytes are intentionally distinct.
  if r['player_path'] not in gm:
   old=next(x for x in oldrows if x['player_path']==r['player_path']);r.clear();r.update(old)
 assert len(rows)==361 and sum(a!=b for a,b in zip(rows,oldrows))==30
 oldstatus=table((W/'prior-pending-status-with-unreleased.tsv').read_bytes());status=[dict(x) for x in oldstatus];changedmap={r['reader_path']:r for r in rows if r['player_path'] in gm}
 for r in status:
  if r['reader_path'] in changedmap:r['candidate_blob']=changedmap[r['reader_path']]['candidate_blob']
 assert len(status)==385 and sum(a!=b for a,b in zip(status,oldstatus))==30
 prior=load('prior-unreleased-summary.json');summary=dict(prior);summary.update(schema=5,updated_at=now,batch=BATCH,entry=DEST+'README.md',previous_prepared=361,this_batch_new=0,this_batch_new_body_changes=90,this_batch_body_fields_reviewed=0,fresh_body_fields_corrected=prior['fresh_body_fields_corrected']+90,combined_text_address_changes=10402,txt_files_prepared=export['files'],txt_physical_span_edits=export['current_unique_span_operations'],residual_amended_candidate_files=30,residual_recheck_added_fields=90,new_full_review_count_this_batch=0,field_candidate_blob_is_historical_review_generation=True,active_candidate_versions='docs/story-quality/contributions/active-candidate-generations.json',current_origin_audit=DEST+'origin-refresh-summary.json',next_action='Continue targeted QA of residual machine fields or provenance-only sources; do not translate exempt human text. Client must pin latest manifest SHA, integrate same-source Scenario/delta and return receipt. Reader integration remains a separate unpublished gate.')
 summary['batches']=list(prior['batches'])+[{'batch':BATCH,'canonical_entry':DEST+'README.md','kind':'targeted_residual_machine_amendment','new_full_review':0,'exact_source_reuse':0,'prepared_targets':0,'existing_targets_amended':30,'fresh_body_changes':90,'choice_changes':0,'reuse_sync_changes':0,'published':False}]
 assert summary['new_full_review_unreleased']==278 and summary['reviewed_text_reuse_unreleased']==83 and summary['fresh_body_fields_corrected']==8267
 fielddoc=dict(olddoc);fielddoc.update(schema=2,records=combined,new_body_changes=olddoc['new_body_changes']+90,batches=summary['batches'],generation_note='Each field record candidate_blob is immutable evidence of the candidate generation when that decision was made. Resolve current candidate bytes with active-candidate-generations.json and the current READY packet; do not rewrite historical records just to make their metadata match the latest whole-file blob.')
 generations=[]
 for r in rows:
  historical=sorted({x['candidate_blob'] for x in combined if x['player_path']==r['player_path']})
  generations.append({'reader_path':r['reader_path'],'player_path':r['player_path'],'current_reader_candidate_blob':r['candidate_blob'],'current_player_candidate_blob':entries[r['player_path']]['after_blob'],'current_player_sha256':entries[r['player_path']]['after_sha256'],'historical_decision_candidate_blobs':historical,'active_manifest_sha256':ready['manifest_sha256']})
 validation.update(validated_at=now,tests_passed=77,test_groups={'translation_contract':23,'append_only_amendment':16,'client_overlay':28,'remote_ready_freshness':10},test_log_sha256=sha(test),actual_reader_parser_files=30,parser_proof_sha256=sha((W/'parser-validation.json').read_bytes()),new_full_story_count=0,all_old_field_values_and_order_preserved=True,active_tsv_candidate_generations_updated=30,cumulative_export=export,source_audit=origin,client_preflight=load('client-preflight.json'),production_build_run=False,website_qa_run=False,game_device_test_run=False)
 (W/'validation.json').write_bytes(enc(validation));(W/'unreleased-summary.json').write_bytes(enc(summary));(W/'active-candidate-generations.json').write_bytes(enc({'schema':1,'files':generations}));(W/'active-unreleased-scripts.tsv').write_bytes(tsv(rows,list(rows[0])))
 counts=collections.Counter(r['script_id'] for r in proof);tbl='\n'.join('| '+sid+' | '+str(n)+' |' for sid,n in counts.items())
 report=f'''# 第16批：待发AI剧情残余纠错与防止客户端拿旧候选发包\n\n记录时间：{now}。本轮未写游戏或Reader运行资源、未发包、未触发发布/同步、未部署。所有实质记录、累计台账、候选与恢复材料仅CN patch。\n\n## 实际断点与推进\n\n恢复时第15批已经完成并入库：26个新片段、638个字段；旧50待办另有23个人译恢复和1个已完成历史复核的豁免。不能重复计算为本轮成果。原历史1079来源池当前分为694份已有发布账、361个已准备未发布目标、24个来源/历史复核豁免。\n\n本轮对361份候选的22230个显示字段进行程序筛查，逐项审视269个语义疑点并读取必要上下文，还检查了御影等剧情中的原机翻残句。筛查不是全文复核证明。最终在30份既有候选中追加90处有原始日文、导入记录及机器输出日志精确对应的修正；新增全文复核片段数为0。现有10312条字段记录的地址、原文、修订值和顺序完整保留，累计10402条。未改之前已决定的翻译，不改官方/确认人工和受保护字段。\n\n修复包括：‘又没能成为一家人’不能写成‘再也不能’；纸牌‘再来一局’不是‘再打一架’；‘マジか’此处是‘真的假的’，不是‘严重地’；润称赞老奶奶懂自己，不是自己理解了；御魂只让自己如愿的自责、渚收下昂贵礼物的主语，以及衣服试穿、哈欠、无法承担价格等语境。角色当时的错误认识和未揭晓的真相不提前改写。\n\n| 既有片段 | 新增纠错字段 |\n| --- | ---: |\n{tbl}\n\n## 当前来源审计的边界\n\n以当前固定Reader main `{origin['reader_source']}` 扫描10907个中文JSON路径。旧1079范围之外没有新增满足‘现译仍等于已知机器导入字段、原日中对也在机器输出日志、且不属于人工/恢复保护’全部条件的目标。1635个未得到精确机器证据、23个日文路径待确定的结果只是来源调查，不因此自动重译。这个结论只针对已知导入证据与该版本，不是全仓库无误译证明，也不说明未知来源已经全部核实。\n\n## 不重复计数与版本留存\n\n361目标仍为278个新增全文复核、83个同源复用；359个文件有修订、2个原字节相同。第16批只增加90个以前未修改的字段地址，正文累计8267（含此前1处人工原句恢复）、选项14、复用同步2121，总计10402。旧694/385发布账、498个历史ID和24项豁免不变。\n\n30个活动候选的整文件blob更新。旧361行TSV与前10312条字段记录均保留不可变快照；累计字段记录中candidate_blob继续表示当时判断的历史版本，不篡改旧记录。`active-candidate-generations.json`明确每个目标当前Reader/玩家候选版本和历史判断版本，当前READY内全部操作与10402条字段原值/新值逐项一致。\n\n## TXT候选与测试\n\n77项测试通过：23文本控制契约、16追加纠错保护、28客户端ZIP覆盖、10远端READY新鲜度。30个真实Reader解析比较通过，可见文字改变但行数、说话人、事件、音频均不变；本次没有新增显示节点，之前恢复的抱紧旁白保持。\n\n本批重建50份TXT/网页配对候选，2454处从生产底稿到当前候选的物理差异中包含既有修订，不能全计成本轮新贡献。跨第11—15批恢复文档做完整合并后，累计240份TXT候选保留旧26844处差异，本轮实际追加254个物理位置，总计27098。所有更改精确绑定完整导出节，并可逆向恢复原始字节；零遗漏、零待核。累计导出文档保存于本目录cumulative-reader-exports.json.gz，未写Reader运行文件。\n\n未跑生产构建、线上阅读验收或实际游戏安装；没有借用旧测试结果。\n\n## 客户端接入\n\n唯一入口`docs/story-quality/client-integration/READY.json`，本版manifest SHA256：`{ready['manifest_sha256']}`。依旧361目标，但已有30份内容变化；不能用目标数、旧版本号、曾经的READY成功代替当前SHA核对。旧manifest `{ready['supersedes_manifest_sha256']}`按原SHA完整归档。\n\n新工具current_ready_gate.py先读取origin实际main引用和该提交READY，再核对本地manifest SHA；同样361目标但旧SHA、错误源仓、过期本地对象、核验期间main移动均会拒绝。这是交付给客户端的接入工具，尚未改动客户端生产工作流；仍须由对方在整合/构建及串行发布事务前执行。只读新鲜度检查不替代发布锁、源检查、真实ZIP与最终设备文件核验。\n\n原delta补充路径128加361目标仍为489，生产配置未动。全部361个源码和1125条保全路径重新预检通过，实际旧源码及客户端缓存旧包仍被拒绝冒充新稿。Scenario与累计JS delta须从同一个已整合提交构建，完整JS103不因本次文字修改重打。等待客户端带本次SHA的实际整合/发行/安装回执；Reader部署单独验收。\n'''
 (W/'Reader_AI_Held_Batch16_20261003.md').write_text(report,encoding='utf8')
 # Recovery document: text only, no credentials/font/model/game ZIP binary.
 shutil.copyfile(W.parent/'semantic-batch15-ai-only-held-20261003'/'recover_held.py',W/'recover_held.py');from recover_held import inspect
 bundle={}
 def include(p,name):
  data=p.read_bytes();text=data.decode('utf8');assert text.encode()==data;bundle[name]={'utf8':text,'bytes':len(data),'sha256':sha(data)}
 for p in W.iterdir():
  if p.is_file() and p.suffix in ('.py','.cjs','.json','.tsv','.md') and p.name not in ('reader-tree.json','patch-tree.json','public-tree.json','baseline-census.json','baseline-contributions.json','initial-status-z.bin','final-document-commit.json'):include(p,p.name)
 for folder in ['originals','prior-stage','stage','japanese']:
  for p in (W/folder).rglob('*'):
   if p.is_file():include(p,p.relative_to(W).as_posix())
 packed=gzip.compress(enc({'schema':1,'kind':'held_translation_recovery_document_not_game_package','published':False,'release_version':None,'batch':BATCH,'files':bundle,'previous_packet_sha256':ready['supersedes_manifest_sha256'],'current_packet_sha256':ready['manifest_sha256'],'instructions':'Materialize only to a fresh isolated directory. The immutable prior packet is in client-integration/history; all latest candidates in active READY. Never use historical field candidate_blob as an active whole-file hash without checking active-candidate-generations.'}),mtime=0);doc,digest=inspect(packed);assert len(doc['files'])==len(bundle);(W/'held-recovery.json.gz').write_bytes(packed);meta={'path':DEST+'held-recovery.json.gz','sha256':digest,'bytes':len(packed),'files':len(bundle),'not_game_package':True};(W/'recovery-metadata.json').write_bytes(enc(meta))
 git('patch','fetch','origin','main');head=git('patch','rev-parse','FETCH_HEAD').decode().strip();cur=tree('patch',head);root='docs/story-quality/contributions/';kitroot='docs/story-quality/client-integration/';assert git('patch','show',head+':'+kitroot+'READY.json')==(W/'prior-client-ready.json').read_bytes()
 assert not any(p.startswith(kitroot+'CLIENT_RECEIPT') for p in cur),'Client receipt appeared; reconcile release state first'
 assert git('patch','show',head+':'+root+'unreleased-scripts.tsv')==originaltsv
 preflight('A:/StoryQuality-20260930-1739/patch.git',head,packet)
 files={DEST+'README.md':report.encode(),DEST+'validation.json':enc(validation),DEST+'held-recovery.json.gz':packed,DEST+'recovery-metadata.json':enc(meta),DEST+'recover_held.py':(W/'recover_held.py').read_bytes(),DEST+'amendment-proof.json.gz':gzip.compress(enc(proof),mtime=0),DEST+'amendment-decisions.json':(W/'amendment-decisions.json').read_bytes(),DEST+'candidate-generations.json':enc(gens),DEST+'origin-refresh-summary.json':enc(origin),DEST+'origin-refresh-ledger.json.gz':(W/'origin-refresh-ledger.json.gz').read_bytes(),DEST+'cumulative-reader-exports.json.gz':(W/'cumulative-reader-exports.json.gz').read_bytes(),DEST+'cumulative-reader-exports-metadata.json':enc(export),DEST+'parser-validation.json':(W/'parser-validation.json').read_bytes(),DEST+'tests-final.log.json':enc({'log_utf8':test.decode('utf8'),'sha256':sha(test),'tests':77,'passed':True}),root+'unreleased-summary.json':enc(summary),root+'unreleased-scripts.tsv':tsv(rows,list(rows[0])),root+'pending-status-with-unreleased.tsv':tsv(status,list(status[0])),root+'unreleased-field-changes.json.gz':gzip.compress(enc(fielddoc),mtime=0),root+'active-candidate-generations.json':enc({'schema':1,'files':generations})}
 progress=load('progress.json');progress.update(stage='validated_held_amendments_client_ready',checkpoint='第16批30既有候选追加90字段；361目标、10402字段，来源分账不变，77测试和30真实解析通过；仅文档，未整合/发布',validation=DEST+'validation.json',client_ready=kitroot+'READY.json',updated_at=now);files[DEST+'progress.json']=enc(progress);(W/'progress.json').write_bytes(enc(progress))
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
 for n in ['amendment_contract.py','test_amendment_contract.py','build_amendments.py','merge_reader_exports.py','prepare_client16.py','finalize_records16.py']:
  files[DEST+'tools/'+n]=(W/n).read_bytes()
 files[kitroot+'source-before-integration-block.json']=(W/'unintegrated-source-negative-check.json').read_bytes();files[kitroot+'current-package-negative-check.json']=(W/'old-package-negative-check.json').read_bytes();files[kitroot+'client-test-evidence.json']=enc({'client_overlay_tests':28,'new_current_READY_tests':10,'full_batch_tests':77,'passed':True,'log_sha256':sha(test),'device_test':False,'new_packages_tested':False})
 oldreadme=git('patch','show',head+':'+root+'README.md').decode();files[root+'README.md']=(f'<!-- HELD-BATCH16-AMENDMENTS -->\n## 第16批：361目标不变，追加90处漏改机翻\n\n30个既有候选已改进，累计10402字段。旧10312记录的值/顺序保留；活动候选版本在active-candidate-generations.json，旧361行索引快照在客户端history/{ready["supersedes_manifest_sha256"]}/ledger-snapshot/。不是新增90篇或新增30篇；694发布账、361未发布目标、24已核销来源项不变。\n\n[本批记录](../unreleased/{BATCH}/README.md)；[客户端最新READY](../client-integration/READY.json)，整合前必须使用current_ready_gate.py与远端main核对SHA，不只比较目标数。运行资源和发布均未改动。\n<!-- /HELD-BATCH16-AMENDMENTS -->\n\n'+oldreadme).encode()
 expected={p:cur.get(p) for p in files};frozen=load('patch-tree.json')
 for n in ['summary.json','ledger.json.gz']:expected[root+n]=frozen[root+n]
 for p,h in load('prior-doc-hashes.json').items():assert cur.get(p)==h,p
 result=commit('patch',files,'held-batch16 validated residual amendments and current READY gate',expected_old=expected)
 receipt={'patch':result,'files':{p:sha(b) for p,b in files.items()},'snapshot_files':snapshot,'recovery':meta,'manifest_sha256':ready['manifest_sha256'],'previous_manifest_sha256':ready['supersedes_manifest_sha256'],'counts':{'targets':361,'fields':10402,'amended_existing_targets':30,'new_fields':90,'new_completed_stories':0},'runtime_changed':False,'published':False};(W/'final-document-commit.json').write_bytes(enc(receipt));guard();print('CN_PATCH_FINAL',result,'RECOVERY',meta,'DOC_FILES',len(files))
if __name__=='__main__':main()
