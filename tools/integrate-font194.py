#!/usr/bin/env python3
"""Apply the reviewed font-only change and submit the owner's explicit 194 build request."""
import ast, copy, json, os, pathlib, pprint, re, subprocess, sys
import yaml
PATCH='HiiragiNemu/magireco-cn-patch'
NATIVE=os.environ['NATIVE_SOURCE_REPO']
FONT='24e3b0c56d478c7b8cf972347761ad255fc253db'
NATIVE_BASE='8e1da563a6df34418a54eec6a544307f26e4c8c9'
OLD_FONT='71d3278ea246b58b4a3bc6808a01c96a4e65bdcd'
AUTHOR={'name':'HiiragiNemu','email':'128921071+HiiragiNemu@users.noreply.github.com'}
J='patch/src/main/java/io/kamihama/magianative/'
OUT=pathlib.Path('font194-integration');OUT.mkdir(exist_ok=True)

def api(path,method='GET',data=None):
    cmd=['gh','api',path]
    if method!='GET':cmd+=['--method',method]
    if data is not None:cmd+=['--input','-']
    return json.loads(subprocess.check_output(cmd,input=None if data is None else json.dumps(data).encode()))
def read(repo,path,ref):
    return subprocess.check_output(['gh','api',f'repos/{repo}/contents/{path}?ref={ref}','-H','Accept: application/vnd.github.raw+json']).decode('utf8')
def head(repo):return api(f'repos/{repo}/git/ref/heads/main')['object']['sha']
def replace_one(text,old,new):
    assert text.count(old)==1,'Expected exactly one occurrence: '+old[:100]
    return text.replace(old,new)
def commit(repo,parent,files,title):
    assert head(repo)==parent,'Concurrent main update; no force push'
    tree0=api(f'repos/{repo}/git/commits/{parent}')['tree']['sha']
    entries=[{'path':n,'mode':'100644','type':'blob','content':s} for n,s in files.items()]
    tree=api(f'repos/{repo}/git/trees','POST',{'base_tree':tree0,'tree':entries})['sha']
    message=title+'\n\n只替换字体与校验身份，原生历史载体、游戏路由、下载顺序和安装标记保持。195入口默认关闭，保留后续准备。\n\n文档: 更新字体替换、来源及实机验收说明。\n\nCo-authored-by: Codex <noreply@openai.com>'
    sha=api(f'repos/{repo}/git/commits','POST',{'tree':tree,'parents':[parent],'author':AUTHOR,'committer':AUTHOR,'message':message})['sha']
    api(f'repos/{repo}/git/refs/heads/main','PATCH',{'sha':sha,'force':False})
    return sha

CHECKER=r'''#!/usr/bin/env python3
"""Verify final APK font bytes and licenses without weakening the existing font guard."""
import argparse,hashlib,json,pathlib,subprocess,sys,tempfile,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('apk',type=pathlib.Path);a=p.parse_args()
reviewed=ROOT/'.reviewed-fonts/magica'
manifest=json.loads((reviewed/'font-licenses/font194-manifest.json').read_text(encoding='utf8'))
assert manifest['version']=='1.0.194'
old={'1fe1fdc28cc7347e26099bf2fb54b85370617acd91efc6e63903cf3c33a62541','c69dea79d5b33864bbda85645641d5208790f8c394a291992e898a3753dd71d3'}
record={'version':'1.0.194','fonts':{},'device_visual_acceptance':'pending maintainer','font_routing_changed':False,'download_priority_changed':False}
with zipfile.ZipFile(a.apk) as z,tempfile.TemporaryDirectory() as tmp:
    names=z.namelist();assert len(names)==len(set(names)),'Duplicate APK entries'
    tree=pathlib.Path(tmp)
    for name in names:
        if name.startswith('assets/fonts/') and not name.endswith('/'):
            data=z.read(name);path=tree/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        if name.lower().endswith(('.ttf','.otf','.woff','.woff2')):
            data=z.read(name);h=hashlib.sha256(data).hexdigest()
            assert h not in old,'Old proprietary font found: '+name
            for word in ['Tensentype JiaLiDaYuan','Tensentype ZhiHei','腾祥嘉丽大圆','腾祥智黑']:
                assert word.encode('utf-16-be') not in data and word.encode('utf8') not in data,'Old family metadata: '+name
            record['fonts'][name]={'sha256':h,'size':len(data)}
    for name,row in manifest['fonts'].items():
        data=z.read('assets/fonts/'+name)
        assert len(data)==row['size'] and hashlib.sha256(data).hexdigest()==row['sha256'],name
    licenses=list((reviewed/'font-licenses').iterdir());assert len(licenses)>=8
    for f in licenses:
        if f.is_file():assert z.read('assets/font-licenses/'+f.name)==f.read_bytes(),'Missing/mismatched license: '+f.name
    subprocess.run([sys.executable,str(ROOT/'tools/check-fonts.py'),'--tree',str(tree)],check=True,cwd=ROOT)
    record['all_registered_fonts_passed']=True
    record['required_supplemental_characters_per_font']=len(next(iter(manifest['fonts'].values()))['required_coverage'])
    record['license_files_verified']=len(licenses)
(ROOT/'.build/font194-apk-verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print('PASS_FINAL_APK_FONT_REPLACEMENT',json.dumps(record))
'''

