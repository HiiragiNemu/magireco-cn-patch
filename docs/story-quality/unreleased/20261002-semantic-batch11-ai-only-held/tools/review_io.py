"""Readable complete chapter views and explicit sparse review recording."""
from pathlib import Path
import json,sys
W=Path(__file__).resolve().parent

def show(chapters):
 sources=json.loads((W/'review-sources.json').read_bytes())
 for s in sources:
  if s['chapter_id'] not in chapters:continue
  rows=json.loads((W/'review'/(s['id']+'.aligned.json')).read_bytes())
  print('\n###',s['id'],'FIELDS',len(rows),'###')
  for r in rows:
   print(str(r['ordinal'])+' '+str(r['cn_name'])+' | J:'+json.dumps(r['jp'],ensure_ascii=False)+' | C:'+json.dumps(r['cn'],ensure_ascii=False))
  print('### END',s['id'],'###')

def record(path):
 from decisions import record
 items=json.loads(Path(path).read_text(encoding='utf8'))
 for sid,d in items.items():record(sid,d['edits'],d['note'])
 print('RECORDED',len(items),'fully read scripts')
if __name__=='__main__':
 if sys.argv[1]=='show':show(sys.argv[2:])
 elif sys.argv[1]=='record':record(sys.argv[2])
 else:raise ValueError('show or record expected')
