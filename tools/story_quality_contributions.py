"""Rebuild source-bound story contribution records; never write runtime or author-credit UI.

Run with a Reader checkout, fetched patch/public Git stores, pinned revisions and an
output directory. All authoritative inputs are read from Git, not a dirty worktree.
The only writes are generated reports beneath --output. Historical applied-list
claims are retained separately from current full-scene semantic review evidence.
"""
from __future__ import annotations
import argparse,collections,csv,datetime,gzip,hashlib,io,json,re,subprocess
from pathlib import Path
from typing import Any
CN='magireco-translate-data-master/Scenarios_full/'
JP='magireco-source-master/Scenarios_full/'
BODY={'textLeft','textRight','textCenter','textAvLeft','textAvRight','textAvCenter','narration','Fnarration','fnarration','progressNarration','progressFnarration','textSelect'}
NAMES={'nameLeft','nameCenter','nameRight','nameNarration','nameFnarration'}
TAGS=re.compile(r'\[[^\[\]]*\]')
TAKEOVER='5f7cab788d32a2cc9cfe7db005be3e67fe621945'

class Git:
 def __init__(self,path:Path,bare:bool=False):
  self.prefix=['git',*(['--git-dir='+str(path)] if bare else ['-C',str(path)])]
  self.proc=subprocess.Popen(self.prefix+['cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
  self.cache={}
 def run(self,*args:str)->bytes:return subprocess.check_output(self.prefix+list(args),stderr=subprocess.PIPE,timeout=120)
 def read(self,spec:str)->bytes:
  if spec in self.cache:return self.cache[spec]
  assert self.proc.stdin and self.proc.stdout
  self.proc.stdin.write(spec.encode()+b'\n');self.proc.stdin.flush();header=self.proc.stdout.readline().split()
  if len(header)!=3:raise ValueError('Git object unavailable: '+spec)
  size=int(header[2]);data=self.proc.stdout.read(size);assert len(data)==size and self.proc.stdout.read(1)==b'\n'
  self.cache[spec]=data;return data
 def obj(self,spec:str)->Any:
  b=self.read(spec);return json.loads(gzip.decompress(b) if b.startswith(b'\x1f\x8b') else b)
 def tree(self,ref:str)->dict[str,str]:
  out={}
  for row in self.run('ls-tree','-r','-z',ref).split(b'\0'):
   if row:
    m,p=row.split(b'\t',1);out[p.decode()]=m.split()[2].decode()
  return out
 def close(self):
  if self.proc.stdin:self.proc.stdin.close()
  self.proc.wait(timeout=10)

def blob(b:bytes)->str:return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def encoded(x:Any)->bytes:return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def leaves(v:Any,address:tuple=())->dict[tuple,Any]:
 if isinstance(v,dict):return {p:x for k,a in v.items() for p,x in leaves(a,address+(k,)).items()}
 if isinstance(v,list):return {p:x for i,a in enumerate(v) for p,x in leaves(a,address+(i,)).items()}
 return {address:v}
def text_tokens(s:str)->list[str]:
 return [re.sub(r'^(\[text(?:Red|Blue|Yellow|Black):).*\]$',r'\1<text>]',x,flags=re.S) for x in TAGS.findall(s)]
def changes(a:Any,b:Any)->list[dict]:
 left,right=leaves(a),leaves(b);out=[]
 for address in sorted(left.keys()|right.keys(),key=lambda x:json.dumps(x)):
  before,after=left.get(address),right.get(address)
  if address in left and address in right and before==after:continue
  key=address[-1] if address else '';kind='body' if key in BODY else 'speaker_name' if key in NAMES else 'runtime_structure'
  out.append({'address':list(address),'before':before,'after':after,'kind':kind,'same_executable_tags':text_tokens(before)==text_tokens(after) if isinstance(before,str) and isinstance(after,str) and kind in ('body','speaker_name') else None})
 return out

def write_tsv(path:Path,rows:list[dict],columns:list[str]):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=columns,delimiter='\t',extrasaction='ignore');w.writeheader()
  for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,separators=(',',':')) if isinstance(v,(list,dict)) else v for k,v in row.items()})

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--reader',type=Path,required=True);ap.add_argument('--patch-git',type=Path,required=True);ap.add_argument('--public-git',type=Path,required=True);ap.add_argument('--reader-ref',default='HEAD');ap.add_argument('--patch-ref',default='FETCH_HEAD');ap.add_argument('--public-ref',default='FETCH_HEAD');ap.add_argument('--last-version',type=int,required=True);ap.add_argument('--census-file',type=Path);ap.add_argument('--output',type=Path,required=True)
 args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
 rg,pg,ug=Git(args.reader),Git(args.patch_git,True),Git(args.public_git,True)
 try:
  rr=rg.run('rev-parse',args.reader_ref).decode().strip();pr=pg.run('rev-parse',args.patch_ref).decode().strip();ur=ug.run('rev-parse',args.public_ref).decode().strip();rt=rg.tree(rr);pt=pg.tree(pr)
  census=json.loads(gzip.decompress(args.census_file.read_bytes())) if args.census_file else pg.obj(pr+':docs/story-quality/20261002-ai-only-census.json.gz')
  ai={x['path']:x for x in census['scripts']};proof={x['path']:x for x in census['completed_evidence']};assert len(ai)==len(census['scripts']) and all(rt.get(p)==x['current_blob'] and rt.get(x['jp_path'])==x['jp_blob'] for p,x in ai.items()),'AI ledger source drift: refresh before contribution accounting'
  assert set(proof)=={p for p,x in ai.items() if x['complete']},'Every completion requires evidence, not a scan'
  for p,e in proof.items():assert e['cn_blob']==rt[p] and e['jp_blob']==rt[e['jp_path']]
  idx=rg.obj(rr+':website/public/story_index.json');source_routes=collections.defaultdict(list);id_routes=collections.defaultdict(list)
  for story in idx:
   id_routes[str(story['id'])].append(story)
   for p in story.get('json_sources_cn',[]):source_routes[p].append(story)
  byname=collections.defaultdict(list)
  for path in rt:
   if path.startswith(CN) and path.endswith('.json'):byname[Path(path).name].append(path)
  def route_info(paths):
   seen={}
   for path in paths:
    for s in source_routes[path]:seen[s.get('source_identity') or str(s['id'])]={'story_id':str(s['id']),'title':s.get('title',''),'source_identity':s.get('source_identity'),'category':s.get('category'),'folder':s.get('folder')}
   return list(seen.values())
  receipts=[];batches=[];history=collections.defaultdict(list);ops=[];period_paths=collections.defaultdict(set);period_body=collections.defaultdict(set);period_fields=collections.defaultdict(set)
  for version in range(3301,args.last_version+1):
   receipt_path=f'story-quality/releases/{version}.json';rec=ug.obj(ur+':'+receipt_path);assert rec['version']==version and rec['status']=='published_and_anonymously_verified'
   commit=rec['cn_patch_commit'];c_tree=pg.tree(commit);parent=pg.run('rev-parse',commit+'^').decode().strip();parent_tree=pg.tree(parent)
   prior_agent=subprocess.run(rg.prefix+['merge-base','--is-ancestor',rec['reader_commit'],TAKEOVER],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode==0
   period='before_20261001_takeover' if prior_agent else 'after_20261001_takeover'
   mode='runtime_alignment' if version==3310 else 'runtime_alignment_and_name' if version==3311 else 'source_restoration' if version==3312 else 'text_correction'
   rows=rec['files'];assert len({x['path'] for x in rows})==len(rows)
   bc=collections.Counter();bodypaths=set();addresses=set();batch_index=[]
   for item in rows:
    path=item['path'];new=item['git_blob'];assert c_tree.get(path)==new,(version,path,'published source differs')
    old=item.get('before') or parent_tree.get(path);assert old is not None
    a,b=pg.read(old),pg.read(new);assert blob(a)==old and blob(b)==new and a!=b,(version,path)
    diff=changes(json.loads(a),json.loads(b));cnt=collections.Counter(d['kind'] for d in diff)
    assert sum(cnt.values())>0,(version,path)
    paths=byname[Path(path).name];info=route_info(paths);mapping='unique_filename' if len(paths)==1 else 'multiple_same_script_paths' if paths else 'no_current_reader_path'
    # Multiple references describe one runtime script, never multiple contributions.
    e={'version':version,'batch':rec['batch'],'period':period,'mode':mode,'reader_commit':rec['reader_commit'],'cn_patch_commit':commit,'receipt_path':receipt_path,'receipt_git_blob':blob(ug.read(ur+':'+receipt_path)),'verified_at':rec.get('verified_at'),'before_blob':old,'after_blob':new,'diff_counts':dict(cnt),'structural_alignment_present':bool(cnt['runtime_structure']),'source_paths':paths,'routes':info,'mapping':mapping,'published':True}
    history[path].append(e);period_paths[period].add(path);bc.update(cnt);batch_index+=info
    for d in diff:
     d={'version':version,'batch':rec['batch'],'period':period,'mode':mode,'runtime_path':path,'before_blob':old,'after_blob':new,**d};ops.append(d)
     if d['kind']=='body' and mode=='text_correction':
      bodypaths.add(path);period_body[period].add(path);addresses.add((path,tuple(d['address'])));period_fields[period].add((path,tuple(d['address'])))
   metadata={k:v for k,v in rec.items() if k not in ('files','public_assets')};receipts.append({'path':receipt_path,'git_blob':blob(ug.read(ur+':'+receipt_path)),'report':rec})
   titles={x['source_identity'] or x['story_id']:x for x in batch_index}
   batches.append({'version':version,'batch':rec['batch'],'period':period,'category':mode,'runtime_scripts_modified':len(rows),'scripts_with_body_correction':len(bodypaths),'distinct_body_addresses_this_batch':len(addresses),'raw_leaf_diff_counts':dict(bc),'reader_commit':rec['reader_commit'],'cn_patch_commit':commit,'receipt_path':receipt_path,'stories_touched':list(titles.values()),'reported_counts':metadata})
  last={p:events[-1]['after_blob'] for p,events in history.items()};assert all(pt.get(p)==sha for p,sha in last.items()),'Published scenario differs from current patch; reconcile concurrent work'
  runtime=[]
  for path,events in sorted(history.items()):
   aliases=events[-1]['source_paths'];complete=[p for p in aliases if p in proof];runtime.append({'script_id':Path(path).stem,'runtime_path':path,'reader_paths':aliases,'story_ids':sorted({s['story_id'] for e in events for s in e['routes']}),'titles':sorted({s['title'] for e in events for s in e['routes']}),'first_version':events[0]['version'],'latest_version':events[-1]['version'],'versions':[e['version'] for e in events],'periods':sorted({e['period'] for e in events}),'change_categories':sorted({e['mode'] for e in events}),'current_patch_blob':pt[path],'current_confirmed_ai_full_review':bool(complete),'completed_reader_paths':complete,'all_sources_currently_byte_equal':all(rt[p]==pt[path] for p in aliases),'events':events})
  airows=[]
  for path,x in sorted(ai.items()):
   routes=route_info([path]);sid=Path(path).stem; pp=[p for p in history if Path(p).stem==sid]
   ev=proof.get(path);evr=(ev or {}).get('evidence',{});prior=(evr.get('prior_evidence') or {})
   evidence_report=evr.get('report') or prior.get('report');evidence_commit=evr.get('source_commit') or prior.get('source_commit')
   earlier=bool(x['complete'] and (evr.get('status') in ('prior_44_bound_full_reviews','whole_scene_verified_equivalent_3312','full_review_3313')))
   airows.append({'script_id':sid,'reader_path':path,'story_ids':sorted({s['story_id'] for s in routes}),'titles':sorted({s['title'] for s in routes}),'source_identities':sorted({s['source_identity'] for s in routes if s['source_identity']}),'indexed':x['indexed'],'complete':x['complete'],'completion_period':'before_20261001_takeover' if earlier else 'after_20261001_takeover' if x['complete'] else 'pending','body_fields':x.get('body_fields'),'current_cn_blob':x['current_blob'],'current_jp_blob':x['jp_blob'],'jp_path':x['jp_path'],'machine_output_pair_count':x.get('machine_output_pair_count'),'review_evidence':ev,'evidence_report':evidence_report,'evidence_source_commit':evidence_commit,'published_change_versions':sorted({e['version'] for p in pp for e in history[p]}),'requires_semantic_review':not x['complete']})
  # Include full-read histories outside the confirmed-AI denominator without claiming authorship.
  oldcorpus=rg.obj(rr+':manifests/story_quality_corpus_20260930_07.json.gz')
  historical_full=[{'reader_path':x['path'],'script_id':x['script_id'],'kind':x['semantic_review'],'source_report':'manifests/story_quality_corpus_20260930_07.json.gz','jp_blob':x.get('jp_blob'),'reviewed_cn_blob':x.get('projected_blob') or x['git_blob'],'body_fingerprint':x.get('body_fingerprint'),'field_count':x['text_fields'],'evidence':x.get('review_evidence'),'current_confirmed_ai_completion':x['path'] in proof} for x in oldcorpus if x['semantic_review']!='not_individually_verified_in_this_audit']
  assert len(historical_full)==44
  act=rg.obj(rr+':manifests/story_quality_act2_20260930.json')
  for x in act['runtime_files']:
   historical_full.append({'reader_path':x['reader_path'],'script_id':x['id'],'version':3309,'kind':'reported_full_review_act2','source_report':'manifests/story_quality_act2_20260930.json','jp_blob':x['jp_blob'],'reviewed_cn_blob':x['after'],'field_count':sum(p[-1] in BODY for p in leaves(json.loads(rg.read(x['after'])))),'current_confirmed_ai_completion':x['reader_path'] in proof})
  batch_versions={b['batch']:b['version'] for b in batches}
  for ep in sorted(rt):
   if not ep.startswith('manifests/story_quality_') or not ep.endswith('_evidence.json.gz'):continue
   d=rg.obj(rr+':'+ep)
   if not isinstance(d,dict):continue
   plan=d.get('plan',{});version=batch_versions.get(plan.get('batch'))
   if version is None or not plan.get('reviewed_stories'):continue
   for x in plan['reviewed_stories']:
    path=x.get('cn_path') or x.get('path');assert path in rt,(ep,x.get('id'))
    historical_full.append({'reader_path':path,'script_id':x['id'],'version':version,'kind':'full_read_completed' if x.get('semantic_complete',True) else 'full_read_source_adjudication_pending','source_report':ep,'source_report_blob':rt[ep],'jp_blob':x.get('jp_sha'),'reviewed_cn_blob':x.get('cn_sha'),'field_count':x.get('fields_reviewed'),'review_note':x.get('review_note'),'current_confirmed_ai_completion':path in proof})
  registry_path='manual_retranslation/PROCESSED_STORY_TITLES.md';registry=rg.read(rr+':'+registry_path).decode();section=registry.split('### 唯一剧情 ID（498）',1)[1].split('## 问题文件与异常记录',1)[0]
  registered=re.findall(r'^- \[x\] `([^`]+)`\s*[—-]\s*(.+)$',section,re.M);assert len(registered)==len({x[0] for x in registered})==498
  legacy=[]
  for sid,title in registered:
   matches=id_routes[sid];paths=sorted({p for s in matches for p in s.get('json_sources_cn',[])})
   legacy.append({'story_id':sid,'historical_title':title,'current_titles':sorted({s.get('title','') for s in matches}),'reader_paths':paths,'current_blobs':{p:rt.get(p) for p in paths},'record_source':registry_path,'source_git_blob':rt[registry_path],'historical_claim':'applied_and_structure_checked','current_semantic_completion_granted_by_this_registration':False,'current_ai_scripts':sum(p in ai for p in paths),'current_ai_full_reviewed_scripts':sum(p in proof for p in paths),'historical_runtime_publication_proven_by_registration':False,'credit_attribution':'preserve_existing_translator_credits_not_reassign_from_git_author'})
  chapterrows=[]
  runtime_byname={Path(p).stem:p for p in history}
  for story in idx:
   paths=story.get('json_sources_cn',[]);machine=[p for p in paths if p in ai];touched={runtime_byname[Path(p).stem] for p in paths if Path(p).stem in runtime_byname}; registered_here=str(story['id']) in {x[0] for x in registered}
   if not(machine or touched or registered_here):continue
   done=[p for p in machine if p in proof]
   chapterrows.append({'story_id':str(story['id']),'title':story.get('title'),'source_identity':story.get('source_identity'),'category':story.get('category'),'folder':story.get('folder'),'total_mapped_scripts':len(set(paths)),'confirmed_ai_scripts':len(set(machine)),'confirmed_ai_completed_scripts':len(set(done)),'confirmed_ai_pending_scripts':len(set(machine)-set(done)),'all_mapped_scripts_confirmed_ai_and_complete':bool(paths) and set(paths)<=set(proof),'all_confirmed_ai_members_complete':bool(machine) and set(machine)<=set(proof),'modified_runtime_script_count':len(touched),'modified_runtime_paths':sorted(touched),'legacy_registered':registered_here,'source_paths':paths,'completion_note':'A touched subscript never makes a whole chapter complete; non-AI members keep their own authorship/provenance.'})
  incomplete=[x for x in airows if not x['complete']];complete=[x for x in airows if x['complete']]
  periods={k:{'unique_modified_runtime_scripts':len(v),'unique_body_corrected_runtime_scripts':len(period_body[k]),'unique_body_corrected_addresses':len(period_fields[k])} for k,v in period_paths.items()}
  unique_body=set.union(*period_body.values()) if period_body else set();unique_fields=set.union(*period_fields.values()) if period_fields else set()
  reader_unknown=len(census.get('reader_provenance_only',[]))+len(census.get('import_no_exact_machine_output_pair',[]))
  client_unknown=sum(x.get('status')=='extra_body_provenance_unresolved' for x in census.get('client_extra_queue',[]))
  summary={'schema':1,'reader_revision':rr,'patch_revision':pr,'public_revision':ur,'last_published_scenario_version':args.last_version,'takeover_boundary_reader_main':TAKEOVER,'confirmed_ai_runtime_scripts':len(airows),'confirmed_ai_fully_reviewed':len(complete),'confirmed_ai_pending':len(incomplete),'pending_unindexed_included':sum(not x['indexed'] for x in incomplete),'completed_before_takeover':sum(x['completion_period']=='before_20261001_takeover' for x in complete),'completed_after_takeover':sum(x['completion_period']=='after_20261001_takeover' for x in complete),'published_unique_runtime_scripts_modified':len(runtime),'published_unique_runtime_scripts_with_body_correction':len(unique_body),'published_unique_body_addresses_corrected':len(unique_fields),'published_body_correction_events':sum(x['kind']=='body' and x['mode']=='text_correction' for x in ops),'body_address_metric_is_not_newly_translated_sentence_count':True,'body_address_metric_includes_source_text_alignment_and_wording_repairs':True,'historical_body_events_with_changed_embedded_tag_sequence':sum(x['kind']=='body' and x['mode']=='text_correction' and x.get('same_executable_tags') is False for x in ops),'periods':periods,'full_read_evidence_histories_retained':len(historical_full),'legacy_applied_candidate_claim':507,'legacy_unique_registered_ids':len(legacy),'legacy_current_semantic_completion_assumed':0,'registered_list_duplicate_bullets_removed':len(re.findall(r'^- \[x\] `([^`]+)`',registry,re.M))-len(legacy),'reader_unknown_provenance':reader_unknown,'client_unknown_provenance':client_unknown,'modified_runtime_overlap_between_periods':sum(len(v) for v in period_paths.values())-len(runtime),'whole_corpus_complete':False,'game_credit_ui_changed':False,'original_translation_authorship_reassigned':False,'units_note':'Versions/events cannot be added as unique stories. Physical runtime JSON paths, indexed chapters and field addresses are distinct units. Source/TXT/player mirrors count once. Legacy applied/structural claims do not grant semantic completion or human authorship.'}
  assert len(complete)+len(incomplete)==len(airows) and summary['completed_before_takeover']+summary['completed_after_takeover']==len(complete)
  full={'schema':1,'summary':summary,'batches':batches,'runtime_changes':runtime,'field_change_history':ops,'confirmed_ai_scripts':airows,'historical_full_review_evidence':historical_full,'legacy_registrations':legacy,'indexed_chapters':chapterrows,'release_receipts':receipts,'source_provenance_queues':{'reader_new':census.get('reader_provenance_only'),'reader_no_exact_pair':census.get('import_no_exact_machine_output_pair'),'client':census.get('client_extra_queue')},'census_source':{'revision':census['source_revision'],'full_original_ledger':census}}
  (out/'summary.json').write_bytes(encoded(summary));(out/'ledger.json.gz').write_bytes(gzip.compress(encoded(full),mtime=0));(out/'batches.json').write_bytes(encoded(batches))
  write_tsv(out/'processed-runtime-scripts.tsv',runtime,['script_id','story_ids','titles','runtime_path','reader_paths','first_version','latest_version','versions','periods','change_categories','current_patch_blob','current_confirmed_ai_full_review','all_sources_currently_byte_equal'])
  ac=['script_id','story_ids','titles','reader_path','indexed','complete','completion_period','body_fields','current_cn_blob','jp_path','current_jp_blob','machine_output_pair_count','evidence_report','evidence_source_commit','published_change_versions','review_evidence']
  write_tsv(out/'full-reviewed-ai-scripts.tsv',complete,ac);write_tsv(out/'pending-ai-scripts.tsv',incomplete,ac)
  write_tsv(out/'indexed-chapters.tsv',chapterrows,['story_id','title','source_identity','category','folder','total_mapped_scripts','confirmed_ai_scripts','confirmed_ai_completed_scripts','confirmed_ai_pending_scripts','all_mapped_scripts_confirmed_ai_and_complete','all_confirmed_ai_members_complete','modified_runtime_script_count','modified_runtime_paths','legacy_registered','source_paths'])
  write_tsv(out/'legacy-registered-stories.tsv',legacy,['story_id','historical_title','current_titles','reader_paths','record_source','source_git_blob','historical_claim','current_ai_scripts','current_ai_full_reviewed_scripts','current_semantic_completion_granted_by_this_registration','historical_runtime_publication_proven_by_registration','credit_attribution'])
  lines=['# 剧情校订与累计贡献台账','',f'核定快照：玩家剧情包 **{args.last_version}**。Reader `{rr}`；CN patch `{pr}`；发行仓 `{ur}`。','',f'确认 AI／机翻来源的独立运行片段共 **{len(airows)}**，全文复核 **{len(complete)}**，尚待 **{len(incomplete)}**（已含未索引 {summary["pending_unindexed_included"]}）。完成中接手前已有 **{summary["completed_before_takeover"]}**，接手后 **{summary["completed_after_takeover"]}**；前一个 AI 的成果没有清零。','',f'自 3301 至 {args.last_version} 的已发布改动按运行 JSON 路径去重，共涉及 **{len(runtime)}** 个片段。其中存在正文校订的 **{len(unique_body)}** 个片段、**{len(unique_fields)}** 个不同字段地址；历史重复校订计 **{summary["published_body_correction_events"]}** 次操作，不能把操作次数当新句数。姓名修正、运行结构对齐和原稿恢复另列，不能都声称为原创翻译或全文复核。','', '## 固定文件与统计口径','', '`processed-runtime-scripts.tsv`：全部已发布修改的运行片段，含剧情 ID、标题、Reader 路径、首次／最近版本和累计版本；同一剧情镜像不重复计数。','', '`full-reviewed-ai-scripts.tsv` 与 `pending-ai-scripts.tsv`：逐片段完整复核／剩余清单，附当前中日文 blob、来源和复核证据。','', '`indexed-chapters.tsv`：整话与片段关系，区分触及部分片段、AI 部分完成、整话所有片段均有完整证据。','', '`batches.json`：接手前后每批发布数、原始报告口径、剧情列表和提交 SHA。`ledger.json.gz`：完整字段级前后文字、地址、历史事件、来源台账与发行回执；可用于核对实际贡献范围。','', '正文字段数是按当前JSON地址记录的显示字段修改数，并非新译句数。它也可能包含称呼、字词、文本错位归位、换行和标点修正；例如3309的102502-1_lDVQb存在台词与内嵌标签一起归位的历史记录，完整前后文字和same_executable_tags标志都已保留，不能据此声称新增了同等数量的原创翻译。','', '## 更早的历史登记同样保留','', '旧 `manual_retranslation/PROCESSED_STORY_TITLES.md` 登记 507 个候选条目、498 个唯一剧情 ID。原档不删除；本台账把 498 个 ID 全部保存在 `legacy-registered-stories.tsv`，去掉不同段落重复列举的条目。该旧档的“剩余 0”指译文写入和结构校验，不代表当前逐句质量审查已完成。不得与本台账的片段数直接相加，也不得据文件名中的“人工”重写原作者署名。','', '## 贡献署名边界','', '可据此核定维护者主导、AI 辅助的剧情校订、姓名规范、运行兼容、来源恢复与整合发布工作。原国服、官方、Wiki 和确认人工译者的原文贡献继续归原作者；本台账只记录实际新增改动与复核，不把保留的原译据为己有。具体展示署名由维护者确认，当前未修改游戏贡献 UI／APK。','', f'另有 Reader {reader_unknown} 个与客户端独有 {client_unknown} 个正文仅属于来源调查；没有把未知来源自动算为 AI、待重译或已完成。43 份既有 V4 兼容和 196 份授权中文是保全范围，不因保全而新增翻译贡献数。','', '## 接手前后批次','', '| 版本 | 阶段 | 类型 | 修改片段 | 有正文校订片段 | 正文字段地址 | 数据提交 |','|---|---|---|---:|---:|---:|---|']
  for b in batches:lines.append(f'| {b["version"]} | {"接手前" if b["period"].startswith("before") else "接手后"} | {b["category"]} | {b["runtime_scripts_modified"]} | {b["scripts_with_body_correction"]} | {b["distinct_body_addresses_this_batch"]} | `{b["reader_commit"][:10]}` |')
  lines+=['','各阶段修改片段合计需要扣除跨阶段重复：当前有 '+str(summary['modified_runtime_overlap_between_periods'])+' 个运行片段在接手前后均有改动，累计总数已经去重。','', '## 后续维护','', '每批发布并完成当前来源核对后，用 `tools/story_quality_contributions.py` 重新生成以上记录。先刷新三仓 main 和已发布版本，固定 Reader、patch、public 引用；有并行改动或中日文 blob 漂移时必须中止核算并刷新来源。不得删除历史批次，不得只改汇总数字，未发布的暂存校订单独留在当前批次交接中。','', '示例：`python tools/story_quality_contributions.py --reader . --patch-git <patch.git> --public-git <public.git> --reader-ref <SHA> --patch-ref <SHA> --public-ref <SHA> --last-version '+str(args.last_version)+' --output <staging-directory>`。生成器只读 Git、只写指定报告目录，不触碰剧情与贡献展示。','']
  lines+=['## 唯一保存位置','', '按维护者要求，累计贡献、完整已复核/待处理台账及包含这些信息的恢复包只保存在 HiiragiNemu/magireco-cn-patch。Reader 和 ProgettoMagius-1 只保留接续指针和必要的单批校订/发布证据，不提交生成目录副本，也不在ZIP内夹带台账。前一位AI和接手前的已确认贡献持续保留。','']
  (out/'README.md').write_text('\n'.join(lines),encoding='utf8');print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
 finally:rg.close();pg.close();ug.close()
if __name__=='__main__':main()
