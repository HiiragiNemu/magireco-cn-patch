"""Prepare a source-bound, superseding 361-target packet for the separate client publisher. No publish actions."""
from pathlib import Path
import sys,json,gzip,hashlib,copy,subprocess,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W))
from checkpoint import guard,enc
from initialize import git,save
from client_candidate_tools import preflight,load_packet,verify_layers


def read(n):return json.loads((W/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    guard();coverage=read('sweep-completion-validation.json');assert coverage['passed'] and coverage['pending_fields']==0
    oldready=read('prior-client-ready.json');oldpacket=json.loads(gzip.decompress((W/'prior-integration-manifest.json.gz').read_bytes()));packet=json.loads(gzip.decompress((W/'amended-integration-manifest.json.gz').read_bytes()))
    git('patch','fetch','origin','main');ref=git('patch','rev-parse','FETCH_HEAD').decode().strip()
    assert git('patch','show',ref+':docs/story-quality/client-integration/READY.json')==(W/'prior-client-ready.json').read_bytes(),'Parallel READY changed; reconcile'
    staged,proof=preflight('A:/StoryQuality-20260930-1739/patch.git',ref,packet)
    assert len(staged)==362 and sum(v=='staged_only' for v in proof['states'].values())==359 and sum(v=='already_integrated' for v in proof['states'].values())==2
    proposal=staged['configures/js-delta-baseline.json'];cfg=json.loads(proposal);assert len(cfg['supplemental_product_paths'])==489 and cfg['supplemental_product_paths'][:128]==packet['config_before']['supplemental_product_paths']
    oldentries={e['path']:e for e in oldpacket['files']};changed=[]
    for e in packet['files']:
        o=oldentries[e['path']];assert e['operations'][:len(o['operations'])]==o['operations']
        if e!=o:changed.append(e['path'])
    assert len(changed)==235 and packet['field_change_count']==11226 and len(packet['preservation_guards'])==1125
    packet['source_reference']=ref
    evidence='docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/validation.json'
    if evidence not in packet['batch_validation_entries']:packet['batch_validation_entries'].append(evidence)
    packet.update(freshness_gate='current_ready_gate.py',same_target_count_does_not_imply_same_content=True,residual_review_coverage=coverage['source_fields'])
    kit=W/'client-kit';kit.mkdir(exist_ok=True);packed=gzip.compress(enc(packet),mtime=0);(kit/'integration-manifest.json.gz').write_bytes(packed);load_packet(kit/'integration-manifest.json.gz',sha(packed));(kit/'js-delta-baseline.proposed.json').write_bytes(proposal)
    for n in ['client_candidate_tools.py','exact_json.py','translation_rules.py','test_client_integration.py','current_ready_gate.py','test_current_ready_gate.py']:(kit/n).write_bytes((W/n).read_bytes())
    proof.update(passed=True,targets=361,changed_targets=359,field_changes=11226,amended_existing_targets=235,appended_fields=824,new_completed_stories=0,old_field_operations_preserved=10402,unchanged_packet_entries=126,prior_manifest_sha256=oldready['manifest_sha256'],preservation_guard_paths=1125,old_delta_paths=128,proposed_delta_paths=489,published=False,runtime_applied=False,real_new_packages_tested=False,device_test_performed=False)
    (kit/'integration-preflight.json').write_bytes(enc(proof));save('client-preflight.json',proof)
    text=f'''# 客户端统一发布：第17批后的最新候选接入

本窗口没有写运行资源、发包、触发同步或部署。当前361个目标、11226个显示字段操作，包含第11—17批已验证成果；本批在235个既有目标追加824处残余纠错，不增加全文复核篇数。此前10402条操作逐项保留。当前manifest SHA-256：`{sha(packed)}`。

旧manifest `{oldready['manifest_sha256']}` 及其361目标快照按原SHA保存在history/。不能因数量同为361就继续用旧稿或旧验收回执；本批新增的是候选内容版本，不是新剧情路径。

## 固定最新版本再整合

在客户端CN patch工作树先正常刷新origin/main，再读取本目录READY。先执行current_ready_gate.py检查远端当前main的READY与实际本地manifest是否一致；它不会把旧本地READY当成最新，也不会改文件或发包。示例：

```powershell
$kit = Join-Path $PWD 'docs/story-quality/client-integration'
$ready = Get-Content (Join-Path $kit 'READY.json') -Raw | ConvertFrom-Json
$manifest = Join-Path $kit 'integration-manifest.json.gz'
python (Join-Path $kit 'current_ready_gate.py') --repo $PWD --manifest $manifest --manifest-sha256 $ready.manifest_sha256
python (Join-Path $kit 'client_candidate_tools.py') --manifest $manifest --manifest-sha256 $ready.manifest_sha256 check-source --repo $PWD --ref HEAD
```

需要准备文件时，用同一工具的stage命令，输出必须是Git工作树外尚不存在的新目录。它只构造隔离候选，不合并、不提交、不推送：

```powershell
python (Join-Path $kit 'client_candidate_tools.py') --manifest $manifest --manifest-sha256 $ready.manifest_sha256 stage --repo $PWD --ref HEAD --output 'D:\\magia\\deliveries\\client-story-candidates-through-batch17'
```

全部目标绑定各自客户端原始blob及SHA，521110-9仍保留Reader/客户端原有图片差异，不能复制Reader整文件替代客户端候选。遇到源的第三种版本时停止并逐字段协调。2个already_integrated状态是原文本来已相同，不代表其余359份候选已经合入。

## Scenario和累计JS delta必须同时接入

普通delta的product()不自动选scenario，补充选择提案保留原128项再加361目标，共489项。生产configures/js-delta-baseline.json没有被本窗口改动。客户端须在同一个受审main提交中合入正文与补充路径列表；不得丢弃旧项或从旧delta还原过时剧情。完整JS103本体无需因为本批文本而重制。

整合提交后，再次确认远端最新READY，并执行：

```powershell
python (Join-Path $kit 'client_candidate_tools.py') --manifest $manifest --manifest-sha256 $ready.manifest_sha256 check-integrated --repo $PWD --ref HEAD
```

check-source仅证明可以准备；check-integrated才要求所有候选已合入且delta列表完整。通过后由已有.github/workflows/publish-js-delta.yml统一流程从同一提交构建Scenario和累计JS delta，保留客户端串行发布事务、防回退及元数据身份核验。一次只读新鲜度检查不替代发布锁；开始实际发布事务前还须复核当前清单SHA。

## 验证实际包和设备

工具verify-packages需要真实Scenario、delta、完整JS包，基础包用--base逐个加入。必须检查所有361目标在两个包中均等于当前候选、1125条既有源码保全路径、全部剧情交叠条目，以及Scenario/JS/delta安装和缓存delta重放的最终字节。新版本号里面装旧字节会失败。

本次真实旧源码和留存旧包被拒绝，仅证明它们不含最新候选；没有构建新游戏包，也没有完成新包设备验收。客户端须测试适用的正常更新、全新安装、缓存重放、离线导入、手动重下与设备最终文件，留下带当前manifest SHA、整合提交、Scenario/delta版本与SHA、元数据及设备证据的CLIENT_RECEIPT。

Reader运行源和部署仍是独立未完成交付。累计Reader TXT候选在第17批cumulative-reader-exports.json.gz，仅CN patch存储，不从旧批单份TXT覆盖后续修改。全部累计贡献和已处理/待处理台账仍仅CN patch；历史原译者署名不重新归功。
'''
    (kit/'README.md').write_text(text,encoding='utf8')
    ready=copy.deepcopy(oldready);ready.update(schema=4,source_reference=ref,field_changes=11226,manifest_sha256=sha(packed),supersedes_manifest_sha256=oldready['manifest_sha256'],previous_targets_preserved=361,new_targets=0,amended_existing_targets=235,appended_fields=824,immutable_previous_snapshot='docs/story-quality/client-integration/history/'+oldready['manifest_sha256']+'/READY.json',freshness_gate='docs/story-quality/client-integration/current_ready_gate.py',same_target_count_does_not_imply_same_candidate=True,ready_for_client_integration=True,production_build_ready=False,published=False,runtime_applied=False,residual_review_coverage_complete=True,residual_review_fields=6372)
    ready['files']={p.name:sha(p.read_bytes()) for p in kit.iterdir() if p.name!='READY.json' and p.is_file()};(kit/'READY.json').write_bytes(enc(ready));save('new-client-ready.json',ready)
    args=[sys.executable,str(kit/'client_candidate_tools.py'),'--manifest',str(kit/'integration-manifest.json.gz'),'--manifest-sha256',ready['manifest_sha256'],'check-integrated','--repo','A:/StoryQuality-20260930-1739/patch.git','--ref',ref]
    cp=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120);assert cp.returncode==2 and b'Not all candidate bytes' in cp.stderr
    save('unintegrated-source-negative-check.json',{'passed':True,'expected_exit':2,'exit':cp.returncode,'stdout':cp.stdout.decode('utf8'),'stderr':cp.stderr.decode('utf8'),'source':ref,'manifest_sha256':ready['manifest_sha256'],'production_changed':False})
    cache=Path(r'D:\magia\deliveries\resource-integrity-20261002-src\.build\resume-final-20261003\public');paths=[cache/'cn_scenario_update.zip',cache/'cn_js_delta.zip',cache/'cn_js_update.zip'];assert all(p.is_file() for p in paths)
    try:verify_layers(packet,*paths)
    except ValueError as exc:message=str(exc)
    else:raise AssertionError('Old packages incorrectly accepted')
    assert 'failed target/preservation proof' in message
    save('old-package-negative-check.json',{'passed':True,'existing_package_paths':[str(p) for p in paths],'manifest_sha256':ready['manifest_sha256'],'expected_rejection':message,'real_new_packages_tested':False,'no_new_game_package_created':True})
    guard();print('CLIENT17_READY',ready['manifest_sha256'],'361 targets; 11226 fields; 235 amended; 489 delta selection paths; no release')

if __name__=='__main__':main()
