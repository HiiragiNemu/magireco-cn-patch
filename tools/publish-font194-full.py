#!/usr/bin/env python3
"""Font-only full-JS replacement with preservation of the cumulative overlay.
Serializes with the existing JS publisher; bodies precede version identities.
"""
import copy,hashlib,importlib.util,json,os,pathlib,subprocess,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
REPO='HiiragiNemu/magireco-cn-patch';FONT='24e3b0c56d478c7b8cf972347761ad255fc253db'
WORK=ROOT/'font194-full';BACK=WORK/'previous';OUT=WORK/'payload'
for p in (BACK,OUT):p.mkdir(parents=True,exist_ok=True)
NAMES=['cn_js_update.zip','cn_js_delta.zip','cn_js_update_manifest.json','cn_js_delta_manifest.json','manifest.json','version_js.json','version_js_delta.json']
DENY={'1fe1fdc28cc7347e26099bf2fb54b85370617acd91efc6e63903cf3c33a62541','c69dea79d5b33864bbda85645641d5208790f8c394a291992e898a3753dd71d3'}

def digest(path,alg='sha256'):
    with open(path,'rb') as f:return hashlib.file_digest(f,alg).hexdigest()
def api(path,method='GET',obj=None):
    cmd=['gh','api',path]
    if method!='GET':cmd+=['--method',method]
    if obj is not None:cmd+=['--input','-']
    return json.loads(subprocess.check_output(cmd,input=None if obj is None else json.dumps(obj).encode()))
