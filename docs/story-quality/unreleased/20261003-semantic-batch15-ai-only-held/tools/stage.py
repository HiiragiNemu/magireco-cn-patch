"""Build exact scalar-edit candidates outside repositories; never build a resource package."""
from pathlib import Path
import sys,json,collections
W=Path(__file__).resolve().parent;ROOT=W.parent
sys.path[:0]=[str(W),str(ROOT/'severe-5109-20261001'),str(ROOT/'control-authority-20260930')]
from collect_review import fields,shape,TEXT,CTRL
TEXT.add('textSelect')
from exact_json import apply,blob
from translation_rules import validate,execution_tokens,color_types
from stage_and_validate import expanded
from control_safety import no_added_undefined_references
from checkpoint import guard,enc

def save(n,x):
 p=W/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(enc(x))
def main():
 guard();sources=json.loads((W/'review-sources.json').read_bytes());bases=json.loads((W/'bases.json').read_bytes());old=json.loads((W/'baseline-census.json').read_bytes());prior={x['path']:x for x in old['scripts']}
 plan={'schema':2,'batch':'20261003-semantic-batch15-ai-only-held','base_version':3322,'target_version':None,'published':False,'publication_prohibited':True,'runtime_source_paths_written':False,'bases':bases,'reader_files':[],'runtime_files':[],'reviewed_stories':[],'inputs':{},'execution_changes':0,'whole_corpus_review_complete':False,'review_method':'fresh_full_Japanese_comparison_or_verified_exact_source_reuse_distinguished'}
 for s in sources:
  dp=W/'review'/(s['id']+'.edits.json')
  if not dp.exists():continue
  d=json.loads(dp.read_bytes());assert d['source_cn_blob']==s['cn_sha'] and d['source_jp_blob']==s['jp_sha'] and d['field_count']==s['cn_fields']
  mode=s['review_mode'];reuse=mode=='exact_reviewed_text_reuse';context=mode=='context_only'
  if reuse:assert not d['reviewed_all_fields'] and d['all_display_fields_verified_by_exact_source_reuse']
  else:assert d['reviewed_all_fields'] and (mode=='fresh_full_review' or context)
  rows=json.loads((W/'review'/(s['id']+'.aligned.json')).read_bytes());lines=[CTRL.sub('§',r['cn']) for r in rows];ops=[];records=[]
  for key,new in d['edits'].items():
   i=int(key);assert str(i)==key and 0<=i<len(rows);lines[i]=new
  for row,line in zip(rows,lines):
   new=expanded(row['cn'],line)
   assert execution_tokens(new)==execution_tokens(row['cn']) and color_types(new)==color_types(row['cn'])
   assert new.count('userName')==row['cn'].count('userName')
   if new!=row['cn']:
    assert new.strip() and '\ufffd' not in new and '§' not in new
    ops.append([row['address'],row['cn'],new]);records.append({'ordinal':row['ordinal'],'address':row['address'],'speaker':row['cn_name'],'jp':row['jp'],'before':row['cn'],'after':new,'mode':mode})
  body_count=len(ops);choice_count=0
  for choice in d.get('choice_edits',[]):
   assert mode=='fresh_full_review' and choice['address'][-1]=='textSelect'
   assert not execution_tokens(choice['before']) and not execution_tokens(choice['after'])
   ops.append([choice['address'],choice['before'],choice['after']]);choice_count+=1
   records.append({'ordinal':None,'address':choice['address'],'speaker':'选项','jp':choice['japanese'],'before':choice['before'],'after':choice['after'],'mode':'nested_choice_text_only','alternativeId':choice['alternativeId'],'target_group':choice['target_group']})
  if context:assert prior[s['cn_path']]['complete'] and not ops,'Do not silently edit old complete context'
  a=(W/'review'/(s['id']+'.cn.json')).read_bytes();jp=(W/'review'/(s['id']+'.jp.json')).read_bytes();assert blob(a)==s['cn_sha'] and blob(jp)==s['jp_sha']
  if 'allowed_body_ordinals' in s:
   assert set(map(int,d['edits'])).issubset(s['allowed_body_ordinals']),'Attempt to rewrite human mixed-payload field'
  excluded=json.loads((W/'authority-exclusions.json').read_bytes())['excluded']
  assert s['cn_path'] not in {e['reader_path'] for e in excluded},'Human restoration or prior full review cannot be retranslated'
  humanpins=json.loads((W/'protected-field-pins.json').read_bytes())['records']
  protected={tuple(x['address']):x['current'] for x in humanpins if x['script_id']==s['id']}
  assert not {tuple(x[0]) for x in ops}&set(protected),'Attempt to rewrite pinned human restoration'
  for address,value in protected.items():
   node=json.loads(a)
   for key in address:node=node[key]
   assert node==value,'Pinned human field changed outside this batch'
  from independent_runtime import stage_pair
  pa=(W/'review'/(s['id']+'.player.json')).read_bytes();assert blob(pa)==s['patch_sha']
  proofs=json.loads((W/'source-adjudications.json').read_bytes())['records']
  b,pb=stage_pair(s['id'],a,pa,ops,proofs)
  no_added_undefined_references(pa,pb)
  assert shape(json.loads(a))==shape(json.loads(b))
  assert [(x['address'],x['name'],x['actor_id']) for x in fields(json.loads(a))]==[(x['address'],x['name'],x['actor_id']) for x in fields(json.loads(b))]
  no_added_undefined_references(a,b)
  if reuse:
   assert blob(b)==d['candidate_blob'];donor=(W/'review'/(s['id']+'.donor.json')).read_bytes();assert blob(donor)==d['donor_cn_blob']
   assert [(x['address'],x['text'],x['actor_id']) for x in fields(json.loads(b))]==[(x['address'],x['text'],x['actor_id']) for x in fields(json.loads(donor))]
  for repo,path,ra,rb in [('reader',s['cn_path'],a,b),('patch',s['patch_path'],pa,pb)]:
   for folder,data in [('originals',ra),('stage',rb)]:
    dest=W/folder/repo/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
   if ops:plan['reader_files' if repo=='reader' else 'runtime_files'].append({'path':path,'before':blob(ra),'after':blob(rb),'operations':ops,'jp_path':s['jp_path'],'jp_sha':s['jp_sha'],'reader_paths':[s['cn_path']],'review_mode':mode})
  plan['inputs'].update({s['cn_path']:s['cn_sha'],s['jp_path']:s['jp_sha']})
  if reuse:plan['inputs'].update({d['donor_path']:d['donor_cn_blob'],d['donor_completed_evidence']['jp_path']:s['jp_sha']})
  story=s|{'fields_reviewed':len(rows),'fields_changed':len(ops),'body_fields_changed':body_count,'choice_fields_changed':choice_count,'choice_fields_reviewed':d.get('choice_fields_reviewed',0),'name_fields_changed':0,'review_note':d['review_note'],'semantic_complete':not reuse,'prepared_complete':True,'unresolved':[],'aligned_review':records,'candidate_blob':blob(b),'player_candidate_blob':blob(pb),'player_source_blob':blob(pa),'repository_specific_originals_preserved':True}
  plan['reviewed_stories'].append(story);(W/'review'/(s['id']+'.final.txt')).write_text('\n'.join(lines)+'\n',encoding='utf8')
 groups=collections.Counter(x['review_mode'] for x in plan['reviewed_stories']);plan.update(reviewed_fields=sum(s['fields_reviewed'] for s in plan['reviewed_stories']),changed_fields=sum(s['fields_changed'] for s in plan['reviewed_stories']),fresh_full_review_scripts=groups['fresh_full_review'],reuse_verified_scripts=groups['exact_reviewed_text_reuse'],context_only_scripts=groups['context_only'])
 plan['newly_read_fields']=sum(x['fields_reviewed'] for x in plan['reviewed_stories'] if x['review_mode']=='fresh_full_review');plan['new_translation_correction_fields']=sum(x['body_fields_changed'] for x in plan['reviewed_stories'] if x['review_mode']=='fresh_full_review');plan['reuse_synchronization_fields']=sum(x['fields_changed'] for x in plan['reviewed_stories'] if x['review_mode']=='exact_reviewed_text_reuse');plan['completed_review_stories']=[s['id'] for s in plan['reviewed_stories']];plan['pending_adjudication_stories']=[]
 plan['choice_fields_reviewed']=sum(x['choice_fields_reviewed'] for x in plan['reviewed_stories']);plan['choice_fields_changed']=sum(x['choice_fields_changed'] for x in plan['reviewed_stories'])
 save('repair-plan.json',plan);progress=json.loads((W/'progress.json').read_bytes());progress.update(stage='review_in_isolation',reviewed=[{'id':s['id'],'mode':s['review_mode'],'fields':s['fields_reviewed'],'changed':s['fields_changed']} for s in plan['reviewed_stories']],fresh_full_review_scripts=plan['fresh_full_review_scripts'],reuse_verified_scripts=plan['reuse_verified_scripts'],context_only_scripts=plan['context_only_scripts'],new_translation_correction_fields=plan['new_translation_correction_fields'],reuse_synchronization_fields=plan['reuse_synchronization_fields'],changed_fields=plan['changed_fields'],target_version=None,published=False,checkpoint='Exact text candidates saved only outside runtime paths; new full review and prior-proof reuse are separate; release held')
 save('progress.json',progress);guard();print('HELD_STAGE',json.dumps({k:plan[k] for k in ['fresh_full_review_scripts','reuse_verified_scripts','context_only_scripts','newly_read_fields','new_translation_correction_fields','reuse_synchronization_fields','changed_fields','published','target_version']},ensure_ascii=False))
if __name__=='__main__':main()
