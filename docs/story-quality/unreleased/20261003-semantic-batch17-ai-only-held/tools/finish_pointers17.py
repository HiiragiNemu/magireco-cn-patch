"""Update Reader reference-only handoff and append a pointer to the client's known audit file."""
from pathlib import Path
import sys,json,hashlib,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from checkpoint import guard,git,tree,commit,enc,DEST

def main():
 guard();assert not (W/'pointer-final.json').exists();rec=json.loads((W/'final-document-commit.json').read_bytes());ready=json.loads((W/'client-kit/READY.json').read_bytes());now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 git('reader','fetch','origin','main');ref=git('reader','rev-parse','FETCH_HEAD').decode().strip();rt=tree('reader',ref)
 marker='<!-- AI-ONLY-HELD-BATCH16 -->';end='<!-- /AI-ONLY-HELD-BATCH16 -->';ptr=f'''{marker}
## 第17批已完成：待发稿残余纠错及当前READY核验，仍不发布

最新完成与独立验证入口：`HiiragiNemu/magireco-cn-patch:{DEST}README.md`，候选提交`{rec['patch']['commit']}`。累计清单/候选/恢复文档只有CN patch保存；本Reader只保留指针。

本地`{W}`，任务`tsk_b9a74c32a7e449d6`。读取CN patch当前未发布汇总与`active-candidate-generations.json`；不要从旧聊天的第14批队列重复处理已做完或已经豁免的人工恢复。本批固定残余字段复查已经闭合；完整剩余核算见CN patch本批remaining-status-summary.json与scope-status.tsv。后续只对新增确证问题或来源线索继续审查，不能把程序扫描当作全文校订完成。

客户端接入以CN patch当前`docs/story-quality/client-integration/READY.json`为准；目标数相同也必须核对manifest SHA。新`current_ready_gate.py`核对origin实时main与READY，整合/构建和串行发布前需执行；该工具不发包、不改运行源。Scenario与delta仍须同源并验收真实安装。原Reader并行UI部署保留，不能因玩家发布就宣布Reader新稿上线。

本窗口继续禁止写运行剧情、发包、触发同步和Reader/ADV部署。AgentDock写文件、执行命令和main文档推送均实际可用，不要把接口发现失败当成用户权限不足。
{end}

'''
 files={};expected={}
 for p in ['STORY_QUALITY_HANDOFF.md','docs/story-quality/CONTINUATION.md']:
  text=git('reader','show',ref+':'+p).decode()
  if marker in text:a=text.index(marker);b=text.index(end,a)+len(end);text=(text[:a]+text[b:]).lstrip('\r\n')
  files[p]=(ptr+text).encode();expected[p]=rt[p]
 p='docs/story-quality/CONTINUATION_STATE.json';d=json.loads(git('reader','show',ref+':'+p));d.update(updated_at=now,checkpoint='第17批残余校订与客户端最新READY核验工具已存CN patch；不新增全文完成数，不发包不部署',task_id='tsk_b9a74c32a7e449d6',active_translation_hold={'stage':'validated_held_residual_amendments','canonical_repository':'HiiragiNemu/magireco-cn-patch','path':DEST+'README.md','commit':rec['patch']['commit'],'workspace':str(W),'publication_prohibited':True,'runtime_source_writes_prohibited':True,'release_version':None,'evidence':DEST+'validation.json','client_ready':'docs/story-quality/client-integration/READY.json','manifest_sha256':ready['manifest_sha256']});d['paths']['current_batch']=str(W);files[p]=enc(d);expected[p]=rt[p]
 reader=commit('reader',files,'held-batch17 final pointer only',expected_old=expected)
 target=Path(r'D:\magia\deliveries\resource-integrity-20261002-src\.build\finish-20261003\TRANSLATION_WINDOW_HANDOFF.md');old=target.read_bytes();header=f'''<!-- TRANSLATION-CLIENT-READY-BATCH17 -->
## 当前接入：第17批纠错后361目标 / 11226字段，目标数量未增加但稿件已变化

更新时间：{now}。候选提交`{rec['patch']['commit']}`。权威入口CN patch的`docs/story-quality/client-integration/READY.json`；本版manifest SHA256 `{ready['manifest_sha256']}`。旧版361目标SHA `{ready['supersedes_manifest_sha256']}`已经被替代并保留历史快照；旧335/255信息见下方仅作历史记录。

第15批26目标早已纳入；第17批在235个已备稿中追加824个漏改机翻字段，没有新计235篇。10402条先前判断的before/after全部保留，更新后的活动候选和历史判断版本对应关系见active-candidate-generations.json。请勿混用旧361包与新READY。

整合/构建以及发布事务前，运行新current_ready_gate.py核对origin实际main/READY的SHA，然后执行既有check-source、check-integrated、verify-packages以及实际安装/缓存重放/离线/重下读回。原128补充路径+361目标=489；正文和选择列表须在同一个受审main中，同源生成Scenario和累计delta。静态新鲜度检查不能替代你方串行锁和事务复验。生产工作流、资源文件没有被本窗口修改。

当前新稿仍未合入或发布。请你方按维护者决策接入后，在CN patch留包含本版SHA、实际整合提交、Scenario/delta版本及包与设备核验的CLIENT_RECEIPT。当前文件写入不代表你方已阅读或已经发包。Reader候选导出单独存本批累计文档，未部署；不要因客户端包成功而宣称Reader已上线。
<!-- /TRANSLATION-CLIENT-READY-BATCH17 -->

'''.encode()
 assert b'<!-- TRANSLATION-CLIENT-READY-BATCH17 -->' not in old and target.read_bytes()==old;target.write_bytes(header+old);assert target.read_bytes().endswith(old)
 pointer={'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'previous_sha256':hashlib.sha256(old).hexdigest(),'previous_content_preserved_as_suffix':True,'receiver_acknowledged':False,'manifest_sha256':ready['manifest_sha256'],'candidate_commit':rec['patch']['commit'],'runtime_or_workflows_changed':False}
 out={'reader':reader,'reader_hashes':{p:hashlib.sha256(b).hexdigest() for p,b in files.items()},'client_pointer':pointer};(W/'pointer-final.json').write_bytes(enc(out));guard();print('POINTERS',json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
