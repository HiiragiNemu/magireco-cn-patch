"""Transfer already-reviewed display text only after exact Japanese/runtime/source-proof checks."""
from pathlib import Path
import json,sys,collections
W=Path(__file__).resolve().parent;ROOT=W.parent;sys.path[:0]=[str(W),str(ROOT/'semantic-batch03-20261001'),str(ROOT/'severe-5109-20261001')]
from census import Store
from collect_review import fields,shape,TEXT,CTRL
TEXT.add('textSelect')
from translation_rules import execution_tokens,color_types,validate
from exact_json import apply,blob
from baseline import save

def transfer(original,donor,japanese,donor_japanese):
 if japanese!=donor_japanese:raise ValueError('Japanese differs')
 c,d,j=json.loads(original),json.loads(donor),json.loads(japanese)
 if shape(c)!=shape(d) or shape(c)!=shape(j):raise ValueError('Nontext execution identity differs')
 cf,df,jf=fields(c),fields(d),fields(j)
 if [x['address'] for x in cf]!=[x['address'] for x in df] or [x['address'] for x in cf]!=[x['address'] for x in jf]:raise ValueError('Display correspondence differs')
 ops=[]
 for a,b in zip(cf,df):
  if a['actor_id']!=b['actor_id']:raise ValueError('Staged actor differs')
  if execution_tokens(a['text'])!=execution_tokens(b['text']) or color_types(a['text'])!=color_types(b['text']):raise ValueError('Donor would alter executable/color tags')
  if a['text']!=b['text']:ops.append([a['address'],a['text'],b['text']])
 out=apply(original,ops);validate(original,out,ops)
 if apply(out,[[a,n,o] for a,o,n in ops])!=original:raise ValueError('Not byte reversible')
 return out,ops

def main():
 sources=json.loads((W/'review-sources.json').read_bytes());old=json.loads((W/'baseline-census.json').read_bytes());rt=json.loads((W/'reader-tree.json').read_bytes());proof={x['path']:x for x in old['completed_evidence']};rows={x['path']:x for x in old['scripts']};donors=collections.defaultdict(list)
 for x in old['scripts']:
  if x['complete']:donors[x['jp_blob']].append(x)
 rs=Store();results=[]
 for s in sources:
  if s['review_mode']!='exact_reviewed_text_reuse':continue
  target=rows[s['cn_path']];assert not target['complete'] and target['machine_output_pair_count']>0
  ds=donors[s['jp_sha']];assert len(ds)==1;d=ds[0];p=proof[d['path']]
  assert p['cn_blob']==d['current_blob']==rt[d['path']] and p['jp_blob']==d['jp_blob']==s['jp_sha']==rt[d['jp_path']]
  original=(W/'review'/(s['id']+'.cn.json')).read_bytes();jp=(W/'review'/(s['id']+'.jp.json')).read_bytes();donor=rs.get(d['current_blob']);djp=rs.get(d['jp_blob']);out,ops=transfer(original,donor,jp,djp)
  aligned=json.loads((W/'review'/(s['id']+'.aligned.json')).read_bytes());byaddr={tuple(r['address']):r for r in aligned};edits={}
  for at,before,after in ops:
   r=byaddr[tuple(at)];assert r['cn']==before;edits[str(r['ordinal'])]=CTRL.sub('§',after)
  decision={'id':s['id'],'review_mode':'exact_reviewed_text_reuse','reviewed_all_fields':False,'all_display_fields_verified_by_exact_source_reuse':True,'source_cn_blob':s['cn_sha'],'source_jp_blob':s['jp_sha'],'field_count':s['cn_fields'],'edits':edits,'review_note':'逐字节相同日文、相同非文本执行结构和位置身份；只复用有当前blob绑定全文校订证据的显示文字。不算本轮新翻译或重新全文阅读。','donor_path':d['path'],'donor_cn_blob':d['current_blob'],'donor_jp_blob':d['jp_blob'],'donor_completed_evidence':p,'candidate_blob':blob(out),'original_authorship_not_reassigned':True}
  dest=W/'review'/(s['id']+'.edits.json');assert not dest.exists();save('review/'+s['id']+'.edits.json',decision)
  (W/'review'/(s['id']+'.donor.json')).write_bytes(donor)
  results.append({'id':s['id'],'target_path':s['cn_path'],'target_blob':s['cn_sha'],'player_path':s['patch_path'],'player_blob':s['patch_sha'],'jp_blob':s['jp_sha'],'donor_path':d['path'],'donor_blob':d['current_blob'],'candidate_blob':blob(out),'display_fields_compared':s['cn_fields'],'display_fields_synchronized':len(ops),'donor_evidence':p,'exact_japanese_bytes':True,'same_execution_and_actors':True,'published':False})
  print(s['id'],'FROM',Path(d['path']).stem,'fields',s['cn_fields'],'sync',len(ops),flush=True)
 save('reuse-results.json',{'records':results,'scripts':len(results),'display_fields_compared':sum(x['display_fields_compared'] for x in results),'display_fields_synchronized':sum(x['display_fields_synchronized'] for x in results),'counts_as_new_translation':False,'published':False});rs.close()
 print('REUSE_PREPARED',len(results),'BODY_SYNCS',sum(x['display_fields_synchronized'] for x in results))
if __name__=='__main__':main()
