"""Exact reviewed successor contract; no product writes and no inferred acceptance."""
from __future__ import annotations
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

REGISTRY_RELATIVE = 'magica/i18n_audit/release_v26_authority/reviewed_successors_20260908/registry.json'
REGISTRY_SHA256 = '6a58936da81ff435c8938ce3a40cf96fbebd022aac7a50b8dfec5e1f797fd552'
PINNED_SHA256 = '4d1821807ff2a1c90f026886cf6c1fe31041b687eb5270853a4d0549b39d2a30'
IMMUTABLE = ('change_id','file','json_pointer','stable_key','field','before','source_tier','manual_review_status')
ID_FIELDS = {
 'magica/js/libs/cardList.json': ('cardId',int),
 'magica/js/libs/charaList.json': ('id',int),
 'magica/js/libs/itemList.json': ('itemCode',str),
 'magica/js/libs/sectionList.json': ('sectionId',int),
 'magica/js/libs/shopItemList.json': ('id',int),
 'magica/js/libs/pieceSkillMap.json': ('$key',str),
 'magica/js/libs/emotionSkillMap.json': ('$key',str),
}

def digest(b):
 return hashlib.sha256(b).hexdigest()

def canonical(value):
 return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')

def pointer(value, path):
 if path == '': return value
 if not path.startswith('/'): raise ValueError('invalid source pointer')
 for token in path.split('/')[1:]:
  token=token.replace('~1','/').replace('~0','~')
  value=value[int(token)] if isinstance(value,list) else value[token]
 return value

def confined(base, relative):
 p=Path(relative)
 if p.is_absolute() or '..' in p.parts: raise ValueError('proof path escapes evidence package')
 result=(base/p).resolve()
 if not result.is_relative_to(base.resolve()): raise ValueError('proof path escapes evidence package')
 return result

class ReviewedContract:
 def __init__(self):
  self.entries={}; self.by_target={}; self.errors=[]; self.proof_count=0
  self.prior_counts=Counter()
 def report(self):
  return {'path':REGISTRY_RELATIVE,'pinned_sha256':REGISTRY_SHA256,
   'valid_entries':len(self.entries),'validated_source_proofs':self.proof_count,
   'prior_terminal_classes':dict(self.prior_counts),'failures':self.errors}
 def resolve(self,row,document):
  e=self.entries[row['change_id']]
  key,typ=ID_FIELDS[e['file']]; sid=e['stableId'];field=e['field']
  if key=='$key':
   if not isinstance(document,dict):raise ValueError('reviewed skill map is not keyed')
   obj=document[sid]
   if not isinstance(obj,dict):raise ValueError('reviewed skill object is not a record')
   if 'id' in obj and (type(obj['id']) is not int or obj['id']!=int(sid)):
    raise ValueError('reviewed skill inline ID disagrees with map key')
   current_pointer=f'/{sid}/{field}'
  else:
   if not isinstance(document,list):raise ValueError('reviewed stable-ID table is not an array')
   expected=typ(sid)
   matches=[(i,o) for i,o in enumerate(document) if isinstance(o,dict) and type(o.get(key)) is typ and o[key]==expected]
   if len(matches)!=1:raise ValueError(f'reviewed stable ID has {len(matches)} matches')
   i,obj=matches[0];current_pointer=f'/{i}/{field}'
  return obj[field],current_pointer,f"{e['file']}|{sid}|{field}"

