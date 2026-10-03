"""Verify a cumulative delta against pinned full baselines and current authoritative Git bytes.
This tool does not build, upload or install packages. Scenario is a frozen baseline,
not the required byte authority for files deliberately superseded by the new delta.
"""
from __future__ import annotations
import argparse,copy,gzip,hashlib,json,stat,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from client_candidate_tools import git,read_blobs,preflight,load_packet,config_with_targets
from current_ready_gate import check as check_current
PREFIX='madomagi/resource/scenario/json/'
META='magica/.cn_js_delta.json'
SCHEMA='magireco-cn-js-delta/v1'

def require(ok:bool,message:str):
 if not ok:raise ValueError(message)
def digest(path:Path,algorithm='sha256')->str:
 h=hashlib.new(algorithm)
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def blob(raw:bytes)->str:return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def product(p:str)->bool:
 return not p.startswith(('magica/research/','magica/i18n_audit/')) and (p.startswith(('magica/','madomagi/resource/image_native/')) or p in ('madomagi/engine_i18n.tsv','madomagi/repair_manifest.json'))
def story(p:str)->bool:return p.startswith(PREFIX) and p.endswith('.json')
def inventory(path:Path)->dict:
 records={};metadata=None
 with zipfile.ZipFile(path) as z:
  for info in z.infolist():
   if info.is_dir():continue
   name=info.filename
   require(name==info.orig_filename and not any(ord(c)<32 for c in name),'Unsafe ZIP member')
   require('\\' not in name and ':' not in name and name.split('/')[0] in ('magica','madomagi') and all(s not in ('','.','..') for s in name.split('/')),'Unsafe ZIP path: '+name)
   require(stat.S_IFMT(info.external_attr>>16)!=stat.S_IFLNK,'ZIP symlink rejected')
   require(name not in records,'Duplicate ZIP member: '+name)
   require(info.file_size<=1024*1024*1024,'Oversized ZIP member')
   h=hashlib.sha256();g=hashlib.sha1(b'blob '+str(info.file_size).encode()+b'\0');size=0
   with z.open(info) as f:
    for raw in iter(lambda:f.read(1024*1024),b''):h.update(raw);g.update(raw);size+=len(raw)
   require(size==info.file_size,'Incomplete ZIP member')
   records[name]={'sha256':h.hexdigest(),'blob':g.hexdigest(),'size':size}
   if name==META:
    require(size<8*1024*1024,'Oversized delta manifest');metadata=json.loads(z.read(info))
 return {'archive_sha256':digest(path),'archive_md5':digest(path,'md5'),'archive_bytes':path.stat().st_size,'files':records,'metadata':metadata}

def validate_delta(item:dict,base_sha:str,base_version:int)->dict:
 m=item['metadata'];require(isinstance(m,dict) and m.get('schema')==SCHEMA,'Invalid delta schema')
 require(m.get('base_js_sha256')==base_sha and m.get('base_js_version')==base_version,'Wrong frozen JS baseline')
 require(isinstance(m.get('version'),int) and not isinstance(m['version'],bool) and m['version']>0,'Invalid delta version')
 entries=m.get('entries');require(isinstance(entries,list),'Invalid entries')
 declared={r['path']:r for r in entries};require(len(declared)==len(entries),'Duplicate manifest entry')
 require(set(item['files'])==set(declared)|{META},'Delta inventory differs from manifest')
 for p,r in declared.items():require(item['files'][p]['sha256']==r['sha256'] and item['files'][p]['size']==r['size'],'Delta payload differs from manifest: '+p)
 return declared

