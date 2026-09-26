#!/usr/bin/env python3
"""Build symbol-complete font replacements; no routing or existing-outline changes."""
import base64, hashlib, io, json, os, pathlib, re, subprocess, unicodedata, urllib.request, zipfile
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.boundsPen import BoundsPen
from PIL import Image, ImageDraw, ImageFont

R=pathlib.Path(__file__).resolve().parents[1]
OUT=R/'.font194'; OUT.mkdir(exist_ok=True)
PRODUCT=OUT/'product'; PRODUCT.mkdir(exist_ok=True)
REPO='HiiragiNemu/magireco-cn-patch'
OLD_REF='71d3278ea246b58b4a3bc6808a01c96a4e65bdcd'
NOTO_REF='f8d157532fbfaeda587e826d4cd5b21a49186f7c'
MUSIC=set(range(0x2669,0x2670))
OLD={
'TTDaYuanGB3.ttf':'1fe1fdc28cc7347e26099bf2fb54b85370617acd91efc6e63903cf3c33a62541',
'TTZhiHeiGB3-W4.ttf':'c69dea79d5b33864bbda85645641d5208790f8c394a291992e898a3753dd71d3'}
SPECS=[
('TTDaYuanGB3.ttf','ChillRoundF Bold','Magius Round Symbols','Bold',
'https://github.com/Warren2060/ChillRound/releases/download/v3.200/ChillRoundF_v3.200.zip',
'7a061e39cc8f377ce122f0ae68d1fe3ef43d78431388362c61ea8d695722d267',
'ChillRoundF_v3.200/ChillRoundFBold.ttf','f2c4f9295d9d04a1eb6392ae3c51ecf2a9ffab355a45c6686eeec5eede3381ec'),
('TTZhiHeiGB3-W4.ttf','MiSans Semibold','Magius Sans Symbols','Semibold',
'https://hyperos.mi.com/font-download/MiSans.zip',
'b6aa1fc827035922612df8edf36e5609bca1c5441e25cd57572204569b7b81d9',
'MiSans/ttf/MiSans-Semibold.ttf','77c23f31ae124867778344970155a0c8d34a89897dedaab81aeee82ff00a4ce6')]

def sha(data):return hashlib.sha256(data).hexdigest()
def blob(data):return hashlib.sha1(('blob %d\0'%len(data)).encode()+data).hexdigest()
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Magius-Font194','Accept-Encoding':'identity'})
    with urllib.request.urlopen(req,timeout=120) as response:return response.read()
def api(path,method='GET',body=None):
    cmd=['gh','api',path]
    if method!='GET':cmd+=['--method',method]
    if body is not None:cmd+=['--input','-']
    return json.loads(subprocess.check_output(cmd,input=None if body is None else json.dumps(body).encode()))
def write(name,data):
    p=PRODUCT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(data.encode('utf8') if isinstance(data,str) else data)
def raw_font(repository,path,ref):
    meta=api(f'repos/{repository}/contents/{path}?ref={ref}')
    data=get(f'https://raw.githubusercontent.com/{repository}/{ref}/{path}')
    assert blob(data)==meta['sha'],'donor content mismatch'
    return data

def outlines(font):return {n:sha(font['glyf'][n].compile(font['glyf'])) for n in font.getGlyphOrder()}
def vertical(font):
    return [font['hhea'].ascent,font['hhea'].descent,font['hhea'].lineGap,
    font['OS/2'].sTypoAscender,font['OS/2'].sTypoDescender,font['OS/2'].sTypoLineGap,
    font['OS/2'].usWinAscent,font['OS/2'].usWinDescent]
def bounds(font,cp):
    name=(font.getBestCmap() or {}).get(cp)
    if name is None or name=='.notdef':return None
    gs=font.getGlyphSet();pen=BoundsPen(gs);gs[name].draw(pen);return pen.bounds

