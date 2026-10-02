"""Normalize explicitly reviewed raw control runs to existing safe placeholders, without changing them."""
from pathlib import Path
import json,sys
W=Path(__file__).resolve().parent
sys.path[:0]=[str(W),str(W.parent/'severe-5109-20261001')]
from collect_review import CTRL
from stage_and_validate import expanded,canonical_tags
from decisions import record

def main():
 p=Path(sys.argv[1]);decisions=json.loads(p.read_text(encoding='utf8'))
 normalized={}
 for sid,d in decisions.items():
  rows=json.loads((W/'review'/(sid+'.aligned.json')).read_bytes());edits={}
  for key,new in d['edits'].items():
   old=rows[int(key)]['cn']
   if '§' in new:
    expanded(old,new);edits[key]=new
   else:
    assert CTRL.findall(old)==CTRL.findall(new),(sid,key,'raw executable runs differ')
    assert canonical_tags(old)==canonical_tags(new),(sid,key,'raw tag identity differs')
    line=CTRL.sub('§',new);assert expanded(old,line)==new,(sid,key)
    edits[key]=line
  normalized[sid]={'edits':edits,'note':d['note']}
 for sid,d in normalized.items():record(sid,d['edits'],d['note'])
 print('RECORDED_RAW_SAFE',len(normalized),'scripts')
if __name__=='__main__':main()
