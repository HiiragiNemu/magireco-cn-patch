"""Persist independent verification and actual client pointer delivery; never claim a client receipt."""
from pathlib import Path
import sys,json,hashlib
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from checkpoint import guard,git,tree,commit,enc,DEST

def load(n):return json.loads((W/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 guard();assert not (W/'final-proof-commit.json').exists();v=load('final-verification.json');r=load('final-document-commit.json');p=load('pointer-final.json');ready=load('client-kit/READY.json');assert v['passed'] and v['live_readback_complete'] and v['same_count_freshness_check_tested_against_real_remote']
 versions=[x['data']['version'] for x in v['live'] if 'version_scenario.json' in x['url']];delta=[x['data']['version'] for x in v['live'] if 'version_js_delta.json' in x['url']];assert len(set(versions))==1
 target=Path(p['client_pointer']['path']);assert sha(target.read_bytes())==p['client_pointer']['sha256'];proof=f'''# 第16批最终核验与客户端接入指针回执

核验时间：{v['verified_at']}。本批CN patch候选/账本提交`{r['patch']['commit']}`，Reader三份指针提交`{p['reader']['commit']}`。

独立从远端读回59份CN patch文档、3份Reader指针，当前361候选/10402字段与清单一致。前10312条判断的原文、译文、地址、顺序完整保留，30个活动候选版本更新，旧361候选及配套字段/逐篇索引快照保留。694/385旧发布账、498历史ID、24项来源豁免未改；所有生产JSON与240个原TXT源仍是此前字节，delta生产配置未改。

来源刷新中的新增候选筛选还使用了去除控制片段后至少5个字符的门槛，以减少短句偶合；没有被选中不等于该文本已被证明人工翻译或语义正确。短句、格式包装及无法精确对上既有机器日志的内容仍属于来源调查边界，不据此宣称全库无AI误译。\n\n77项测试与30真实Reader解析通过，所有新增90字段仍具有严格机器导入证据。第15批26片段/638字段只作为已有成果保留，不再计入本轮。旧正文/执行节点/图像基线不受影响，特别是521110-9的Reader/玩家双图像基线没有相互覆盖。

最新版manifest SHA `{ready['manifest_sha256']}`。已用真实origin main执行current_ready_gate：新清单通过；同为361目标的旧清单`{r['previous_manifest_sha256']}`被明确拒绝为已被替代。此检查工具已入库，但没有修改对方生产工作流；客户端必须在其整合/构建和串行发布前执行，不能把一次通过当成永远不会有并行变化。

客户端当前审计目录的TRANSLATION_WINDOW_HANDOFF.md已更新，先前完整内容保留为后缀，SHA `{p['client_pointer']['sha256']}`。这只证明接手材料已写到对方工作目录，不证明对方已读或已接入。当前无CLIENT_RECEIPT。

普通玩家入口此次读回Scenario {versions[0]} / JS delta {delta[0]}，不是本窗口新发包。Reader/ADV当前源码为15d2ee951514ea13e67d68a6864707a7f926fa98，这是并行UI线的既有部署，本窗口未部署新剧情。五个入口均200，但不把这当成本轮新稿上线或新包实机验收。

本窗口未创建资源ZIP/Release、未触发发布或同步、未写运行资源、未部署。Reader和公开仓的累计台账/候选副本为0，原工作树修改/暂存/未跟踪状态保留。

恢复文档包含{r['recovery']['files']}项UTF-8文件内容，SHA `{r['recovery']['sha256']}`；实际入库状态以本最终核验和当前READY为准，不以恢复快照中可能保留的过渡进度为准。下一阶段仍可复查有机器证据的残句或调查尚未确认来源的路径，不自动重译人译/官方稿，不重复发旧包。
'''
 files={DEST+'final-verification.json':(W/'final-verification.json').read_bytes(),DEST+'final-verification.md':proof.encode(),DEST+'tools/verify_remote16.py':(W/'verify_remote16.py').read_bytes(),DEST+'tools/finish_pointers16.py':(W/'finish_pointers16.py').read_bytes(),DEST+'tools/closeout16.py':(W/'closeout16.py').read_bytes(),DEST+'recording-tool-error.json':(W/'recording-tool-error.json').read_bytes(),'docs/story-quality/client-integration/client-pointer-delivered.json':enc(p['client_pointer']),'docs/story-quality/client-integration/current-ready-gate-validation.json':enc({'actual_remote_current_pass':v['current_READY_gate'],'actual_remote_old_same_count_rejected':v['old_361_manifest_rejected'],'old_manifest_sha256':r['previous_manifest_sha256'],'new_manifest_sha256':r['manifest_sha256'],'no_workflow_modified':True,'no_runtime_or_publication_performed':True})}
 git('patch','fetch','origin','main');head=git('patch','rev-parse','FETCH_HEAD').decode().strip();cur=tree('patch',head);result=commit('patch',files,'held-batch16 independent verification and client coordination',expected_old={p:cur.get(p) for p in files})
 git('patch','fetch','origin','main');latest=git('patch','rev-parse','FETCH_HEAD').decode().strip()
 for path,data in files.items():assert git('patch','show',latest+':'+path)==data,path
 (W/'final-proof-commit.json').write_bytes(enc({'commit':result,'remote_main_readback':latest,'files_verified':len(files),'published':False}));report=W/'Reader_AI_Held_Batch16_20261003.md';report.write_text(report.read_text(encoding='utf8')+'\n\n'+proof+'\n最终核验与协调提交：`'+result['commit']+'`。\n',encoding='utf8');guard();print('CLOSEOUT',result,'REMOTE_PROOF_FILES',len(files));print('REPORT',str(report),'SHA256',sha(report.read_bytes()))
if __name__=='__main__':main()
