"""Independent verification of actual final-main data and deployable source-pack members."""
from pathlib import Path
import sys,json,gzip,hashlib,collections,datetime,urllib.request
W=Path(__file__).resolve().parent;S=W/'reader';PUB=S/'website/.pages-deploy';REV=(W/'source-revision.txt').read_text().strip();sys.path.insert(0,str(W));from integrate import save,sha,run
packet=json.loads(gzip.decompress((W/'kit/docs/story-quality/production-handoff/reader-input-manifest.json.gz').read_bytes()))
assert json.loads((W/'build-success.json').read_bytes())['passed']
for e in packet['files']:assert sha((S/e['path']).read_bytes())==e['candidate_sha256'],e['path']
index=json.loads((PUB/'story_index.json').read_bytes())
# The checked-in catalogue omits an already-live 103105 section; compare the actual pre-deploy production catalogue, not that stale generated file.
old=(W/'live-index-before-deploy.json').read_bytes();oldidx=json.loads(old)
assert (PUB/'story_index.json').read_bytes()==old and index==oldidx and len(index)==3054
mapping=collections.defaultdict(list)
for st in index:
 for lang in ['cn','jp']:
  for i,p in enumerate(st.get('json_sources_'+lang,[])):mapping[p].append('/api/story-json/'+str(st['id'])+'/'+lang+'/'+str(i))
targets={e['path']:e for e in packet['files'] if e['path'].endswith('.json')};assert len(targets)==361 and all(mapping[p] for p in targets)
refs={};shards=list((PUB/'story-json-catalog/v1').glob('*.json'))
for f in shards:
 d=json.loads(f.read_bytes());assert d['source_revision']==REV
 for p,r in d['source_packs'].items():
  if p in refs:assert refs[p]==r
  refs[p]=r
cache={};checked=[]
for p,r in refs.items():
 asset=r['asset'];f=PUB/asset.lstrip('/')
 if asset not in cache:
  cache[asset]=f.read_bytes();assert len(cache[asset])==r['pack_length'] and f.stem==sha(cache[asset])
 compressed=cache[asset][r['offset']:r['offset']+r['length']];assert sha(compressed)==r['compressed_sha256'];raw=gzip.decompress(compressed)
 assert sha(raw)==r['sha256'] and len(raw)==r['raw_length'] and raw==(S/p).read_bytes(),p
 if p in targets:
  assert sha(raw)==targets[p]['candidate_sha256'];checked.append({'path':p,'routes':mapping[p],'sha256':sha(raw),'pack':asset})
assert len(checked)==361
save('all-target-source-pack-checks.json',checked)
search={}
for scope in ['magireco','exedra']:
 m=json.loads((PUB/f'search_index_manifest.{scope}.json').read_bytes());payload=(S/f'artifacts/search-split/search_content.{scope}.json').read_bytes();assert sha(payload)==m['sha256'] and len(payload)==m['bytes'] and len(json.loads(payload))==m['entries'];assert m['story_index_sha256']==sha((PUB/'story_index.json').read_bytes())
 search[scope]={'entries':m['entries'],'chunks':len(m['chunks']),'sha256':m['sha256']}
build=json.loads((PUB/'adv-release-build.json').read_bytes());assert build['source_revision']==REV and len(refs)==build['source_packs']['files']
# Only a deployment content manifest, not a duplicate contribution ledger.
products=[]
for f in PUB.rglob('*'):
 if f.is_file():products.append({'path':f.relative_to(PUB).as_posix(),'sha256':sha(f.read_bytes()),'bytes':f.stat().st_size})
(W/'deployment-file-hashes.json.gz').write_bytes(gzip.compress(json.dumps({'source_revision':REV,'files':products},ensure_ascii=False).encode(),mtime=0))
result={'passed':True,'source_revision':REV,'input_files':601,'target_json':361,'txt_exports':240,'catalog_stories':len(index),'catalog_unchanged':True,'catalog_sha256':sha((PUB/'story_index.json').read_bytes()),'catalog_shards':len(shards),'source_pack_files':len(cache),'packed_source_members_checked':len(refs),'all_final_targets_match':True,'search':search,'deployment_asset_count':len(products),'worker_present':(PUB/'_worker.js').is_file(),'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
save('data-verification.json',result);print('DATA_VERIFIED',json.dumps(result,ensure_ascii=False),flush=True)
