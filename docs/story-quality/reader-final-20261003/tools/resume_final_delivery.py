"""Recover a completed Reader release and verify the game delta-only handoff; never publish."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime, gzip, json, subprocess, sys, urllib.request

W = Path(__file__).resolve().parent
OUT = W / 'resume-finalization-20261003'
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(W))
from integrate import R, P, run, tree, enc, sha
from verify_live import public_json, check
sys.path.insert(0, str(W / 'kit/docs/story-quality/client-integration'))
from client_candidate_tools import read_blobs
C = 'docs/story-quality/client-integration/'
H = 'docs/story-quality/production-handoff/'
D = 'docs/story-quality/reader-final-20261003/'
REV = (W / 'source-revision.txt').read_text().strip()
EXPECTED_MANIFEST = 'f4db42783439dc15e2cb94cdcc10857c5e40c8d2e020b4004891bf9e5cc258a1'

def save(name, value):
    (OUT / name).write_bytes(enc(value))

def refresh(repo):
    run(repo, 'fetch', 'origin', 'main')
    return run(repo, 'rev-parse', 'FETCH_HEAD').decode().strip()

def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Reader-Resume-Delivery-Verification', 'Accept-Encoding': 'identity'})
    with urllib.request.urlopen(req, timeout=45) as response:
        assert response.status == 200
        return {'url': url, 'status': response.status, 'data': json.load(response)}

def main():
    start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with ThreadPoolExecutor(max_workers=2) as pool:
        rf = pool.submit(refresh, R)
        pf = pool.submit(refresh, P)
        rh, ph = rf.result(), pf.result()
    rt, pt = tree(R, rh), tree(P, ph)
    get = lambda path: run(P, 'show', ph + ':' + path)
    ready_raw = get(C + 'READY.json')
    ready = json.loads(ready_raw)
    assert ready['manifest_sha256'] == EXPECTED_MANIFEST, 'Candidate generation changed: reconcile before continuing'
    policy_raw = get(ready['publication_policy_path'])
    policy = json.loads(policy_raw)
    assert sha(policy_raw) == ready['publication_policy_sha256']
    assert policy['mode'] == 'delta_only_cumulative' and not policy['publish_new_scenario'] and not policy['publish_new_full_js']
    assert policy['candidate_manifest_sha256'] == EXPECTED_MANIFEST
    current_files = read_blobs(str(P), ph, [C + n for n in ready['files']])
    for name, digest in ready['files'].items():
        assert sha(current_files[C + name]) == digest, name
    assert sha(get(C + 'integration-manifest.json.gz')) == EXPECTED_MANIFEST
    packet = json.loads(gzip.decompress(get(C + 'integration-manifest.json.gz')))
    inputs_raw = get(H + 'reader-input-manifest.json.gz')
    prod = json.loads(get(H + 'READY.json'))
    assert sha(inputs_raw) == prod['reader_input_manifest_sha256']
    inputs = json.loads(gzip.decompress(inputs_raw))
    assert len(inputs['files']) == 601 and len(packet['files']) == 361
    for item in inputs['files']:
        assert rt[item['path']][1] == item['candidate_blob'], ('Reader source drift', item['path'])
    client_states = {}
    for item in packet['files']:
        h = pt[item['path']][1]
        assert h in {item['before_blob'], item['after_blob']}, ('Client concurrent source change', item['path'])
        client_states[item['path']] = ('unchanged_target' if item['before_blob'] == item['after_blob'] else 'integrated' if h == item['after_blob'] else 'pending')
    old = json.loads((W / 'original-worktree-state.json').read_bytes())
    assert run(R, 'status', '--porcelain=v1', '-z').hex() == old['status']
    assert sha(run(R, 'diff', '--binary')) == old['diff'] and sha(run(R, 'diff', '--cached', '--binary')) == old['cached']
    prior = json.loads((W / 'final-delivery-commits.json').read_bytes())
    for path, h in prior['old_contribution_paths_preserved'].items():
        assert pt[path][1] == h, path
    receipt = json.loads(get(D + 'receipt.json'))
    assert receipt['reader_source_revision'] == REV and receipt['reader_deployment_id'].startswith('2086f41c')
    live = {p: public_json(p) for p in ['/adv-release-build.json', '/api/adv/release', '/api/proofreading/config']}
    assert all(x.get('source_revision') == REV for x in live.values())
    assert live['/api/adv/release']['deployment'] == 'https://2086f41c.magireader.pages.dev'
    plan = json.loads((W / 'online-plan.json').read_bytes())
    earlier = json.loads((W / 'online-verification.json').read_bytes())
    assert earlier['source_revision'] == REV and earlier['total'] == earlier['passed'] == 2929 and earlier['failed'] == 0
    by_path = {p['path']: p for p in plan['checks']}
    for result in earlier['results']:
        expected = by_path[result['path']]
        assert result['ok'] and result['bytes'] == expected['bytes'] and result['sha256'] == expected['sha256']
    # Repeat all target routes (including aliases), exports, catalog shards and search chunks.
    selected = [e for e in plan['checks'] if e['kind'] in {'final_reviewed_json', 'final_reviewed_export', 'index_or_manifest', 'catalog_shard', 'search_chunk'}]
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(check, e) for e in selected]
        for fut in as_completed(futures):
            results.append(fut.result())
            if len(results) % 200 == 0:
                save('live-progress.json', {'expected': len(selected), 'results': results})
                print('RECHECK', len(results), '/', len(selected), 'FAILURES', sum(not r['ok'] for r in results), flush=True)
    online = {'source_revision': REV, 'total': len(results), 'passed': sum(x['ok'] for x in results), 'failed': sum(not x['ok'] for x in results), 'retried_requests': sum(x.get('attempts', 1) > 1 for x in results), 'results': results}
    save('live-recheck.json', online)
    assert not online['failed'], [r for r in results if not r['ok']]
    assert public_json('/adv-release-build.json')['source_revision'] == REV
    # Re-run the delivered checker tests using the remote files, rather than old local copies.
    tools = OUT / 'verified-tools'
    tools.mkdir(exist_ok=True)
    required = ['delta_only_guard.py', 'test_delta_only_guard.py', 'client_candidate_tools.py', 'current_ready_gate.py', 'exact_json.py', 'translation_rules.py']
    for name in required:
        raw = get(C + name)
        assert name in ready['files'] and sha(raw) == ready['files'][name], name
        (tools / name).write_bytes(raw)
    cp = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(tools), '-p', 'test_delta_only_guard.py', '-v'], cwd=tools, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (OUT / 'delta-only-tests.log').write_bytes(cp.stdout)
    assert cp.returncode == 0 and b'Ran 21 tests' in cp.stdout and b'\nOK' in cp.stdout
    versions = [get_json('https://magireco-personal-release.pages.dev/' + name) for name in ['version_scenario.json', 'version_js.json', 'version_js_delta.json']]
    save('game-live-versions.json', versions)
    workflow = get('.github/workflows/publish-js-delta.yml').decode()
    publisher = get('tools/publish_coherent_resources.py').decode()
    save('game-publisher-audit.json', {'source_reference': ph, 'workflow_sha256': sha(workflow.encode()), 'publisher_sha256': sha(publisher.encode()), 'workflow_calls_coherent_publisher': 'publish_coherent_resources.py' in workflow, 'requires_client_delta_only_adaptation': policy['production_workflow_still_requires_client_delta_only_adaptation'], 'audit_only_no_source_changes': True})
    summary = {
        'passed': True, 'started_at': start, 'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'reader_main': rh, 'patch_main': ph, 'reader_source_revision': REV, 'reader_deployment_id': receipt['reader_deployment_id'],
        'reader_input_count': len(inputs['files']), 'reader_inputs_all_match': True,
        'rechecked_live_resources': len(results), 'rechecked_live_passed': online['passed'], 'rechecked_live_failed': online['failed'], 'rechecked_live_retries': online['retried_requests'],
        'previous_full_2929_results_preserved_and_validated': True, 'live_identity': live,
        'client_manifest_sha256': EXPECTED_MANIFEST, 'policy_sha256': sha(policy_raw), 'ready_sha256': sha(ready_raw),
        'delivered_tool_hashes_verified': len(ready['files']), 'delta_only_tests': 21,
        'client_target_states': {k: sum(s == k for s in client_states.values()) for k in set(client_states.values())},
        'client_receipt_paths': [p for p in pt if p.startswith(C + 'CLIENT_RECEIPT')],
        'game_versions': versions, 'publication_policy': policy['mode'],
        'original_worktree_preserved': True, 'old_contribution_paths_preserved': len(prior['old_contribution_paths_preserved']),
        'repeated_deployment': False, 'game_package_built_or_published': False, 'game_production_workflow_modified': False,
        'client_install_rollback_fix_still_needs_production_implementation_and_device_validation': True
    }
    save('resume-verification.json', summary)
    (OUT / 'DELTA_ONLY_HANDOFF.md').write_bytes(get(C + 'DELTA_ONLY_HANDOFF.md'))
    (OUT / 'release-policy.json').write_bytes(policy_raw)
    (OUT / 'READY.json').write_bytes(ready_raw)
    print('RESUMED_VERIFIED', json.dumps({k:v for k,v in summary.items() if k not in {'live_identity','game_versions'}}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
