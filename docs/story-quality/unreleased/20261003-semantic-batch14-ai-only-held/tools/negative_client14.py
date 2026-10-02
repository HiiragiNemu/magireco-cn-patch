"""Read existing client cache and reject stale packages/source for the current fixed candidate manifest."""
from pathlib import Path
import sys,json,subprocess,hashlib
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from checkpoint import enc,guard
from client_candidate_tools import load_packet,verify_layers,ZipLayer

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 guard();ready=json.loads((W/'client-kit/READY.json').read_bytes());m=W/'client-kit/integration-manifest.json.gz';packet=load_packet(m,ready['manifest_sha256'])
 cmd=[sys.executable,str(W/'client_candidate_tools.py'),'--manifest',str(m),'--manifest-sha256',ready['manifest_sha256'],'check-integrated','--repo','A:/StoryQuality-20260930-1739/patch.git','--ref','FETCH_HEAD']
 cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
 assert cp.returncode==2 and b'Not all candidate bytes have been integrated' in cp.stderr,(cp.returncode,cp.stderr)
 (W/'client-real-not-integrated-expected-block.json').write_bytes(enc({'manifest_sha256':ready['manifest_sha256'],'actual_exit_code':cp.returncode,'expected_exit_code':2,'stdout':cp.stdout.decode(),'stderr':cp.stderr.decode(),'passed':True,'production_changed':False}))
 cache=Path(r'D:\magia\deliveries\resource-integrity-20261002-src\.build\resume-final-20261003\public')
 paths=[cache/'cn_scenario_update.zip',cache/'cn_js_delta.zip',cache/'cn_js_update.zip'];assert all(p.is_file() for p in paths),'Existing cached packages missing; do not invent verification'
 identity=[{'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)} for p in paths]
 try:verify_layers(packet,*paths)
 except ValueError as e:
  assert 'Full Scenario failed target/preservation proof:' in str(e) or 'New reviewed target missing or outdated in JS delta:' in str(e),str(e)
  result=str(e)
 else:raise AssertionError('Cached old packages unexpectedly match new candidates; investigate rather than claim negative test')
 z=ZipLayer(paths[2]);count=sum(p.startswith('madomagi/resource/scenario/') for p in z.entries);z.close()
 (W/'current-resources-not-ready-expected-block.json').write_bytes(enc({'manifest_sha256':ready['manifest_sha256'],'cache_directory':str(cache),'actual_package_identities':identity,'expected_failure':True,'passed':True,'result':result,'full_js_story_entries':count,'reason':'This is a static negative check against existing cache, not a new download or proof of newly published packages','published':False,'actual_new_packages_tested':False}))
 guard();print('REAL_SOURCE_AND_CACHED_OLD_PACKAGES_CORRECTLY_REJECTED',result,'FULL_JS_STORY_ENTRIES',count)
if __name__=='__main__':main()
