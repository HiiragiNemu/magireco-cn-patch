"""Verify or materialize held evidence into a NEW isolated directory. Never apply to a live repository."""
import argparse,gzip,hashlib,json
from pathlib import Path,PurePosixPath

def inspect(raw,expected=None):
 actual=hashlib.sha256(raw).hexdigest()
 if expected and actual!=expected:raise ValueError('Recovery document checksum mismatch')
 doc=json.loads(gzip.decompress(raw))
 if doc.get('kind')!='held_translation_recovery_document_not_game_package' or doc.get('published') is not False or doc.get('release_version') is not None:raise ValueError('Not an unpublished recovery document')
 for name,item in doc['files'].items():
  p=PurePosixPath(name)
  if p.is_absolute() or '..' in p.parts or any(c in name for c in ('\\',':','\0')):raise ValueError('Unsafe relative file path')
  b=item['utf8'].encode('utf8')
  if len(b)!=item['bytes'] or hashlib.sha256(b).hexdigest()!=item['sha256']:raise ValueError('Damaged file: '+name)
 return doc,actual

def main():
 a=argparse.ArgumentParser();a.add_argument('recovery');a.add_argument('--expected-sha256');a.add_argument('--output');args=a.parse_args();doc,digest=inspect(Path(args.recovery).read_bytes(),args.expected_sha256)
 if args.output:
  out=Path(args.output).resolve()
  if out.exists():raise ValueError('Output must be a new isolated directory; no overwrites permitted')
  if any((p/'.git').exists() for p in (out,*out.parents)):raise ValueError('Refusing to materialize inside a Git working tree')
  out.mkdir(parents=True)
  for name,item in doc['files'].items():
   p=out.joinpath(*PurePosixPath(name).parts);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(item['utf8'].encode('utf8'))
  print('ISOLATED_EVIDENCE_RESTORED',out)
 print(json.dumps({'passed':True,'files':len(doc['files']),'sha256':digest,'runtime_integration_performed':False,'game_package_created':False,'published':False},ensure_ascii=False))
if __name__=='__main__':main()