def complements(droid):
    """Two independently drawn music signs and a halfwidth compatibility adaptation."""
    def polygon(p,points):
        p.moveTo(points[0])
        for point in points[1:]:p.lineTo(point)
        p.closePath()
    def ellipse(p,cx,cy,rx,ry):
        p.moveTo((cx+rx,cy))
        p.qCurveTo((cx+rx,cy-ry),(cx,cy-ry))
        p.qCurveTo((cx-rx,cy-ry),(cx-rx,cy))
        p.qCurveTo((cx-rx,cy+ry),(cx,cy+ry))
        p.qCurveTo((cx+rx,cy+ry),(cx+rx,cy));p.closePath()
    glyphs={'.notdef':TTGlyphPen(None).glyph()}
    p=TTGlyphPen(None)
    ellipse(p,245,95,105,67);ellipse(p,665,195,105,67)
    polygon(p,[(295,95),(295,790),(350,790),(350,95)])
    polygon(p,[(715,195),(715,890),(770,890),(770,195)])
    polygon(p,[(295,685),(295,790),(770,890),(770,785)])
    glyphs['beamedEighth']=p.glyph()
    p=TTGlyphPen(None)
    polygon(p,[(340,140),(340,840),(400,840),(400,140)])
    polygon(p,[(600,-60),(600,640),(660,640),(660,-60)])
    polygon(p,[(340,490),(340,570),(660,670),(660,590)])
    polygon(p,[(340,230),(340,310),(660,410),(660,330)])
    glyphs['natural']=p.glyph()
    cp=0x3146 if 0x3146 in droid.getBestCmap() else 0x110A
    assert cp in droid.getBestCmap(),'Missing Hangul ssang-sios donor'
    assert unicodedata.normalize('NFKC',chr(0xFFBA))==unicodedata.normalize('NFKC',chr(cp))
    rec=DecomposingRecordingPen(droid.getGlyphSet());droid.getGlyphSet()[droid.getBestCmap()[cp]].draw(rec)
    p=TTGlyphPen(None);scale=1000/droid['head'].unitsPerEm
    rec.replay(TransformPen(p,(scale*0.5,0,0,scale,0,0)));glyphs['halfwidthSsangSios']=p.glyph()
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({0x266B:'beamedEighth',0x266E:'natural',0xFFBA:'halfwidthSsangSios'})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n:(500 if n=='halfwidthSsangSios' else 1000,0) for n in glyphs})
    fb.setupHorizontalHeader(ascent=900,descent=-100)
    fb.setupNameTable({'familyName':'Magius Supplement Symbols','styleName':'Regular'})
    fb.setupOS2(sTypoAscender=900,sTypoDescender=-100,usWinAscent=900,usWinDescent=100)
    fb.setupPost();fb.setupMaxp();fb.font['head'].created=fb.font['head'].modified=2082844800
    out=io.BytesIO();fb.save(out);return out.getvalue()

def add_glyph(target,donor,cp):
    source_name=donor.getBestCmap().get(cp)
    assert source_name and bounds(donor,cp),f'donor has no visible U+{cp:04X}'
    target_name=f'mag194_U{cp:06X}';assert target_name not in target.getGlyphOrder()
    scale=target['head'].unitsPerEm/donor['head'].unitsPerEm
    gs=donor.getGlyphSet();rec=DecomposingRecordingPen(gs);gs[source_name].draw(rec)
    pen=TTGlyphPen(None);curved=Cu2QuPen(pen,max_err=0.8,reverse_direction=True) if 'CFF ' in donor else pen
    rec.replay(TransformPen(curved,(scale,0,0,scale,0,0)))
    glyph=pen.glyph();glyph.recalcBounds(target['glyf'])
    order=target.getGlyphOrder()+[target_name];target.setGlyphOrder(order);target['glyf'][target_name]=glyph
    advance,lsb=donor['hmtx'].metrics[source_name]
    target['hmtx'].metrics[target_name]=(round(advance*scale),round(lsb*scale))
    if 'vmtx' in target:target['vmtx'].metrics[target_name]=(target['head'].unitsPerEm,target['OS/2'].sTypoAscender-glyph.yMax)
    for table in target['cmap'].tables:
        if table.isUnicode() and table.format in (4,12):
            if cp<=0xFFFF or table.format==12:table.cmap[cp]=target_name
    if not any(t.isUnicode() and t.format==12 for t in target['cmap'].tables):
        t=CmapSubtable.newSubtable(12);t.platformID=3;t.platEncID=10;t.language=0
        t.cmap=dict(target.getBestCmap());t.cmap[cp]=target_name;target['cmap'].tables.append(t)
    target['maxp'].numGlyphs=len(order)

