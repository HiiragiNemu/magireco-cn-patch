"""Independent source-slice coverage and per-script remaining-count reconciliation; no runtime writes."""
from pathlib import Path
import sys,json,gzip,hashlib,collections,csv,io,datetime
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W))
from checkpoint import guard,git,enc,DEST
from sweep_contract import validate_coverage


def read(n):return json.loads((W/n).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(W/n).write_bytes(enc(v))


def main():
    guard();source=read('sweep-set.json');slice_paths=sorted((W/'sweep-reviews').glob('decisions-*.json'));parts=[json.loads(p.read_bytes()) for p in slice_paths]
    result=validate_coverage(source,parts,True);assert result['source_fields']==6372 and result['source_scripts']==276
    ledger=read('sweep-review-ledger.json');decisions=read('amendment-decisions.json');proof=read('amendment-proof.json');packet=json.loads(gzip.decompress((W/'amended-integration-manifest.json.gz').read_bytes()))
    ordered=sorted([r for p in parts for r in p['rows']],key=lambda r:r['sweep_id'])
    assert ordered==sorted(ledger['rows'],key=lambda r:r['sweep_id'])
    corrected={(r['id'],r['ordinal']):r for r in ordered if r['disposition']=='correct'}
    assert len(corrected)==len(proof)==sum(len(x) for x in decisions.values())==824
    assert result['amended_scripts']==235 and result['retained_fields']==5548
    for p in proof:
        r=corrected[p['script_id'],p['ordinal']]
        assert p['address']==r['address'] and p['japanese']==r['japanese'] and p['before']==r['prior_candidate'] and p['after']==r['after'] and p['rationale']==r['rationale']
        assert p['unchanged_imported_machine_field'] and not p['protected'] and p['machine_types']
    old=json.loads(gzip.decompress((W/'prior-unreleased-field-changes.json.gz').read_bytes()))['records'];new=read('new-field-records.json')
    assert len(old)==10402 and len(new)==824
    ops={(e['path'],tuple(a)):(b,c) for e in packet['files'] for a,b,c in e['operations']}
    assert len(ops)==sum(len(e['operations']) for e in packet['files'])==11226
    assert len({(r['player_path'],tuple(r['address'])) for r in old+new})==11226
    for r in old+new:assert ops[r['player_path'],tuple(r['address'])]==(r['before'],r['after'])
    result.update(verified_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),slice_documents=len(parts),slices={p.name:sha(p.read_bytes()) for p in slice_paths},original_sweep_sha256=sha((W/'sweep-set.json').read_bytes()),ledger_sha256=sha((W/'sweep-review-ledger.json').read_bytes()),prior_fields_preserved=10402,active_fields=11226,new_full_story_count=0,published=False)
    save('sweep-completion-validation.json',result)
    base=read('baseline-census.json');ref=read('bases.json')['patch'];expath='docs/story-quality/unreleased/20261003-semantic-batch15-ai-only-held/authority-exclusions.json';excluded=json.loads(git('patch','show',ref+':'+expath))['excluded'];ex={r['reader_path']:r for r in excluded};prepared={e['reader_path']:e for e in packet['files']}
    assert len(ex)==24 and len(prepared)==361 and not set(ex)&set(prepared)
    scope=[]
    for r in base['scripts']:
        p=r['path']
        if r['complete']:
            status='historical_published_full_review';evidence='docs/story-quality/contributions/full-reviewed-ai-scripts.tsv'
            assert p not in ex and p not in prepared
        elif p in prepared:
            status='validated_candidate_waiting_integration_and_release';evidence='docs/story-quality/client-integration/READY.json'
        elif p in ex:
            status=ex[p]['status'];evidence=expath
        else:
            raise AssertionError(('Unaccounted source-scope script',p))
        scope.append({'script_id':r['script_id'],'reader_path':p,'status':status,'evidence':evidence,'indexed':r['indexed'],'first_review_still_required':False,'new_credit_this_batch':False})
    counts=dict(collections.Counter(r['status'] for r in scope));assert len(scope)==len({r['reader_path'] for r in scope})==1079
    assert counts['historical_published_full_review']==694 and counts['validated_candidate_waiting_integration_and_release']==361 and counts['pinned_human_restoration_excluded_from_ai_retranslation']==23
    assert len(counts)==4 and sorted(counts.values())==[1,23,361,694]
    o=io.StringIO(newline='');wr=csv.DictWriter(o,fieldnames=list(scope[0]),delimiter='\t',lineterminator='\n');wr.writeheader();wr.writerows(scope);(W/'scope-status.tsv').write_bytes(o.getvalue().encode('utf8'))
    summary={'schema':1,'verified_at':result['verified_at'],'historical_source_pool':1079,'status_counts':counts,'actionable_first_review_pending':0,'identified_residual_review_pending_fields':0,'identified_residual_review_pending_scripts':0,'validated_unpublished_targets':361,'published_full_review_history_unchanged':694,'excluded_human_restored':23,'excluded_previous_full_review':1,'new_story_completions_in_this_batch':0,'current_batch_residual_fields_reviewed':6372,'current_batch_corrections':824,'current_batch_amended_targets':235,'scope_status_tsv_sha256':sha((W/'scope-status.tsv').read_bytes()),'machine_proof_does_not_include_unverified_sources':True,'whole_repository_error_free_claim':False,'source_audit':DEST+'origin-refresh-summary.json','published':False}
    save('remaining-status-summary.json',summary);guard();print('SWEEP_COMPLETION',json.dumps(result|{'slices':'see saved evidence'},ensure_ascii=False));print('REMAINING_COUNTS',json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
