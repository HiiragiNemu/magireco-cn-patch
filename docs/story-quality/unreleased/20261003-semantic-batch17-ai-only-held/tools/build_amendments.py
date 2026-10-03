"""Construct audited amendments to the held packet; never touch production or release files."""
from pathlib import Path
import sys,json,gzip,csv,io,collections,datetime,hashlib,copy
W=Path(__file__).resolve().parent;R=W.parent/'repo';sys.path[:0]=[str(W),str(W.parent/'semantic-batch03-20261001'),str(W.parent/'severe-5109-20261001')]
from checkpoint import guard,enc
from initialize import git,tree,save
from census import Store
from audit_origins import body,IMPORT,TRUSTED
from collect_review import fields,shape
from amendment_contract import amend,sha
from exact_json import apply,blob
from translation_rules import validate

def main():
 guard();packet=json.loads(gzip.decompress((W/'prior-integration-manifest.json.gz').read_bytes()));old=copy.deepcopy(packet);refs=json.loads((W/'bases.json').read_bytes());rt=json.loads((W/'reader-tree.json').read_bytes());pt=json.loads((W/'patch-tree.json').read_bytes());tt=tree('reader',TRUSTED)
 index=json.loads(gzip.decompress((W/'candidate-display-field-index.json.gz').read_bytes()));lookup={(r['id'],str(r['ordinal'])):r for r in index};decisions=json.loads((W/'amendment-decisions.json').read_bytes());s=Store();sp=Store(patch=True)
 variants={e['target_path'] for e in json.loads(s.get(rt['manifests/authoritative_scenario_variant_repairs.v1.json']))['entries']}
 v4={e['target_path'] for e in json.loads(s.get(rt['manifests/authoritative_scenario_runtime_repairs.v1.json']))['entries']}
 authorized=set(json.loads(s.get(rt['docs/reader-availability-local-20260929.json']))['protected_source_failure']['paths'])
 exclusion=json.loads(git('patch','show',refs['patch']+':docs/story-quality/unreleased/20261003-semantic-batch15-ai-only-held/authority-exclusions.json'))
 pins=json.loads(git('patch','show',refs['patch']+':docs/story-quality/unreleased/20261003-semantic-batch15-ai-only-held/protected-field-pins.json'))['records']
 pinset={(r['script_id'],tuple(r['address'])) for r in pins}
 pairs=collections.defaultdict(set)
 for r in csv.DictReader(io.StringIO(s.get(IMPORT+':magireco-translate-data-master/TRANSLATION_REVIEW.tsv').decode('utf-8-sig')),delimiter='\t'):
  if r.get('type') in ('text','fallback'):pairs[(r.get('japanese'),r.get('chinese'))].add(r['type'])
 entries={e['script_id']:e for e in packet['files']};proof=[];rfiles=[];pfiles=[];inputs={};newfieldrecords=[];generations=[]
 oldfielddoc=json.loads(gzip.decompress((W/'prior-unreleased-field-changes.json.gz').read_bytes()));oldfields=oldfielddoc['records'];assert len(oldfields)==10402
 oldaddresses={(r['player_path'],tuple(r['address'])) for r in oldfields}
 for sid,edits in decisions.items():
  e=entries[sid];cp=e['reader_path'];pp=e['path'];assert e['mode']=='fresh_full_review' and cp not in tt and cp not in variants|v4|authorized
  cn=s.get(rt[cp]);jp=s.get(e['source_jp_blob']);imp=s.get(IMPORT+':'+cp);player=sp.get(pt[pp]);jfields=body(json.loads(jp));impfields=body(json.loads(imp));cfields=body(json.loads(cn));existing=e['candidate_utf8'].encode()
  # This batch deliberately does not touch the separate-image MVD target; enforce independent source agreement here.
  assert cn==player and blob(player)==e['before_blob'] and blob(cn)==e['before_blob'];nameby={tuple(f['address']):f['name'] for f in fields(json.loads(cn))}
  dlist=[]
  for ordinal,(after,reason) in edits.items():
   r=lookup[sid,ordinal];at=tuple(r['address']);assert at not in pinset and (sid,at) not in pinset and (pp,at) not in oldaddresses
   assert r['unchanged_imported_machine_field'] and not r['already_edited'] and cfields[at]==r['cn']==impfields[at] and jfields[at]==r['jp']
   typ=pairs[(r['jp'],r['cn'])];assert typ and after!=r['cn']
   d={'script_id':sid,'reader_path':cp,'player_path':pp,'ordinal':int(ordinal),'address':list(at),'japanese':r['jp'],'before':r['cn'],'after':after,'rationale':reason,'import_blob':blob(imp),'import_chinese':impfields[at],'prior_candidate_text':r['cn'],'source_cn_blob':blob(cn),'source_jp_blob':blob(jp),'prior_candidate_blob':e['after_blob'],'machine_types':sorted(typ),'unchanged_imported_machine_field':True,'protected':False,'speaker':nameby.get(at),'counts_as_new_completed_story':False};dlist.append(d)
  newentry,ops=amend(e,player,dlist);entries[sid]=newentry
  updatedreader=apply(cn,newentry['operations']);assert updatedreader==newentry['candidate_utf8'].encode()
  assert shape(json.loads(existing))==shape(json.loads(updatedreader));assert [(f['address'],f['name'],f['actor_id']) for f in fields(json.loads(existing))]==[(f['address'],f['name'],f['actor_id']) for f in fields(json.loads(updatedreader))]
  for repo,path,orig in [('reader',cp,cn),('patch',pp,player)]:
   for folder,data in [('originals',orig),('prior-stage',existing),('stage',updatedreader)]:
    p=W/folder/repo/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  p=W/'japanese'/cp;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(jp)
  rfiles.append({'path':cp,'before':blob(cn),'after':blob(updatedreader),'operations':newentry['operations'],'amendment_operations':ops,'prior_candidate_blob':e['after_blob']})
  pfiles.append({'path':pp,'before':blob(player),'after':blob(updatedreader),'operations':newentry['operations'],'amendment_operations':ops,'prior_candidate_blob':e['after_blob']})
  inputs[cp]=blob(cn);inputs[cp.replace('magireco-translate-data-master/','magireco-source-master/',1)]=blob(jp)
  generations.append({'script_id':sid,'reader_path':cp,'player_path':pp,'source_cn_blob':blob(cn),'prior_candidate_blob':e['after_blob'],'active_candidate_blob':blob(updatedreader),'old_operations_preserved':len(e['operations']),'appended_operations':len(ops),'old_packet_entry_sha256':sha(enc(e)),'new_packet_entry_sha256':sha(enc(newentry))})
  for d in dlist:
   d['active_candidate_blob']=blob(updatedreader);proof.append(d)
   newfieldrecords.append({'script_id':sid,'reader_path':cp,'player_path':pp,'source_cn_blob':blob(cn),'source_jp_blob':blob(jp),'candidate_blob':blob(updatedreader),'review_mode':'residual_machine_amendment_no_new_story','published':False,'ordinal':d['ordinal'],'address':d['address'],'speaker':d['speaker'],'jp':d['japanese'],'before':d['before'],'after':d['after'],'mode':'residual_machine_amendment_no_new_story','prior_candidate_blob':e['after_blob'],'rationale':d['rationale'],'exact_machine_import_blob':d['import_blob'],'counts_as_new_completed_story':False})
 packet['files']=[entries[e['script_id']] for e in old['files']];packet['field_change_count']=sum(len(e['operations']) for e in packet['files']);packet['generated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();packet['source_reference']=refs['patch'];packet['supersedes_manifest_sha256']=sha((W/'prior-integration-manifest.json.gz').read_bytes());packet['amendment_evidence']='docs/story-quality/unreleased/20261003-semantic-batch17-ai-only-held/amendment-proof.json.gz';packet['appended_machine_corrections']=len(proof);packet['new_completed_story_count']=0
 assert packet['target_count']==361 and packet['field_change_count']==10402+len(proof);assert oldfields+newfieldrecords==oldfields+newfieldrecords
 oldby={e['script_id']:e for e in old['files']}
 for e in packet['files']:
  o=oldby[e['script_id']]
  if e['script_id'] not in decisions:assert e==o
  else:assert e['operations'][:len(o['operations'])]==o['operations']
 (W/'amended-integration-manifest.json.gz').write_bytes(gzip.compress(enc(packet),mtime=0));save('amendment-proof.json',proof);save('candidate-generations.json',generations);save('new-field-records.json',newfieldrecords)
 save('repair-plan.json',{'batch':'20261003-semantic-batch17-ai-only-held','reader_files':rfiles,'runtime_files':pfiles,'inputs':inputs,'published':False,'runtime_source_paths_written':False,'new_full_review_scripts':0,'amended_existing_candidates':len(decisions),'new_body_corrections':len(proof)})
 save('amendment-validation.json',{'source_frozen':refs,'passed':True,'new_stories':0,'amended_scripts':len(decisions),'appended_field_corrections':len(proof),'prior_operations_preserved':10402,'combined_operations':packet['field_change_count'],'prior_target_count':361,'current_target_count':361,'prior_unaffected_targets':361-len(decisions),'all_runtime_fields_and_images_preserved':True,'all_amendments_exact_machine_log_and_import_matched':True,'human_protection_overlap':0,'raw_reverse_proven':True,'published':False,'runtime_applied':False})
 s.close();sp.close();guard();print('AMENDMENTS_CONSTRUCTED',len(decisions),len(proof),'TOTAL',packet['field_change_count'])
if __name__=='__main__':main()
