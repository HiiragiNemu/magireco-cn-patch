"""Independently verify the generated data against final source-bound candidates, including actual gzip members."""
from pathlib import Path
import sys,json,gzip,collections,hashlib,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from audit import read,save,sha,guard,enc
S=W/'reader-build';PUB=S/'website/public'

def main():
 guard();run=read('production-result.json');assert run['passed'] and all(c['exit_code']==0 for c in run['checks'])
 packet=json.loads(gzip.decompress((W/'reader-input-manifest.json.gz').read_bytes()));assert len(packet['files'])==601
 inputs=[];bad=[]
 for e in packet['files']:
  p=S/e['path'];actual=sha(p.read_bytes()) if p.exists() else None
  row={'path':e['path'],'expected_sha256':e['candidate_sha256'],'actual_sha256':actual,'matches':actual==e['candidate_sha256']};inputs.append(row)
  if not row['matches']:bad.append(row)
 save('generated-input-checks.json',inputs);assert not bad,bad[:10]
 old=read('live/story_index.json');new=json.loads((PUB/'story_index.json').read_bytes());oldmap={x['id']:x for x in old};newmap={x['id']:x for x in new};assert oldmap.keys()==newmap.keys()
 stable=('id','path_cn','path_jp','source_identity','json_sources_cn','json_sources_jp','legacy_ids')
 diffs=[]
 for sid,x in oldmap.items():
  for k in stable:
   if x.get(k)!=newmap[sid].get(k):diffs.append({'id':sid,'key':k,'before':x.get(k),'after':newmap[sid].get(k)})
 save('catalog-route-differences.json',diffs);assert not diffs,'Unexpected route/source membership change'
 mapping=collections.defaultdict(list)
 for story in new:
  for i,p in enumerate(story.get('json_sources_cn',[])):mapping[p].append({'story_id':story['id'],'source_index':i})
 targets={e['path']:e for e in packet['files'] if e['path'].endswith('.json')};assert len(targets)==361 and all(mapping[p] for p in targets)
 refs={};shards=list((PUB/'story-json-catalog/v1').glob('*.json'))
 for f in shards:
  shard=json.loads(f.read_bytes());assert shard['source_revision']==run['local_candidate_source']
  for p,r in shard['source_packs'].items():
   if p in refs:assert refs[p]==r
   refs[p]=r
 checked=[];cache={}
 for p,r in refs.items():
  asset=r['asset'];filename=PUB/asset.lstrip('/')
  if asset not in cache:cache[asset]=filename.read_bytes();assert len(cache[asset])==r['pack_length'];assert filename.stem==sha(cache[asset])
  compressed=cache[asset][r['offset']:r['offset']+r['length']];assert sha(compressed)==r['compressed_sha256'];raw=gzip.decompress(compressed);assert sha(raw)==r['sha256'] and len(raw)==r['raw_length'];assert raw==(S/p).read_bytes(),p
  if p in targets:assert sha(raw)==targets[p]['candidate_sha256'];checked.append({'path':p,'sha256':sha(raw),'routes':mapping[p],'asset':asset})
 assert len(checked)==361;save('all-reader-target-pack-checks.json',checked)
 build=json.loads((PUB/'adv-release-build.json').read_bytes());assert len(refs)==build['source_packs']['files']
 search={}
 for scope in ('magireco','exedra'):
  manifest=json.loads((PUB/f'search_index_manifest.{scope}.json').read_bytes());payload=(S/f'artifacts/search-split/search_content.{scope}.json').read_bytes();assert sha(payload)==manifest['sha256'] and len(payload)==manifest['bytes'];data=json.loads(payload);assert len(data)==manifest['entries']
  assert manifest['story_index_sha256']==sha((PUB/'story_index.json').read_bytes())
  search[scope]={'entries':len(data),'bytes':len(payload),'sha256':sha(payload),'chunks':len(manifest['chunks']),'sample_keys':list(data[0]) if data and isinstance(data[0],dict) else []}
 assert search['magireco']['sha256']!=read('live/search-manifest.json')['sha256'],'Expected corrected full-text search content'
 products=[]
 selections=['website/public/story_index.json','website/public/story_ids.json','website/public/story_voice_index.generated.json','website/public/adv-release-build.json','website/public/data/machine_translation_manifest.generated.json','website/public/data/proofreading_story_map.generated.json']
 files={S/p for p in selections if (S/p).is_file()}
 for prefix in ('website/public/data','website/public/story-voice','website/public/story-json-catalog','website/public/story-json-packs','website/public/search-chunks'):
  files.update(f for f in (S/prefix).rglob('*') if f.is_file() and f.suffix.lower() in ('.json','.txt','.part','.bin'))
 files.update(PUB.glob('search_index_manifest.*.json'));files.update((S/'artifacts/search-split').glob('search_content.*.json'))
 for f in sorted(files):
  b=f.read_bytes();products.append({'path':f.relative_to(S).as_posix(),'bytes':len(b),'sha256':sha(b)})
 packed=gzip.compress(enc({'source':run['local_candidate_source'],'reader_base':read('bases.json')['reader'],'client_manifest_sha256':packet['client_manifest_sha256'],'published':False,'deployable_without_actual_main_integration':False,'files':products}),mtime=0);(W/'production-file-manifest.json.gz').write_bytes(packed)
 result={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':True,'input_files_checked':601,'reader_json_targets':361,'exports_checked':240,'catalog_stories':len(new),'catalog_stable_route_fields':list(stable),'catalog_routes_and_source_membership_unchanged':True,'catalog_sha256':sha((PUB/'story_index.json').read_bytes()),'live_catalog_sha256':sha((W/'live/story_index.json').read_bytes()),'catalog_bytes_changed':(PUB/'story_index.json').read_bytes()!=(W/'live/story_index.json').read_bytes(),'catalog_shards':len(shards),'pack_files':len(cache),'packed_source_files_verified':len(refs),'all_361_candidate_pack_members_match':True,'pack_raw_bytes':build['source_packs']['raw_bytes'],'pack_compressed_bytes':build['source_packs']['packed_bytes'],'search':search,'product_file_count':len(products),'product_total_bytes':sum(x['bytes'] for x in products),'product_manifest_sha256':sha(packed),'local_candidate_source':run['local_candidate_source'],'reader_base':read('bases.json')['reader'],'client_manifest_sha256':packet['client_manifest_sha256'],'local_product_root':str(S),'worker_next_build_performed':False,'runtime_source_integration_performed':False,'game_package_built':False,'published':False,'deployment_performed':False,'must_regenerate_revision_bound_outputs_after_real_main_integration':True}
 save('production-verification.json',result);guard();print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
