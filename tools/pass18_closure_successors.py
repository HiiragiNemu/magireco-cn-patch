"""Pinned closure-only successor contract; preserve the separate 939/74 manifest contract."""
from __future__ import annotations
import csv, io, json, re
from pathlib import Path
from pass18_reviewed_successors import canonical, confined, digest, pointer

REGISTRY_RELATIVE='magica/i18n_audit/release_v26_authority/closure_reviewed_successors_20260908/registry.json'
REGISTRY_SHA256='063e9c40787f4fdfe09947014c64ac283b08d20e60400aac2a0ab6964521d24b'
CLOSURE_RELATIVE='magica/research/totentanz-full-localization-20260817/runtime-dictionary/visible-term-closure-3136.tsv'
KIND_FILE={'PIECE_SKILL':'pieceSkillMap.json','CARD_SKILL':'cardSkillMap.json','DOPPEL_CARD_MAGIA':'doppelCardMagiaMap.json','EMOTION_SKILL':'emotionSkillMap.json'}
SUFFIX={'PIECE_SKILL':r'/pieceSkill2?$','CARD_SKILL':r'/cardSkill$','DOPPEL_CARD_MAGIA':r'/doppelCardMagia$','EMOTION_SKILL':r'/emotionSkillList/\d+$'}

class ClosureContract:
 def __init__(self):self.entries={};self.errors=[];self.proof_count=0
 def report(self):return dict(path=REGISTRY_RELATIVE,pinned_sha256=REGISTRY_SHA256,valid_entries=len(self.entries),validated_source_proofs=self.proof_count,failures=self.errors,denominator_added=0)
 def resolve(self,row,document):
  e=self.entries[row['closure_id']]
  if row!=e['immutableClosure']:raise ValueError('closure successor original row drift')
  if not isinstance(document,dict):raise ValueError('closure successor requires keyed dictionary')
  o=document[e['stableId']]
  if not isinstance(o,dict):raise ValueError('closure target record type drift')
  if 'id' in o and (type(o['id']) is not int or o['id']!=int(e['stableId'])):raise ValueError('closure inline ID disagrees with stable key')
  return o[e['field']]

def selected_proof(p,sources,parsed):
 if p['path'] not in sources or sources[p['path']][0]['sha256']!=p['sha256']:raise ValueError('closure proof source identity drift')
 if p['path'] not in parsed:
  b=sources[p['path']][1];parsed[p['path']]=json.loads(b) if p['path'].endswith('.json') else b.decode('utf-8-sig')
 data=parsed[p['path']];sel=p['selector']
 if sel['type']=='json-pointer':chosen=pointer(data,sel['pointer'])
 elif sel['type']=='tsv-closure-id':
  matches=[r for r in csv.DictReader(io.StringIO(data),delimiter='\t') if r['closure_id']==sel['pointer']]
  if len(matches)!=1:raise ValueError('closure source row not unique')
  chosen=matches[0]
 else:raise ValueError('unregistered closure proof selector')
 if digest(canonical(chosen))!=p['selectedSha256']:raise ValueError('closure selected source digest drift')
 for path,value in p['checks'].items():
  if pointer(chosen,path)!=value:raise ValueError('closure source exact assertion differs')
 return chosen

def validate_entry(e,closures,sources,parsed):
 c=closures[e['closureId']];f=e['originalFailure'];sid=e['stableId'];kind=e['recordType'];field=e['field']
 if e['file']!='magica/js/libs/'+KIND_FILE[kind] or e['idField']!='$key' or field!='shortDescription':raise ValueError('unregistered closure identity schema')
 if e['stableIdentity']!=f'{kind}|{sid}|{field}':raise ValueError('closure stable identity differs')
 if e['immutableClosure']!=c:raise ValueError('closure immutable predecessor drift')
 identity=(e['closureId'],e['file'],sid,field,e['oldExpected'])
 if identity!=(c['closure_id'],c['path'],c['stable_key'],c['field'],c['after']):raise ValueError('closure original target binding drift')
 if identity!=(f['closure_id'],f['path'],f['stable_key'],f['field'],f['expected']) or e['observedCurrent']!=f['actual']:raise ValueError('closure original failure binding drift')
 chosen={}
 for p in e['sourceProof']:
  if p['role'] in chosen:raise ValueError('duplicate closure source proof role')
  chosen[p['role']]=selected_proof(p,sources,parsed)
 if chosen['original-failure-exact-row']!=f or chosen['original-closure-exact-row']!=c:raise ValueError('closure original source rows differ')
 api=chosen['real-api-stable-kind-id-field'];ap=next(p['selector']['pointer'] for p in e['sourceProof'] if p['role']=='real-api-stable-kind-id-field')
 if type(api['id']) is not int or str(api['id'])!=sid or api['shortDescription']!=e['runtimeExactSource'] or not re.search(SUFFIX[kind],ap):raise ValueError('closure wrong real API kind, ID, or source')
 if 'historical-exact-stable-revision' in chosen:
  patch=chosen['historical-exact-stable-revision'];review=chosen['historical-source-review']
  if (patch['relativePath'],patch['recordType'],patch['id'],patch['field'],patch['stableIdentity'])!=(e['file'],kind,sid,field,e['stableIdentity']):raise ValueError('historical closure revision identity drift')
  if patch['exactBefore']!=e['oldExpected'] or patch['target']!=e['currentAuthorizedExact'] or patch['runtimeExactSource']!=api['shortDescription']:raise ValueError('historical closure exact before/target/source drift')
  if patch['reviewId']!=review['reviewId'] or patch['reviewId']!=e['sourceReviewId'] or review['target']!=patch['target'] or review['exactBefore']!=api['shortDescription'] or e['stableIdentity'] not in review['stableIdentities']:raise ValueError('historical review source binding drift')
  if patch['machineTranslated'] is not False or review['machineTranslated'] is not False:raise ValueError('historical source translation status drift')
 else:
  official=chosen['official-cn-component-not-same-id'];wiki=chosen['wiki-exact-parent-number-and-slot'];parent=chosen['real-api-piece-parent-slot'];event=chosen['same-id-event-dropadd']
  if kind!='PIECE_SKILL' or str(official['id'])==sid or official['shortDescription']!=e['oldExpected']:raise ValueError('official component identity or value misrepresented')
  slot='effect_max' if ap.endswith('/pieceSkill2') else 'effect';parent_slot=ap.rsplit('/',1)[1]
  if parent['pieceId']!=wiki['number'] or wiki['number']!=int(sid)//100 or parent[parent_slot]['id']!=int(sid) or wiki[slot]!=e['observedCurrent']:raise ValueError('wiki same-parent same-slot identity drift')
  expected=wiki[slot].replace('UP','提升').replace('DOWN','下降')
  if expected!=e['currentAuthorizedExact'] or expected!=e['oldExpected']+e['dropSuffix'] or not e['dropSuffix'].startswith(' & “'):raise ValueError('closure component or preserved suffix drift')
  art=event['eventArt1']
  if event!=api or art['verbCode']!='OTHER' or art['effectCode']!='DROPADD' or art['effectValue']!=e['dropCount']*1000:raise ValueError('real same-ID event effect drift')
  if re.search(r'＋(\d+)$',event['eventDescription'])[1]!=str(e['dropCount']) or re.search(r'＋(\d+)$',e['dropSuffix'])[1]!=str(e['dropCount']):raise ValueError('drop count drift')
 if not isinstance(e['currentAuthorizedExact'],str) or e['currentAuthorizedExact']==e['oldExpected']:raise ValueError('closure successor is not an exact distinct target')
 return len(e['sourceProof'])

