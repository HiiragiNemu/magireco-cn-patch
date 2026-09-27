#!/usr/bin/env python3
"""Prepare bounded 195 trees; branch publication is performed by the maintainer.

A rerun after BOTH prepared commits have been fast-forwarded dispatches the
existing explicitly authorized client build once. No resource/CF deployment.
"""
import ast
import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import pprint
import re
import shutil
import subprocess
import sys
import zipfile
import yaml
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

REPO = 'HiiragiNemu/magireco-cn-patch'
SOURCE = 'HiiragiNemu/magirecocn-legacy-client'
BASE = '3f2ff638579f25200303fe648a68610829a037a2'
FONT = '24e3b0c56d478c7b8cf972347761ad255fc253db'
ROUND = 'a6adbd53d4d061c54a210194d800fafd989f656a6bd5334843fc069c08ed8f48'
OLD_APK = '505af4ff313f4180e7aff3ab08ab78ca17a4beaa0100884562c091f02a10c769'
ROOT = Path.cwd()
SRC = ROOT/'.native'
REVIEW = SRC/'.reviewed-fonts'
OUT = ROOT/'font195-evidence'
OUT.mkdir(exist_ok=True)

def api(path, data=None, method=None):
    cmd = ['gh', 'api', path]
    if data is not None:
        cmd += ['--method', method or 'POST', '--input', '-']
    p = subprocess.run(cmd, input=json.dumps(data) if data is not None else None,
                       text=True, capture_output=True, check=True)
    return json.loads(p.stdout) if p.stdout.strip() else None

def ref(repo):
    return api(f'repos/{repo}/git/ref/heads/main')['object']['sha']

def text(repo, path, commit):
    row = api(f'repos/{repo}/contents/{path}?ref={commit}')
    assert row['encoding'] == 'base64', path
    return base64.b64decode(row['content']).decode('utf8')

def replace_once(s, old, new):
    assert s.count(old) == 1, ('Unexpected replacement count', old, s.count(old))
    return s.replace(old, new, 1)

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')

def edit_workflow(raw, personal):
    doc = yaml.safe_load(raw)
    if True in doc:
        doc['on'] = doc.pop(True)
    before = copy.deepcopy(doc)
    steps = doc['jobs']['build']['steps']
    replaced = 0
    checked = 0
    for step in steps:
        run = step.get('run', '')
        if 'install -m 0644 assets/fonts/mbm_20160902.ttf' in run:
            assert run.count('install -m 0644 assets/fonts/mbm_20160902.ttf') == 2
            run = run.replace('install -m 0644 assets/fonts/mbm_20160902.ttf',
                              'install -m 0644 .reviewed-fonts/magica/fonts/TTDaYuanGB3.ttf')
            run += '\ncmp "${TREE}/assets/fonts/TTDaYuanGB3.ttf" "${TREE}/assets/fonts/MTF4a5kp.ttf"\ncmp "${TREE}/assets/fonts/TTDaYuanGB3.ttf" "${TREE}/assets/fonts/mbm_20160902.ttf"\n'
            step['run'] = run
            replaced += 1
        if 'tools/check-font194-artifact.py' in run:
            step['run'] = run.replace('tools/check-font194-artifact.py', 'tools/check-font195-artifact.py')
            step['name'] = '核验195实际原生圆体别名、符号与许可'
            checked += 1
        if personal and step.get('uses', '').startswith('actions/upload-artifact@'):
            if step.get('with', {}).get('name') == 'personal-native-main-verified':
                step['with']['path'] += '\n.build/font195-apk-verification.json'
    assert replaced == 1 and checked == 1, (replaced, checked)
    # All job policy, triggers and unrelated steps remain semantically identical.
    approved = set()
    for i, (old, new) in enumerate(zip(before['jobs']['build']['steps'], steps)):
        if old != new:
            assert ('install -m 0644 assets/fonts/mbm_20160902.ttf' in old.get('run','')
                    or 'tools/check-font194-artifact.py' in old.get('run','')
                    or (personal and old.get('with',{}).get('name') == 'personal-native-main-verified'))
            approved.add(i)
    review = copy.deepcopy(doc)
    review['jobs']['build']['steps'] = before['jobs']['build']['steps']
    assert review == before
    assert len(approved) == (3 if personal else 2)
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120)

