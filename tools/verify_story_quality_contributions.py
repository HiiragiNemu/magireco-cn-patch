"""Independent accounting checks for a generated contribution directory; no runtime writes."""
from pathlib import Path
import json,gzip,sys,collections,hashlib,csv

def verify(root:Path):
 summary=json.loads((root/'summary.json').read_bytes());d=json.loads(gzip.decompress((root/'ledger.json.gz').read_bytes()));assert d['summary']==summary
 checks=[]
 def check(name,condition):
  assert condition,name
  checks.append(name)
 rows=d['runtime_changes'];ai=d['confirmed_ai_scripts'];done=[r for r in ai if r['complete']];pending=[r for r in ai if not r['complete']];events=d['field_change_history']
 check('runtime paths unique; source aliases never multiply totals',len(rows)==len({r['runtime_path'] for r in rows})==summary['published_unique_runtime_scripts_modified'])
 check('AI completion plus pending equals exact source-bound universe',len(ai)==len({r['reader_path'] for r in ai})==len(done)+len(pending)==summary['confirmed_ai_runtime_scripts'])
 check('all completed scripts have exact current CN and JP proof',all(r['review_evidence'] and r['review_evidence']['cn_blob']==r['current_cn_blob'] and r['review_evidence']['jp_blob']==r['current_jp_blob'] for r in done))
 check('pending has no automatic full-review grant',all(r['review_evidence'] is None and r['requires_semantic_review'] for r in pending))
 check('unindexed remainder is included not added again',sum(not r['indexed'] for r in pending)==summary['pending_unindexed_included'])
 check('pre-takeover and post-takeover completed work preserved',sum(r['completion_period']=='before_20261001_takeover' for r in done)==summary['completed_before_takeover'] and sum(r['completion_period']=='after_20261001_takeover' for r in done)==summary['completed_after_takeover'])
 check('published version history continuous including previous AI',list(range(3301,summary['last_published_scenario_version']+1))==[b['version'] for b in d['batches']])
 check('all publication receipts are successful separately from source validation',all(r['report']['status']=='published_and_anonymously_verified' for r in d['release_receipts']))
 body=[e for e in events if e['kind']=='body' and e['mode']=='text_correction']
 check('body fields deduplicated by runtime path and address',len({(e['runtime_path'],tuple(e['address'])) for e in body})==summary['published_unique_body_addresses_corrected'])
 check('body correction scripts separately deduplicated',len({e['runtime_path'] for e in body})==summary['published_unique_runtime_scripts_with_body_correction'])
 check('restoration and runtime migration not counted as original translation',all(e['version'] not in (3310,3311,3312) for e in body))
 check('all actual changes have before-after difference',all(e['before']!=e['after'] for e in events))
 legacy=d['legacy_registrations'];check('historical 498 stable IDs preserved and not semantic completion',len(legacy)==len({r['story_id'] for r in legacy})==498 and all(r['current_semantic_completion_granted_by_this_registration'] is False for r in legacy))
 check('game credits unchanged and original authorship not reassigned',summary['game_credit_ui_changed'] is False and summary['original_translation_authorship_reassigned'] is False)
 check('whole-chapter completion requires all mapped scripts',all(not r['all_mapped_scripts_confirmed_ai_and_complete'] or set(r['source_paths'])<=set(x['reader_path'] for x in done) for r in d['indexed_chapters']))
 for filename,expected in [('full-reviewed-ai-scripts.tsv',len(done)),('pending-ai-scripts.tsv',len(pending)),('processed-runtime-scripts.tsv',len(rows)),('legacy-registered-stories.tsv',498)]:
  with (root/filename).open(encoding='utf-8-sig',newline='') as f:actual=list(csv.DictReader(f,delimiter='\t'))
  check('export row count '+filename,len(actual)==expected)
 report={'passed':True,'checks':len(checks),'verified':checks,'ledger_sha256':hashlib.sha256((root/'ledger.json.gz').read_bytes()).hexdigest(),'source_summary':summary}
 (root/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('CONTRIBUTION_CHECKS_PASSED',len(checks),flush=True);return report
if __name__=='__main__':verify(Path(sys.argv[1]))
