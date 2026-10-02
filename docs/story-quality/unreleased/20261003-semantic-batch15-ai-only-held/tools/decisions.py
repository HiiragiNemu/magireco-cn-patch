"""Record explicit full-scene bilingual decisions; no runtime files are written here."""
from pathlib import Path
import json,sys
W=Path(__file__).resolve().parent
sys.path.insert(0,str(W.parent/'severe-5109-20261001'))
from collect_review import CTRL
from stage_and_validate import expanded

def record(sid,edits,note):
 rows=json.loads((W/'review'/(sid+'.aligned.json')).read_bytes())
 sources={s['id']:s for s in json.loads((W/'review-sources.json').read_bytes())};source=sources[sid]
 assert source['same_field_addresses'],sid
 verified={}
 for k,v in edits.items():
  i=int(k);assert 0<=i<len(rows);new=expanded(rows[i]['cn'],v)
  if new!=rows[i]['cn']:verified[str(i)]=v
 proof={'id':sid,'reviewed_all_fields':True,'review_note':note,'source_cn_blob':source['cn_sha'],'source_jp_blob':source['jp_sha'],'field_count':len(rows),'edits':verified,'reviewer_type':'model_assisted_Japanese_comparison_not_official_human_authorship'}
 p=W/'review'/(sid+'.edits.json');assert not p.exists(),'Already recorded: '+sid
 p.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(sid,'reviewed',len(rows),'changed',len(verified))
