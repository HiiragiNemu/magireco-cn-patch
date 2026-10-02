"""Build and validate the amended immutable client packet, without publication or production writes."""
from pathlib import Path
import sys,json,gzip,hashlib,copy,subprocess,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W))
from checkpoint import guard,enc
from initialize import git,save
from client_candidate_tools import preflight,config_with_targets,load_packet,verify_layers,ZipLayer

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 guard();oldready=json.loads((W/'prior-client-ready.json').read_bytes());oldpacket=json.loads(gzip.decompress((W/'prior-integration-manifest.json.gz').read_bytes()));packet=json.loads(gzip.decompress((W/'amended-integration-manifest.json.gz').read_bytes()))
 git('patch','fetch','origin','main');ref=git('patch','rev-parse','FETCH_HEAD').decode().strip()
 assert git('patch','show',ref+':docs/story-quality/client-integration/READY.json')==(W/'prior-client-ready.json').read_bytes(),'Parallel READY changed; reconcile'
 staged,proof=preflight('A:/StoryQuality-20260930-1739/patch.git',ref,packet)
 assert len(staged)==362 and sum(v=='staged_only' for v in proof['states'].values())==359 and sum(v=='already_integrated' for v in proof['states'].values())==2
 proposal=staged['configures/js-delta-baseline.json'];cfg=json.loads(proposal);assert len(cfg['supplemental_product_paths'])==489 and cfg['supplemental_product_paths'][:128]==packet['config_before']['supplemental_product_paths']
 oldentries={e['path']:e for e in oldpacket['files']};changed=[]
 for e in packet['files']:
  o=oldentries[e['path']];assert e['operations'][:len(o['operations'])]==o['operations']
  if e!=o:changed.append(e['path'])
 assert len(changed)==30 and packet['field_change_count']==10402 and len(packet['preservation_guards'])==1125
 packet['source_reference']=ref;packet['batch_validation_entries'].append('docs/story-quality/unreleased/20261003-semantic-batch16-ai-only-held/validation.json');packet['freshness_gate']='current_ready_gate.py';packet['same_target_count_does_not_imply_same_content']=True
 kit=W/'client-kit';kit.mkdir(exist_ok=True);packed=gzip.compress(enc(packet),mtime=0);(kit/'integration-manifest.json.gz').write_bytes(packed);load_packet(kit/'integration-manifest.json.gz',sha(packed));(kit/'js-delta-baseline.proposed.json').write_bytes(proposal)
 for n in ['client_candidate_tools.py','exact_json.py','translation_rules.py','test_client_integration.py','current_ready_gate.py','test_current_ready_gate.py']:(kit/n).write_bytes((W/n).read_bytes())
 proof.update(passed=True,targets=361,changed_targets=359,field_changes=10402,amended_existing_targets=30,appended_fields=90,new_completed_stories=0,old_field_operations_preserved=10312,unchanged_packet_entries=331,prior_manifest_sha256=oldready['manifest_sha256'],preservation_guard_paths=1125,old_delta_paths=128,proposed_delta_paths=489,published=False,runtime_applied=False,real_new_packages_tested=False,device_test_performed=False)
 (kit/'integration-preflight.json').write_bytes(enc(proof));save('client-preflight.json',proof)
 text=(W/'client-prior/README.md').read_text(encoding='utf8').replace('10312','10402').replace('10,312','10,402')
 prefix=f'''# 当前接入版本：第16批残余复查后候选\n\n候选目标仍是361，字段已由10312增加到10402；30个既有候选追加90处机翻纠正，新增完整剧情数为0。前10312条操作的地址、原文、修订值逐项保留。不要因目标数量相同继续使用旧包。当前manifest SHA256 `{sha(packed)}`；上一版`{oldready['manifest_sha256']}`及配套材料保存在history/下，不得混用。\n\n## 新增必查：远端最新READY\n\n整合/构建之前，以及客户端的串行发布事务开始前，先刷新CN patch main，运行：\n\n```powershell\n$kit = Join-Path $PWD 'docs/story-quality/client-integration'\n$ready = Get-Content (Join-Path $kit 'READY.json') -Raw | ConvertFrom-Json\npython (Join-Path $kit 'current_ready_gate.py') --repo $PWD --manifest (Join-Path $kit 'integration-manifest.json.gz') --manifest-sha256 $ready.manifest_sha256\n```\n\n该检查实际读取origin当前main引用，再读取该提交的READY，而不是只相信本地旧文件。即使旧稿与新稿都是361目标，只要SHA已经被替代就拒绝。远端在核验中移动、最新提交本地不可读时也停止，要求刷新；不会自动抓取、改工作树、降低权限检查或发包。它仅验证新鲜度，不能替代check-source、check-integrated、真实ZIP和设备最终文件核验；最终发布仍由客户端既有串行锁/事务保证，不能把一次只读检查说成永久无竞争。\n\n原补充路径128＋361目标＝489，生产配置仍未写入。Reader导出也有新候选，但未部署，权威累计导出文档在第16批的cumulative-reader-exports.json.gz，仅CN patch留存。\n\n以下是沿用的集成步骤（数字已更新；历史背景不作为本轮已发布声明）：\n\n'''
 (kit/'README.md').write_text(prefix+text,encoding='utf8')
 ready=copy.deepcopy(oldready);ready.update(schema=3,source_reference=ref,field_changes=10402,manifest_sha256=sha(packed),supersedes_manifest_sha256=oldready['manifest_sha256'],previous_targets_preserved=361,new_targets=0,amended_existing_targets=30,appended_fields=90,immutable_previous_snapshot='docs/story-quality/client-integration/history/'+oldready['manifest_sha256']+'/READY.json',freshness_gate='docs/story-quality/client-integration/current_ready_gate.py',same_target_count_does_not_imply_same_candidate=True,ready_for_client_integration=True,production_build_ready=False,published=False,runtime_applied=False)
 ready['files']={p.name:sha(p.read_bytes()) for p in kit.iterdir() if p.name!='READY.json' and p.is_file()};(kit/'READY.json').write_bytes(enc(ready));save('new-client-ready.json',ready)
 args=[sys.executable,str(kit/'client_candidate_tools.py'),'--manifest',str(kit/'integration-manifest.json.gz'),'--manifest-sha256',ready['manifest_sha256'],'check-integrated','--repo','A:/StoryQuality-20260930-1739/patch.git','--ref',ref]
 cp=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120);assert cp.returncode==2 and b'Not all candidate bytes' in cp.stderr
 save('unintegrated-source-negative-check.json',{'passed':True,'expected_exit':2,'exit':cp.returncode,'stdout':cp.stdout.decode(),'stderr':cp.stderr.decode(),'source':ref,'manifest_sha256':ready['manifest_sha256'],'production_changed':False})
 cache=Path(r'D:\magia\deliveries\resource-integrity-20261002-src\.build\resume-final-20261003\public');paths=[cache/'cn_scenario_update.zip',cache/'cn_js_delta.zip',cache/'cn_js_update.zip'];assert all(p.is_file() for p in paths)
 try:verify_layers(packet,*paths)
 except ValueError as exc:message=str(exc)
 else:raise AssertionError('Old packages were incorrectly accepted as amended candidates')
 assert 'failed target/preservation proof' in message
 save('old-package-negative-check.json',{'passed':True,'existing_package_paths':[str(p) for p in paths],'manifest_sha256':ready['manifest_sha256'],'expected_rejection':message,'real_new_packages_tested':False,'no_new_game_package_created':True})
 guard();print('CLIENT16_READY',ready['manifest_sha256'],'361 targets 10402 fields; 489 delta paths; both old-source and cached-old-package checks rejected correctly')
if __name__=='__main__':main()
