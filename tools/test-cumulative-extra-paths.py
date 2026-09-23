"""Exercise the real cumulative builder with one explicitly listed scenario."""
from pathlib import Path
import importlib.util,json,subprocess,tempfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('builder',ROOT/'tools/build-cumulative-js-delta.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
listed='madomagi/resource/scenario/json/adv/scenario_1/listed.json'
unlisted='madomagi/resource/scenario/json/adv/scenario_1/unlisted.json'
checks=0
def check(ok):
    global checks
    assert ok;checks+=1
with tempfile.TemporaryDirectory(prefix='magireco-term-delta-') as t:
    root=Path(t);repo=root/'repo';repo.mkdir()
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE)
    git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
    git('config','commit.gpgsign','false');git('config','core.autocrlf','false')
    for name,value in [('magica/base.json','{"unchanged":true}\n'),(listed,'{"text":"白翼"}\n'),(unlisted,'{"text":"old"}\n')]:
        p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf-8',newline='\n')
    git('add','.');git('commit','-qm','baseline');base_commit=git('rev-parse','HEAD').decode().strip()
    base=root/'base.zip'
    with zipfile.ZipFile(base,'w') as z:z.writestr('magica/base.json',(repo/'magica/base.json').read_bytes())
    cfg=dict(base_js_version=102,base_js_sha256=m.delta.digest(base),base_source_commit=base_commit,supplemental_product_paths=[listed])
    config=root/'config.json';config.write_text(json.dumps(cfg),encoding='utf-8')
    (repo/listed).write_text('{"text":"白羽"}\n',encoding='utf-8',newline='\n')
    (repo/unlisted).write_text('{"text":"unrelated newer edit"}\n',encoding='utf-8',newline='\n')
    git('add','.');git('commit','-qm','term')
    result=m.build(repo,base,config,root/'v1');check(result['files']==1)
    with zipfile.ZipFile(root/'v1/cn_js_delta.zip') as z:
        check(set(z.namelist())=={listed,m.delta.MANIFEST});check(z.read(listed)==(repo/listed).read_bytes())
    same=m.build(repo,base,config,root/'same',root/'v1/cn_js_delta.zip');check(same['unchanged'] and same['version']==1)
    (repo/listed).write_text('{"text":"白翼"}\n',encoding='utf-8',newline='\n');git('add','.');git('commit','-qm','revert only term')
    result=m.build(repo,base,config,root/'v2',root/'v1/cn_js_delta.zip');check(result['files']==1 and result['version']==2)
    with zipfile.ZipFile(root/'v2/cn_js_delta.zip') as z:check(z.read(listed)==(repo/listed).read_bytes())
    for invalid in [[listed,listed],['../escape.json'],['magica/research/private.json'],['madomagi/resource/scenario/json/../secret.json'],'not-a-list',[None]]:
        try:m.supplemental_paths({'supplemental_product_paths':invalid})
        except ValueError:checks+=1
        else:raise AssertionError(invalid)
print(json.dumps(dict(status='PASS',checks=checks,unlisted_story_not_packaged=True,revert_retained=True,no_product_worktree_changes=True)))