def rename(font,family,style):
    values={1:family,2:style,3:family+' '+style+';Magius-font194',4:family+' '+style,
    5:'Version 1.194; symbol supplement; upstream preserved in notices',6:(family+'-'+style).replace(' ',''),
    16:family,17:style,18:family+' '+style,21:family,22:style}
    for rec in list(font['name'].names):
        if rec.nameID in values:font['name'].setName(values[rec.nameID],rec.nameID,rec.platformID,rec.platEncID,rec.langID)
    for nid,value in values.items():font['name'].setName(value,nid,3,1,0x409)
    font['name'].setName('Magius symbol supplement, not an unmodified upstream release. See bundled font-licenses notices.',10,3,1,0x409)

def main():
    if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise SystemExit('Unexpected repository')
    starting=api(f'repos/{REPO}/git/ref/heads/main')['object']['sha']
    assert starting==subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'Main advanced'
    (OUT/'report.json').write_text('{}');old_fonts={}
    for name,expected in OLD.items():
        data=get(f'https://raw.githubusercontent.com/{REPO}/{OLD_REF}/magica/fonts/{name}');assert sha(data)==expected
        old_fonts[name]=TTFont(io.BytesIO(data))
    requirements={n:{cp for cp,g in f.getBestCmap().items() if g.startswith('cnfix_')} for n,f in old_fonts.items()}
    assert all(len(v)==49 for v in requirements.values()) and len(set(map(frozenset,requirements.values())))==1
    corpus=set()
    for name in ['cn_js_update.zip','cn_js_delta.zip','cn_scenario_update.zip']:
        data=get(f'https://github.com/{REPO}/releases/download/latest/{name}')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                if not member.lower().endswith(('.json','.js','.html','.tsv')):continue
                try:text=z.read(member).decode('utf8')
                except UnicodeDecodeError:continue
                corpus.update(map(ord,text));corpus.update(int(m,16) for m in re.findall(r'\\u([0-9A-Fa-f]{4})',text))
        del data
    corpus={cp for cp in corpus if unicodedata.category(chr(cp))[0] not in ('C','Z')}
    donors={};aosp='aosp-mirror/platform_frameworks_base';aosp_ref='android-4.4_r1'
    for name in ['DroidSansFallback.ttf','DroidSans.ttf']:
        data=raw_font(aosp,'data/fonts/'+name,aosp_ref);donors[name]=(TTFont(io.BytesIO(data)),sha(data),'Apache-2.0')
    data=complements(donors['DroidSansFallback.ttf'][0]);donors['MagiusSymbols.ttf']=(TTFont(io.BytesIO(data)),sha(data),'Apache-2.0')
    noto=raw_font('notofonts/noto-cjk','Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf',NOTO_REF)
    donors['NotoSansCJKsc-Bold.otf']=(TTFont(io.BytesIO(noto)),sha(noto),'OFL-1.1')
    report={'version':'1.0.194','old_fixed_codepoints':[f'U+{c:04X}' for c in sorted(next(iter(requirements.values())))],
    'fonts':{},'native_historical_fonts_changed':False,'routing_changed':False,'migration_195_enabled':False,
    'device_visual_acceptance':'awaiting maintainer','unresolved_private_use':['U+F6DB'],
    'donors':{k:{'sha256':v[1],'license':v[2]} for k,v in donors.items()}}
    write('magica/font-licenses/Apache-Droid-NOTICE.txt',get(f'https://raw.githubusercontent.com/{aosp}/{aosp_ref}/data/fonts/NOTICE'))
    write('magica/font-licenses/Noto-CJK-OFL.txt',get(f'https://raw.githubusercontent.com/notofonts/noto-cjk/{NOTO_REF}/Sans/LICENSE'))
    write('magica/font-licenses/Magius-Symbols-NOTICE.txt','Two original geometric music signs U+266B and U+266E, implemented in prepare-font194.py, licensed under Apache-2.0. U+FFBA is a horizontally scaled adaptation of the corresponding Apache-2.0 Droid Hangul glyph; NFKC equivalence is asserted. No Tengxiang outlines used. Full Apache license and Droid copyright accompany this file.\n')
    image=Image.new('RGB',(1300,440),'white');draw=ImageDraw.Draw(image)
    for idx,spec in enumerate(SPECS):
        name,label,family,style,url,archive_sha,member,font_sha=spec
        archive=get(url);assert sha(archive)==archive_sha,label+' archive changed'
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            original=z.read(member);assert sha(original)==font_sha
            if idx==0:write('magica/font-licenses/ChillRoundF-OFL.txt',z.read('ChillRoundF_v3.200/LICENSE.txt'))
        font=TTFont(io.BytesIO(original),recalcTimestamp=False)
        original_outlines=outlines(font);original_metrics=dict(font['hmtx'].metrics);original_vertical=vertical(font)
        upstream=[]
        for nid in (0,7,8,9,11,13,14):
            values=sorted({r.toUnicode() for r in font['name'].names if r.nameID==nid})
            if values:upstream.append(f'nameID {nid}:\n'+'\n'.join(values))
        write('magica/font-licenses/'+('ChillRoundF' if idx==0 else 'MiSans')+'-UPSTREAM.txt',label+'\nSource: '+url+'\n\n'+'\n\n'.join(upstream)+'\n')
        required=requirements[name]|MUSIC;actual=corpus & set(old_fonts[name].getBestCmap())
        missing=sorted((required|actual)-set(font.getBestCmap()));additions={};unavailable=[]
        allowed=list(donors) if idx==0 else ['DroidSansFallback.ttf','DroidSans.ttf','MagiusSymbols.ttf']
        for cp in missing:
            found=next((d for d in allowed if cp in donors[d][0].getBestCmap() and bounds(donors[d][0],cp)),None)
            if found is None:unavailable.append(f'U+{cp:04X}');continue
            add_glyph(font,donors[found][0],cp);additions[f'U+{cp:04X}']=found
        if unavailable:raise RuntimeError(label+' unsupported actual characters: '+repr(unavailable))
        rename(font,family,style);target=PRODUCT/'magica/fonts'/name;target.parent.mkdir(parents=True,exist_ok=True)
        font.save(target);font.close()
        with TTFont(target) as verified:
            assert vertical(verified)==original_vertical,'Vertical metrics changed'
            assert all(verified['hmtx'].metrics[n]==m for n,m in original_metrics.items()),'Existing advances changed'
            changed=[n for n,d in original_outlines.items() if sha(verified['glyf'][n].compile(verified['glyf']))!=d]
            assert not changed,'Existing outlines changed: '+repr(changed[:5])
            assert all(bounds(verified,cp) for cp in required),'Required glyph is empty'
            assert not ((required|actual)-set(verified.getBestCmap()))
            data=target.read_bytes();report['fonts'][name]={'source':label,'source_url':url,'source_sha256':font_sha,
            'size':len(data),'sha256':sha(data),'gitblob':blob(data),'family':verified['name'].getDebugName(1),
            'added':additions,'added_count':len(additions),'required_coverage':{f'U+{cp:04X}':list(bounds(verified,cp)) for cp in sorted(required)},
            'corpus_required_count':len(actual),'existing_outlines_unchanged':len(original_outlines),'vertical_metrics':original_vertical}
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        draw.text((20,idx*210+12),label+' / symbol-complete derivative',fill='black')
        for y,size in [(45,30),(94,48),(155,24)]:
            ft=ImageFont.truetype(str(target),size)
            text='魔法纪录 音乐符号：♩♪♫♬♭♮♯ ♥ 𫚕' if size!=24 else '攻击 防御 开始 继续 保存 0123456789 ABCabc'
            draw.text((20,idx*210+y),text,font=ft,fill='black')
        for cp in required:assert ImageFont.truetype(str(target),48).getmask(chr(cp)).getbbox(),f'Raster-empty U+{cp:04X}'
        print('VERIFIED_FONT',name,'added',len(additions),'corpus',len(actual),flush=True)
    write('magica/fonts/mbm_20160902.ttf',(PRODUCT/'magica/fonts/TTZhiHeiGB3-W4.ttf').read_bytes())
    write('magica/font-licenses/MODIFICATIONS.md','''# 字体替换与补字（客户端 1.0.194）

外部文件名只是既有加载接口的兼容别名，不表示文件仍是腾祥字体。
TTDaYuanGB3.ttf：寒蝉全圆体 Bold 3.200 补字版，内部名 Magius Round Symbols Bold。
TTZhiHeiGB3-W4.ttf 及 Web mbm_20160902.ttf：MiSans Semibold 4.009 补字版，内部名 Magius Sans Symbols Semibold。

仅增加目标缺失的字符；原版已有轮廓、字宽和垂直度量逐一校验不变。需求覆盖旧版49个补字字符、七种音乐符号及现行游戏文本。补充轮廓来自Apache-2.0的Droid字体与独立几何音乐符号；圆体可另用OFL的Noto Sans CJK。半角韩文字形按Unicode规范化对应关系适配。未从腾祥字体复制轮廓。

寒蝉修改版遵守OFL并使用不同家族名，版权和许可证均随包保留。使用了MiSans，其上游版权与许可信息保留；此补字版不是小米官方原版。项目维护者指定的改动不等于小米对修改的额外许可，不能以修改幅度或被发现概率推断许可。官方说明：https://hyperos.mi.com/font/zh/faq/

原生MTF4a5kp.ttf和assets/fonts/mbm_20160902.ttf历史字节不动，字体路由和文本布局不改。U+F6DB语义仍未明确，不伪造字形；真机显示由维护者验收。
''')
    write('magica/font-licenses/font194-manifest.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n');image.save(OUT/'symbols.png')
    assert all(sha((PRODUCT/'magica/fonts'/n).read_bytes()) not in OLD.values() for n in ['TTDaYuanGB3.ttf','TTZhiHeiGB3-W4.ttf','mbm_20160902.ttf'])
    assert api(f'repos/{REPO}/git/ref/heads/main')['object']['sha']==starting,'Concurrent main update'
    tree0=api(f'repos/{REPO}/git/commits/{starting}')['tree']['sha'];entries=[]
    for path in sorted(PRODUCT.rglob('*')):
        if not path.is_file():continue
        made=api(f'repos/{REPO}/git/blobs','POST',{'encoding':'base64','content':base64.b64encode(path.read_bytes()).decode()})
        entries.append({'path':path.relative_to(PRODUCT).as_posix(),'mode':'100644','type':'blob','sha':made['sha']})
    tree=api(f'repos/{REPO}/git/trees','POST',{'base_tree':tree0,'tree':entries})['sha']
    author={'name':'HiiragiNemu','email':'128921071+HiiragiNemu@users.noreply.github.com'}
    message='fix(font): 同名替换双字体并补齐历史字符和音乐符号\n\n原有轮廓、字宽和度量均校验保留；替换Web智黑别名副本，不改路由。\n\n文档: 附字体来源、许可、修改声明与覆盖记录。\n\nCo-authored-by: Codex <noreply@openai.com>'
    commit=api(f'repos/{REPO}/git/commits','POST',{'tree':tree,'parents':[starting],'message':message,'author':author,'committer':author})['sha']
    api(f'repos/{REPO}/git/refs/heads/main','PATCH',{'sha':commit,'force':False})
    print('FONT_ASSET_COMMIT',commit)
    for name,info in report['fonts'].items():print(name,json.dumps({k:info[k] for k in ['size','sha256','gitblob','family','added_count','corpus_required_count']}))
    print('PASS original glyphs, advances and vertical metrics unchanged; all 54 required characters have outlines and pixels; no font binaries exported as Actions artifacts')

if __name__=='__main__':main()
