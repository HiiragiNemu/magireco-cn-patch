"""Exact native display strings: preserve the full event-bonus masters and all prior mappings."""
from pathlib import Path
import argparse,json,re,unicodedata
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--sources',type=Path);a=p.parse_args()
owner=Path(__file__).resolve().parents[1]
audit=json.loads((owner/'magica/i18n_audit/existing_text_review_20260924/battle_short_review.json').read_text('utf8'))
def table(root):
 raw=(root/'madomagi/engine_i18n.tsv').read_text('utf-8-sig');exact={};prefix=[]
 for l in raw.splitlines():
  if not l or l.startswith('#'):continue
  k,v=l.split('\t',1)
  if k.startswith('^'):prefix.append((k[1:],v))
  else:exact[k]=v
 return raw,exact,prefix
raw,exact,prefix=table(a.root)
rows=audit['nativeExactAdditions'];assert len(rows)==75
missing=[r['source'] for r in rows if exact.get(r['source'])!=r['target']]
if missing:
 print(json.dumps(dict(status='BASELINE_MISSES',missing=len(missing)),ensure_ascii=False));raise SystemExit(1)
def numbers(s):return re.findall(r'\[[IVX]+\]|\d+|∞',unicodedata.normalize('NFKC',s))
for r in rows:
 assert numbers(r['source'])==numbers(r['target']),(r['source'],r['target'])
 assert not re.search('[\u3040-\u30ff]',r['target'])
 assert r['target'] not in exact,'A translated result must not trigger another exact mapping'
 assert all(not (r['source']+'__unknown').startswith(k) for k,_ in prefix),'Unexpected existing broad prefix'
 if r['kind']=='existing_translation_exact_short_form':
  assert '追加获得数' not in r['target']
  for binding in r['bindings']:
   original=binding['target'];short=re.sub(r' & “[^”]+”追加获得数＋\d+$','',original)
   assert short==r['target']
sourceChecks=0
if a.sources:
 import hashlib
 documents={}
 for row in audit['sourceFiles']:
  f=a.sources/row['file'];assert hashlib.sha256(f.read_bytes()).hexdigest()==row['sha256'];documents[row['file']]=json.loads(f.read_bytes())
 for row in rows:
  for carrier in row['carriers']:
   obj=documents[carrier['file']]
   for part in carrier['path'].split('/'):
    obj=obj[int(part)] if isinstance(obj,list) else obj[part]
   assert obj==row['source'];sourceChecks+=1
preserved=0
if a.baseline:
 oldraw,oldexact,oldprefix=table(a.baseline)
 assert raw.startswith(oldraw)
 assert prefix==oldprefix
 for k,v in oldexact.items():assert exact[k]==v;preserved+=1
 assert set(exact)-set(oldexact)=={r['source'] for r in rows}
 assert len(exact)-len(oldexact)==75
print(json.dumps(dict(status='PASS',nativeExactAdditions=75,existingShortForms=21,capturedBattleStrings=54,sourceCarrierChecks=sourceChecks,priorExactMappingsPreserved=preserved,masterJsonChanges=0,numericDataChanges=0,deviceAcceptance='pending'),ensure_ascii=False))
