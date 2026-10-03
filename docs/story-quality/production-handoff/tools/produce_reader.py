"""Generate Reader data in an isolated, locally pinned candidate tree; never deploy or publish."""
from pathlib import Path, PurePosixPath
import sys,os,json,gzip,hashlib,subprocess,tarfile,datetime,time
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from audit import git,tree,read,save,sha,enc,R,PREV,guard
sys.path.insert(0,str(PREV));from exact_json import blob
S=W/'reader-build';B=W/'build-only.git'

def command(args,cwd=None,env=None,data=None):
 p=subprocess.run(args,cwd=cwd,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=180)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
 return p.stdout

def main():
 guard();assert not (W/'production-result.json').exists(),'Already generated: verify existing products instead'
 bases=read('bases.json');now=tree('reader','origin/main');frozen=tree('reader',bases['reader']);assert {p:h for p,h in now.items() if not p.startswith('docs/story-quality/') and p!='STORY_QUALITY_HANDOFF.md'}=={p:h for p,h in frozen.items() if not p.startswith('docs/story-quality/') and p!='STORY_QUALITY_HANDOFF.md'},'Production source changed; reconcile before building'
 overlays={e['path']:e for e in read('reader-candidates.json')['files']};exports=json.loads(gzip.decompress((W/'cumulative-reader-exports.json.gz').read_bytes()))['files'];assert not set(overlays)&set(exports)
 before=tree('reader',bases['reader']);inputs={}
 for p,e in {**overlays,**exports}.items():
  assert before[p]==e['source_blob'];raw=(W/'reader-inputs'/p).read_bytes();assert sha(raw)==e['candidate_sha256'] and blob(raw)==e['candidate_blob'];inputs[p]=raw
 assert len(inputs)==601
 if not (W/'candidate-snapshot.json').exists():
  if not B.exists():command(['git','init','--bare',str(B)])
  alt=B/'objects/info/alternates';alt.parent.mkdir(exist_ok=True);alt.write_bytes((str(R/'.git/objects').replace('\\','/')+'\n').encode('utf8'))
  env=os.environ.copy()|{'GIT_INDEX_FILE':str(W/'isolated-candidate.index'),'GIT_AUTHOR_NAME':'Story Production Verification','GIT_AUTHOR_EMAIL':'verification@localhost','GIT_COMMITTER_NAME':'Story Production Verification','GIT_COMMITTER_EMAIL':'verification@localhost'}
  command(['git','--git-dir='+str(B),'read-tree',bases['reader']],env=env);rows=[]
  for p,raw in inputs.items():
   h=command(['git','--git-dir='+str(B),'hash-object','-w','--stdin'],data=raw).decode().strip();rows.append(('100644 '+h+'\t'+p+'\0').encode())
  command(['git','--git-dir='+str(B),'update-index','-z','--index-info'],data=b''.join(rows),env=env);nt=command(['git','--git-dir='+str(B),'write-tree'],env=env).decode().strip();ref=command(['git','--git-dir='+str(B),'commit-tree',nt,'-p',bases['reader']],data=('LOCAL DATA VERIFICATION ONLY; client manifest '+read('ready.json')['manifest_sha256']+'; never push this build snapshot\n').encode(),env=env).decode().strip()
  command(['git','--git-dir='+str(B),'update-ref','--no-deref','HEAD',ref]);save('candidate-snapshot.json',{'reader_base':bases['reader'],'local_candidate_source':ref,'tree':nt,'source_bound_input_paths':601,'no_production_branch_or_remote_updated':True,'not_authorized_for_deployment':True,'client_manifest_sha256':read('ready.json')['manifest_sha256']})
 else:ref=read('candidate-snapshot.json')['local_candidate_source']
 if not (W/'snapshot-extraction.json').exists():
  assert not S.exists(),'Partial extraction exists; inspect instead of deleting blindly';S.mkdir()
  # No font/model/game package binaries are copied or delivered. Generators use their tracked JSON/TXT inputs.
  skipped=[];files=0;total=0
  proc=subprocess.Popen(['git','-c','core.autocrlf=false','-c','core.eol=lf','--git-dir='+str(B),'archive','--format=tar',ref],stdout=subprocess.PIPE,stderr=open(W/'snapshot-archive-stderr.log','wb'))
  with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
   for m in archive:
    if m.isdir():continue
    path=PurePosixPath(m.name);assert not path.is_absolute() and '..' not in path.parts and '\\' not in m.name and ':' not in m.name
    if not m.isfile() or path.suffix.lower() in ('.ttf','.otf','.woff','.woff2','.apk','.zip','.7z','.pyc','.exe','.dll','.pdb') or m.name.startswith(('docs/story-quality/','__pycache__/')):
     skipped.append({'path':m.name,'size':m.size});continue
    f=S.joinpath(*path.parts);f.parent.mkdir(parents=True,exist_ok=True)
    with archive.extractfile(m) as src, f.open('wb') as dst:
     while chunk:=src.read(1024*1024):dst.write(chunk)
    files+=1;total+=m.size
  assert proc.wait(timeout=120)==0;save('snapshot-extraction.json',{'files':files,'bytes':total,'skipped_nonproduction_files':skipped,'reference':ref});print('EXTRACTED',files,total,flush=True)
 for p,raw in inputs.items():assert (S/p).read_bytes()==raw,p
 env=os.environ.copy()|{'PYTHONUTF8':'1','GIT_DIR':str(B),'GIT_WORK_TREE':str(S),'SOURCE_COMMIT_SHA':ref}
 steps=[
 ('story-index',[sys.executable,'generate_story_index.py'],S),
 ('tw-metadata',[sys.executable,'tools/apply_tw_official_metadata.py'],S),
 ('voice-manifest',[sys.executable,'tools/generate_story_voice_manifest.py'],S),
 ('voice-validate',[sys.executable,'tools/generate_story_voice_manifest.py','--validate-only'],S),
 ('machine-manifest',[sys.executable,'generate_machine_translation_manifest.py','--translation-base','65f221f2aaa5a9fe161ed32e03e4dfbb93d4746d','--translation-commit','3d463befe7a10d4cb72034378ce2a6f23c377abb','--source-ref',ref],S),
 ('split-search',[sys.executable,'tools/build_split_search_indexes.py'],S),
 ('search-validate',[sys.executable,'tools/build_split_search_indexes.py','--validate-only'],S),
 ('search-chunks',[sys.executable,'../tools/search_chunk_delivery.py','materialize'],S/'website'),
 ('chunks-validate',[sys.executable,'../tools/search_chunk_delivery.py','verify-tree','--root','public'],S/'website'),
 ('json-catalog-packs',['node','--experimental-strip-types','scripts/build-story-json-catalog.ts'],S/'website'),
 ('other-text-validate',[sys.executable,'tools/verify_other_text.py','--root','website/public'],S),
 ]
 report=read('production-steps.json') if (W/'production-steps.json').exists() else {'local_candidate_source':ref,'client_manifest_sha256':read('ready.json')['manifest_sha256'],'checks':[],'published':False,'production_runtime_modified':False}
 done={x['name'] for x in report['checks'] if x['exit_code']==0}
 for name,args,cwd in steps:
  if name in done:continue
  log=W/(name+'.log');start=time.time();print('START',name,flush=True)
  with log.open('wb') as f:cp=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=480)
  record={'name':name,'args':args,'cwd_relative':str(cwd.relative_to(S)),'exit_code':cp.returncode,'seconds':round(time.time()-start,3),'log_sha256':sha(log.read_bytes())};report['checks'].append(record);save('production-steps.json',report);print('END',name,cp.returncode,flush=True)
  if cp.returncode:print(log.read_text(encoding='utf8',errors='replace')[-7000:],flush=True);raise SystemExit(cp.returncode)
 guard();report.update(passed=True,completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),full_next_worker_build_performed=False,deploy_performed=False,game_package_created=False);save('production-result.json',report)
 print('ALL_DATA_GENERATORS_PASSED',len(steps),flush=True)
if __name__=='__main__':main()