def read_reviewed_contract(root, manifest_rows):
 result=ReviewedContract()
 try:
  path=root/REGISTRY_RELATIVE;raw=path.read_bytes()
  if digest(raw)!=REGISTRY_SHA256:raise ValueError('reviewed registry digest mismatch')
  reg=json.loads(raw);base=path.parent
  if reg['schema']!='pass18-reviewed-successors/v1':raise ValueError('reviewed registry schema mismatch')
  if reg['pinnedManifestCommit']!='95e6284eb7a64f3f54309acbd614056f643f6ccd':raise ValueError('reviewed historical pin mismatch')
  pinned=confined(base,reg['pinnedManifestPath']).read_bytes()
  if digest(pinned)!=PINNED_SHA256 or reg['pinnedManifestSha256']!=PINNED_SHA256:raise ValueError('reviewed pinned history digest mismatch')
  history=list(csv.DictReader(io.StringIO(pinned.decode('utf-8')),delimiter='\t'))
  if len(history)!=939 or len({r['change_id'] for r in history})!=939:raise ValueError('reviewed history must retain 939 identities')
  history={r['change_id']:r for r in history};live={r['change_id']:r for r in manifest_rows}
  if len(live)!=939 or len(manifest_rows)!=939 or set(live)!=set(history):raise ValueError('reviewed contract requires all 939 historical identities')
  for cid,old in history.items():
   if any(live[cid].get(k)!=old[k] for k in IMMUTABLE):raise ValueError(f'{cid}: immutable lineage differs')
  # Preserve the two already-enriched after-images without opening arbitrary edits.
  expected_after={cid:old['after'] for cid,old in history.items()}
  enriched=set()
  for known in reg['knownPreexistingAfterEnrichments']:
   cid=known['changeId']
   if cid in enriched or history[cid]['after']!=known['originalAfter']:raise ValueError('invalid known historical after enrichment')
   enriched.add(cid);expected_after[cid]=known['knownAfter']
  for cid,current in live.items():
   if current['after']!=expected_after[cid]:raise ValueError(f'{cid}: unregistered manifest after drift')
  closure_path=root/'magica/research/totentanz-full-localization-20260817/runtime-dictionary/visible-term-closure-3136.tsv'
  closure_bytes=closure_path.read_bytes()
  if digest(closure_bytes)!=reg['closureSha256']:raise ValueError('reviewed predecessor closure digest mismatch')
  closures=list(csv.DictReader(io.StringIO(closure_bytes.decode('utf-8-sig')),delimiter='\t'))
  closure_index={(r['path'],r['stable_key'],r['field']):r for r in closures}
  sources={};parsed={};proof_count=0
  for s in reg['sourceFiles']:
   if s['path'] in sources:raise ValueError('duplicate proof source path')
   b=confined(base,s['path']).read_bytes()
   if digest(b)!=s['sha256'] or len(b)!=s['bytes']:raise ValueError(f"source proof digest mismatch: {s['path']}")
   sources[s['path']]=(s,b)
  entries={};targets={};prior=Counter()
  for e in reg['entries']:
   cid=e['changeId'];old=history[cid];current=live[cid]
   if cid in entries:raise ValueError('duplicate reviewed change ID')
   if e['immutableIdentity']!={k:old[k] for k in IMMUTABLE}:raise ValueError(f'{cid}: reviewed immutable identity differs')
   if (e['file'],e['stableId'],e['field'],e['oldExpected'])!=(old['file'],old['stable_key'],old['field'],old['after']):raise ValueError(f'{cid}: reviewed original field binding differs')
   if current['after']!=e['oldExpected']:raise ValueError(f'{cid}: mutable manifest after drift')
   if not isinstance(e['currentAuthorizedExact'],str) or e['currentAuthorizedExact']==e['oldExpected']:raise ValueError('reviewed successor must be an exact different string')
   if e['file'] not in ID_FIELDS or e['idField']!=ID_FIELDS[e['file']][0]:raise ValueError('unregistered stable-ID schema')
   target=(e['file'],e['stableId'],e['field'])
   if target in targets:raise ValueError('duplicate reviewed target')
   closure=closure_index.get(target)
   if e['priorClosure']!=closure:raise ValueError('reviewed predecessor closure differs')
   prior_class='runtime_superseded' if closure else 'runtime_direct'
   if prior_class!=e['priorTerminalClass']:raise ValueError('reviewed prior terminal class differs')
   if closure and (closure['before']!=e['oldExpected'] or closure['after']==e['currentAuthorizedExact']):raise ValueError('reviewed closure chain is not exact')
   if not e['sourceProof'] or not any(p['role']=='reviewed-exact-decision' for p in e['sourceProof']):raise ValueError('reviewed target has no exact decision proof')
   for proof in e['sourceProof']:
    source,b=sources[proof['path']]
    if proof['sha256']!=source['sha256']:raise ValueError('wrong source proof binding')
    selector=proof['selector'];kind=selector['type'];cache_key=(proof['path'],kind)
    if cache_key not in parsed:
     if kind=='json-pointer':parsed[cache_key]=json.loads(b.decode('utf-8-sig'))
     elif kind=='tsv-gzip-row':parsed[cache_key]=list(csv.DictReader(io.StringIO(gzip.decompress(b).decode('utf-8-sig')),delimiter='\t'))
     else:raise ValueError('unregistered source selector type')
    if kind=='json-pointer':selected=pointer(parsed[cache_key],selector['pointer'])
    else:
     line=selector['line']
     if type(line) is not int or line<2:raise ValueError('invalid source row')
     selected=parsed[cache_key][line-2]
    if digest(canonical(selected))!=proof['selectedSha256']:raise ValueError('source proof selector/value mismatch')
    for sub,expected in proof['checks'].items():
     if pointer(selected,sub)!=expected:raise ValueError('source proof exact assertion mismatch')
    if proof['role']=='reviewed-exact-decision':
     if selected.get('changeId')!=cid or selected.get('file',selected.get('relativePath'))!=e['file'] or selected['field']!=e['field'] or selected['exactAfter']!=e['currentAuthorizedExact']:raise ValueError('review decision targets a different field/value')
     sid=selected.get('stableId') or selected.get('compositeKey',[None,None])[1]
     if sid!=e['stableId']:raise ValueError('review decision targets a different stable ID')
    if proof['role']=='historical-exact-field-source':
     if (selected['file'],selected['key'],selected['field'])!=(Path(e['file']).name,e['stableId'],e['field']):raise ValueError('historical source targets a different stable ID')
    if proof['role']=='real-api-stable-skill-source':
     if type(selected.get('id')) is not int or selected['id']!=int(e['stableId']):raise ValueError('API proof targets a different stable ID')
    proof_count+=1
   entries[cid]=e;targets[target]=e;prior[prior_class]+=1
  if len(entries)!=reg['expectedEntries'] or len(entries)!=74 or dict(prior)!=reg['priorTerminalClasses']:raise ValueError('reviewed coverage differs')
  result.entries=entries;result.by_target=targets;result.prior_counts=prior;result.proof_count=proof_count
 except (OSError,UnicodeError,ValueError,KeyError,IndexError,TypeError,OverflowError) as exc:
  result.errors.append('reviewed successor contract: '+str(exc))
 return result
