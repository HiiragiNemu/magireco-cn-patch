from pathlib import Path
import sys,json,gzip
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from audit import read,enc,save,sha,guard,R,P
from reader_inputs import validate_packet,preflight

guard();body=read('reader-candidates.json');exports=json.loads(gzip.decompress((W/'cumulative-reader-exports.json.gz').read_bytes()))['files'];entries=[]
for e in body['files']:
 entries.append({k:e[k] for k in ('path','source_blob','source_sha256','candidate_blob','candidate_sha256','candidate_utf8')}|{'type':'reader_scenario_json','player_path':e['player_path'],'reader_player_bytes_differ':e['candidate_blob']!=e['player_candidate_blob']})
for p,e in exports.items():entries.append({'path':p,**{k:e[k] for k in ('source_blob','source_sha256','candidate_blob','candidate_sha256','candidate_utf8')},'type':'reader_cn_text_export'})
packet={'schema':1,'kind':'reader_translation_inputs_not_deployment','client_manifest_sha256':read('ready.json')['manifest_sha256'],'reader_base':read('bases.json')['reader'],'input_count':len(entries),'json_targets':361,'txt_targets':240,'published':False,'runtime_applied':False,'files':entries,'rule':'Use Reader bytes only for Reader; client bytes remain in client-integration. Pin current remote READY before staging. Do not deploy local audit snapshot as a production commit.'}
validate_packet(packet);packed=gzip.compress(enc(packet),mtime=0);(W/'reader-input-manifest.json.gz').write_bytes(packed)
files,proof=preflight(str(R),read('bases.json')['reader'],packet);assert len(files)==601 and sum(v=='staged_only' for v in proof['states'].values())==599
for p,b in files.items():assert b==(W/'reader-inputs'/p).read_bytes()
save('reader-input-preflight.json',proof);save('reader-input-metadata.json',{'sha256':sha(packed),'bytes':len(packed),'files':len(entries),'json':361,'txt':240,'actual_changed_input_files':599,'reader_player_distinct_paths':[e['path'] for e in entries if e.get('reader_player_bytes_differ')],'current_client_manifest_sha256':packet['client_manifest_sha256'],'published':False,'runtime_applied':False});guard();print('READER_INPUTS_READY',len(entries),sha(packed))
