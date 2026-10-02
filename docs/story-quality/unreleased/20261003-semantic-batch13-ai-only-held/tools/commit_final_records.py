"""Persist validated held records to CN patch and references only to Reader. No resource publication."""
from pathlib import Path
import sys,json,hashlib,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W))
from checkpoint import guard,git,tree,commit,enc,DEST,BATCH
from recover_held import inspect

def read(n):return json.loads((W/n).read_bytes())
def save(n,x):(W/n).write_bytes(enc(x))

def main():
 guard();out=W/'final-held-commits.json';assert not out.exists(),'Already finalized; independent readback only'
 v=read('validation.json');assert v['passed'] and not v['published'];plan=read('final-document-plan.json');meta=read('recovery-metadata.json');doc,digest=inspect((W/'held-recovery.json.gz').read_bytes(),meta['sha256']);assert len(doc['files'])==meta['files']
 files={};expect={}
 for e in plan['files']:
  raw=(W/'final-docs'/e['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==e['sha256'];files[e['path']]=raw;expect[e['path']]=e['expected_old_blob']
 for name,key in [('summary.json','published_summary_blob_preserved'),('ledger.json.gz','published_ledger_blob_preserved')]:expect['docs/story-quality/contributions/'+name]=plan[key]
 pc=commit('patch',files,'held-batch13 finalized candidates and cumulative unreleased ledger',expected_old=expect)
 save('patch-final-commit.json',pc)
 git('reader','fetch','origin','main');head=git('reader','rev-parse','FETCH_HEAD').decode().strip();rt=tree('reader',head);rfiles={};rexpect={};stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();n=read('unreleased-summary.json')
 marker='<!-- AI-ONLY-HELD-BATCH13 -->';end='<!-- /AI-ONLY-HELD-BATCH13 -->'
 pointer=f'''{marker}
## 当前断点：第13批校订候选已验证，候选可供客户端接入，本窗口不发布

维护者要求继续校订并准备客户端发包接入，本窗口不发包。候选只在隔离目录与CN patch文档证据中，尚未写入任何运行资源。不得运行旧scenario发布器、资源同步、Reader/ADV部署。资源审计修正对齐后仍要重新核对最新源blob，并由维护者另行决定整合发布。

最新恢复入口：`HiiragiNemu/magireco-cn-patch:{DEST}README.md`，提交`{pc['commit']}`。验证、候选、完整已处理/待处理和累计未发布清单仅CN patch；Reader只留本指针，不复制累计台账。客户端统一接入入口是CN patch的`docs/story-quality/client-integration/READY.json`，只表明候选已备妥，不表示已发布；必须保持原delta路径并扩展新目标，Scenario和delta由同一个已整合main构建。

本地`{W}`，任务`tsk_ea56506361255df4`。先读CN patch当前未发布汇总和`next-unprepared-queue.json`；下一未准备入口`{n['next_unprepared_chapter']}`《{n['next_unprepared_title']}》。不要重复审读或重新归算已备稿。

AgentDock内置`exec_command`、`file_edit`、Git main文档推送已实际验证可用。工具发现不完整应继续检查精确入口并实际调用，不能解释为账户只有读取权限；长命令优先读持久日志/退出码，不以会话索引过期判断权限。本批新增覆盖一致性核验工具在CN patch客户端接入目录。

{end}

'''
 for path in ('STORY_QUALITY_HANDOFF.md','docs/story-quality/CONTINUATION.md'):
  text=git('reader','show',head+':'+path).decode()
  if marker in text:
   a=text.index(marker);b=text.index(end,a)+len(end);text=(text[:a]+text[b:]).lstrip('\r\n')
  rfiles[path]=(pointer+text).encode();rexpect[path]=rt[path]
 path='docs/story-quality/CONTINUATION_STATE.json';s=json.loads(git('reader','show',head+':'+path));s.update(updated_at=stamp,checkpoint='第13批未发布候选已完整验证并存CN patch；后续校订继续，整合/发包/部署暂停',instruction='只校订确认AI稿；不发包、不写运行资源、不部署。累计和完整清单仅CN patch。',task_id='tsk_ea56506361255df4',active_translation_hold={'publication_prohibited':True,'runtime_source_writes_prohibited':True,'canonical_repository':'HiiragiNemu/magireco-cn-patch','path':DEST+'README.md','evidence':DEST+'validation.json','commit':pc['commit'],'workspace':str(W),'stage':'validated_held_ready','release_version':None,'next_unprepared_chapter':n['next_unprepared_chapter'],'recovery':meta});s['paths']['current_batch']=str(W);rfiles[path]=enc(s);rexpect[path]=rt[path]
 rc=commit('reader',rfiles,'held-batch13 final recovery pointer',expected_old=rexpect)
 receipt={'patch':pc,'reader':rc,'canonical_entry':DEST+'README.md','recovery':meta,'document_files':plan['files'],'reader_pointer_hashes':{p:hashlib.sha256(b).hexdigest() for p,b in rfiles.items()},'published_summary_blob_preserved':plan['published_summary_blob_preserved'],'published_ledger_blob_preserved':plan['published_ledger_blob_preserved'],'runtime_integration_performed':False,'release_created':False,'website_deployed':False,'ADV_registered':False}
 out.write_bytes(enc(receipt));guard();print('FINAL_HELD_DOCS',json.dumps({'patch':pc,'reader':rc,'recovery':meta,'runtime_integration_performed':False},ensure_ascii=False))
if __name__=='__main__':main()
