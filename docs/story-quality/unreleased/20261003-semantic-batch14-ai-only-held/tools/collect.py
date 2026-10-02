"""Freeze exact AI-only targets; no runtime repository writes and no publication."""
from pathlib import Path
import sys,json,hashlib,csv,io,collections
W=Path(__file__).resolve().parent;ROOT=W.parent;R=ROOT/'repo'
sys.path[:0]=[str(ROOT/'semantic-batch03-20261001'),str(ROOT/'severe-5109-20261001')]
from census import Store
from collect_review import fields,shape,differences,TEXT,CTRL
TEXT.add('textSelect')
IMPORT='3d463befe7a10d4cb72034378ce2a6f23c377abb';TRUSTED='65f221f2aaa5a9fe161ed32e03e4dfbb93d4746d'
REUSE_CHAPTERS=[]
FRESH_CHAPTERS=['615701', '617501', '619001', '626601', '628101', '634101', '710017', '710024', '710025', '710035', '710036', '710044', '710045', '710055', '710056', '710063', '710113', '710153', '710221', '710222', '710231', '710232', '710241', '710242', '710381', '720033', '720053', '720054', '720065', '720072', '720091', '722031', '730072', '730101', '730131', '730281', '730302', '730341', '730352', '730401', '730522', '730532', '730571', 'costume_story_730102_1-1_69414e2639', 'mirror_story_420131_1-4_9c6c2dfea7']
from baseline import git,tree,save

