"""Exercise the exact supplied handoff CLIs on current remote Git data; isolate output, never integrate."""
from pathlib import Path
import json,sys,subprocess,hashlib,os,collections
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from audit import read,save,enc,sha,git,guard,R,P

def run(name,args,expected=0):
 cp=subprocess.run([sys.executable,*map(str,args)],cwd=W,env=os.environ.copy()|{'PYTHONUTF8':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
 (W/(name+'.stdout.log')).write_bytes(cp.stdout);(W/(name+'.stderr.log')).write_bytes(cp.stderr)
 if cp.returncode!=expected:raise RuntimeError(name+': '+cp.stderr.decode(errors='replace'))
 row={'name':name,'exit_code':cp.returncode,'expected_exit_code':expected,'stdout_sha256':sha(cp.stdout),'stderr_sha256':sha(cp.stderr)}
 return row,cp

def main():
 guard();ready=read('ready.json');meta=read('reader-input-metadata.json');steps=[];kit=W/'client-kit'
 git('patch','fetch','origin','main');p_ref=git('patch','rev-parse','FETCH_HEAD').decode().strip();git('reader','fetch','origin','main');r_ref=git('reader','rev-parse','FETCH_HEAD').decode().strip()
 q,cp=run('current-client-freshness',[kit/'current_ready_gate.py','--repo',P,'--manifest',kit/'integration-manifest.json.gz','--manifest-sha256',ready['manifest_sha256']]);steps.append(q);fresh=json.loads(cp.stdout)
 q,cp=run('client-contract-tests',['-m','unittest','discover','-s',kit,'-p','test_*.py','-v']);steps.append(q)
 client=[kit/'client_candidate_tools.py','--manifest',kit/'integration-manifest.json.gz','--manifest-sha256',ready['manifest_sha256']]
 q,cp=run('client-stage',client+['stage','--repo',P,'--ref',p_ref,'--output',W/'staged-client-delivery']);steps.append(q);client_stage=json.loads(cp.stdout)
 q,cp=run('client-not-integrated',client+['check-integrated','--repo',P,'--ref',p_ref],2);assert b'Not all candidate bytes have been integrated' in cp.stderr;steps.append(q)
 reader=[W/'reader_inputs.py','--manifest',W/'reader-input-manifest.json.gz','--manifest-sha256',meta['sha256'],'--patch-repo',P,'--reader-repo',R,'--ref',r_ref]
 q,cp=run('reader-stage',reader+['stage','--output',W/'staged-reader-delivery']);steps.append(q);reader_stage=json.loads(cp.stdout)
 q,cp=run('reader-not-integrated',reader+['check-integrated'],2);assert b'not all integrated' in cp.stderr;steps.append(q)
 save('tool-execution-proof.json',{'passed':True,'current_client_freshness':fresh,'source_refs':{'reader':r_ref,'patch':p_ref},'steps':steps,'client_staged_target_count':client_stage['target_count'],'client_state_counts':dict(collections.Counter(client_stage['states'].values())),'reader_staged_input_count':reader_stage['inputs'],'reader_state_counts':dict(collections.Counter(reader_stage['states'].values())),'client_output':str(W/'staged-client-delivery'),'reader_output':str(W/'staged-reader-delivery'),'unintegrated_sources_correctly_blocked':True,'published':False,'runtime_modified':False})
 guard();print('ACTUAL_HANDOFF_CLI_STAGE_AND_NEGATIVE_CHECKS_PASSED',len(steps))
if __name__=='__main__':main()
