"""Fast-forward the organization mirror from the personal authority; never reverse."""
import argparse,json,os,subprocess,sys

PERSONAL='HiiragiNemu/magireco-cn-patch'
ORGANIZATION='MagirecoCN-Revival-Project/magireco-cn-patch'
def run(args):
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(f'{args[0]} operation failed (exit {p.returncode}): {p.stderr[-1200:]}')
    return p.stdout.strip()
def decision(repository,source,current_personal,destination,is_ancestor):
    if repository!=PERSONAL:return 'SKIP_NON_AUTHORITY'
    if source!=current_personal:return 'SKIP_STALE_RUN'
    if source==destination:return 'ALREADY_CURRENT'
    if not is_ancestor:return 'HOLD_UNINTEGRATED_ORGANIZATION_COMMITS'
    return 'FAST_FORWARD'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY')!=PERSONAL:
        print(json.dumps({'status':'SKIP_NON_AUTHORITY'}));return
    source=run(['git','rev-parse','HEAD'])
    personal=run(['gh','api',f'repos/{PERSONAL}/git/ref/heads/main','--jq','.object.sha'])
    if source!=personal:
        print(json.dumps({'status':'SKIP_STALE_RUN','source':source,'personal':personal}));return
    url=f'https://github.com/{ORGANIZATION}.git'
    auth=['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential']
    run(auth+['fetch','--no-tags',url,'refs/heads/main:refs/remotes/organization/main'])
    destination=run(['git','rev-parse','refs/remotes/organization/main'])
    p=subprocess.run(['git','merge-base','--is-ancestor',destination,source])
    if p.returncode not in (0,1):raise RuntimeError('Ancestry query failed')
    status=decision(PERSONAL,source,personal,destination,p.returncode==0)
    record={'status':status,'personal':source,'organizationBefore':destination,'execute':args.execute}
    if status.startswith('HOLD_'):
        print(json.dumps(record));sys.exit(2)
    if status=='FAST_FORWARD' and args.execute:
        run(auth+['push',url,'HEAD:refs/heads/main'])
        actual=run(['gh','api',f'repos/{ORGANIZATION}/git/ref/heads/main','--jq','.object.sha'])
        if actual!=source:raise RuntimeError('Organization readback does not match personal')
        record.update(status='MIRRORED',organizationAfter=actual)
    print(json.dumps(record))
if __name__=='__main__':main()
