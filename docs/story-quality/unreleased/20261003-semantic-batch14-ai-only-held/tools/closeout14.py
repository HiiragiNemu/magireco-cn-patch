"""Persist final proofs and an append-only coordination pointer. No runtime integration or publication."""
from pathlib import Path
import sys,json,hashlib,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from checkpoint import guard,git,tree,commit,enc,DEST

def read(n):return json.loads((W/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 guard();assert not (W/'final-proof-commit.json').exists(),'Already closed; read back instead'
 f=read('final-verification.json');r=read('final-held-commits.json');v=read('validation.json');s=read('unreleased-summary.json');ready=read('client-kit/READY.json');m=read('recovery-metadata.json')
 assert f['passed'] and f['live_readback_complete'] and f['all_candidates_still_unapplied'] and f['previous_client_targets_unchanged']==255 and not f['client_receipt_present']
 for name in ['client-real-not-integrated-expected-block.json','current-resources-not-ready-expected-block.json']:
  e=read(name);assert e['passed'] and e['manifest_sha256']==ready['manifest_sha256']
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();versions={x['url'].rsplit('/',1)[-1]:x['data'].get('version') for x in f['live']}
 coord=Path(r'D:\magia\deliveries\resource-integrity-20261002-src\.build\finish-20261003\TRANSLATION_WINDOW_HANDOFF.md');before=coord.read_bytes();marker='<!-- TRANSLATION-CLIENT-READY-BATCH11-14 -->';assert marker.encode() not in before
 note=f'''{marker}
## 最新可接入：第11—14批335目标，旧255目标原样保留

更新时间：{now}。CN patch候选提交 `{r['patch']['commit']}`，唯一入口 `docs/story-quality/client-integration/READY.json`。新manifest SHA256 `{ready['manifest_sha256']}`。335目标、333实际改文件、9674字段，原255目标的全部候选字节和操作逐项未变。旧固定清单在history/{ready['supersedes_manifest_sha256']}/中完整保存。

已阅读你方 `docs/story-quality/coordination/20261003-resource-coherence-repair-receipt.md`，它核定的是既有3323/22配套包与设备修复，不包含本窗口尚未集成的新稿。这里不要求重做旧审计，也不自行解除发布暂停。客户端准备接入时请刷新最新READY，固定SHA，并核对你方是否已有其他源修改。

将335份候选和supplemental_product_paths提案合入同一个受审main：保留原128项，追加335项，共463。check-integrated必须在该整合提交通过，然后使用统一资源工作流共同构建Scenario和delta。新版本号不是旧字节合法化的理由；真实ZIP和最终安装/缓存重放必须验证。28覆盖反例测试和335真实源/1105保全路径预检通过，现有旧源码/缓存包被正确拒绝当成新稿。没有更改你方生产配置或工作流。

请用当前manifest SHA在CN patch留下实际CLIENT_RECEIPT、整合提交、Scenario/delta版本和SHA、适用安装/设备核验结果。旧255目标清单的回执不能结算新增80目标。当前文件的存在不意味着你方已经阅读或接入；本窗口未发包、未写运行资源、Reader/ADV未部署。
<!-- /TRANSLATION-CLIENT-READY-BATCH11-14 -->

'''
 coord.write_bytes(note.encode()+before);assert coord.read_bytes().endswith(before)
 pointer={'path':str(coord),'sha256':sha(coord.read_bytes()),'previous_document_sha256':sha(before),'previous_document_preserved_as_suffix':True,'candidate_commit':r['patch']['commit'],'manifest_sha256':ready['manifest_sha256'],'targets':335,'receiver_acknowledged':False,'client_runtime_or_workflow_changed':False,'resource_repair_receipt_read':'docs/story-quality/coordination/20261003-resource-coherence-repair-receipt.md','resource_repair_receipt_excludes_held_translation':True}
 (W/'client-pointer-delivered.json').write_bytes(enc(pointer))
 proof=f'''# 第14批：最终独立核验与客户端交接

核验时间：{f['verified_at']}。CN patch候选/台账/客户端材料提交 `{r['patch']['commit']}`；Reader仅三份交接指针 `{r['reader']['commit']}`。

{f['doc_hash_checks']}份CN patch文档和3份Reader指针逐字节读回；15份已发布账文件、498历史登记以及前255个候选/7447字段的内容和顺序完整保留。旧客户端固定清单{f['previous_client_snapshot_files_verified']}份文件已归档校验，旧255目标与新清单中的对应条目逐项完全相同。

本轮80新全文/79改稿/1原样，2227正文修订；84完整日中片段包括4个旧上下文。88校订专项和28客户端接入反例测试通过，84真实Reader解析、158TXT6570精确位置同步通过。唯一显示恢复为已绑定原始日文与机器fallback日志的710044-1抱紧旁白，原节点/执行命令不变。

累计335未发布目标、9674字段；其中252新全文、83既有稿复用，尚未准备50（26已索引、24未索引）。原已发布694/385账不变。剩余50已反向生成全路径清单，不以自动整话预览为空宣称结束。下一入口324011的两个补缺片段需先核定人工/保护边界与中日对应，再决定文字修订范围。

客户端READY SHA `{ready['manifest_sha256']}`。335目标必须同时进入完整Scenario与累计JS delta。生产配置未改；补充路径提案为128旧项+335新目标=463。1105条旧修订守卫、全部335当前源字节和候选构造已经独立预检；333项尚未合入，2项因原字节相同而无需改动。现有旧源码和客户端缓存旧包均被正确拒绝冒充本批新稿。静态测试不替代新包真实设备验证。

普通玩家入口读回Scenario {versions['version_scenario.json']} / delta {versions['version_js_delta.json']}，Reader/ADV仍为9f881c9b及672900ac。这些是既有状态，不包括本批新稿。另一窗口的68524393资源修复回执已经读取，明确不包含未发布翻译。已向对方当前审计目录更新335目标接手指针，保留原文；尚无CLIENT_RECEIPT或已读确认。

本窗口未写运行资源、未发包、未创建新Release、未触发同步、未部署Reader/ADV。所有完整台账、候选及恢复材料仍只在CN patch，Reader/公开仓没有副本。原工作树修改、暂存和未跟踪状态保留。

恢复文档：`{m['path']}`；{m['files']}项文件内容，{m['bytes']}字节，SHA256 `{m['sha256']}`。这是校订恢复证据，不是游戏安装包。
'''
 files={DEST+'final-verification.json':(W/'final-verification.json').read_bytes(),DEST+'final-verification.md':proof.encode(),DEST+'tools/verify_final.py':(W/'verify_final.py').read_bytes(),DEST+'tools/negative_client14.py':(W/'negative_client14.py').read_bytes(),DEST+'tools/closeout14.py':Path(__file__).read_bytes(),'docs/story-quality/client-integration/client-pointer-delivered.json':enc(pointer),'docs/story-quality/client-integration/source-before-integration-block.json':(W/'client-real-not-integrated-expected-block.json').read_bytes(),'docs/story-quality/client-integration/current-package-negative-check.json':(W/'current-resources-not-ready-expected-block.json').read_bytes()}
 git('patch','fetch','origin','main');head=git('patch','rev-parse','FETCH_HEAD').decode().strip();cur=tree('patch',head)
 active=git('patch','show',head+':docs/story-quality/client-integration/READY.json');assert json.loads(active)['manifest_sha256']==ready['manifest_sha256']
 assert not any(p.startswith('docs/story-quality/client-integration/CLIENT_RECEIPT') for p in cur),'Client receipt appeared; reconcile before closeout'
 receipt=commit('patch',files,'held-batch14 independent final and current client-readiness pointer',expected_old={p:cur.get(p) for p in files}|{'docs/story-quality/client-integration/READY.json':cur['docs/story-quality/client-integration/READY.json']})
 (W/'final-proof-commit.json').write_bytes(enc(receipt))
 for p,b in files.items():assert git('patch','show',receipt['commit']+':'+p)==b
 path=W/'Reader_AI_Held_Batch14_20261003.md';path.write_text(path.read_text(encoding='utf8')+'\n\n'+proof+'\n最终独立核验记录提交：`'+receipt['commit']+'`。\n',encoding='utf8')
 guard();print('CLOSEOUT',json.dumps(receipt,ensure_ascii=False));print('REPORT',str(path),'SHA256',sha(path.read_bytes()));print('CLIENT_POINTER',json.dumps(pointer,ensure_ascii=False))
if __name__=='__main__':main()
