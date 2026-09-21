"""Pinned engine extension lineage and exact historical target successors.

No runtime values or historical count constants are rewritten by this module.
The accepted table is an immutable prior released artifact, not the current input.
"""
from __future__ import annotations
import csv,hashlib,json
from pathlib import Path
REGISTRY='magica/i18n_audit/release_v26_authority/engine_reviewed_successors_20260908/registry.json'
REGISTRY_SHA256='6ab51b4abfea72056e84c05ff0481f4369919e003f649769fa00e5017ff4d9a8'
HISTORICAL_COMMIT='c2e8615f116eb699a981e98c80a29a6335b290f2'
RELEASED_COMMIT='93d0e8ed415154be244abd2d61cc4689a7307499'
HISTORICAL_SHA256='054a726ade2241900a3b0b89ff2cf671162131ec9ff73939f6efe5108211a384'
RELEASED_SHA256='5350f514ada4def218c4b7cd210a351233f44f116bc431d81dd69d7fbe0163c6'
OFFICIAL_SOURCE='Critical Hit Chance [IV] / ATK UP [II] / Negate Charm'
def digest(b):return hashlib.sha256(b).hexdigest()
def at(o,p):
 for k in p.strip('/').split('/'):o=o[int(k)] if isinstance(o,list) else o[k]
 return o
def table(raw):
 if raw.startswith(b'\xef\xbb\xbf') or b'\r' in raw:raise ValueError('pinned table encoding/line ending differs')
 lines=raw.decode('utf-8').splitlines();rows={}
 for line in lines:
  if not line or line.startswith('#'):continue
  cols=line.split('\t')
  if len(cols)!=2 or not cols[0] or cols[0] in rows:raise ValueError('pinned table malformed or duplicate source')
  rows[cols[0]]=cols[1]
 return rows,len(lines)
class EngineContract:
 def __init__(self):
  self.errors=[];self.valid=False;self.official_row=None;self.official_target=None;self.successors={}
  self.report={'schema':'totentanz-pass18-engine-reviewed-contract-result/v1','valid':False,'historical_data_rows':621,'historical_physical_lines':622,'failures':self.errors}
 def official_expected(self,row):
  if self.valid and row==self.official_row:return self.official_target
  return row.get('current_cn','')
 def successor_for(self,source):
  return self.successors.get(source) if self.valid else None
 def expected_target(self,source,fallback):
  row=self.successor_for(source)
  return row['authorizedExact'] if row else fallback