def verify_maps(plan:dict,new:dict)->dict:
 declared=validate_delta(new,plan['full_js_sha256'],plan['base_js_version'])
 require(new['metadata']['version']>plan['previous_delta_version'],'New delta version must advance')
 required=set(plan['required_delta_paths']);require(required<=set(declared),'Cumulative delta omitted required/previously owned paths: '+str(sorted(required-set(declared))[:8]))
 for p in declared:
  require(p in plan['source_product_blobs'],'Unapproved payload: '+p)
  require(new['files'][p]['blob']==plan['source_product_blobs'][p],'Stale delta differs from authoritative integrated source: '+p)
 for p,e in plan['final_source_expectations'].items():
  actual=new['files'].get(p,plan['frozen_overlay'].get(p))
  require(actual is not None and actual['blob']==e,'Final baseline + latest delta regresses: '+p)
 # Reinstall or skipped-update clients must converge after the current delta is reapplied.
 first=copy.deepcopy(plan['frozen_overlay']);first.update({p:r for p,r in new['files'].items() if p!=META})
 replay=copy.deepcopy(first);replay.update(plan['frozen_overlay']);replay.update({p:r for p,r in new['files'].items() if p!=META})
 for p,e in plan['final_source_expectations'].items():require(first[p]['blob']==replay[p]['blob']==e,'Latest-delta replay failed: '+p)
 return {'passed':True,'delta_version':new['metadata']['version'],'delta_payload_files':len(declared),'required_paths':len(required),'all_final_source_checks':len(plan['final_source_expectations']),'cumulative_previous_paths_preserved':True,'scenario_baseline_deliberately_unchanged':True,'old_scenario_equality_not_required':True,'actual_device_test_performed':False}

