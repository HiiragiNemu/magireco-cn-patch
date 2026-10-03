"""Pin actual published baselines and prepare the delta-only verifier without building a game ZIP."""
from pathlib import Path
import sys,json,urllib.request,gzip,copy,datetime
W=Path(__file__).resolve().parent;sys.path[:0]=[str(W),str(W/'kit/docs/story-quality/client-integration')]
from integrate import P,run,save,sha,enc
from delta_only_guard import inventory,make_plan,verify_maps,load_packet,META
from current_ready_gate import check
C=Path(r'D:\magia\deliveries\resource-integrity-20261002-src\.build\resume-final-20261003\public')
ready=json.loads((W/'kit/docs/story-quality/client-integration/READY.json').read_bytes());manifest=W/'kit/docs/story-quality/client-integration/integration-manifest.json.gz'
check(str(P),manifest,ready['manifest_sha256']);packet=load_packet(manifest,ready['manifest_sha256']);packet['manifest_sha256']=ready['manifest_sha256']
run(P,'fetch','origin','main');ref=run(P,'rev-parse','FETCH_HEAD').decode().strip()
live={}
for kind,filename in [('scenario','version_scenario.json'),('full_js','version_js.json'),('previous_delta','version_js_delta.json')]:
 urls=['https://magireco-personal-release.pages.dev/'+filename,'https://github.com/HiiragiNemu/ProgettoMagius-1/releases/download/latest/'+filename]
 readings=[]
 for url in urls:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Reader-Delta-Only-Handoff','Accept-Encoding':'identity'}),timeout=45) as r:readings.append(json.load(r))
 require_same=readings[0]==readings[1]==json.loads((C/filename).read_bytes());assert require_same,(kind,'Published identity changed; refresh files')
 live[kind]=readings[0]
scenario,full,previous=[inventory(C/p) for p in ['cn_scenario_update.zip','cn_js_update.zip','cn_js_delta.zip']]
lock={'schema':1,'policy':'delta_only_cumulative','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_reference':ref,'client_manifest_sha256':ready['manifest_sha256'],'no_new_full_scenario_or_full_js':True,'scenario':{},'full_js':{},'previous_delta':{}}
for kind,item in [('scenario',scenario),('full_js',full),('previous_delta',previous)]:
 v=live[kind];assert item['archive_md5']==v['md5'] and item['archive_bytes']==v['size'];lock[kind]={'version':v['version'],'sha256':item['archive_sha256'],'bytes':item['archive_bytes'],'md5':item['archive_md5']}
save('delta-only-baseline-lock.json',lock)
plan=make_plan(str(P),ref,packet,scenario,full,previous,lock)
(W/'delta-only-plan.json.gz').write_bytes(gzip.compress(enc(plan),mtime=0))
save('delta-only-js-delta-baseline.proposed.json',plan['delta_selection_proposal'])
# Deliberately try the actual old payload inventory while relabelling its version in memory.
# This creates no game package and demonstrates that a larger counter cannot cure old bytes.
relabelled=copy.deepcopy(previous);relabelled['metadata']['version']=previous['metadata']['version']+1
errors=[]
try:verify_maps(plan,relabelled)
except ValueError as e:errors.append({'case':'old_zip_inventory_relabelled_in_memory','blocked':True,'error':str(e)})
else:raise AssertionError('Old delta incorrectly accepted')
# A putative cumulative inventory containing every required path but retaining old story bytes must also fail.
expanded={p:copy.deepcopy(previous['files'].get(p) or plan['frozen_overlay'].get(p)) for p in plan['required_delta_paths']}
assert all(expanded.values())
m=copy.deepcopy(relabelled['metadata']);m['entries']=[{'path':p,'size':v['size'],'sha256':v['sha256']} for p,v in expanded.items()]
expanded[META]=previous['files'][META]
try:verify_maps(plan,{'files':expanded,'metadata':m})
except ValueError as e:errors.append({'case':'all_required_paths_but_old_story_bytes_in_memory','blocked':True,'error':str(e)})
else:raise AssertionError('Stale story contents incorrectly accepted')
result={k:plan[k] for k in ['source_revision','production_ready','client_source_integrated','delta_config_integrated','story_changes_against_frozen_scenario','previous_payload_count','old_scenario_paths','all_candidate_paths']}
result.update(required_delta_paths=len(plan['required_delta_paths']),required_scenario_paths=len(plan['required_scenario_paths']),final_source_checks=len(plan['final_source_expectations']),new_package_built=False,published=False,negative_cases=errors,baseline_lock_sha256=sha((W/'delta-only-baseline-lock.json').read_bytes()),plan_sha256=sha((W/'delta-only-plan.json.gz').read_bytes()))
save('delta-only-plan-verification.json',result);print('DELTA_ONLY_HANDOFF_VERIFIED',json.dumps(result,ensure_ascii=False),flush=True)
