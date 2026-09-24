"""Keep confirmed official CN names and type-specific ambiguity; only add exact display strings."""
from pathlib import Path
import argparse,json,re,unicodedata,hashlib
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--sources',type=Path);p.add_argument('--cn-sources',type=Path);a=p.parse_args()
owner=Path(__file__).resolve().parents[1]
review=json.loads((owner/'magica/i18n_audit/existing_text_review_20260924/battle_cn_authority_review.json').read_text('utf8'))
def table(root):
 raw=(root/'madomagi/engine_i18n.tsv').read_text('utf-8-sig');exact={};prefix=[]
 for l in raw.splitlines():
  if not l or l.startswith('#'):continue
  k,v=l.split('\t',1)
  if k.startswith('^'):prefix.append((k[1:],v))
  else:exact[k]=v
 return raw,exact,prefix
raw,exact,prefix=table(a.root);rows=review['nativeExactAdditions'];assert len(rows)==46
missing=[r for r in rows if exact.get(r['source'])!=r['target']]
if missing:print(json.dumps(dict(status='BASELINE_MISSES',missing=len(missing))));raise SystemExit(1)
def nums(s):return re.findall(r'\[[IVX]+\]|\d+|∞',unicodedata.normalize('NFKC',s))
for r in rows:
 assert not re.search('[\u3040-\u30ff]',r['target'])
 assert nums(r['source'])==nums(r['target'])
 assert exact.get(r['target'],r['target'])==r['target']
 if r['source'].endswith('？'):assert r['target'].endswith('？')
 if r['source'].endswith('/ミラー'):assert r['target'].endswith('/镜像')
 if r['source'].startswith('？？？'):assert r['target'].startswith('？？？')
 if r['kind']=='official_cn_skill_name':assert r['target']==r['evidence'][0]['fieldValue']
held=review['sameSourceDifferentOfficialNames'];assert held['source'] not in exact
assert {e['fieldValue'] for e in held['officialEvidence']}=={'快速魔法提升','魔力骤升'}
checks=0
def resolve(d,path):
 for part in path.split('/'):d=d[int(part)] if isinstance(d,list) else d[part]
 return d
if a.sources:
 src={}
 for r in review['sourceFiles']:
  f=a.sources/r['file'];assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'];src[r['file']]=json.loads(f.read_bytes())
 for r in rows:
  for c in r['carriers']:assert resolve(src[c['file']],c['path'])==r['source'];checks+=1
cnchecks=0
if a.cn_sources:
 cache={}
 for r in review['cnSourceFiles']:
  f=a.cn_sources/r['file'];assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'];cache[r['file']]=json.loads(f.read_bytes())
 for ev in [e for r in rows for e in r['evidence']]+held['officialEvidence']:
  if ev['kind']=='official_cn_capture':assert resolve(cache[ev['file']],ev['path'])==ev['fieldValue'];cnchecks+=1
preserved=0
if a.baseline:
 oldraw,old,oldprefix=table(a.baseline);assert raw.startswith(oldraw) and prefix==oldprefix
 for k,v in old.items():assert exact[k]==v;preserved+=1
 assert set(exact)-set(old)=={r['source'] for r in rows}
print(json.dumps(dict(status='PASS',nativeAdditions=46,officialSkillQuestionsResolved=5,sourceCarrierChecks=checks,officialCnFieldChecks=cnchecks,priorExactMappingsPreserved=preserved,remainingContextualNames=1,numericDataChanges=0,deviceAcceptance='pending')))
