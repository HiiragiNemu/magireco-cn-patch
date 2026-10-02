"""Union source-bound held TXT exports; preserve edits from every prior held batch."""
from pathlib import Path
import sys,json,gzip,hashlib,collections
W=Path(__file__).resolve().parent;R=W.parent/'repo';sys.path[:0]=[str(W),str(W.parent/'semantic-batch03-20261001')]
from checkpoint import guard,enc
from initialize import git,save
from census import Store
from exact_json import blob

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 guard();ref=json.loads((W/'bases.json').read_bytes())['patch'];prior=json.loads((W/'prior-unreleased-summary.json').read_bytes());plans=[];snapshot_proofs=[];sp=Store(patch=True)
 for b in prior['batches']:
  prefix=b['canonical_entry'].removesuffix('README.md');meta=json.loads(sp.get(ref+':'+prefix+'recovery-metadata.json'));packed=sp.get(ref+':'+meta['path']);assert sha(packed)==meta['sha256'];doc=json.loads(gzip.decompress(packed));item=doc['files']['text-plan.json'];raw=item['utf8'].encode();assert sha(raw)==item['sha256'];plan=json.loads(raw);assert not plan['holds'] and not plan['missing'];plans.append((b['batch'],plan));snapshot_proofs.append({'batch':b['batch'],'recovery_sha256':meta['sha256'],'text_plan_sha256':sha(raw),'files':len(plan['files'])});del doc,packed
 sp.close();active={};origblobs={};changed_after=[]
 for label,plan in plans:
  for f in plan['files']:
   p=f['path'];assert p not in origblobs or origblobs[p]==f['before'],('Prior export baseline drift',p);origblobs[p]=f['before'];mapping=active.setdefault(p,{})
   for e in f['edits']:
    k=(e['start'],e['end']);assert k not in mapping or (mapping[k]['before_text'],mapping[k]['after_text'])==(e['before_text'],e['after_text']),('Prior held TXT spans conflict',p,k)
    mapping[k]=dict(e,batch=label)
 before_union={p:{k:dict(v) for k,v in m.items()} for p,m in active.items()};before_unique_ops=sum(map(len,active.values()))
 proof=json.loads((W/'amendment-proof.json').read_bytes());allowed={(r['reader_path'],tuple(r['address'])) for r in proof};newplan=json.loads((W/'text-plan.json').read_bytes())
 assert not newplan['holds'] and not newplan['missing']
 for f in newplan['files']:
  p=f['path'];assert origblobs.get(p,f['before'])==f['before'];origblobs[p]=f['before'];mapping=active.setdefault(p,{})
  for e in f['edits']:
   k=(e['start'],e['end']);old=mapping.get(k)
   if old and old['after_text']!=e['after_text']:
    assert old['before_text']==e['before_text'] and (e['source_path'],tuple(e['address'])) in allowed,('Unreviewed change of prior TXT candidate',p,k,e['address'])
    changed_after.append({'path':p,'range':list(k),'source_path':e['source_path'],'address':e['address'],'prior_after_text':old['after_text'],'new_after_text':e['after_text']})
   elif not old:
    assert (e['source_path'],tuple(e['address'])) in allowed,('Unexpected new TXT field not an amendment',p,e['address'])
    changed_after.append({'path':p,'range':list(k),'source_path':e['source_path'],'address':e['address'],'prior_after_text':e['before_text'],'new_after_text':e['after_text']})
   mapping[k]=dict(e,batch='20261003-semantic-batch16-ai-only-held')
 s=Store();files={}
 for p,m in active.items():
  raw=s.get(origblobs[p]);bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'';text=raw[len(bom):].decode();ops=sorted(m.values(),key=lambda e:e['start']);cursor=-1
  for e in ops:assert e['start']>=cursor and text[e['start']:e['end']]==e['before_text'];cursor=e['end']
  result=text
  for e in reversed(ops):result=result[:e['start']]+e['after_text']+result[e['end']:]
  beforetext=text
  for e in sorted(before_union.get(p,{}).values(),key=lambda e:e['start'],reverse=True):beforetext=beforetext[:e['start']]+e['after_text']+beforetext[e['end']:]
  final=bom+result.encode();previous=bom+beforetext.encode();rev=result;shift=0;shiftops=[]
  for e in ops:a=e['start']+shift;z=a+len(e['after_text']);shiftops.append((a,z,e));shift+=len(e['after_text'])-(e['end']-e['start'])
  for a,z,e in reversed(shiftops):assert rev[a:z]==e['after_text'];rev=rev[:a]+e['before_text']+rev[z:]
  assert bom+rev.encode()==raw
  files[p]={'source_blob':origblobs[p],'source_sha256':sha(raw),'prior_candidate_sha256':sha(previous),'candidate_blob':blob(final),'candidate_sha256':sha(final),'candidate_utf8':final.decode(),'source_operations':ops,'changed_in_batch16':final!=previous}
 s.close();bundle={'schema':1,'kind':'cumulative_reader_export_candidate_document_not_runtime','published':False,'runtime_applied':False,'files':files,'prior_batches':snapshot_proofs,'amendment_spans':changed_after,'all_spans_reverse_to_committed_original':True}
 packed=gzip.compress(enc(bundle),mtime=0);(W/'cumulative-reader-exports.json.gz').write_bytes(packed)
 meta={'passed':True,'files':len(files),'old_distinct_files':len(before_union),'updated_files':sum(x['changed_in_batch16'] for x in files.values()),'prior_unique_span_operations':before_unique_ops,'current_unique_span_operations':sum(len(x['source_operations']) for x in files.values()),'amendment_physical_spans':len(changed_after),'sha256':sha(packed),'bytes':len(packed),'previous_candidate_nonamendment_spans_preserved':True,'production_applied':False,'no_additional_translation_count_for_exports':True};save('cumulative-reader-exports-metadata.json',meta);guard();print('CUMULATIVE_READER_EXPORTS',json.dumps(meta))
if __name__=='__main__':main()
