"""Persist only held translation evidence and handoff docs. Runtime/release writes forbidden."""
from pathlib import Path
import os,subprocess,datetime,json,gzip,hashlib,sys
W=Path(__file__).resolve().parent;ROOT=W.parent;R=ROOT/'repo';P='A:/StoryQuality-20260930-1739/patch.git'
BATCH='20261003-semantic-batch14-ai-only-held';DEST='docs/story-quality/unreleased/'+BATCH+'/'
def git(repo,*args,data=None,env=None):
 p=subprocess.run(['git',*(['--git-dir='+P] if repo=='patch' else []),*args],cwd=R,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=120)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
 return p.stdout
def tree(repo,ref):
 out={}
 for row in git(repo,'ls-tree','-rz',ref).split(b'\0'):
  if row:m,p=row.split(b'\t',1);out[p.decode()]=m.decode().split()[2]
 return out
def enc(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def read(n):return json.loads((W/n).read_bytes())
def guard():
 for n,args in [('initial-diff.bin',('diff','--binary')),('initial-staged.bin',('diff','--cached','--binary')),('initial-status-z.bin',('status','--porcelain=v1','-z'))]:assert git('reader',*args)==(W/n).read_bytes(),n
 for n in ['dirty-tracked-hashes.json','untracked-hashes.json']:
  for p,h in read(n).items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p

def commit(repo,files,label,expected_old=None):
 assert repo in ('reader','patch') and files
 for p,b in files.items():
  assert p=='STORY_QUALITY_HANDOFF.md' or p.startswith('docs/story-quality/'),('Forbidden non-document path',p)
  from pending_contract import allow_document_destination
  allow_document_destination(repo,p)
  assert isinstance(b,bytes) and p.endswith(('.md','.json','.json.gz','.tsv','.py','.cjs')),p
  if repo=='reader':assert p in ['STORY_QUALITY_HANDOFF.md','docs/story-quality/CONTINUATION.md','docs/story-quality/CONTINUATION_STATE.json'],'Reader may only get a pointer'
 guard();git(repo,'fetch','origin','main');base=git(repo,'rev-parse','FETCH_HEAD').decode().strip();bt=tree(repo,base);expect={p:bt.get(p) for p in files}
 if expected_old is not None:assert all(bt.get(p)==h for p,h in expected_old.items()),'Destination changed since explicit read; reconcile before committing'
 for attempt in range(3):
  git(repo,'fetch','origin','main');head=git(repo,'rev-parse','FETCH_HEAD').decode().strip();cur=tree(repo,head);assert all(cur.get(p)==h for p,h in expect.items()),'Concurrent destination edit; reconcile first'
  env=os.environ.copy()|{'GIT_INDEX_FILE':str(W/(repo+'-docs-index-'+datetime.datetime.now().strftime('%H%M%S%f'))),'GIT_AUTHOR_NAME':'HiiragiNemu','GIT_AUTHOR_EMAIL':'128921071+HiiragiNemu@users.noreply.github.com','GIT_COMMITTER_NAME':'HiiragiNemu','GIT_COMMITTER_EMAIL':'128921071+HiiragiNemu@users.noreply.github.com'}
  git(repo,'read-tree',head,env=env);rows=[];newblobs={}
  for p,b in files.items():
   h=git(repo,'hash-object','-w','--stdin',data=b).decode().strip();newblobs[p]=h;rows.append(('100644 '+h+'\t'+p+'\0').encode())
  if all(cur.get(p)==h for p,h in newblobs.items()):return {'commit':head,'noop':True}
  git(repo,'update-index','-z','--index-info',data=b''.join(rows),env=env);nt=git(repo,'write-tree',env=env).decode().strip();c=git(repo,'commit-tree',nt,'-p',head,data=('docs(story): '+label+'; unreleased translation only [skip ci]\n').encode(),env=env).decode().strip();after=tree(repo,c)
  assert all(after[p]==v for p,v in cur.items() if p not in files) and all(after[p]==h for p,h in newblobs.items())
  try:git(repo,'push','origin',c+':refs/heads/main')
  except RuntimeError:
   if attempt==2:raise
   continue
  git(repo,'fetch','origin','main');remote=tree(repo,'FETCH_HEAD');assert all(remote[p]==h for p,h in newblobs.items()),'Remote docs readback mismatch'
  if repo=='reader':git(repo,'merge','--ff-only',c);guard()
  return {'commit':c,'parent':head,'files':len(files),'runtime_and_all_other_paths_preserved':True,'nonforce_main_push':True,'published':False}
 raise RuntimeError('No stable documentation head')

def main():
 note=' '.join(sys.argv[1:]) or 'Unreleased translation preparation checkpoint'
 progress=read('progress.json');progress.update(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),checkpoint=note,published=False,release_version=None,publication_prohibited=True);(W/'progress.json').write_bytes(enc(progress))
 names=['progress.json','bases.json','live-baseline.json','chapters.json','review-sources.json','provenance.json','repair-plan.json','reuse-results.json','validation.json','text-plan.json','pending-summary.json','final-verification.json','choice-review.json','second-pass-applied.json','trusted-terms.json','trusted-terms-02.json']
 evidence={n:read(n) for n in names if (W/n).exists()}
 evidence['decisions']={p.name:json.loads(p.read_bytes()) for p in sorted((W/'review').glob('*.edits.json'))}
 evidence['aligned_sources']={p.name:json.loads(p.read_bytes()) for p in sorted((W/'review').glob('*.aligned.json'))}
 evidence['policy']={'game_packages_created':False,'release_assets_written':False,'runtime_source_paths_committed':False,'website_deployed':False,'ADV_registered':False,'canonical_storage':'CN patch only','awaiting_resource_audit_alignment':True}
 local=enc(evidence);compressed=gzip.compress(local,mtime=0);(W/'checkpoint-evidence.json.gz').write_bytes(compressed)
 md=f'# 未发布剧情校订：{BATCH}\n\n更新：{progress["updated_at"]}\n\n{note}\n\n本轮维护者明确要求继续校订但不发包。所有候选文字仅在隔离暂存目录与此文档证据中，不修改两仓运行资源，不构建资源包、不推送Release、不触发同步、不部署Reader/ADV。资源窗口完成审计与修正对齐后仍须刷新源blob并重新审核是否发布，不能直接执行旧发布器。\n\n本地目录：`{W}`。任务：`tsk_4278bf15fbb6e329`。恢复先读`progress.json`与`checkpoint-evidence.json.gz`。所有字段的日文、旧译、新译、源版本和来源依据保留。已发布与已校订未发布分账；校订文本复用不得冒充新翻译。累计台账和全部待办只在CN patch；旧已发布记录、498个历史ID和快照不覆盖。\n'
 files={DEST+'README.md':md.encode(),DEST+'progress.json':enc(progress),DEST+'checkpoint-evidence.json.gz':compressed}
 for p in W.glob('*.py'):
  if p.name in ['baseline.py','collect.py','checkpoint.py','reuse.py','stage.py','decisions.py','review_io.py','record_raw.py','exact_json.py','translation_rules.py']:files[DEST+'tools/'+p.name]=p.read_bytes()
 pc=commit('patch',files,'held-batch14 checkpoint')
 marker='<!-- AI-ONLY-HELD-BATCH14 -->';end='<!-- /AI-ONLY-HELD-BATCH14 -->'
 pointer=f'{marker}\n## 当前任务：继续校订，禁止发布\n\n维护者最新指示：继续翻译校订，但不发包；等待资源审计修正对齐后再考虑发布。本轮不得调用旧scenario发布器、镜像工作流或Reader/ADV部署。运行资源路径保持原样，候选文字仅隔离暂存。\n\n最新未发布恢复入口只在 `HiiragiNemu/magireco-cn-patch:{DEST}README.md`，本次文档提交 `{pc["commit"]}`；本地 `{W}`，任务 `tsk_4278bf15fbb6e329`。本批详细处理清单与累计未发布统计只在CN patch，Reader不存副本。\n\n{end}\n\n'
 rfiles={}
 for p in ['STORY_QUALITY_HANDOFF.md','docs/story-quality/CONTINUATION.md']:
  t=(R/p).read_text(encoding='utf8')
  if marker in t:
   a=t.index(marker);b=t.index(end,a)+len(end);t=t[:a]+t[b:];t=t.lstrip('\r\n')
  rfiles[p]=(pointer+t).encode()
 st=json.loads((R/'docs/story-quality/CONTINUATION_STATE.json').read_bytes());st.update(updated_at=progress['updated_at'],instruction='继续确认AI剧情校订；本轮不发包、不写运行资源、不部署；待资源审计修正对齐后重新评估发布。累计与完整清单仅CN patch。',checkpoint='校订项目继续，全部新增成果未发布；见CN patch独立未发布恢复入口',task_id='tsk_4278bf15fbb6e329',active_translation_hold={'publication_prohibited':True,'runtime_source_writes_prohibited':True,'canonical_repository':'HiiragiNemu/magireco-cn-patch','path':DEST+'README.md','evidence':DEST+'checkpoint-evidence.json.gz','commit':pc['commit'],'workspace':str(W),'release_version':None});st['paths']['current_batch']=str(W)
 rfiles['docs/story-quality/CONTINUATION_STATE.json']=enc(st);rc=commit('reader',rfiles,'held-batch14 pointer')
 receipt={'patch':pc,'reader':rc,'note':note,'evidence_sha256':hashlib.sha256(compressed).hexdigest()};(W/'last-checkpoint-commits.json').write_bytes(enc(receipt));print('CHECKPOINT',json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':main()
