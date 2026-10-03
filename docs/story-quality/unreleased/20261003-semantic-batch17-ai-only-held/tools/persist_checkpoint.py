"""Save source-audit/amendment recovery and Reader pointer only; no runtime writes."""
from pathlib import Path
import sys,json,gzip,datetime,hashlib
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from checkpoint import commit,git,tree,guard,enc,DEST,BATCH

def main():
 guard();note=' '.join(sys.argv[1:]);now=datetime.datetime.now(datetime.timezone.utc).isoformat();progress=json.loads((W/'progress.json').read_bytes());progress.update(stage='residual_machine_candidate_review',checkpoint=note,updated_at=now,extra_completed_scripts=0,published=False);(W/'progress.json').write_bytes(enc(progress))
 names=['progress.json','bases.json','origin-refresh-summary.json','new-origin-candidates.json','residual-machine-eligible.json','semantic-signals.json','amendment-decisions.json','amendment-validation.json','sweep-summary.json','sweep-review-ledger.json']
 evidence={name:json.loads((W/name).read_bytes()) for name in names if (W/name).exists()};archive=gzip.compress(enc(evidence),mtime=0)
 md=f'# 第17批恢复：来源刷新与待发稿残余复查\n\n{now}\n\n{note}\n\n第16批已经落盘，361待发目标及24来源豁免保留；本轮检查与修订不增加首次全文校订篇数。不修改运行资源、不发包、不部署。累计资料及全文清单只在CN patch。\n\n本地`{W}`；任务`tsk_b9a74c32a7e449d6`。先读本目录checkpoint-evidence.json.gz。客户端仍应固定最新READY，不能从当前中间记录打包。\n'
 files={DEST+'README.md':md.encode(),DEST+'progress.json':enc(progress),DEST+'checkpoint-evidence.json.gz':archive}
 for name in ['audit_origins.py','scout_candidates.py','persist_checkpoint.py','sweep17.py']:
  files[DEST+'tools/'+name]=(W/name).read_bytes()
 if (W/'origin-refresh-ledger.json.gz').exists():files[DEST+'origin-refresh-ledger.json.gz']=(W/'origin-refresh-ledger.json.gz').read_bytes()
 pc=commit('patch',files,'held-batch17 source audit and residual review checkpoint');rhead=git('reader','rev-parse','HEAD').decode().strip();rt=tree('reader',rhead)
 marker='<!-- AI-ONLY-HELD-BATCH16 -->';end='<!-- /AI-ONLY-HELD-BATCH16 -->'
 ptr=f'{marker}\n## 第17批：刷新来源与待发稿复查，禁止自行发布\n\n实际第16批成果已经保存在CN patch。本轮先从最新源核实范围，不重复处理此前豁免的人工稿，也不把二次修订重算成新剧情。权威恢复入口：`HiiragiNemu/magireco-cn-patch:{DEST}README.md`，提交`{pc["commit"]}`。本地`{W}`，任务`tsk_b9a74c32a7e449d6`。\n\n本窗口不写运行资源、不发包、不部署；完整清单/候选/累计仅CN patch。客户端整合前读回最新`docs/story-quality/client-integration/READY.json`和manifest SHA。Reader已有独立UI部署与并行改动保持。\n{end}\n\n'
 rf={};ex={}
 for p in ['STORY_QUALITY_HANDOFF.md','docs/story-quality/CONTINUATION.md']:
  text=git('reader','show',rhead+':'+p).decode()
  if marker in text:a=text.index(marker);b=text.index(end,a)+len(end);text=(text[:a]+text[b:]).lstrip('\r\n')
  rf[p]=(ptr+text).encode();ex[p]=rt[p]
 p='docs/story-quality/CONTINUATION_STATE.json';state=json.loads(git('reader','show',rhead+':'+p));state.update(updated_at=now,checkpoint='第17批来源刷新和已备稿残余复查；仅CN patch保留新证据，不发包',task_id='tsk_b9a74c32a7e449d6',active_translation_hold={'canonical_repository':'HiiragiNemu/magireco-cn-patch','path':DEST+'README.md','commit':pc['commit'],'publication_prohibited':True,'runtime_source_writes_prohibited':True,'workspace':str(W),'release_version':None});state['paths']['current_batch']=str(W);rf[p]=enc(state);ex[p]=rt[p]
 rc=commit('reader',rf,'held-batch17 recovery pointer',expected_old=ex);(W/'last-checkpoint-commits.json').write_bytes(enc({'patch':pc,'reader':rc,'note':note}));print('CHECKPOINT',pc,rc);guard()
if __name__=='__main__':main()