def main():
 assert not (W/'review-sources.json').exists()
 bases=json.loads((W/'bases.json').read_bytes());rt=json.loads((W/'reader-tree.json').read_bytes());pt=json.loads((W/'patch-tree.json').read_bytes());old=json.loads((W/'baseline-census.json').read_bytes());confirmed={x['path']:x for x in old['scripts']}
 it=tree('reader',IMPORT);trusted=tree('reader',TRUSTED);rs=Store();ps=Store(True)
 manifest=json.loads(rs.get(rt['website/public/data/machine_translation_manifest.generated.json']));index=json.loads(rs.get(rt['website/public/story_index.json']))
 candidates={x['story_id']:x for x in manifest['entries'] if not x['manual_human_verified']}
 human={p for x in manifest['entries'] if x['manual_human_verified'] for s in index if s.get('source_identity')==x['source_identity'] for p in s.get('json_sources_cn',[])}
 protected=set(json.loads(rs.get(rt['docs/reader-availability-local-20260929.json']))['protected_source_failure']['paths']);protected.update(x['target_path'] for x in json.loads(rs.get(rt['manifests/authoritative_scenario_runtime_repairs.v1.json']))['entries'])
 pairs=collections.defaultdict(list)
 for row in csv.DictReader(io.StringIO(rs.get(it['magireco-translate-data-master/TRANSLATION_REVIEW.tsv']).decode('utf-8-sig')),delimiter='\t'):pairs[row['japanese']].append(row)
 ppnames=collections.defaultdict(list)
 for p in pt:
  if p.startswith('madomagi/resource/scenario/json/adv/') and p.endswith('.json'):ppnames[Path(p).name].append(p)
 sources=[];chapters=[]
 for chapterid in REUSE_CHAPTERS+FRESH_CHAPTERS:
  assert chapterid in candidates
  hits=[x for x in index if x.get('source_identity')==candidates[chapterid]['source_identity']];assert len(hits)==1
  chapter=hits[0];ch=[]
  for cp in chapter['json_sources_cn']:
   assert cp not in human|protected and cp not in trusted and cp in it,cp
   assert cp not in set(json.loads((W/'prior-prepared-paths.json').read_bytes())),('Already held in prior batch',cp)
   p=confirmed[cp];assert p['machine_output_pair_count']>0 and p['current_blob']==rt[cp] and p['jp_blob']==rt[p['jp_path']]
   sid=Path(cp).stem;jp=p['jp_path'];a=rs.get(rt[cp]);b=rs.get(rt[jp]);init=rs.get(it[cp]);c=json.loads(a);j=json.loads(b);cf=fields(c);jf=fields(j)
   assert [x['address'] for x in cf]==[x['address'] for x in jf] and shape(c)==shape(j),('Require exact execution and display correspondence',sid)
   assert len(ppnames[Path(cp).name])==1;pp=ppnames[Path(cp).name][0];pb=ps.get(pt[pp]);assert pb==a,('Player differs; independently adjudicate before edits',sid)
   ff={tuple(x['address']):x for x in fields(json.loads(init))};aligned=[]
   for n,(x,y) in enumerate(zip(cf,jf)):
    orig=ff[tuple(x['address'])]['text'];aligned.append({'ordinal':n,'address':x['address'],'cn_name':x['name'],'jp_name':y['name'],'actor_id':x['actor_id'],'jp_actor_id':y['actor_id'],'cn':x['text'],'jp':y['text'],'initial_import_cn':orig,'current_same_as_import':orig==x['text'],'translation_review_matches':pairs.get(y['text'],[])})
   mode='context_only' if p['complete'] else 'exact_reviewed_text_reuse' if chapterid in REUSE_CHAPTERS else 'fresh_full_review'
   meta={'id':sid,'chapter_id':chapterid,'cn_path':cp,'cn_sha':rt[cp],'jp_path':jp,'jp_sha':rt[jp],'patch_path':pp,'patch_sha':pt[pp],'cn_fields':len(cf),'jp_fields':len(jf),'same_field_addresses':True,'reader_player_bytes_equal':True,'nontext_diff_count':0,'already_complete_context_only':p['complete'],'review_mode':mode,'provenance':{'report_commit':IMPORT,'import_blob':it[cp],'absent_from_trusted_baseline':True,'verified_human_excluded':True,'current_machine_pair_count':p['machine_output_pair_count']}}
   (W/'review').mkdir(exist_ok=True)
   for suffix,data in [('cn',a),('jp',b),('import',init)]:(W/'review'/(sid+'.'+suffix+'.json')).write_bytes(data)
   for suffix,obj in [('aligned',aligned),('cn-fields',cf),('jp-fields',jf)]:save('review/'+sid+'.'+suffix+'.json',obj)
   sources.append(meta);ch.append(meta)
  chapters.append({'story_id':chapterid,'title':chapter.get('title') or chapter['source_identity'].split('/')[1].split(' - ',1)[-1],'source_identity':chapter['source_identity'],'script_ids':[x['id'] for x in ch],'paths':[x['cn_path'] for x in ch],'fields':sum(x['cn_fields'] for x in ch),'kind':'reuse' if chapterid in REUSE_CHAPTERS else 'fresh'})
  print(chapterid,len(ch),chapters[-1]['fields'],'new',sum(not x['already_complete_context_only'] for x in ch),flush=True)
 assert len({x['cn_path'] for x in sources})==len(sources)
 save('review-sources.json',sources);save('chapters.json',chapters);save('provenance.json',{'origin_commit':IMPORT,'trusted_baseline':TRUSTED,'report_path':'magireco-translate-data-master/TRANSLATION_TEST_REPORT.md','report_blob':it['magireco-translate-data-master/TRANSLATION_TEST_REPORT.md'],'report_text':rs.get(it['magireco-translate-data-master/TRANSLATION_TEST_REPORT.md']).decode('utf8'),'sources':sources,'warning':'Reused human text memory inside an AI-origin file is retained; reviewed AI does not become original human translation.'})
 progress=json.loads((W/'progress.json').read_bytes());progress.update(stage='review',selected_scripts=len(sources),selected_chapters=len(chapters),selected_fields=sum(x['cn_fields'] for x in sources),selected_modes=dict(collections.Counter(x['review_mode'] for x in sources)),checkpoint='Selected indexed chapters frozen for full AI-only review; prior held candidates excluded; no publication');save('progress.json',progress)
 rs.close();ps.close();print('FROZEN',progress['selected_modes'],progress['selected_fields'])
if __name__=='__main__':main()