def patch_workflow(source,manifest):
    workflow=yaml.safe_load(source)
    if True in workflow:workflow['on']=workflow.pop(True)
    assert set(workflow['on'])<={'workflow_dispatch','workflow_call'},'Not a manually controlled APK build'
    before=copy.deepcopy(workflow);found=installs=checks=0
    for job in workflow['jobs'].values():
        steps=job.get('steps',[])
        for s in steps:
            w=s.get('with',{})
            if w.get('path')=='.reviewed-fonts':
                assert w['ref']==OLD_FONT
                w['ref']=FONT;w['sparse-checkout']=w['sparse-checkout'].rstrip()+'\nmagica/font-licenses/\n'
                s['name']='核验并取回194补字版字体及许可';found+=1
            run=s.get('run','')
            if '.reviewed-fonts/magica/fonts/TTDaYuanGB3.ttf' in run and 'install -m' in run:
                for name,old in [('TTDaYuanGB3.ttf','b121abca3ef624104c84adf2a25de2ea2bea7cf0'),('TTZhiHeiGB3-W4.ttf','e588b7ddb4b5a1761bf94d73d732b3330d292413')]:
                    assert old in run;run=run.replace(old,manifest['fonts'][name]['gitblob'])
                run+='\nmkdir -p "${TREE}/assets/font-licenses"\ncp .reviewed-fonts/magica/font-licenses/* "${TREE}/assets/font-licenses/"\n'
                run=run.replace('固定使用 71d3278e… 已审阅补字形字体','使用194已核验的替代补字字体')
                s['run']=run;installs+=1
        index=next((i for i,s in enumerate(steps) if s.get('name')=='🔍 构建后自检'),None)
        assert index is not None
        steps.insert(index,{'name':'核验194 APK字体字节、符号与许可','run':'python3 tools/check-font194-artifact.py .build/magirecocn-legacy-client.apk'});checks+=1
    assert (found,installs,checks)==(1,1,1),(found,installs,checks)
    scrub=copy.deepcopy(workflow)
    for name,job in scrub['jobs'].items():
        now=job['steps'];old=before['jobs'][name]['steps']
        now[:]=[s for s in now if s.get('name')!='核验194 APK字体字节、符号与许可'];assert len(now)==len(old)
        for i,(x,y) in enumerate(zip(now,old)):
            if x!=y:
                assert y.get('with',{}).get('path')=='.reviewed-fonts' or ('.reviewed-fonts/magica/fonts/TTDaYuanGB3.ttf' in y.get('run','') and 'install -m' in y.get('run',''))
                now[i]=y
    assert scrub==before,'Unrelated workflow behavior changed'
    return yaml.safe_dump(workflow,allow_unicode=True,sort_keys=False,width=120)

