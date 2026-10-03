"""Deterministic read-only residual review set; record an explicit decision for every displayed slice."""
from pathlib import Path
import sys,json,gzip,collections,hashlib,csv,io,re
W=Path(__file__).resolve().parent;sys.path[:0]=[str(W),str(W.parent/'semantic-batch03-20261001'),str(W.parent/'severe-5109-20261001')]
from initialize import git,tree,save,enc
from checkpoint import guard
from audit_origins import body,IMPORT,TRUSTED
from census import Store
from collect_review import fields

def read(n):return json.loads((W/n).read_bytes())
def digest(raw):return hashlib.sha256(raw).hexdigest()
def prepare():
 guard();assert not (W/'sweep-set.json').exists(),'Reuse fixed sweep set'
 refs=read('bases.json');rt=read('reader-tree.json');tt=tree('reader',TRUSTED);store=Store();packet=json.loads(gzip.decompress((W/'prior-integration-manifest.json.gz').read_bytes()));index=json.loads(gzip.decompress((W/'candidate-display-field-index.json.gz').read_bytes()))
 protected=set(json.loads(store.get(rt['docs/reader-availability-local-20260929.json']))['protected_source_failure']['paths'])
 for name in ('manifests/authoritative_scenario_variant_repairs.v1.json','manifests/authoritative_scenario_runtime_repairs.v1.json'):
  protected.update(e['target_path'] for e in json.loads(store.get(rt[name]))['entries'])
 pins=json.loads(git('patch','show',refs['patch']+':docs/story-quality/unreleased/20261003-semantic-batch15-ai-only-held/protected-field-pins.json'))['records'];pinset={(r['script_id'],tuple(r['address'])) for r in pins}
 es={e['script_id']:e for e in packet['files']};cache={};selected=[];excluded=[]
 for row in index:
  e=es[row['id']];cp=e['reader_path'];at=tuple(row['address'])
  if not row['unchanged_imported_machine_field'] or e['mode']!='fresh_full_review':continue
  if cp in protected or cp in tt or (row['id'],at) in pinset:
   excluded.append({'id':row['id'],'address':list(at),'reason':'Human/authoritative protected or trusted baseline; not an AI amendment target'});continue
  if cp not in cache:
   current=json.loads(store.get(rt[cp]));impraw=store.get(IMPORT+':'+cp);jraw=store.get(e['source_jp_blob']);names={tuple(f['address']):f['name'] for f in fields(current)}
   cache[cp]=(body(json.loads(impraw)),names,digest(jraw))
  imp,names,jsha=cache[cp]
  if imp.get(at)!=row['cn']:
   excluded.append({'id':row['id'],'address':list(at),'reason':'Current field differs from original machine import'});continue
  item=dict(row,sweep_id=len(selected),speaker=names.get(at),source_jp_sha256=jsha)
  selected.append(item)
 store.close();save('sweep-set.json',selected);save('sweep-exclusions.json',excluded)
 save('sweep-summary.json',{'scope':'All source-proven still-unmodified AI fields within fresh-full-review held candidates; not all corpus translations','candidate_manifest_sha256':digest((W/'prior-integration-manifest.json.gz').read_bytes()),'candidate_targets':len(packet['files']),'display_fields_indexed':len(index),'residual_fields':len(selected),'residual_scripts':len({r['id'] for r in selected}),'protected_fields_excluded':len(excluded),'new_full_reviews':0,'published':False})
 (W/'sweep-reviews').mkdir(exist_ok=True)
 print(json.dumps(read('sweep-summary.json'),ensure_ascii=False));guard()
def show(start,stop):
 rows=read('sweep-set.json');part=rows[start:stop];text=[];last=None
 for r in part:
  if r['id']!=last:text.append('\n### '+r['id']+' | '+r['reader_path'].split('Scenarios_full/',1)[-1]);last=r['id']
  text.append(f"{r['sweep_id']} /{r['ordinal']} {r['speaker'] or '旁白/无标签'} | J:{r['jp']} | C:{r['cn']}")
 out='\n'.join(text)+'\n';f=W/'sweep-reviews'/f'display-{start:04d}-{start+len(part):04d}.txt';f.write_text(out,encoding='utf8')
 print(out);print('DISPLAYED',start,start+len(part),'COUNT',len(part),'SHA256',digest(enc(part)))
def record(path):
 guard();d=read(path);rows=read('sweep-set.json');a,b=d['start'],d['stop'];part=rows[a:b];assert d['all_displayed_rows_semantically_reviewed'] and d['source_slice_sha256']==digest(enc(part));assert (W/'sweep-reviews'/f'display-{a:04d}-{b:04d}.txt').exists()
 updates=d['changes'];assert set(map(int,updates)).issubset(range(a,b));out=[]
 for r in part:
  k=str(r['sweep_id']);change=updates.get(k);out.append({'sweep_id':r['sweep_id'],'id':r['id'],'ordinal':r['ordinal'],'address':r['address'],'japanese':r['jp'],'prior_candidate':r['cn'],'disposition':'correct' if change else 'retain','after':change[0] if change else r['cn'],'rationale':change[1] if change else 'Source comparison in this slice found no definite semantic error; retain existing wording; not a new full review.'})
 target=W/'sweep-reviews'/f'decisions-{a:04d}-{b:04d}.json';assert not target.exists(),'Do not silently overwrite reviewed evidence';target.write_bytes(enc({'slice_sha256':d['source_slice_sha256'],'rows':out}));print('RECORDED',a,b,'CORRECTIONS',len(updates));guard()
def merge():
 rows=read('sweep-set.json');seen={};edits={}
 for f in sorted((W/'sweep-reviews').glob('decisions-*.json')):
  for r in json.loads(f.read_bytes())['rows']:
   assert r['sweep_id'] not in seen,'Overlapping review slices';seen[r['sweep_id']]=r
   if r['disposition']=='correct':edits.setdefault(r['id'],{})[str(r['ordinal'])]=[r['after'],r['rationale']]
 save('amendment-decisions.json',edits);todo=[{'sweep_id':r['sweep_id'],'script_id':r['id'],'ordinal':r['ordinal'],'reader_path':r['reader_path']} for r in rows if r['sweep_id'] not in seen]
 save('sweep-review-ledger.json',{'reviewed':len(seen),'corrected':sum(len(e) for e in edits.values()),'amended_scripts':len(edits),'remaining_fields':len(todo),'remaining_scripts':len({r['script_id'] for r in todo}),'remaining':todo,'rows':list(seen.values()),'new_full_reviews':0,'published':False});print('SWEEP',len(rows),'REVIEWED',len(seen),'CORRECTIONS',sum(len(e) for e in edits.values()),'SCRIPTS',len(edits),'REMAINING',len(todo))
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='show':show(int(sys.argv[2]),int(sys.argv[3]))
 elif sys.argv[1]=='record':record(sys.argv[2])
 elif sys.argv[1]=='merge':merge()
