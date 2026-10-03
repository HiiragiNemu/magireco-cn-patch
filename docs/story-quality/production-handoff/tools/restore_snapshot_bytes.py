"""Undo only archive checkout EOL conversion inside the owned isolated snapshot; verify every file against Git blobs."""
from pathlib import Path
import subprocess,json,sys
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W));from audit import read,save,sha,guard
B=W/'build-only.git';S=W/'reader-build';ref=read('candidate-snapshot.json')['local_candidate_source']
guard();assert not (W/'production-steps.json').exists(),'Restoration is only valid before generators run'
raw=subprocess.check_output(['git','--git-dir='+str(B),'ls-tree','-rz',ref]);items=[]
for line in raw.split(b'\0'):
 if not line:continue
 m,p=line.split(b'\t',1);name=p.decode();h=m.split()[2].decode()
 if (S/name).is_file():items.append((name,h))
fixed=[];checked=0
for start in range(0,len(items),400):
 batch=items[start:start+400];cp=subprocess.run(['git','--git-dir='+str(B),'cat-file','--batch'],input=''.join(h+'\n' for _,h in batch).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True);data=cp.stdout;i=0
 for name,h in batch:
  j=data.index(b'\n',i);header=data[i:j].split();assert header[0].decode()==h and header[1]==b'blob';size=int(header[2]);i=j+1;b=data[i:i+size];i+=size+1;old=(S/name).read_bytes()
  if old!=b:
   assert old.replace(b'\r\n',b'\n')==b.replace(b'\r\n',b'\n'),('Unexpected non-EOL archive transform',name)
   (S/name).write_bytes(b);fixed.append({'path':name,'archive_sha256':sha(old),'git_sha256':sha(b)})
  checked+=1
 assert i==len(data)
save('snapshot-byte-verification.json',{'checked':checked,'eol_transforms_restored':len(fixed),'changes':fixed,'only_isolated_snapshot_changed':True,'global_config_changed':False});guard();print('EXACT_BLOB_VERIFIED',checked,'EOL_RESTORED',len(fixed),flush=True)