def main():
    assert os.environ.get('GITHUB_REPOSITORY')==PATCH
    request=json.loads(pathlib.Path('release-requests/font194.json').read_text())
    assert request=={'version':'1.0.194','font_commit':FONT,'native_base':NATIVE_BASE,'dispatch':True}
    patch_head=head(PATCH)
    cfg=json.loads(read(PATCH,'configures/personal-online-config.json',patch_head));assert cfg['client']['version']=='1.0.193'
    manifest=json.loads(read(PATCH,'magica/font-licenses/font194-manifest.json',FONT));assert manifest['version']=='1.0.194'
    assert manifest['fonts']['TTDaYuanGB3.ttf']['sha256']=='a6adbd53d4d061c54a210194d800fafd989f656a6bd5334843fc069c08ed8f48'
    assert manifest['fonts']['TTZhiHeiGB3-W4.ttf']['sha256']=='fa0710a050e8c0c73623d482be4d25a4aed23a8d2fb6056fad79fd98de22289e'
    for row in manifest['fonts'].values():assert len(row['required_coverage'])==54 and row['existing_outlines_unchanged']>10000
    assert head(NATIVE)==NATIVE_BASE,'Native main advanced; reconcile rather than overwrite'
    public_path='.github/workflows/build-personal-client.yml'
    public_original=read(PATCH,public_path,patch_head);public_workflow=patch_workflow(public_original,manifest)
    files={}
    n='magia-native/src/MagiaLegacy.cpp';old=read(NATIVE,n,NATIVE_BASE)
    files[n]=replace_one(old,'static constexpr char CLIENT_VERSION[] = "1.0.193";','static constexpr char CLIENT_VERSION[] = "1.0.194";')
    n=J+'CNPublicResources.java';old=read(NATIVE,n,NATIVE_BASE)
    files[n]=replace_one(old,'final class CNPublicResources {','final class CNPublicResources {\n    // 194只发布字体；195迁移入口保持关闭，后续独立启用并验收。\n    static final boolean ENABLED = false;')
    n=J+'CNUpdateSources.java';old=read(NATIVE,n,NATIVE_BASE)
    for statement in ['add(available, CNPublicResources.RELEASE_BASE, "公开资源仓备用");','add(out, CNPublicResources.RELEASE_BASE, "独立公开资源更新源");','urls.add(CNPublicResources.CONFIG_URL);']:
        old=replace_one(old,statement,'if (CNPublicResources.ENABLED) '+statement)
    files[n]=old
    n='tools/check-fonts.py';old=read(NATIVE,n,NATIVE_BASE);tree=ast.parse(old)
    assignments={node.targets[0].id:node for node in tree.body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)}
    expected=ast.literal_eval(assignments['EXPECTED'].value);required=ast.literal_eval(assignments['REQUIRED_GLYPHS'].value);historical=copy.deepcopy(expected)
    for name,row in manifest['fonts'].items():
        expected[name]=(row['size'],'sha256:'+row['sha256'],row['family'],'194 '+row['source']+' 同名补字替换；原版已有轮廓与度量不变')
        required[name]={int(cp[2:],16):chr(int(cp[2:],16)) for cp in row['required_coverage']}
    for name in set(expected)-set(manifest['fonts']):assert expected[name]==historical[name]
    lines=old.splitlines(keepends=True)
    for key,value in sorted([('EXPECTED',expected),('REQUIRED_GLYPHS',required)],key=lambda kv:assignments[kv[0]].lineno,reverse=True):
        node=assignments[key];lines[node.lineno-1:node.end_lineno]=[key+' = '+pprint.pformat(value,width=110,sort_dicts=False)+'\n']
    old=''.join(lines)
    old=re.sub(r'(?s)\A(#!/[^\n]*\n)""".*?"""',r'\1"""验证194替代补字字体；原生历史载体和路由约束保持不变。"""',old,count=1)
    old=old.replace('原生旧请求使用 6095180 前的 MagiReco CN Medium；Web 字体与 reviewed 补字保持不变。','原生旧请求保持历史载体；两份TT别名必须是194替代补字版。')
    old=old.replace('reviewed 字体内容来自固定提交 71d3278e…，不得临时换回原始缺字形版本。','替代字体来源固定于194审核提交，54项必需字符不可回退。')
    old=old.replace('原生历史载体及 reviewed 补字内容身份均相符','原生历史载体及194替代补字身份均相符');files[n]=old
    n='.github/workflows/build-apk.yml';files[n]=patch_workflow(read(NATIVE,n,NATIVE_BASE),manifest)
    files['tools/check-font194-artifact.py']=CHECKER
    files['docs/font-replacement-194.md']='# 1.0.194 字体发行\n\n以193为基线，仅同名替换两份字体。寒蝉全圆Bold补15项，MiSans Semibold补48项；覆盖旧版49项补字及七种音乐符号，保留替代原版已有轮廓、字宽和垂直度量。Web的智黑别名副本同步替换。\n\n原生MTF4a5kp与mbm历史载体保持原字节，不改变剧情/UI路由、技能标题框高、下载布局、线路优先级、存档及安装标记。195公开入口代码默认关闭，后续独立启用。\n\n打包时从固定资源提交获取字体和所有许可；签名后再次核验字体身份、符号及旧字体残留。替代修改详情和上游版权在APK assets/font-licenses/及Web magica/font-licenses/中。MiSans补字版非小米官方原版，不声称已经取得额外修改许可。\n\n游戏内显示由维护者验收；未知私用字U+F6DB不伪造字义或轮廓。\n'
    n='tools/test-public-resource-fallback.py';old=read(NATIVE,n,NATIVE_BASE)
    old=replace_one(old,'            shutil.copyfile(SOURCE/name,root/name)','''            content=(SOURCE/name).read_text(encoding='utf8')
            if name=='CNPublicResources.java':
                assert 'static final boolean ENABLED = false;' in content
                content=content.replace('static final boolean ENABLED = false;','static final boolean ENABLED = true;')
            (root/name).write_text(content,encoding='utf8')''');files[n]=old
    files['tools/test-font194-scope.py']='''#!/usr/bin/env python3
from pathlib import Path
import subprocess
r=Path(__file__).resolve().parents[1]
j=r/'patch/src/main/java/io/kamihama/magianative'
assert 'static final boolean ENABLED = false;' in (j/'CNPublicResources.java').read_text()
s=(j/'CNUpdateSources.java').read_text()
assert s.count('if (CNPublicResources.ENABLED)')==3
assert 'static constexpr char CLIENT_VERSION[] = "1.0.194";' in (r/'magia-native/src/MagiaLegacy.cpp').read_text()
print('PASS194_SCOPE: only font release; 195 independent publishers disabled')
subprocess.run(['python3',str(r/'tools/test-public-resource-fallback.py')],check=True)
'''
    for path,content in files.items():
        if path.endswith('.py'):compile(content,path,'exec')
    local=OUT/'native';local.mkdir(exist_ok=True)
    for path in ['tools/test-font194-scope.py','tools/test-public-resource-fallback.py',J+'CNPublicResources.java',J+'CNUpdateSources.java','magia-native/src/MagiaLegacy.cpp']:
        p=local/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(files[path],encoding='utf8')
    subprocess.run([sys.executable,str(local/'tools/test-font194-scope.py')],check=True)
    source_commit=commit(NATIVE,NATIVE_BASE,files,'fix(font): 发布194替代补字字体并隔离195入口')
    (OUT/'source.json').write_text(json.dumps({'source_commit':source_commit,'font_commit':FONT}))
    patch_head=head(PATCH);assert read(PATCH,public_path,patch_head)==public_original,'Concurrent workflow change'
    patch_files={public_path:public_workflow,'docs/font194-build.json':json.dumps({'version':'1.0.194','source_commit':source_commit,'font_commit':FONT,'scope':'fonts only; 195 disabled','device_acceptance':'pending'},indent=2)+'\n'}
    workflow_commit=commit(PATCH,patch_head,patch_files,'build(font): 锁定194字体身份并在签名后复核产物')
    assert head(NATIVE)==source_commit
    assert json.loads(read(PATCH,'configures/personal-online-config.json',head(PATCH)))['client']['version']=='1.0.193'
    subprocess.run(['gh','workflow','run','build-personal-client.yml','--repo',PATCH,'--ref','main','-f','source_sha='+source_commit,'-f','client_version=1.0.194','-f','engine=self','-f','debug_overlay=false'],check=True)
    record={'status':'build_requested','client_version':'1.0.194','source_commit':source_commit,'workflow_commit':workflow_commit,'font_commit':FONT,'publication':'pending existing verification workflow'}
    (OUT/'request.json').write_text(json.dumps(record,indent=2)+'\n')
    print('FONT194_BUILD_REQUESTED',json.dumps(record))

if __name__=='__main__':main()
