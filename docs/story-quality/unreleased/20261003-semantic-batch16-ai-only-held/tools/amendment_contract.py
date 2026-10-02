"""Append source-proven missing translation edits without overwriting an earlier decision."""
import copy,hashlib,json
from exact_json import apply,blob
from translation_rules import validate

def sha(b):return hashlib.sha256(b).hexdigest()
def amend(entry,source,decisions):
 if blob(source)!=entry['before_blob'] or sha(source)!=entry['before_sha256']:raise ValueError('Live source differs from frozen client baseline')
 prior=entry['candidate_utf8'].encode('utf8')
 if blob(prior)!=entry['after_blob'] or sha(prior)!=entry['after_sha256']:raise ValueError('Prior candidate identity mismatch')
 if apply(source,entry['operations'])!=prior:raise ValueError('Prior operations do not rebuild prior candidate')
 old_addresses={tuple(op[0]) for op in entry['operations']};seen=set();newops=[]
 for d in decisions:
  at=tuple(d['address'])
  if at in old_addresses:raise ValueError('Earlier reviewed operation cannot be silently rewritten')
  if at in seen:raise ValueError('Duplicate amendment address')
  if not d.get('unchanged_imported_machine_field') or not d.get('machine_types') or not d.get('japanese') or not d.get('rationale'):raise ValueError('Missing exact current machine evidence or semantic review')
  if d.get('protected',False):raise ValueError('Protected human field')
  if d['before']!=d.get('import_chinese') or d['before']!=d.get('prior_candidate_text'):raise ValueError('Current field is not untouched import output')
  if d['before'].count('userName')!=d['after'].count('userName'):raise ValueError('Player placeholder changed')
  seen.add(at);newops.append([d['address'],d['before'],d['after']])
 revised=apply(prior,newops);validate(prior,revised,newops)
 if apply(revised,[[a,n,o] for a,o,n in newops])!=prior:raise ValueError('Amendment not byte reversible')
 combined=copy.deepcopy(entry['operations'])+newops
 if apply(source,combined)!=revised:raise ValueError('Cumulative rebuild failed')
 if apply(revised,[[a,n,o] for a,o,n in combined])!=source:raise ValueError('Combined reverse failed')
 out=copy.deepcopy(entry);out.update(operations=combined,candidate_utf8=revised.decode('utf8'),after_blob=blob(revised),after_sha256=sha(revised))
 return out,newops
