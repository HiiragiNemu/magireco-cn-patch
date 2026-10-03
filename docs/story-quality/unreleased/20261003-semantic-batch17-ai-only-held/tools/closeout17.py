"""Persist independent live/document checks and client pointer evidence, never a release."""
from pathlib import Path
import sys,json,hashlib,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W))
from checkpoint import guard,git,tree,commit,enc,DEST


def load(n):return json.loads((W/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    guard();assert not (W/'final-proof-commit.json').exists(),'Already finalized; read back instead'
    v=load('final-verification.json');r=load('final-document-commit.json');p=load('pointer-final.json');ready=load('client-kit/READY.json');val=load('validation.json');remaining=load('remaining-status-summary.json')
    assert v['passed'] and v['live_readback_complete'] and v['same_count_freshness_check_tested_against_real_remote'] and v['residual_sweep_remote_verified']
    assert val['tests_passed']==87 and val['actual_reader_parser_files']==235 and remaining['actionable_first_review_pending']==0 and remaining['identified_residual_review_pending_fields']==0
    versions=[x['data']['version'] for x in v['live'] if 'version_scenario.json' in x['url']];delta=[x['data']['version'] for x in v['live'] if 'version_js_delta.json' in x['url']];assert len(versions)==2 and len(set(versions))==1 and len(delta)==1
    site=[{'url':x['url'],'data':x['data']} for x in v['live'] if 'magireader.pages.dev' in x['url']]
    website_sources=sorted({x['data'].get('source_revision','not_present') for x in site})
    target=Path(p['client_pointer']['path']);assert sha(target.read_bytes())==p['client_pointer']['sha256']
    proof=f'''# 第17批最终独立读回：校订闭合，游戏仍待整合发布

核验时间：{v['verified_at']}。候选/累计记录提交`{r['patch']['commit']}`；Reader三份交接指针提交`{p['reader']['commit']}`。

实际读回{v['cn_patch_document_hashes_verified']}份CN patch文档及3份Reader指针，{v['historical_published_files_preserved']}份原发布账文件、{v['old_snapshot_files_verified']}份旧候选/账本快照通过哈希核验。当前361个候选的11226条操作与累计记录逐项匹配，原10402条地址/原文/译文/顺序保留；235份活动候选增加824个新纠错地址，0篇新增首次全文复核。

1079个原来源池逐路径核算通过：694份原已发布复核记录，361份已备稿待整合/发布，23份人译恢复及1份已有历史复核不重新处理。当前已确认范围待首次校订0；本批6372条残余原机翻字段已全数判断，824修正、5548保留，未处理字段及片段均0。来源未知和日文映射未知的文本不自动归为机器稿，也不宣布全仓库绝对无错。

完整当前日中文JSON库存和保护清单已与来源审计冻结版本逐项比较，无漂移。所有361份客户端/Reader生产正文及240份生产TXT仍是原先字节；521110-9的独立Reader与客户端图片基线保持。生产delta配置未改。累计候选之外的原始修订和原工作树差异、暂存、未跟踪文件均保留。

87项本批测试与235个真实Reader解析比较通过。200份TXT候选通过622节完整精确匹配、44个历史底稿核验；累计240导出文件保留原27098个修改位置并追加2074个，合计29172。上述导出位置不是新增翻译句数。旧710044抱紧旁白的恢复证明已从历史文件验证后继承，不属于本批新增显示。

最新版manifest SHA：`{ready['manifest_sha256']}`。真实origin当前main的READY检查通过；旧的同为361个目标的manifest `{r['previous_manifest_sha256']}` 被明确拒绝为已替代。检查工具未被嵌入对方生产工作流，客户端仍须在整合、构建及串行发布事务前执行。新鲜度检查不能取代客户端发布锁、真实包/元数据及最终设备文件验证。

JS delta选择提案仍为128旧项加361目标，共489项。所有361个候选和1125条旧源码保全路径已预检。客户端应将正文和补充列表合入同一个受审main，再统一构建Scenario及累计JS delta。实际旧源码和旧缓存包被拒绝只是负例验证，不是已生成新包的验收。

客户端当前审计目录接手文件已更新，原文保留为后缀。文件SHA `{p['client_pointer']['sha256']}`。这只说明材料送达目录，不表明对方已阅读或已经整合；本次未发现CLIENT_RECEIPT。

两条普通玩家入口实际读回Scenario {versions[0]}，delta入口为 {delta[0]}。Reader/ADV实际源码读回为 `{', '.join(website_sources)}`，属于既有状态，不是本窗口发布新剧情。五个只读入口均200。没有进行本批新包设备测试，没有新Release/游戏ZIP/资源同步/Reader部署。

累计账、全部已处理/待处理清单及恢复内容只在CN patch；Reader与公开发行仓没有副本。恢复文档含{r['recovery']['files']}项UTF-8文件内容，SHA `{r['recovery']['sha256']}`，不是游戏安装包。恢复文档中较早过渡状态以本回执及当前READY为准。
'''
    files={DEST+'final-verification.json':(W/'final-verification.json').read_bytes(),DEST+'final-verification.md':proof.encode(),DEST+'tools/verify_remote17.py':(W/'verify_remote17.py').read_bytes(),DEST+'tools/finish_pointers17.py':(W/'finish_pointers17.py').read_bytes(),DEST+'tools/closeout17.py':(W/'closeout17.py').read_bytes(),DEST+'recording-tool-error.json':(W/'recording-tool-error.json').read_bytes(),'docs/story-quality/client-integration/client-pointer-delivered.json':enc(p['client_pointer']),'docs/story-quality/client-integration/current-ready-gate-validation.json':enc({'actual_remote_current_pass':v['current_READY_gate'],'actual_remote_old_same_count_rejected':v['old_361_manifest_rejected'],'old_manifest_sha256':r['previous_manifest_sha256'],'new_manifest_sha256':r['manifest_sha256'],'no_workflow_modified':True,'no_runtime_or_publication_performed':True})}
    git('patch','fetch','origin','main');head=git('patch','rev-parse','FETCH_HEAD').decode().strip();cur=tree('patch',head)
    assert git('patch','show',head+':docs/story-quality/client-integration/READY.json')==(W/'client-kit/READY.json').read_bytes(),'Client READY changed; reconcile'
    assert not any(x.startswith('docs/story-quality/client-integration/CLIENT_RECEIPT') for x in cur),'Client receipt appeared; reconcile'
    result=commit('patch',files,'held-batch17 independent readback and client coordination',expected_old={path:cur.get(path) for path in files})
    git('patch','fetch','origin','main');latest=git('patch','rev-parse','FETCH_HEAD').decode().strip()
    for path,data in files.items():assert git('patch','show',latest+':'+path)==data,path
    (W/'final-proof-commit.json').write_bytes(enc({'commit':result,'remote_main_readback':latest,'files_verified':len(files),'published':False}))
    report=W/'Reader_AI_Held_Batch17_20261003.md';report.write_text(report.read_text(encoding='utf8')+'\n\n'+proof+'\n最终核验提交：`'+result['commit']+'`。\n',encoding='utf8')
    summary=f'''# 第17批交付摘要

新增首次全文校订：0。既有候选中的残余机翻：6372条已全部复查，235片段修正824个此前未改的字段，5548条保留。中断前已完成5900条/767处修正，本次补完472条/57处并统一完成验证、入库和客户端交接。

当前已确认范围：1079个物理片段=694原已发布记录+361已备稿待发布+23人译恢复排除+1旧复核排除。待首次校订0，本次残余复查待处理0；仍待客户端整合/正式发包361。未知来源不自动重译，不声明全仓库无误译。

本版候选累计11226个字段操作=9091正文修订+14选项+2121同源复用同步。原10402字段历史内容及顺序保留。87测试、235真实Reader解析、622TXT完整节及44历史底稿验证通过；累计240导出文件的原27098位置保留并追加2074至29172。

客户端唯一接入：HiiragiNemu/magireco-cn-patch 的 docs/story-quality/client-integration/READY.json。manifest SHA256 {ready['manifest_sha256']}。候选提交 {r['patch']['commit']}；最终核验提交 {result['commit']}。目标数量仍361但235个候选已变；旧manifest已经归档，不能混用。delta提案489路径，生产配置未动。同一个受审main整合正文/选择表后统一构建Scenario/delta，并按客户端规范验收最终安装。

本窗口未发包、未写运行资源、未部署。实际玩家入口仍Scenario{versions[0]}/delta{delta[0]}；没有当前新稿CLIENT_RECEIPT。Reader仅三份指针提交 {p['reader']['commit']}。累计/全部路径/候选/恢复文档仅CN patch，原498历史ID及接手前贡献保留。

完整逐篇记录：{DEST}README.md。剩余核算：{DEST}remaining-status-summary.json、scope-status.tsv。全部6372条判定：{DEST}sweep-review-ledger.json.gz。累计：docs/story-quality/contributions/README.md。恢复证据{r['recovery']['files']}项，SHA256 {r['recovery']['sha256']}。
'''
    (W/'Reader_AI_Held_Batch17_Summary_20261003.md').write_text(summary,encoding='utf8');guard();print('CLOSEOUT',result,'READBACK_FILES',len(files));print('REPORT',str(report),sha(report.read_bytes()));print('SUMMARY',str(W/'Reader_AI_Held_Batch17_Summary_20261003.md'))

if __name__=='__main__':main()