def read_engine_contract(root:Path,current_raw:bytes)->EngineContract:
 out=EngineContract()
 try:
  raw=(root/REGISTRY).read_bytes()
  if digest(raw)!=REGISTRY_SHA256:raise ValueError('engine registry pin differs')
  reg=json.loads(raw)
  if reg['schema']!='totentanz-pass18-engine-reviewed-successors/v1':raise ValueError('engine registry schema differs')
  proofs={}
  for name,p in reg['proofs'].items():
   rel=Path(p['path'])
   if rel.is_absolute() or '..' in rel.parts:raise ValueError('proof path escapes product: '+name)
   target=(root/rel).resolve()
   if not target.is_relative_to(root.resolve()):raise ValueError('resolved proof path escapes product: '+name)
   b=target.read_bytes()
   if len(b)!=p['bytes'] or digest(b)!=p['sha256']:out.errors.append('engine source proof pin differs: '+name)
   else:proofs[name]=b
  if out.errors:return out
  hist,hl=table(proofs['historicalTable']);accepted,al=table(proofs['acceptedReleasedTable'])
  if digest(proofs['historicalTable'])!=HISTORICAL_SHA256 or (len(hist),hl)!=(621,622):raise ValueError('historical 621/622 identity snapshot differs')
  if digest(proofs['acceptedReleasedTable'])!=RELEASED_SHA256:raise ValueError('accepted released engine source differs')
  if reg['historical']!={'commit':HISTORICAL_COMMIT,'dataRows':621,'physicalLines':622,'sha256':HISTORICAL_SHA256}:raise ValueError('historical registry identity differs')
  if reg['accepted']!={'commit':RELEASED_COMMIT,'sha256':RELEASED_SHA256,'bytes':len(proofs['acceptedReleasedTable']),'dataRows':len(accepted),'physicalLines':al}:raise ValueError('accepted released registry differs')
  # Git objects and the actual bounded git-show/ancestor receipt are immutable source evidence.
  for label,commit in [('historicalCommit',HISTORICAL_COMMIT),('releasedCommit',RELEASED_COMMIT)]:
   b=proofs[label];object_id=hashlib.sha1(b'commit '+str(len(b)).encode()+b'\0'+b).hexdigest()
   if object_id!=commit:raise ValueError('commit object identity differs: '+label)
  receipt=json.loads(proofs['ancestryReceipt']);commits={r['commit']:r for r in receipt['commits']}
  old=commits[HISTORICAL_COMMIT];new=commits[RELEASED_COMMIT]
  for row,pkey,c,expected in [(old,'historicalTable',HISTORICAL_COMMIT,HISTORICAL_SHA256),(new,'acceptedReleasedTable',RELEASED_COMMIT,RELEASED_SHA256)]:
   if row['exitStatus']!=0 or row['sha256']!=expected or row['bytes']!=len(proofs[pkey]) or row['command'][-2:]!=['show',c+':madomagi/engine_i18n.tsv']:raise ValueError('git table receipt binding differs')
  anc=old['ancestorCheck']
  if anc['exitStatus']!=0 or anc['command'][-4:]!=['merge-base','--is-ancestor',HISTORICAL_COMMIT,RELEASED_COMMIT]:raise ValueError('historical-to-released ancestor receipt differs')
  v4=json.loads(proofs['acceptedV4Manifest'])['files'][0]
  if v4!={'path':'madomagi/engine_i18n.tsv','beforeSha256':RELEASED_SHA256,'afterSha256':RELEASED_SHA256,'bytes':len(proofs['acceptedReleasedTable']),'action':'PRESERVE_CURRENT_BASELINE'}:raise ValueError('accepted preserved engine artifact binding differs')
  if reg['acceptance']['ledgerExactLine'] not in proofs['overallUserAcceptance'].decode('utf-8-sig').splitlines():raise ValueError('overall user acceptance relay differs')
  successors={x['source']:x for x in reg['historicalTargetSuccessors']}
  changed={k for k in hist if k in accepted and hist[k]!=accepted[k]};added=set(accepted)-set(hist);removed=set(hist)-set(accepted)
  if len(successors)!=2 or changed!=set(successors) or len(added)!=9375 or removed:raise ValueError('registered historical/extension identity partition differs')
  if reg['lineage']!={'ancestor':HISTORICAL_COMMIT,'descendant':RELEASED_COMMIT,'retainedIdentities':621,'unchangedTargets':619,'registeredTargetSuccessors':2,'addedSources':9375,'removedSources':0}:raise ValueError('engine lineage partition metadata differs')
  for source,r in successors.items():
   if hist[source]!=r['oldExpected'] or accepted[source]!=r['authorizedExact']:raise ValueError('historical successor exact before/after differs: '+source)
  off=successors[OFFICIAL_SOURCE]
  if off['kind']!='V42_EXACT_STABLE_SOURCE_SUCCESSOR' or off['entryId']!='ENG-P18-004' or off['stableIdentity']!='PIECE_SKILL|144901|shortDescription':raise ValueError('official successor kind/entry/stable ID differs')
  official=list(csv.DictReader(proofs['historicalOfficialAudit'].decode('utf-8-sig').splitlines(),delimiter='\t'));official_rows=[r for r in official if r['entry_id']=='ENG-P18-004']
  if len(official)!=5 or len(official_rows)!=1 or official_rows[0]!=off['historicalOfficialRow']:raise ValueError('historical official audit identity or source metadata differs')
  if official_rows[0]['source_text']!=OFFICIAL_SOURCE or official_rows[0]['current_cn']!=off['oldExpected']:raise ValueError('official source/old expectation differs')
  dec=at(json.loads(proofs['v42Decision']),off['decisionPointer'])
  if dec!=off['decisionExact'] or dec['reviewId']!='V42-SRC-0593' or dec['action']!='REPLACE_NATIVE_EXACT_FULL_SOURCE_RULE' or dec['exactBefore']!=OFFICIAL_SOURCE or dec['existingTarget']!=off['oldExpected'] or dec['target']!=off['authorizedExact'] or dec['stableIdentities']!=['PIECE_SKILL|144901|shortDescription'] or dec['machineTranslated'] is not False or dec['audioTranscription'] is not False:raise ValueError('V42 exact decision binding differs')
  ent=at(json.loads(proofs['realApi']),off['apiPointer'])
  if ent['id']!=144901 or ent['groupId']!=1121 or ent['shortDescription']!=OFFICIAL_SOURCE or [ent['artId1'],ent['artId2'],ent['artId3']]!=[690206304,390201102,690208300]:raise ValueError('actual API source/stable ID/art identity differs')
  selected=at(json.loads((root/off['runtimeMap']).read_bytes()),off['runtimeMapPointer'])
  if selected!=off['authorizedExact']:out.errors.append('ENG-P18-004 current typed stable-field target differs')
  verified=json.loads(proofs['v42Verification']);independent=json.loads(proofs['v42Independent'])
  if verified['status']!='PASS' or verified['exitStatuses']!={'apply':0,'rollback':0,'reapply':0} or verified['reopen']['engineDecisions']!='2367/2367':raise ValueError('V42 prior verification binding differs')
  if independent['status']!='PASS' or independent['engineRules']!={'original':7722,'modified':9900} or independent['byteEqualityEachPhase']!='7/7':raise ValueError('V42 independent reopen binding differs')
  variable=successors['ヴァリアブル']
  if variable['kind']!='ACCEPTED_RELEASED_ARTIFACT_EXACT' or variable['oldExpected']!='Variable' or variable['authorizedExact']!='全属性克制':raise ValueError('second historical accepted-artifact successor differs')
  current,physical=table(current_raw)
  missing=sorted(set(accepted)-set(current));extra=sorted(set(current)-set(accepted));drift=[{'source':s,'expected':accepted[s],'actual':current[s]} for s in accepted.keys()&current.keys() if accepted[s]!=current[s]]
  if digest(current_raw)!=RELEASED_SHA256:out.errors.append('current engine bytes differ from pinned accepted released artifact')
  if missing:out.errors.append('current engine missing registered sources: '+str(len(missing)))
  if extra:out.errors.append('current engine has unregistered sources: '+str(len(extra)))
  if drift:out.errors.append('current engine exact targets differ: '+str(len(drift)))
  if len(current)!=len(accepted) or physical!=al:out.errors.append('current engine registered expansion data/physical counts differ')
  historical_failures=[{'source':s,'historicalExpected':hist[s],'authorizedExpected':successors[s]['authorizedExact'] if s in successors else hist[s],'actual':current.get(s)} for s in hist if current.get(s)!=(successors[s]['authorizedExact'] if s in successors else hist[s])]
  if historical_failures:out.errors.append('historical 621 source identities/authorized exact targets differ: '+str(len(historical_failures)))
  out.report.update({'registry':REGISTRY,'registry_sha256':REGISTRY_SHA256,'historical_commit':HISTORICAL_COMMIT,'accepted_commit':RELEASED_COMMIT,'accepted_source_sha256':RELEASED_SHA256,'accepted_data_rows':len(accepted),'accepted_physical_lines':al,'historical_retained_identities':len(hist),'historical_unchanged_targets':619,'historical_registered_target_successors':2,'registered_added_sources':len(added),'missing_registered_sources':missing,'unregistered_sources':extra,'target_drift':drift,'historical_identity_failures':historical_failures,'official_reviewed_successor_matches':1 if not out.errors else 0,'registered_successor_ids':[r['successorId'] for r in reg['historicalTargetSuccessors']],'authority_scope':reg['acceptance']['scope']})
  out.official_row=off['historicalOfficialRow'];out.official_target=off['authorizedExact'];out.successors={k:dict(v) for k,v in successors.items()};out.valid=not out.errors;out.report['valid']=out.valid
 except (OSError,ValueError,KeyError,TypeError,IndexError,UnicodeError) as exc:out.errors.append('engine reviewed contract invalid: '+str(exc))
 return out