def commit_candidate(repo, parent, files, message):
    entries = []
    for path, data in files.items():
        if isinstance(data, str):
            data = data.encode('utf8')
        blob = api(f'repos/{repo}/git/blobs', dict(content=base64.b64encode(data).decode(), encoding='base64'))
        entries.append(dict(path=path, mode='100644', type='blob', sha=blob['sha']))
    old = api(f'repos/{repo}/git/commits/{parent}')
    tree = api(f'repos/{repo}/git/trees', dict(base_tree=old['tree']['sha'], tree=entries))
    author = dict(name='HiiragiNemu', email='128921071+HiiragiNemu@users.noreply.github.com')
    commit = api(f'repos/{repo}/git/commits', dict(message=message, tree=tree['sha'], parents=[parent], author=author, committer=author))
    return commit['sha']

def main():
    assert os.environ['GITHUB_REPOSITORY'] == REPO
    live_source, live_patch = ref(SOURCE), ref(REPO)
    if live_source != BASE:
        # This path only runs after explicit branch fast-forwards; it never writes refs.
        receipt = json.loads(text(REPO, 'docs/font195-build.json', live_patch))
        assert receipt['version'] == '1.0.195' and receipt['source_commit'] == live_source
        assert receipt['font_commit'] == FONT and receipt['migration_release'] == '1.0.196'
        cfg = json.loads(text(REPO, 'configures/personal-online-config.json', live_patch))
        if cfg['client']['version'] == '1.0.195':
            print('ALREADY_PUBLISHED_195'); return
        assert cfg['client']['version'] == '1.0.194', 'Unexpected live version; do not race another publisher'
        runs = api(f'repos/{REPO}/actions/workflows/build-personal-client.yml/runs?head_sha={live_patch}&per_page=10')['workflow_runs']
        assert not any(r['event']=='workflow_dispatch' for r in runs), 'Build already requested; inspect existing run'
        api(f'repos/{REPO}/actions/workflows/build-personal-client.yml/dispatches',
            dict(ref='main', inputs=dict(source_sha=live_source, client_version='1.0.195', engine='self', debug_overlay='false')))
        dump(OUT/'dispatch.json', dict(status='dispatched', version='1.0.195', source_commit=live_source, workflow_commit=live_patch))
        print('DISPATCHED_EXISTING_195_BUILD', live_source, live_patch)
        return
    assert live_patch == os.environ['GITHUB_SHA'], 'Patch main advanced; re-review before preparing'
    assert subprocess.check_output(['git','-C',str(SRC),'rev-parse','HEAD'], text=True).strip() == BASE
    round_data = (REVIEW/'magica/fonts/TTDaYuanGB3.ttf').read_bytes()
    assert hashlib.sha256(round_data).hexdigest() == ROUND
    manifest = json.loads((REVIEW/'magica/font-licenses/font194-manifest.json').read_text(encoding='utf8'))
    font = TTFont(io.BytesIO(round_data)); glyphs=font.getGlyphSet(); cmap=font.getBestCmap()
    required = manifest['fonts']['TTDaYuanGB3.ttf']['required_coverage']
    assert len(required) == 54
    for cp in required:
        name = cmap[int(cp[2:],16)]; pen=BoundsPen(glyphs);glyphs[name].draw(pen)
        assert pen.bounds and pen.bounds[0]<pen.bounds[2] and pen.bounds[1]<pen.bounds[3], cp
    font.close()
    native_path = SRC/'magia-native/src/MagiaLegacy.cpp'
    native_before = native_path.read_text(encoding='utf8')
    native = replace_once(native_before, 'static constexpr char CLIENT_VERSION[] = "1.0.194";',
                          'static constexpr char CLIENT_VERSION[] = "1.0.195";')
    native = replace_once(native, '// APK 的 MTF4a5kp / mbm 资源分别承载 reviewed 智黑 / 大圆；Cocos 原样加载。',
                          '// 195：MTF4a5kp / mbm 两个原生文件别名均承载已补字寒蝉全圆 Bold；Cocos 原样加载。')
    native_path.write_text(native, encoding='utf8')
    guard_path = SRC/'tools/check-fonts.py'; guard=guard_path.read_text(encoding='utf8')
    node = next(n for n in ast.parse(guard).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='EXPECTED')
    expected = ast.literal_eval(node.value)
    for name in ('MTF4a5kp.ttf','mbm_20160902.ttf'):
        expected[name] = (len(round_data), 'sha256:'+ROUND, 'Magius Round Symbols', '195：原生同名入口使用已补字寒蝉全圆Bold，不改路由及布局')
    lines=guard.splitlines(keepends=True)
    guard=''.join(lines[:node.lineno-1])+'EXPECTED = '+pprint.pformat(expected,sort_dicts=False)+'\n'+''.join(lines[node.end_lineno:])
    pos=guard.index('\nNATIVE_SRC = ')
    guard=guard[:pos]+"\n# Both native aliases must retain the same 54-character contract as the round font.\nfor _alias in ('MTF4a5kp.ttf', 'mbm_20160902.ttf'):\n    REQUIRED_GLYPHS[_alias] = dict(REQUIRED_GLYPHS['TTDaYuanGB3.ttf'])\n"+guard[pos:]
    guard=guard.replace('验证194替代补字字体；原生历史载体和路由约束保持不变。','验证195原生圆体别名和194补字字体；路由及布局约束不变。')
    guard=guard.replace('原生旧请求保持历史载体；两份TT别名必须是194替代补字版。','原生MTF/mbm必须等于寒蝉全圆Bold补字版；Web黑体保持MiSans。')
    guard=guard.replace('原生历史载体及194替代补字身份均相符','195原生圆体别名及194替代补字身份均相符')
    guard_path.write_text(guard, encoding='utf8')
    (SRC/'assets/fonts/mbm_20160902.ttf').write_bytes(round_data)
    shutil.copyfile(ROOT/'tools/check-font195-artifact.py', SRC/'tools/check-font195-artifact.py')
    workflow_path = SRC/'.github/workflows/build-apk.yml'
    workflow_path.write_text(edit_workflow(workflow_path.read_text(encoding='utf8'),False),encoding='utf8')
    public_path=SRC/'patch/src/main/java/io/kamihama/magianative/CNPublicResources.java'
    public=public_path.read_text(encoding='utf8')
    assert 'static final boolean ENABLED = false;' in public
    public=replace_once(public,'// 194只发布字体；195迁移入口保持关闭，后续独立启用并验收。',
                        '// 194/195只处理字体；196迁移入口保持关闭，后续独立启用并验收。')
    public_path.write_text(public,encoding='utf8')
    doc='''# 1.0.195 原生圆体同名替换\n\n由维护者明确指定：APK assets/fonts/MTF4a5kp.ttf 与 assets/fonts/mbm_20160902.ttf 均使用194已审核寒蝉全圆Bold补字文件，外部文件名不变。TTDaYuan同内容，TTZhiHei及Web字体仍为194的MiSans补字版。\n\n不新增字体钩子，不按场景分流，不改字号、框高或行高；所有请求这两个原生别名的调用点（含共用的非剧情入口）都会使用圆体。保留54个必需字符及七种音乐符号，保留版权和修改说明。完整JS103、累计补充包及剧情资源不重发，不改下载顺序、存档、安装标记。\n\n私有化、Cloudflare双入口与新资源优先级推迟至196；迁移功能仍关闭。195需覆盖安装新APK，资源热更新不能替换已安装APK内的字体。字体字节与包身份由CI验证，最终游戏显示由维护者验收。\n'''
    (SRC/'docs/font-replacement-195.md').write_text(doc,encoding='utf8')
    # Read the actual 194 artifact, and prove the new check fails on that omission.
    old_dir=ROOT/'.old195';old_dir.mkdir(exist_ok=True)
    subprocess.run(['gh','run','download','36260133659','--repo',REPO,'--name','personal-native-main-verified','--dir',str(old_dir)],check=True)
    old_apk=old_dir/'magirecocn-legacy-client.apk'
    assert hashlib.sha256(old_apk.read_bytes()).hexdigest()==OLD_APK
    spec=importlib.util.spec_from_file_location('font195check',SRC/'tools/check-font195-artifact.py')
    check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
    negatives=[]
    def reject(apk,label):
        try: check.verify(apk)
        except (AssertionError,KeyError,subprocess.CalledProcessError):negatives.append(label)
        else:raise AssertionError('Guard accepted '+label)
    reject(old_apk,'actual_194_unreplaced_aliases')
    with zipfile.ZipFile(old_apk) as z:
        members={n:z.read(n) for n in z.namelist() if n.startswith(('assets/fonts/','assets/font-licenses/')) and not n.endswith('/')}
    for name in ('MTF4a5kp.ttf','mbm_20160902.ttf'):members['assets/fonts/'+name]=round_data
    fixture=OUT/'fixture.zip'
    def emit(items):
        with zipfile.ZipFile(fixture,'w') as z:
            for n,b in items.items():z.writestr(n,b)
    emit(members);check.verify(fixture)
    for name in ('MTF4a5kp.ttf','mbm_20160902.ttf'):
        bad=dict(members);bad['assets/fonts/'+name]=bad['assets/fonts/TTZhiHeiGB3-W4.ttf'];emit(bad);reject(fixture,'wrong_font_'+name)
    bad=dict(members);del bad['assets/fonts/mbm_20160902.ttf'];emit(bad);reject(fixture,'missing_native_alias')
    fixture.unlink()
    source_paths=['magia-native/src/MagiaLegacy.cpp','tools/check-fonts.py','tools/check-font195-artifact.py',
                  'assets/fonts/mbm_20160902.ttf','.github/workflows/build-apk.yml',
                  'patch/src/main/java/io/kamihama/magianative/CNPublicResources.java','docs/font-replacement-195.md']
    for path in source_paths:
        if path.endswith('.py'):compile((SRC/path).read_text(encoding='utf8'),path,'exec')
    assert ref(SOURCE)==BASE and ref(REPO)==live_patch,'Concurrent main change'
    message='fix(font): 195原生MTF与mbm同名替换为寒蝉全圆\n\n修正194只打包新字体却未覆盖实际原生入口的遗漏。保留调用和布局，签名后按真实文件名核验；私有化及线路迁移推迟196。\n\n文档: 新增font-replacement-195.md说明共用入口与实机验收边界。\n\nCo-authored-by: Codex <noreply@openai.com>'
    source_commit=commit_candidate(SOURCE,BASE,{p:(SRC/p).read_bytes() for p in source_paths},message)
    patch_workflow='.github/workflows/build-personal-client.yml'
    patch_files={patch_workflow:edit_workflow((ROOT/patch_workflow).read_text(encoding='utf8'),True),
                 'docs/font195-build.json':json.dumps(dict(version='1.0.195',source_commit=source_commit,font_commit=FONT,
                     migration_release='1.0.196',scope='native round aliases only',device_acceptance='pending'),indent=2)+'\n',
                 'docs/font195-preparation.json':json.dumps(dict(verified_round_sha256=ROUND,required_glyphs_with_nonempty_outlines=len(required),
                     actual_194_rejected=True,negative_tests=negatives,positive_alias_fixture_passed=True,
                     source_changed_paths=source_paths,font_routing_changed=False,download_priority_changed=False),indent=2)+'\n'}
    patch_commit=commit_candidate(REPO,live_patch,patch_files,message)
    report=dict(status='prepared_not_published',source_parent=BASE,source_commit=source_commit,
                patch_parent=live_patch,patch_commit=patch_commit,source_changed_paths=source_paths,
                patch_changed_paths=list(patch_files),negative_tests=negatives,positive_alias_fixture_passed=True,
                required_glyphs_with_nonempty_outlines=len(required))
    dump(OUT/'prepared-commits.json',report)
    print('PREPARED_NO_BRANCH_REFS_CHANGED',json.dumps(report))

if __name__=='__main__':main()
