"""Read-only gate: a pinned candidate manifest must equal CN patch's current remote main READY.
Run before integration/build and again immediately before the client's serialized publication.
This does not replace source/ZIP/device checks and does not fetch, commit, or publish anything.
"""
import argparse,json,hashlib,re,sys
from pathlib import Path
from client_candidate_tools import git
READY='docs/story-quality/client-integration/READY.json'
CANONICAL='HiiragiNemu/magireco-cn-patch'

def validate_identity(remote_revision,ready,expected_sha,manifest_bytes):
 if not re.fullmatch('[0-9a-f]{40}',remote_revision):raise ValueError('Invalid remote main revision')
 if not re.fullmatch('[0-9a-f]{64}',expected_sha):raise ValueError('Invalid manifest SHA-256')
 if ready.get('canonical_repository')!=CANONICAL:raise ValueError('Unexpected candidate authority')
 if ready.get('manifest_sha256')!=expected_sha:raise ValueError('Superseded candidate manifest: read current remote main READY even if target count is unchanged')
 if hashlib.sha256(manifest_bytes).hexdigest()!=expected_sha:raise ValueError('Local manifest bytes do not match the pinned SHA-256')
 if not ready.get('ready_for_client_integration'):raise ValueError('Current packet is not ready for integration')
 return {'passed':True,'remote_main':remote_revision,'manifest_sha256':expected_sha,'targets':ready.get('targets'),'field_changes':ready.get('field_changes'),'publication_performed':False,'runtime_changed':False,'note':'This gate checks freshness only. Existing source, integrated-source, ZIP and device gates remain mandatory.'}

def check(repo,manifest,expected):
 origin=git(repo,'remote','get-url','origin').decode().strip().removesuffix('.git').rstrip('/')
 if origin not in ('https://github.com/'+CANONICAL,'git@github.com:'+CANONICAL):raise ValueError('Origin is not the canonical CN patch repository')
 def remote_main():
  rows=git(repo,'ls-remote','--exit-code','origin','refs/heads/main').decode().strip().splitlines()
  if len(rows)!=1:raise ValueError('Remote main is ambiguous')
  parts=rows[0].split()
  if len(parts)!=2 or parts[1]!='refs/heads/main':raise ValueError('Unexpected remote reference')
  return parts[0]
 revision=remote_main()
 try:ready=json.loads(git(repo,'show',revision+':'+READY))
 except (RuntimeError,ValueError) as exc:raise ValueError('Latest remote main is not readable locally; refresh main and rerun the gate, do not fall back to an older READY') from exc
 proof=validate_identity(revision,ready,expected,Path(manifest).read_bytes())
 if remote_main()!=revision:raise ValueError('Remote main moved during readiness check; refresh and rerun')
 return proof

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--manifest-sha256',required=True);a=p.parse_args()
 print(json.dumps(check(a.repo,a.manifest,a.manifest_sha256),ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except (ValueError,OSError,RuntimeError) as e:print('BLOCKED: '+str(e),file=sys.stderr);sys.exit(2)
