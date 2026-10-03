"""Verify or materialize final Reader-only JSON/TXT inputs. Never modifies a repository or publishes.
Install this alongside reader-input-manifest.json.gz, under CN patch docs/story-quality/production-handoff.
The sibling client-integration directory must contain the current authenticated input manifest and tools.
"""
from __future__ import annotations
import argparse,gzip,json,hashlib,re,sys
from pathlib import Path
KIT=Path(__file__).resolve().parent.parent/'client-integration'
if not KIT.is_dir():KIT=Path(__file__).resolve().parent/'client-kit'
sys.path.insert(0,str(KIT))
from client_candidate_tools import read_blobs,write_isolated,git,safe_path
from current_ready_gate import check as freshness_check

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def git_blob(data:bytes)->str:return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def validate_packet(packet:dict)->None:
 if packet.get('kind')!='reader_translation_inputs_not_deployment':raise ValueError('Wrong input packet kind')
 if not re.fullmatch(r'[0-9a-f]{64}',packet.get('client_manifest_sha256','')):raise ValueError('Missing pinned client manifest')
 entries=packet.get('files');seen=set()
 if not isinstance(entries,list) or not entries:raise ValueError('Missing input files')
 for e in entries:
  p=safe_path(e['path'])
  if p in seen:raise ValueError('Duplicate Reader input path')
  seen.add(p)
  if not ((p.startswith('magireco-translate-data-master/Scenarios_full/') and p.endswith(('.json','.txt'))) or (p.startswith('website/public/data/') and p.endswith('_cn.txt'))):raise ValueError('Not an authorized Chinese Reader input')
  b=e['candidate_utf8'].encode('utf8')
  if sha(b)!=e['candidate_sha256'] or git_blob(b)!=e['candidate_blob']:raise ValueError('Candidate byte identity mismatch')
  if not re.fullmatch(r'[0-9a-f]{64}',e['source_sha256']) or not re.fullmatch(r'[0-9a-f]{40}',e['source_blob']):raise ValueError('Invalid baseline identity')
  if p.endswith('.json'):
   x=json.loads(b)
   if not isinstance(x,dict) or not isinstance(x.get('story'),dict):raise ValueError('Invalid story JSON')
 if packet.get('input_count')!=len(entries):raise ValueError('Input count does not match the manifest')

def classify(raw:bytes,entry:dict)->str:
 if sha(raw)==entry['candidate_sha256'] and git_blob(raw)==entry['candidate_blob']:return 'already_integrated'
 if sha(raw)==entry['source_sha256'] and git_blob(raw)==entry['source_blob']:return 'staged_only'
 raise ValueError('Source changed in parallel; merge explicitly instead of overwriting: '+entry['path'])

def preflight(repo:str,ref:str,packet:dict,*,verify_origin:bool=True)->tuple[dict[str,bytes],dict]:
 validate_packet(packet)
 if verify_origin:
  origin=git(repo,'remote','get-url','origin').decode().strip().removesuffix('.git')
  if origin not in ('https://github.com/HiiragiNemu/magi-reader','git@github.com:HiiragiNemu/magi-reader'):raise ValueError('Expected the Reader repository, not the client repository')
 revision=git(repo,'rev-parse',ref+'^{commit}').decode().strip();source=read_blobs(repo,revision,[e['path'] for e in packet['files']]);files={};states={}
 for e in packet['files']:
  states[e['path']]=classify(source[e['path']],e);files[e['path']]=e['candidate_utf8'].encode()
 return files,{'source_revision':revision,'inputs':len(files),'states':states,'client_manifest_sha256':packet['client_manifest_sha256'],'runtime_written':False,'published':False}

def main()->None:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--manifest-sha256',required=True);p.add_argument('--patch-repo',required=True);p.add_argument('--reader-repo',required=True);p.add_argument('--ref',default='HEAD');p.add_argument('action',choices=('check-source','stage','check-integrated'));p.add_argument('--output',type=Path);a=p.parse_args()
 raw=a.manifest.read_bytes()
 if sha(raw)!=a.manifest_sha256:raise ValueError('Reader input manifest SHA mismatch')
 packet=json.loads(gzip.decompress(raw));validate_packet(packet)
 freshness=freshness_check(a.patch_repo,KIT/'integration-manifest.json.gz',packet['client_manifest_sha256'])
 files,report=preflight(a.reader_repo,a.ref,packet);report['current_client_freshness']=freshness
 if a.action=='check-integrated' and any(v!='already_integrated' for v in report['states'].values()):raise ValueError('Reader JSON/TXT inputs are not all integrated; do not deploy stale data')
 if a.action=='stage':
  if a.output is None:raise ValueError('stage requires a new output directory outside all repositories')
  files['READER_INPUT_PREFLIGHT.json']=(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode();write_isolated(files,a.output);report['isolated_output']=str(a.output.resolve())
 report['all_inputs_integrated']=all(v=='already_integrated' for v in report['states'].values());report['remaining_step']='After a reviewed Reader-main integration, regenerate catalog/search/voice/provenance/source packs from that exact commit, run full checks and independently deploy/verify Reader and ADV. This tool does not produce a deployment.'
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,OSError,RuntimeError,json.JSONDecodeError) as exc:print('BLOCKED: '+str(exc),file=sys.stderr);sys.exit(2)
