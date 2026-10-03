"""Independent remote readback and final proof that no runtime/registry was updated by this task."""
from pathlib import Path
import sys,json,gzip,datetime,hashlib
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from audit import read,save,sha,enc,git,tree,get,guard
PREV=W.parent/'semantic-batch17-ai-only-held-20261003';sys.path.insert(0,str(PREV));from checkpoint import commit
D='docs/story-quality/production-handoff/'

def main():
 guard();rec=read('final-handoff-commits.json');bases=read('bases.json');heads={};trees={}
 for repo in ('reader','patch','public'):
  git(repo,'fetch','origin','main');heads[repo]=git(repo,'rev-parse','FETCH_HEAD').decode().strip();trees[repo]=tree(repo,heads[repo])
 for p,h in rec['files'].items():assert sha(git('patch','show',heads['patch']+':'+p))==h,p
 for p,h in rec['reader_pointers'].items():assert sha(git('reader','show',heads['reader']+':'+p))==h,p
 own_runtime_changes={};cumulative=0
 for repo in ('reader','patch'):
  original=read(repo+'-tree.json');new=trees[repo];diff=[p for p in set(original)|set(new) if original.get(p)!=new.get(p) and p!='STORY_QUALITY_HANDOFF.md' and not p.startswith('docs/story-quality/')];assert not diff,(repo,diff);own_runtime_changes[repo]=diff
  if repo=='patch':
   for p,h in original.items():
    if p.startswith('docs/story-quality/contributions/'):
     assert new[p]==h,p;cumulative+=1
 for repo in ('reader','public'):
  assert not [p for p in trees[repo] if p.startswith(('docs/story-quality/contributions/','docs/story-quality/production-handoff/','docs/story-quality/client-integration/'))]
 ready=json.loads(git('patch','show',heads['patch']+':docs/story-quality/client-integration/READY.json'));assert ready==read('ready.json')
 prod=json.loads(git('patch','show',heads['patch']+':'+D+'READY.json'))
 for name,h in prod['files'].items():assert sha(git('patch','show',heads['patch']+':'+D+name))==h,name
 raw=git('patch','show',heads['patch']+':'+prod['reader_input_manifest']);assert sha(raw)==prod['reader_input_manifest_sha256'];rp=json.loads(gzip.decompress(raw));assert len(rp['files'])==601
 for e in rp['files']:assert trees['reader'][e['path']]==e['source_blob'],e['path']
 manifest=json.loads(gzip.decompress(git('patch','show',heads['patch']+':'+ready['manifest'])))
 for e in manifest['files']:assert trees['patch'][e['path']]==e['before_blob'],e['path']
 receipts=[p for p in trees['patch'] if 'CLIENT_RECEIPT' in p.upper() and '/history/' not in p];assert not receipts,receipts
 urls=[('https://magireader.pages.dev/adv-release-build.json','final-live/build.json'),('https://magireader.pages.dev/api/adv/release','final-live/adv.json'),('https://magireco-personal-release.pages.dev/version_scenario.json','final-live/scenario.json'),('https://magireco-personal-release.pages.dev/version_js_delta.json','final-live/delta.json'),('https://magireader.pages.dev/api/story-json/710044/cn/0','final-live/710044.json')]
 live=[get(u,n) for u,n in urls];assert all(x['status']==200 for x in live)
 assert read('final-live/build.json')['source_revision']==read('live/build.json')['source_revision'];assert read('final-live/adv.json')==read('live/adv.json')
 assert read('final-live/scenario.json')['version']==3323 and read('final-live/delta.json')['version']==22
 assert sha((W/'final-live/710044.json').read_bytes())==sha((W/'live/body-710044-1.json').read_bytes())
 proof={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':True,'heads':heads,'cn_patch_document_hashes_checked':len(rec['files']),'reader_pointer_hashes_checked':len(rec['reader_pointers']),'unchanged_cumulative_contribution_files':cumulative,'reader_input_files_checked_remote':601,'client_targets_checked_remote':361,'client_manifest_sha256':ready['manifest_sha256'],'reader_input_manifest_sha256':prod['reader_input_manifest_sha256'],'production_runtime_differences':own_runtime_changes,'client_receipt_present':False,'reader_production_source':read('final-live/build.json')['source_revision'],'reader_deployment':read('final-live/adv.json')['deployment'],'scenario_version':3323,'js_delta_version':22,'live':live,'known_first_review_pending':0,'known_residual_review_pending':0,'unpublished_targets':361,'reader_data_generated_and_verified':True,'reader_live_uses_final_candidates':False,'game_package_created':False,'published':False,'deployed':False,'original_worktree_preserved':True}
 save('final-verification.json',proof)
 paste=f'''# 发给客户端资源发布窗口的接续内容

请从 `HiiragiNemu/magireco-cn-patch` 最新main读取：

- `docs/story-quality/production-handoff/README.md`、`READY.json`
- `docs/story-quality/client-integration/READY.json`

已确认AI校订待办为0；361个已验证目标等待正式整合/发行，最新客户端manifest SHA256是 `{ready['manifest_sha256']}`，11,226条字段操作。生产交付提交`{rec['patch']['commit']}`。目标数量相同不能代替manifest新鲜度检查。

不要从现网Reader下载正文来发包：线上Reader仍是15d2ee95/f271c901旧稿。游戏侧直接使用CN patch的客户端manifest，保留128旧delta补充路径并纳入361目标，共489。先current_ready_gate，再check-source/stage；把正文和补充路径表合入同一个受审main，check-integrated通过后，用既有统一发布流程共同构建完整Scenario与累计JS delta。不能只发delta或只发Scenario，也不要用旧编号发布器。

对实际版本/manifest/ZIP/交叠文件以及正常安装、缓存delta重放、离线导入、手动重下的最终文件进行核验；完成后在CN patch留包含当前manifest SHA、实际整合提交、配套版本及包SHA的CLIENT_RECEIPT。已修复的资源链规则继续保留。

Reader另有601个独立输入及经过实际生成/校验的目录、全文搜索、语音/来源清单、JSON分片/分包；入口在production-handoff。本地隔离产物不是已发布Reader。游戏侧不依赖Reader先上线，且521110-9的两仓原图片不同，禁止跨仓整文件覆盖。Reader的整合/完整应用构建/部署/ADV登记须独立完成。累计贡献和完整台账只在CN patch，保留全部接手前成果。
'''
 files={D+'final-verification.json':enc(proof),D+'PASTE_TO_CLIENT_WINDOW.md':paste.encode(),D+'tools/verify_remote_handoff.py':(W/'verify_remote_handoff.py').read_bytes()}
 pt=trees['patch'];pc=commit('patch',files,'production handoff independent remote verification',expected_old={p:pt.get(p) for p in files});save('final-proof-commit.json',pc)
 report=W/'Reader_Production_Handoff_20261003.md';report.write_bytes(report.read_bytes()+('\n\n## 最终远端读回\n\n产物交付提交：CN patch `'+rec['patch']['commit']+'`；Reader仅指针 `'+rec['reader']['commit']+'`。最终核验提交 `'+pc['commit']+'`。'+str(len(rec['files']))+'份交付文档、3份Reader指针与全部601/361输入源版本读回通过；旧累计账'+str(cumulative)+'份保持。5个在线接口再次返回200，正式Reader仍旧稿、Scenario3323/delta22仍不含待发新稿。\n\n'+paste).encode())
 guard();print(json.dumps({'verified':proof,'final_proof_commit':pc},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
