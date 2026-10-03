"""Two-repository cumulative publication. Never rebuild or upload full baselines."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from build_delta_only import build, mirror_authority, ROOT, git, save, identity
from publish_coherent_resources import (API, SOURCE, PUBLIC, snapshot, asset_identity,
    obtain, matches, public_verify, chunk_identity, asset_map, check_monotonic)
from source_access import authenticated_source_git

PAYLOADS = ('cn_js_delta.zip','cn_js_delta_manifest.json','manifest.json')
GATES = ('version_js_delta.json',)
CHANGED = PAYLOADS + GATES
INPUTS = CHANGED + ('cn_js_update.zip','cn_scenario_update.zip','version_js.json','version_scenario.json',
                    'cn_js_update_manifest.json','cn_scenario_update_manifest.json')


def publish_all(apis, originals, folders, payload, work):
    releases, current, changed = {}, {}, []
    opened = False
    for api in apis:
        release, assets = snapshot(api)
        if asset_identity(assets) != asset_identity(originals[api.repo]):
            raise ValueError('Concurrent release changed before publication')
        check_monotonic(json.loads((folders[api.repo]/GATES[0]).read_bytes()),json.loads((payload/GATES[0]).read_bytes()))
        releases[api.repo], current[api.repo] = release, assets
    try:
        # Both repositories receive verified payloads BEFORE either version gate.
        for phase in (PAYLOADS,GATES):
            for api in apis:
                for name in phase:
                    assets = asset_map(api,releases[api.repo]); path = payload/name
                    if asset_identity(assets) != asset_identity(current[api.repo]):
                        raise ValueError('Concurrent writer during cumulative publication')
                    if matches(path,assets[name]): continue
                    changed.append((api.repo,name))
                    api.json('releases/assets/'+str(assets[name]['id']),'DELETE')
                    api.upload(releases[api.repo],path)
                    assets = asset_map(api,releases[api.repo]); current[api.repo]=assets
                    if not matches(path,assets[name]): raise ValueError('Uploaded identity mismatch: '+name)
                    if name in GATES: opened=True
                    dest=work/'anonymous'/api.repo.split('/')[-1];dest.mkdir(parents=True,exist_ok=True)
                    if getattr(api, 'private', False):
                        api.download(assets[name],dest/name)
                        if identity(dest/name) != identity(path): raise ValueError('Private source readback mismatch')
                    else:
                        public_verify(assets[name]['browser_download_url'],identity(path),dest/name)
                    save(work/'publication-progress.json',dict(changed=changed,version_gate_opened=opened))
                    print('PUBLISHED_VERIFIED',api.repo,name,flush=True)
        for api in apis:
            for n,old in originals[api.repo].items():
                if n not in CHANGED and asset_identity({n:current[api.repo][n]}) != asset_identity({n:old}):
                    raise ValueError('Unrelated asset changed: '+n)
        return dict(passed=True, changed=changed, baseline_and_unrelated_assets_unchanged=True,
                    both_payloads_verified_before_any_version_gate=True)
    except Exception:
        # A lost upload acknowledgement may still have made the gate public.
        for api in apis:
            assets=asset_map(api,releases[api.repo])
            opened |= any((api.repo,n) in changed and n in assets and matches(payload/n,assets[n]) for n in GATES)
        if opened:
            save(work/'publication-recovery.json',dict(action='ROLL_FORWARD_ONLY',changed=changed))
        else:
            for repo,name in reversed(changed):
                api=next(x for x in apis if x.repo==repo);assets=asset_map(api,releases[repo])
                if name in assets: api.json('releases/assets/'+str(assets[name]['id']),'DELETE')
                api.upload(releases[repo],folders[repo]/name)
            save(work/'publication-recovery.json',dict(action='RESTORED_BEFORE_GATE',changed=changed))
        raise


def run(work, cache=None, publish=False):
    work.mkdir(parents=True,exist_ok=True)
    token=os.environ.get('GH_TOKEN','')
    if not token: raise ValueError('Repository credential required')
    apis=[API(SOURCE,token),API(PUBLIC,token)];originals={};folders={}
    source=git(ROOT,'rev-parse','HEAD').decode().strip()
    for api in apis:
        api.private=bool(api.json('').get('private'))
        if api.repo == PUBLIC and api.private: raise ValueError('Player repository must stay public')
        release,assets=snapshot(api); originals[api.repo]=assets
        save(work/(api.repo.split('/')[-1]+'-before.json'),release|{'assets':list(assets.values())})
        folder=work/'before'/api.repo.split('/')[-1];folders[api.repo]=folder
        for n in INPUTS: obtain(api,assets[n],folder/n,cache)
    for n in INPUTS:
        if originals[SOURCE][n]['digest'] != originals[PUBLIC][n]['digest']:
            raise ValueError('Repositories disagree before cumulative build: '+n)
    folder=folders[SOURCE];payload=work/'payload'
    result=build(ROOT,source,folder/'cn_scenario_update.zip',folder/'cn_js_update.zip',folder/'cn_js_delta.zip',payload)
    chunks=json.loads((folder/'manifest.json').read_bytes())
    chunks['cn_js_delta.zip']=chunk_identity(payload/'cn_js_delta.zip',chunks.get('cn_js_delta.zip',{}).get('chunk_size',16*1024*1024))
    save(payload/'manifest.json',chunks)
    meta={n:json.loads(((payload if n in CHANGED else folder)/n).read_bytes()) for n in INPUTS if n.endswith('.json')}
    assets=dict(originals[SOURCE]); assets['cn_js_delta.zip']=dict(size=result['delta']['size'],digest='sha256:'+result['delta']['sha256'])
    mirror_authority(meta,assets)
    save(work/'prepared-report.json',result|{'mirror_current_source_validation':True})
    if publish:
        remote=git(ROOT,'ls-remote','origin','refs/heads/main').decode().split()[0]
        if remote != source: raise ValueError('Main advanced before publication; rebuild current authority')
        report=publish_all(apis,originals,folders,payload,work)
        save(work/'publication-report.json',result|report|{'publication':'PUBLISHED_VERIFIED'})
    print('DELTA_ONLY_'+('PUBLISHED' if publish else 'PREPARED'),result['delta_version'],result['delta_payload_files'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--cache',type=Path);p.add_argument('--publish',action='store_true')
    a=p.parse_args()
    with authenticated_source_git(os.environ.get('GH_TOKEN','')):
        run(a.work,a.cache,a.publish)
