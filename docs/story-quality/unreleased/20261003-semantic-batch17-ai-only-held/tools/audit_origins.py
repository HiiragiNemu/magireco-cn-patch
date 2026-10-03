"""Read-only current corpus provenance refresh; matching a phrase is not semantic approval."""
from pathlib import Path
import sys,json,gzip,csv,io,collections,re,datetime,hashlib
W=Path(__file__).resolve().parent; R=W.parent/'repo'
sys.path[:0]=[str(W),str(W.parent/'semantic-batch03-20261001')]
from initialize import git,tree,save
from checkpoint import guard
from census import Store,display,TEXT
CN='magireco-translate-data-master/Scenarios_full/';JP='magireco-source-master/Scenarios_full/'
IMPORT='3d463befe7a10d4cb72034378ce2a6f23c377abb';TRUSTED='65f221f2aaa5a9fe161ed32e03e4dfbb93d4746d'
def body(d):return {a:v for a,v in display(d) if a[-1] in TEXT}
def lexical(v):return re.sub(r'\[[^\[\]]*\]|[@\s]','',v)
def main():
 guard(); rt=json.loads((W/'reader-tree.json').read_bytes());pt=json.loads((W/'patch-tree.json').read_bytes());it=tree('reader',IMPORT);tt=tree('reader',TRUSTED);s=Store()
 prior=json.loads((W/'baseline-census.json').read_bytes());tracked={r['path'] for r in prior['scripts']}
 index=json.loads(s.get(rt['website/public/story_index.json']));manifest=json.loads(s.get(rt['website/public/data/machine_translation_manifest.generated.json']))
 sourceident={e['source_identity'] for e in manifest['entries'] if e.get('manual_human_verified')}
 human={p for i in index if i.get('source_identity') in sourceident for p in i.get('json_sources_cn',[])}
 protected196=set(json.loads(s.get(rt['docs/reader-availability-local-20260929.json']))['protected_source_failure']['paths'])
 variants=json.loads(s.get(rt['manifests/authoritative_scenario_variant_repairs.v1.json']))['entries'];variants_by={e['target_path']:e for e in variants}
 v4={e['target_path'] for e in json.loads(s.get(rt['manifests/authoritative_scenario_runtime_repairs.v1.json']))['entries']}
 logpath='magireco-translate-data-master/TRANSLATION_REVIEW.tsv';log=s.get(it[logpath]);pairs=collections.defaultdict(set);pair_types=collections.Counter()
 for row in csv.DictReader(io.StringIO(log.decode('utf-8-sig')),delimiter='\t'):
  typ=row.get('type','');pair_types[typ]+=1
  if typ in ('text','fallback') and row.get('japanese') and row.get('chinese'):pairs[(row['japanese'],row['chinese'])].add(typ)
 jpby=collections.defaultdict(list);players=collections.defaultdict(list)
 for p in rt:
  if p.startswith(JP) and p.endswith('.json'):jpby[Path(p).name].append(p)
 for p in pt:
  if p.startswith('madomagi/resource/scenario/json/adv/') and p.endswith('.json'):players[Path(p).name].append(p)
 rows=[];candidates=[];unknown=[];newfiles=[]
 paths=sorted(p for p in rt if p.startswith(CN) and p.endswith('.json'))
 for n,p in enumerate(paths):
  record={'path':p,'current_blob':rt[p],'script_id':Path(p).stem,'in_frozen_1079':p in tracked}
  if p in tracked:record['status']='already_tracked_in_frozen_1079'
  elif p in protected196:record['status']='authorized_196_excluded'
  elif p in variants_by:record['status']='authoritative_variant_519_excluded'
  elif p in human:record['status']='human_marked_excluded'
  elif p in v4:record['status']='v4_protected_excluded'
  elif p in tt and rt[p]==tt[p]:record['status']='unchanged_trusted_baseline'
  else:
   jp=p.replace(CN,JP,1)
   if jp not in rt:jp=jpby[Path(p).name][0] if len(jpby[Path(p).name])==1 else None
   record['jp_path']=jp;record['jp_blob']=rt.get(jp);record['player_paths']=players.get(Path(p).name,[])
   try:c=body(json.loads(s.get(rt[p])));j=body(json.loads(s.get(rt[jp]))) if jp else {}
   except (ValueError,AssertionError) as e:record['status']='unparsed_requires_source_read';record['parse_error']=str(e);rows.append(record);continue
   record['body_fields']=len(c)
   if not jp:record['status']='japanese_mapping_unresolved';unknown.append(record)
   elif not any(re.search(r'[A-Za-z\u3400-\u9fff\u3040-\u30ff]',lexical(v)) for v in c.values()):record['status']='no_lexical_body'
   else:
    imp=body(json.loads(s.get(it[p]))) if p in it else {};trust=body(json.loads(s.get(tt[p]))) if p in tt else {}
    proofs=[]
    for a,v in c.items():
     typ=pairs.get((j.get(a),v))
     if not typ or len(lexical(v))<5:continue
     # Require the current text still equals the machine-import output and differs from trusted input, when present.
     if imp.get(a)!=v or trust.get(a)==v:continue
     proofs.append({'address':list(a),'japanese':j.get(a),'current_chinese':v,'import_chinese':imp[a],'trusted_before':trust.get(a),'log_types':sorted(typ)})
    if proofs:
     record.update(status='new_exact_machine_import_evidence_requires_review',import_blob=it.get(p),trusted_blob=tt.get(p),machine_fields=proofs,machine_fields_count=len(proofs),ai_scope='entire_new_import' if p not in tt else 'mixed_file_changed_machine_fields_only');candidates.append(record)
    else:
     record['status']='no_exact_current_machine_proof';unknown.append(record)
    if p not in it:newfiles.append(record)
  rows.append(record)
  if n%1500==0:print('SCANNED',n,'CANDIDATE_PATHS',len(candidates),flush=True)
 s.close();summary={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reader_source':json.loads((W/'bases.json').read_bytes())['reader'],'scanned_cn_paths':len(paths),'frozen_1079_retained':len(tracked),'status_counts':dict(collections.Counter(r['status'] for r in rows)),'machine_log_blob':it[logpath],'machine_log_sha256':hashlib.sha256(log).hexdigest(),'machine_log_types':dict(pair_types),'new_candidate_paths':len(candidates),'new_candidate_proven_fields':sum(r['machine_fields_count'] for r in candidates),'no_semantic_completion_from_scan':True,'production_changed':False}
 save('origin-refresh-summary.json',summary);(W/'origin-refresh-ledger.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode(),mtime=0));save('new-origin-candidates.json',candidates);save('provenance-only-not-ai.json',unknown);save('post-import-paths.json',newfiles)
 print(json.dumps(summary,ensure_ascii=False,indent=2));print('CANDIDATES',[(r['script_id'],r['machine_fields_count'],r['ai_scope']) for r in candidates],flush=True);guard()
if __name__=='__main__':main()
