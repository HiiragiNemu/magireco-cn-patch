"""Find residual imported-machine fields in unreleased candidates, never rewriting trusted text."""
from pathlib import Path
import sys,json,gzip,csv,io,re,collections,hashlib
W=Path(__file__).resolve().parent;R=W.parent/'repo';sys.path[:0]=[str(W),str(W.parent/'semantic-batch03-20261001')]
from initialize import git,save
from checkpoint import guard
from census import Store,display,TEXT
from audit_origins import body,IMPORT

def main():
 guard();refs=json.loads((W/'bases.json').read_bytes());rt=json.loads((W/'reader-tree.json').read_bytes());s=Store()
 kit='docs/story-quality/client-integration/';readyraw=git('patch','show',refs['patch']+':'+kit+'READY.json');ready=json.loads(readyraw);packraw=git('patch','show',refs['patch']+':'+ready['manifest']);assert hashlib.sha256(packraw).hexdigest()==ready['manifest_sha256'];packet=json.loads(gzip.decompress(packraw))
 (W/'prior-client-ready.json').write_bytes(readyraw);(W/'prior-integration-manifest.json.gz').write_bytes(packraw)
 for name in ready['files']:
  raw=git('patch','show',refs['patch']+':'+kit+name);assert hashlib.sha256(raw).hexdigest()==ready['files'][name];p=W/'client-prior'/name;p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
 pairs=collections.defaultdict(set)
 for row in csv.DictReader(io.StringIO(s.get(IMPORT+':magireco-translate-data-master/TRANSLATION_REVIEW.tsv').decode('utf-8-sig')),delimiter='\t'):
  if row.get('type') in ('text','fallback'):pairs[(row.get('japanese'),row.get('chinese'))].add(row['type'])
 regex=re.compile(r'[A-Za-z][A-Za-z\- ]{1,25}(?:chan|san|tan|桑|酱)|ZX[QN][A-Z0-9]+|存储器|内存|浮点|狂三|水菜|要桑|伊纳姆|阿智士|爱美元|爱 美元|率蛋糕|巧克力 率|是忧|忧 和|忧和|这个忧|当忧|忧@|[\ufffd]|(?:主人|前辈|姐姐|同学)死亡|死亡(?:！|。|吧)|火星|变得疯狂|下巴！|阴沟板|(?:三木|小樱)(?:桑|小姐|同学|的|先生)|(?:人生|感情|自我|心的)存储')
 rows=[];allrows=[]
 for entry in packet['files']:
  cp=entry['reader_path'];jp=cp.replace('magireco-translate-data-master/','magireco-source-master/',1);cnraw=s.get(rt[cp]);jraw=s.get(rt[jp]);c=body(json.loads(entry['candidate_utf8']));before=body(json.loads(cnraw));j=body(json.loads(jraw));ops={tuple(o[0]) for o in entry['operations']}
  for i,(a,v) in enumerate(c.items()):
   hits=regex.findall(v);pair=pairs.get((j.get(a),v));proof=before.get(a)==v and pair and a not in ops
   r={'id':entry['script_id'],'ordinal':i,'reader_path':cp,'player_path':entry['path'],'address':list(a),'jp':j.get(a),'cn':v,'machine_types':sorted(pair) if pair else [],'unchanged_imported_machine_field':bool(proof),'already_edited':a in ops,'signals':hits}
   allrows.append(r)
   if hits:rows.append(r)
 s.close();save('residual-candidate-signals.json',rows);(W/'candidate-display-field-index.json.gz').write_bytes(gzip.compress(json.dumps(allrows,ensure_ascii=False).encode(),mtime=0))
 eligible=[r for r in rows if r['unchanged_imported_machine_field']]
 save('residual-machine-eligible.json',eligible)
 print('CANDIDATE_FIELDS',len(allrows),'SIGNALS',len(rows),'SOURCE_PROVEN_UNEDITED_SIGNALS',len(eligible),'SCRIPTS',len({r['id'] for r in eligible}))
 for n,r in enumerate(eligible): print(n,r['id'],r['ordinal'],'J:',r['jp'],'| C:',r['cn'])
 guard()
if __name__=='__main__':main()