def read_closure_contract(root):
 result=ClosureContract()
 try:
  path=root/REGISTRY_RELATIVE;raw=path.read_bytes()
  if digest(raw)!=REGISTRY_SHA256:raise ValueError('closure registry digest mismatch')
  reg=json.loads(raw);base=path.parent
  if reg['schema']!='pass18-closure-reviewed-successors/v1' or reg['expectedEntries']!=13 or reg['existingManifestSuccessorsRemain']!=74 or reg['denominatorsUnchanged']!={'historicalManifest':939,'visibleTermClosure':3136}:raise ValueError('closure registry denominator or schema drift')
  raw_closure=(root/CLOSURE_RELATIVE).read_bytes()
  if digest(raw_closure)!=reg['closureSha256']:raise ValueError('closure predecessor digest drift')
  rows=list(csv.DictReader(io.StringIO(raw_closure.decode('utf-8-sig')),delimiter='\t'));closures={r['closure_id']:r for r in rows}
  if len(rows)!=3136 or len(closures)!=3136:raise ValueError('closure original identity denominator drift')
  sources={};parsed={}
  for s in reg['sourceFiles']:
   b=confined(base,s['path']).read_bytes()
   if s['path'] in sources or digest(b)!=s['sha256'] or len(b)!=s['bytes']:raise ValueError('closure source file digest/size drift')
   sources[s['path']]=(s,b)
  acc=reg['acceptanceRecord'];b=confined(base,acc['path']).read_bytes()
  if digest(b)!=acc['sha256']:raise ValueError('overall acceptance relay digest drift')
  acceptance=json.loads(b)
  if acceptance['sourceType']!='CURRENT_CONTROLLER_TASK_MESSAGE' or acceptance['reportedBy']!='/root' or acceptance['overallAcceptanceReported'] is not True or acceptance['notPerRowHumanReviewRecords'] is not True or acceptance['doesNotRewriteHistoricalReviewFlags'] is not True:raise ValueError('overall acceptance relay semantics drift')
  entries={};targets=set();count=0
  for e in reg['entries']:
   count+=validate_entry(e,closures,sources,parsed)
   target=(e['file'],e['stableId'],e['field'])
   if e['closureId'] in entries or target in targets:raise ValueError('duplicate closure successor identity')
   entries[e['closureId']]=e;targets.add(target)
  if len(entries)!=13:raise ValueError('closure successor count differs')
  prerequisites=reg['runtimePrerequisites'];seen=set();cache={}
  if len(prerequisites)!=29:raise ValueError('runtime29 prerequisite count differs')
  for p in prerequisites:
   target=(p['file'],p['stableId'],p['field'])
   if target in seen or p['file']!='magica/js/libs/pieceSkillMap.json' or p['field']!='shortDescription':raise ValueError('runtime prerequisite identity drift')
   seen.add(target)
   if p['file'] not in cache:cache[p['file']]=json.loads((root/p['file']).read_bytes())
   if cache[p['file']][p['stableId']][p['field']]!=p['exactExpected']:raise ValueError('runtime29 must be consumed before closure successors: '+p['stableId'])
  result.entries=entries;result.proof_count=count
 except (OSError,UnicodeError,ValueError,KeyError,TypeError,IndexError,StopIteration) as exc:
  result.errors.append('closure reviewed successor contract: '+str(exc))
 return result