def make_plan(repo:str,ref:str,packet:dict,scenario:dict,full:dict,previous:dict,lock:dict,require_integrated=False)->dict:
 for name,item in [('scenario',scenario),('full_js',full),('previous_delta',previous)]:
  require(item['archive_sha256']==lock[name]['sha256'] and item['archive_bytes']==lock[name]['bytes'],'Pinned archive identity changed: '+name)
 old=validate_delta(previous,full['archive_sha256'],lock['full_js']['version'])
 require(previous['metadata']['version']==lock['previous_delta']['version'],'Previous delta identity/version changed')
 staged,proof=preflight(repo,ref,packet);revision=proof['source_revision']
 all_integrated=all(v=='already_integrated' for v in proof['states'].values())
 require(not require_integrated or all_integrated,'Review candidates are not integrated into client source')
 tree={}
 for row in git(repo,'ls-tree','-rz',revision).split(b'\0'):
  if row:
   attr,p=row.split(b'\t',1);tree[p.decode()]=attr.split()[-1].decode()
 cfgraw=read_blobs(repo,revision,['configures/js-delta-baseline.json'])['configures/js-delta-baseline.json'];cfg=json.loads(cfgraw)
 require(cfg['base_js_sha256']==full['archive_sha256'] and cfg['base_js_version']==lock['full_js']['version'],'Git configuration references another frozen baseline')
 source_blobs={p:h for p,h in tree.items() if (product(p) or story(p)) and p!=META}
 for entry in packet['files']:source_blobs[entry['path']]=entry['after_blob']
 frozen=dict(scenario['files']);frozen.update(full['files']);frozen.pop(META,None)
 current_stories={p:h for p,h in source_blobs.items() if story(p)}
 require(all(p in current_stories for p in scenario['files'] if story(p)),'Story deletion requires a supported explicit installer migration')
 differing={p for p,h in current_stories.items() if frozen.get(p,{}).get('blob')!=h}
 changed=[p.decode() for p in git(repo,'diff','--name-only','--no-renames','-z',cfg['base_source_commit'],revision).split(b'\0') if p]
 touched_products={p for p in changed if product(p) and p!=META}
 required=set(old)|set(cfg['supplemental_product_paths'])|{e['path'] for e in packet['files']}|differing|touched_products
 require(all(p in source_blobs for p in required),'Previously owned product removed; explicit migration required')
 # Read every selected current product; never trust old delta bytes as a fallback.
 raw=read_blobs(repo,revision,sorted(required))
 for e in packet['files']:raw[e['path']]=staged[e['path']]
 require(all(blob(b)==source_blobs[p] for p,b in raw.items()),'Source blob verification failed')
 expected=dict(current_stories);expected.update({p:source_blobs[p] for p in required})
 required_story=sorted(p for p in required if story(p));proposal=json.loads(config_with_targets(cfgraw,packet))
 proposal['supplemental_product_paths']+=sorted(set(required_story)-set(proposal['supplemental_product_paths']))
 config_integrated=set(required_story)<=set(cfg['supplemental_product_paths'])
 require(not require_integrated or config_integrated,'All baseline-to-current story changes must be selected for cumulative delta')
 return {'schema':1,'policy':'delta_only_cumulative','source_revision':revision,'client_manifest_sha256':packet.get('manifest_sha256'),'production_ready':all_integrated and config_integrated,'full_js_sha256':full['archive_sha256'],'base_js_version':lock['full_js']['version'],'previous_delta_version':previous['metadata']['version'],'frozen_scenario_version':lock['scenario']['version'],'scenario_sha256':scenario['archive_sha256'],'required_delta_paths':sorted(required),'required_scenario_paths':required_story,'story_changes_against_frozen_scenario':len(differing),'previous_payload_count':len(old),'old_scenario_paths':sum(story(p) for p in old),'all_candidate_paths':len(packet['files']),'final_source_expectations':expected,'source_product_blobs':source_blobs,'frozen_overlay':frozen,'required_payload_sha256':{p:sha(b) for p,b in raw.items()},'delta_selection_proposal':proposal,'published':False,'client_source_integrated':all_integrated,'delta_config_integrated':config_integrated}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['manifest','baseline-lock','scenario','full-js','previous-delta']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--manifest-sha256',required=True);p.add_argument('--repo',required=True);p.add_argument('--ref',default='HEAD')
 sub=p.add_subparsers(dest='action',required=True);s=sub.add_parser('plan');s.add_argument('--out',required=True,type=Path)
 v=sub.add_parser('verify');v.add_argument('--new-delta',required=True,type=Path);v.add_argument('--version-json',required=True,type=Path);v.add_argument('--manifest-json',required=True,type=Path)
 a=p.parse_args();check_current(a.repo,a.manifest,a.manifest_sha256);packet=load_packet(a.manifest,a.manifest_sha256);packet['manifest_sha256']=a.manifest_sha256
 scenario,full,prev=map(inventory,[a.scenario,a.full_js,a.previous_delta]);lock=json.loads(a.baseline_lock.read_bytes())
 plan=make_plan(a.repo,a.ref,packet,scenario,full,prev,lock,require_integrated=a.action=='verify')
 if a.action=='plan':
  require(not a.out.exists(),'Output must be new; do not overwrite an earlier release proof')
  a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(gzip.compress((json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode(),mtime=0))
  result={k:plan[k] for k in ['source_revision','production_ready','story_changes_against_frozen_scenario','previous_payload_count','old_scenario_paths','all_candidate_paths','client_source_integrated','delta_config_integrated']};result.update(required_delta_paths=len(plan['required_delta_paths']),required_scenario_paths=len(plan['required_scenario_paths']),published=False)
 else:
  latest=git(a.repo,'ls-remote','origin','refs/heads/main').decode().split()[0]
  if latest!=plan['source_revision']:
   git(a.repo,'fetch','origin','main');git(a.repo,'merge-base','--is-ancestor',plan['source_revision'],latest)
   diffs=[x.decode() for x in git(a.repo,'diff','--name-only','-z',plan['source_revision'],latest).split(b'\0') if x]
   require(all(x.startswith('docs/') or x in ('README.md','STORY_QUALITY_HANDOFF.md') for x in diffs),'Production source changed after the fixed build revision')
  new=inventory(a.new_delta);result=verify_maps(plan,new)
  require(json.loads(a.manifest_json.read_bytes())==new['metadata'],'External delta manifest differs from ZIP')
  ver=json.loads(a.version_json.read_bytes());require(ver.get('version')==new['metadata']['version'] and ver.get('base_js_version')==plan['base_js_version'] and ver.get('base_js_sha256')==plan['full_js_sha256'] and ver.get('size')==new['archive_bytes'] and ver.get('md5')==new['archive_md5'],'Version metadata does not identify the exact delta ZIP')
  result.update(source_revision=plan['source_revision'],manifest_sha256=a.manifest_sha256,delta_sha256=new['archive_sha256'],published=False)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,OSError,RuntimeError,zipfile.BadZipFile) as exc:print('BLOCKED: '+str(exc),file=sys.stderr);raise SystemExit(2)