def head():return api(f'repos/{REPO}/git/ref/heads/main')['object']['sha']
def raw(path,ref):return subprocess.check_output(['gh','api',f'repos/{REPO}/contents/{path}?ref={ref}','-H','Accept: application/vnd.github.raw+json'])
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def download(name,folder):subprocess.run(['gh','release','download','latest','--repo',REPO,'--pattern',name,'--dir',str(folder),'--clobber'],check=True)
def assets():return {x['name']:x for x in api(f'repos/{REPO}/releases/tags/latest')['assets']}
def load_module(path):
    spec=importlib.util.spec_from_file_location('delta194',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    assert os.environ.get('GITHUB_REPOSITORY')==REPO
    req=json.loads((ROOT/'release-requests/font194-full.json').read_text())
    assert req=={'base_version':102,'version':103,'font_commit':FONT}
    start=head();cfg_path='configures/js-delta-baseline.json';cfg0=raw(cfg_path,start);cfg=json.loads(cfg0)
    assert cfg['base_js_version']==102 and cfg['base_js_sha256']=='c248f8d61c3344dfaa40dcfd92f4e1957ec743a114077c7a5d01c5c79cea184d'
    snapshot=assets()
    for name in NAMES:
        download(name,BACK)
        assert digest(BACK/name)==snapshot[name]['digest'].removeprefix('sha256:') and (BACK/name).stat().st_size==snapshot[name]['size'],name
    old_version=json.loads((BACK/'version_js.json').read_text());old_delta=json.loads((BACK/'version_js_delta.json').read_text())
    assert old_version['version']==102 and old_version['md5']==digest(BACK/'cn_js_update.zip','md5')
    assert old_delta['base_js_version']==102 and old_delta['md5']==digest(BACK/'cn_js_delta.zip','md5')
    assert digest(BACK/'cn_js_update.zip')==cfg['base_js_sha256']
    files={}
    for row in api(f'repos/{REPO}/contents/magica/font-licenses?ref={FONT}'):
        if row['type']=='file':files[row['path']]=raw(row['path'],FONT)
    manifest=json.loads(files['magica/font-licenses/font194-manifest.json'])
    for name,row in manifest['fonts'].items():
        files['magica/fonts/'+name]=raw('magica/fonts/'+name,FONT)
        assert hashlib.sha256(files['magica/fonts/'+name]).hexdigest()==row['sha256']
    files['magica/fonts/mbm_20160902.ttf']=files['magica/fonts/TTZhiHeiGB3-W4.ttf']
    assert len([n for n in files if n.endswith('.ttf')])==3
    changed=[];preserved=0
    with zipfile.ZipFile(BACK/'cn_js_update.zip') as old,zipfile.ZipFile(OUT/'cn_js_update.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as new:
        assert len(old.namelist())==len(set(old.namelist()));known=set(old.namelist())
        for info in old.infolist():
            data=old.read(info.filename);value=files.get(info.filename,data);new.writestr(info,value)
            if value!=data:changed.append(info.filename)
            else:preserved+=1
        for name in sorted(set(files)-known):new.writestr(name,files[name]);changed.append(name)
    assert set(changed)<=set(files)
    with zipfile.ZipFile(BACK/'cn_js_update.zip') as old,zipfile.ZipFile(OUT/'cn_js_update.zip') as new:
        assert new.testzip() is None
        for name in old.namelist():
            if name not in files:assert old.read(name)==new.read(name),name
        for name in new.namelist():
            if name.endswith(('.ttf','.otf','.woff','.woff2')):assert hashlib.sha256(new.read(name)).hexdigest() not in DENY,name
    delta=load_module(ROOT/'tools/i18n-delta-package.py')
    with zipfile.ZipFile(BACK/'cn_js_delta.zip') as dz:
        previous_manifest=json.loads(dz.read(delta.MANIFEST))
        assert previous_manifest['version']==old_delta['version'] and previous_manifest['base_js_version']==102
        previous_entries={x['path']:dz.read(x['path']) for x in previous_manifest['entries']}
        for e in previous_manifest['entries']:assert hashlib.sha256(previous_entries[e['path']]).hexdigest()==e['sha256']
        seed_manifest=copy.deepcopy(previous_manifest);seed_manifest['base_js_version']=103;seed_manifest['base_js_sha256']=digest(OUT/'cn_js_update.zip')
        with zipfile.ZipFile(WORK/'rebase-seed.zip','w') as seed:
            for info in dz.infolist():seed.writestr(info,json.dumps(seed_manifest,ensure_ascii=False,indent=2).encode() if info.filename==delta.MANIFEST else dz.read(info.filename))
    overlay={**previous_entries,**files};target=WORK/'target.zip'
    with zipfile.ZipFile(OUT/'cn_js_update.zip') as bz,zipfile.ZipFile(target,'w') as tz:
        known=set(bz.namelist())
        for info in bz.infolist():tz.writestr(info,overlay.get(info.filename,bz.read(info.filename)))
        for name in sorted(set(overlay)-known):tz.writestr(name,overlay[name])
    delta.build(OUT/'cn_js_update.zip',target,OUT/'cn_js_delta.zip',103,previous_manifest['version']+1,WORK/'rebase-seed.zip')
    with zipfile.ZipFile(OUT/'cn_js_delta.zip') as z:
        new_delta_manifest=json.loads(z.read(delta.MANIFEST));new_entries={x['path']:z.read(x['path']) for x in new_delta_manifest['entries']}
        assert set(previous_entries)<=set(new_entries)
        for name,data in previous_entries.items():
            if name not in files:assert new_entries[name]==data,'Lost previous overlay: '+name
        for name,data in files.items():assert new_entries[name]==data,'New font/notice missing: '+name
    save(OUT/'version_js.json',{'version':103,'size':(OUT/'cn_js_update.zip').stat().st_size,'md5':digest(OUT/'cn_js_update.zip','md5')})
    subprocess.run([sys.executable,'scripts/build_manifest.py','--zip',str(OUT/'cn_js_update.zip'),'--package','cn_js_update','--version','103','--out',str(OUT),'--ledger-mode','check'],check=True,cwd=ROOT)
    chunks=json.loads((BACK/'manifest.json').read_text());old_chunks=copy.deepcopy(chunks)
    for name in ['cn_js_update.zip','cn_js_delta.zip']:
        size=16777216;hashes=[]
        with (OUT/name).open('rb') as f:
            while b:=f.read(size):hashes.append(hashlib.md5(b).hexdigest())
        chunks[name]={'size':(OUT/name).stat().st_size,'chunk_size':size,'chunks':hashes}
    for name,value in old_chunks.items():
        if name not in ('cn_js_update.zip','cn_js_delta.zip'):assert chunks[name]==value
    save(OUT/'manifest.json',chunks);assert all((OUT/n).is_file() for n in NAMES)
    for meta,package in [('version_js.json','cn_js_update.zip'),('version_js_delta.json','cn_js_delta.zip')]:
        m=json.loads((OUT/meta).read_text());assert m['size']==(OUT/package).stat().st_size and m['md5']==digest(OUT/package,'md5')
    current=assets()
    for name in NAMES:assert current[name]['id']==snapshot[name]['id'] and current[name]['digest']==snapshot[name]['digest'],'Concurrent publisher: '+name
    applied=[]
    try:
        for name in NAMES:
            subprocess.run(['gh','release','upload','latest',str(OUT/name),'--repo',REPO,'--clobber'],check=True);applied.append(name)
            a=assets()[name];assert a['digest']=='sha256:'+digest(OUT/name) and a['size']==(OUT/name).stat().st_size,name
        check=WORK/'readback';check.mkdir(exist_ok=True)
        for name in NAMES:download(name,check);assert digest(check/name)==digest(OUT/name),name
        parent=head();assert raw(cfg_path,parent)==cfg0,'Concurrent full-JS baseline update'
        cfg['base_js_version']=103;cfg['base_js_sha256']=digest(OUT/'cn_js_update.zip');cfg['font194_base_overlay_commit']=FONT
        finalized_path='configures/finalized-localization-assets.json';finalized=json.loads(raw(finalized_path,parent))
        for name in ['cn_js_update.zip','cn_js_update_manifest.json','manifest.json','version_js.json']:
            finalized['files'][name]={'bytes':(OUT/name).stat().st_size,'sha256':digest(OUT/name)}
        finalized['source_commit']=FONT
        finalized['scope_approval']='Owner-approved font-only replacement. Every previous full-JS non-font member and cumulative-overlay payload is preserved. Scenario, native engine behavior, download priorities and installation markers are unchanged.'
        receipt={'status':'published','js_version':103,'delta_version':new_delta_manifest['version'],'font_commit':FONT,'nonfont_full_members_preserved':preserved,'previous_overlay_entries_preserved':len(previous_entries),'changed_full_paths':changed,'files':{n:{'size':(OUT/n).stat().st_size,'sha256':digest(OUT/n)} for n in NAMES},'device_acceptance':'pending maintainer','scenario_changed':False,'download_priority_changed':False}
        updates={cfg_path:cfg,finalized_path:finalized,'configures/manifest.json':chunks,'docs/font194-hotupdate-receipt.json':receipt}
        tree0=api(f'repos/{REPO}/git/commits/{parent}')['tree']['sha']
        tree=api(f'repos/{REPO}/git/trees','POST',{'base_tree':tree0,'tree':[{'path':p,'mode':'100644','type':'blob','content':json.dumps(v,ensure_ascii=False,indent=2)+'\n'} for p,v in updates.items()]})['sha']
        author={'name':'HiiragiNemu','email':'128921071+HiiragiNemu@users.noreply.github.com'}
        msg='fix(font): 以103完整包清除旧字体并保留累计更新层\n\n完整包只替换字体和许可；保留全部非字体成员及旧累计层，所有包回读核对后更新版本基线。\n\n文档: 附字体热更新交付记录与逐包身份。\n\nCo-authored-by: Codex <noreply@openai.com>'
        sha=api(f'repos/{REPO}/git/commits','POST',{'tree':tree,'parents':[parent],'message':msg,'author':author,'committer':author})['sha']
        api(f'repos/{REPO}/git/refs/heads/main','PATCH',{'sha':sha,'force':False})
        save(WORK/'receipt.json',dict(receipt,commit=sha));print('FONT194_FULL_AND_DELTA_PUBLISHED',json.dumps(dict(receipt,commit=sha)),flush=True)
    except Exception:
        for name in applied:subprocess.run(['gh','release','upload','latest',str(BACK/name),'--repo',REPO,'--clobber'],check=True)
        raise

if __name__=='__main__':main()
