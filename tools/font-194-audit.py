#!/usr/bin/env python3
"""Read-only audit of official replacements and the currently published font carriers."""
import concurrent.futures, hashlib, io, json, os, pathlib, urllib.request, zipfile
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen

OUT = pathlib.Path('font194-audit'); OUT.mkdir(exist_ok=True)
URLS = {
    'ChillRoundF': 'https://github.com/Warren2060/ChillRound/releases/download/v3.200/ChillRoundF_v3.200.zip',
    'MiSans': 'https://hyperos.mi.com/font-download/MiSans.zip',
}
SYMBOLS = [0x2669,0x266A,0x266B,0x266C,0x266D,0x266E,0x266F,0xF6DB]

def download(url, path):
    req=urllib.request.Request(url,headers={'User-Agent':'Font-194-ReadOnly-Audit'})
    with urllib.request.urlopen(req,timeout=120) as r, path.open('wb') as f:
        while True:
            b=r.read(1048576)
            if not b: break
            f.write(b)
    return path

def inspect(data):
    with TTFont(io.BytesIO(data)) as font:
        cmap=font.getBestCmap() or {}; gs=font.getGlyphSet()
        def entry(cp):
            name=cmap.get(cp); bounds=None
            if name and name != '.notdef':
                pen=BoundsPen(gs); gs[name].draw(pen); bounds=pen.bounds
            return {'glyph':name,'bounds':bounds,'advance':font['hmtx'].metrics.get(name,[None])[0]}
        fixed=sorted(cp for cp,g in cmap.items() if g.startswith('cnfix_'))
        return {'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                'gitblob':hashlib.sha1(('blob %s\0'%len(data)).encode()+data).hexdigest(),
                'family':font['name'].getDebugName(1),'full_name':font['name'].getDebugName(4),
                'version':font['name'].getDebugName(5),'glyph_count':len(cmap),'upem':font['head'].unitsPerEm,
                'weight':font['OS/2'].usWeightClass,
                'vertical_metrics':{'hhea':[font['hhea'].ascent,font['hhea'].descent,font['hhea'].lineGap],
                                    'typo':[font['OS/2'].sTypoAscender,font['OS/2'].sTypoDescender,font['OS/2'].sTypoLineGap],
                                    'win':[font['OS/2'].usWinAscent,font['OS/2'].usWinDescent]},
                'symbols':{f'U+{cp:04X}':entry(cp) for cp in SYMBOLS},
                'previously_added':{f'U+{cp:04X}':entry(cp) for cp in fixed}}

report={'candidate_fonts':{},'current_repository_fonts':{},'published_packages':{}}
for name in ['TTDaYuanGB3.ttf','TTZhiHeiGB3-W4.ttf']:
    report['current_repository_fonts'][name]=inspect((pathlib.Path('magica/fonts')/name).read_bytes())

def candidate(item):
    label,url=item; path=download(url,OUT/(label+'.zip'))
    with zipfile.ZipFile(path) as z:
        suffix='ChillRoundFBold.ttf' if label=='ChillRoundF' else 'MiSans-Semibold.ttf'
        found=[n for n in z.namelist() if n.rsplit('/',1)[-1]==suffix and not n.startswith('__MACOSX/')]
        if len(found)!=1: raise RuntimeError((label,found,z.namelist()[:30]))
        data=z.read(found[0]); info=inspect(data)
        with TTFont(io.BytesIO(data)) as font:
            cmap=font.getBestCmap() or {}
            old=report['current_repository_fonts']['TTDaYuanGB3.ttf' if label=='ChillRoundF' else 'TTZhiHeiGB3-W4.ttf']['previously_added']
            info['missing_previously_added']=[cp for cp in old if int(cp[2:],16) not in cmap]
        info['source_url']=url; info['archive_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();info['archive_member']=found[0]
        info['license_members']=[n for n in z.namelist() if any(s in n.lower() for s in ['license','ofl','许可','授权'])]
    return label,info
with concurrent.futures.ThreadPoolExecutor(2) as ex:
    for label,info in ex.map(candidate,URLS.items()): report['candidate_fonts'][label]=info

for name in ['magireco-latest-legacy-client.apk','cn_js_update.zip','cn_js_delta.zip','cn_magica_resource.zip']:
    path=download('https://github.com/HiiragiNemu/magireco-cn-patch/releases/download/latest/'+name,OUT/name)
    entries={}
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if n.lower().endswith(('.ttf','.otf','.woff','.woff2')):
                entries[n]=inspect(z.read(n))
    report['published_packages'][name]={'fonts':entries,'size':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    path.unlink()
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
# Report contains identities/metrics only. Never upload the font binaries as artifacts.
print(json.dumps(report,ensure_ascii=False,indent=2))
