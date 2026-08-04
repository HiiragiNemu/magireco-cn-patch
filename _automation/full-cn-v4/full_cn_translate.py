#!/usr/bin/env python3
import json,re,html,time,shutil,zipfile,subprocess,sys
from pathlib import Path
from collections import Counter
from opencc import OpenCC

ROOT=Path('.').resolve(); OUT=ROOT/'_automation/full-cn-v4/output'; WORK=OUT/'work'
KANA=re.compile(r'[\u3040-\u30ff\u31f0-\u31ff]')
PH=re.compile(r'(?:<%[\s\S]*?%>|\$\{[\s\S]*?\}|https?://[^\s\'"<>]+|\\(?:n|r|t|u[0-9A-Fa-f]{4})|%(?:\d+\$)?[-+#0 ]*\d*(?:\.\d+)?[A-Za-z]|\{[^{}\n]{0,80}\}|@[A-Za-z0-9_]*)')
TERMS={'マギアレコード':'魔法纪录','マギア':'Magia','ドッペル':'Doppel','メモリア':'记忆结晶','ミラーズコイン':'镜界币','ミラーズ':'镜界','デスティニージェム':'命运宝石','ソウルジェム':'灵魂宝石','ガチャ':'抽卡','クエスト':'任务','ストーリー':'剧情','ショップ':'商店','イベント':'活动','ログインボーナス':'登录奖励','ログイン':'登录','プレイヤー':'玩家','ユーザー':'用户','サポート':'支援','チーム':'队伍','パーティ':'队伍','バトル':'战斗','ダメージ':'伤害','スキル':'技能','アビリティ':'能力','コネクト':'连携','ブラスト':'Blast','アクセル':'Accele','チャージ':'Charge','クリティカル':'暴击','カウンター':'反击','エピソード':'章节','プロフィール':'个人资料','ランキング':'排行榜','ポイント':'点数','コイン':'硬币','チケット':'券','アイテム':'道具','ボーナス':'奖励','レベル':'等级','ランク':'等级','エネミー':'敌人','ボス':'首领','ターン':'回合','ウェーブ':'波次','クリア':'通关','ミッション':'任务','チャレンジ':'挑战','オート':'自动','コンティニュー':'继续','リーダー':'队长','フォロー':'关注','フレンド':'好友','フォロワー':'粉丝','アーカイブ':'保管库','フィルター':'筛选','ソート':'排序','キャンセル':'取消','エラー':'错误','メンテナンス':'维护','ダウンロード':'下载','タイトル':'标题','ボイス':'语音','ムービー':'影片','ライブ2D':'Live2D','ルームウェア':'居家服','パジャマ':'睡衣','クリスマス':'圣诞节','ハロウィン':'万圣节','バレンタイン':'情人节','ホワイトデー':'白色情人节','サンタ':'圣诞老人','水着':'泳装','浴衣':'浴衣','お正月':'新年','制服':'校服','私服':'便服','冬服':'冬装','夏服':'夏装','魔法少女':'魔法少女','魔女':'魔女','使い魔':'使魔','ウワサ':'传闻','キモチ':'心魔','マギウス':'玛吉斯','ネオ・マギウス':'Neo-Magius','ネオマギウス':'Neo-Magius','神浜':'神滨','見滝原':'见泷原','宝崎':'宝崎','湯国':'汤国','精神強化':'精神强化','覚醒':'觉醒','限界突破':'界限突破','強化':'强化','編成':'编成','魔力解放':'魔力解放','攻撃力':'攻击力','防御力':'防御力','状態異常':'异常状态','耐性':'抗性','確率':'概率','味方':'我方','敵':'敌方','全体':'全体','単体':'单体','自分':'自身','自身':'自身','付与':'赋予','解除':'解除','回復':'回复','上昇':'提升','低下':'降低','無効':'无效','必ず':'必定','ターゲット':'目标','クールタイム':'冷却时间'}
EXACT={'はい':'是','いいえ':'否','決定':'确定','戻る':'返回','閉じる':'关闭','次へ':'下一步','スキップ':'跳过','受け取る':'领取','一括受取':'全部领取','詳細':'详情','所持数':'持有数量','交換':'兑换','購入':'购买','売却':'出售','確認':'确认','注意':'注意','未所持':'未持有','所持':'已持有','未開放':'未解锁','開放済':'已解锁','開催中':'进行中','終了':'已结束','準備中':'准备中','魔法少女ストーリー':'魔法少女剧情','メインストーリー':'主线剧情','アナザーストーリー':'另一篇章','イベントストーリー':'活动剧情','衣装ストーリー':'服装剧情','お知らせ':'公告','プレゼント':'礼物','パジャマ':'睡衣','ルームウェア':'居家服','冬服':'冬装','夏服':'夏装','お正月衣装':'新年服装','クリスマス衣装':'圣诞节服装','病院服':'病号服','入院着':'住院服','アトリエ着':'画室服装'}

report={'started':time.time(),'methods':Counter()}; cache={}; cc=OpenCC('t2s'); google=None
try:
 from argostranslate import package,translate
 package.update_package_index(); av=package.get_available_packages(); ins=package.get_installed_packages()
 def has(a,b): return any(p.from_code==a and p.to_code==b for p in package.get_installed_packages())
 def install(a,b):
  if has(a,b): return True
  xs=[p for p in av if p.from_code==a and p.to_code==b]
  if not xs:return False
  p=xs[-1]; print('install',a,b,p,flush=True); package.install_from_path(p.download()); return True
 argos=install('ja','zh') or (install('ja','en') and install('en','zh'))
except Exception as e: argos=False; report['argos_error']=repr(e)

def gtranslate(s):
 global google
 if google is None:
  from deep_translator import GoogleTranslator
  google=GoogleTranslator(source='ja',target='zh-CN')
 for i in range(5):
  try:return google.translate(s)
  except Exception:
   if i==4:raise
   time.sleep(2**i)

def mask(s):
 mp={}; n=0
 def add(v):
  nonlocal n
  k=f'ZXQ{n:05d}QXZ';n+=1;mp[k]=v;return k
 s=PH.sub(lambda m:add(m.group()),s)
 for a,b in sorted(TERMS.items(),key=lambda x:-len(x[0])):
  if a in s:s=s.replace(a,add(b))
 return s,mp

def tr(src):
 if not KANA.search(src):return src
 if src in cache:return cache[src]
 st=src.strip()
 if st in EXACT:r=src.replace(st,EXACT[st]);cache[src]=r;return r
 s,mp=mask(src)
 try:
  if not argos:raise RuntimeError()
  r=translate.translate(s,'ja','zh'); method='argos'
 except Exception:
  r=gtranslate(s); method='google'
 for k,v in mp.items():r=re.sub(k.replace('QXZ',r'\s*QXZ'),lambda _:v,r)
 r=cc.convert(html.unescape(r)).replace('神浜','神滨').replace('見滝原','见泷原').replace('魔法記錄','魔法纪录').replace('＠','@').strip()
 if KANA.search(r):
  try:
   q=gtranslate(s)
   for k,v in mp.items():q=q.replace(k,v)
   q=cc.convert(html.unescape(q)).replace('＠','@').strip()
   if len(KANA.findall(q))<len(KANA.findall(r)):r=q;method='google-rescue'
  except Exception:pass
 lead=src[:len(src)-len(src.lstrip())];tail=src[len(src.rstrip()):];r=lead+r+tail
 cache[src]=r;report['methods'][method]+=1
 if len(cache)%100==0:
  (OUT/'translation_cache.json').write_text(json.dumps(cache,ensure_ascii=False,indent=2),'utf-8');print('translated',len(cache),flush=True)
 return r

def jwalk(x):
 if isinstance(x,str):return tr(x)
 if isinstance(x,list):return [jwalk(v) for v in x]
 if isinstance(x,dict):return {k:jwalk(v) for k,v in x.items()}
 return x

def spans(t):
 z=[];i=0;n=len(t)
 while i<n:
  if t.startswith('//',i):j=t.find('\n',i+2);i=n if j<0 else j+1;continue
  if t.startswith('/*',i):j=t.find('*/',i+2);i=n if j<0 else j+2;continue
  if t[i] not in "'\"`":i+=1;continue
  q=t[i];a=i+1;j=a;esc=False
  while j<n:
   if esc:esc=False;j+=1;continue
   if t[j]=='\\':esc=True;j+=1;continue
   if t[j]==q:break
   j+=1
  if j>=n:break
  z.append((a,j,q,t[a:j]));i=j+1
 return z

def js(t):
 rs=[]
 for a,b,q,s in spans(t):
  if KANA.search(s):
   v=tr(s).replace('\\','\\\\').replace(q,'\\'+q).replace('\\\\n','\\n').replace('\\\\r','\\r').replace('\\\\t','\\t');rs.append((a,b,v))
 for a,b,v in reversed(rs):t=t[:a]+v+t[b:]
 return t

def htm(t):
 t=js(t); parts=re.split(r'(<[^>]+>)',t);script=style=comment=False
 for i,p in enumerate(parts):
  low=p.lower()
  if p.startswith('<!--'):comment=True
  if comment:
   if p.endswith('-->'):comment=False
   continue
  if low.startswith('<script'):script=True;continue
  if low.startswith('</script'):script=False;continue
  if low.startswith('<style'):style=True;continue
  if low.startswith('</style'):style=False;continue
  if p.startswith('<') or script or style:continue
  if KANA.search(p):parts[i]=tr(p)
 return ''.join(parts)

if WORK.exists():shutil.rmtree(WORK)
WORK.mkdir(parents=True); files=[]
for base in [ROOT/'magica/js',ROOT/'magica/template']:
 if not base.exists():continue
 for p in base.rglob('*'):
  if p.is_file() and p.suffix.lower() in {'.json','.js','.html'}:
   q=WORK/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);files.append(q)
modified=[];errors=[]
for i,p in enumerate(files,1):
 try:
  before=p.read_text('utf-8')
  if not KANA.search(before):continue
  if p.suffix=='.json':after=json.dumps(jwalk(json.loads(before)),ensure_ascii=False,indent=2)+'\n'
  elif p.suffix=='.js':after=js(before)
  else:after=htm(before)
  if after!=before:p.write_text(after,'utf-8');modified.append(str(p.relative_to(WORK)));print(i,len(files),modified[-1],flush=True)
 except Exception as e:errors.append({'file':str(p.relative_to(WORK)),'error':repr(e)})
(OUT/'translation_cache.json').write_text(json.dumps(cache,ensure_ascii=False,indent=2),'utf-8')
jsonerr=[]
for p in WORK.rglob('*.json'):
 try:json.loads(p.read_text('utf-8'))
 except Exception as e:jsonerr.append({'file':str(p.relative_to(WORK)),'error':repr(e)})
res=[]
for p in WORK.rglob('*'):
 if p.is_file() and p.suffix.lower() in {'.json','.js','.html'}:
  t=p.read_text('utf-8')
  if p.suffix=='.json':
   def ck(x,path='$'):
    if isinstance(x,str) and KANA.search(x):res.append({'file':str(p.relative_to(WORK)),'path':path,'text':x})
    elif isinstance(x,list):
     for i,v in enumerate(x):ck(v,f'{path}[{i}]')
    elif isinstance(x,dict):
     for k,v in x.items():ck(v,f'{path}.{k}')
   ck(json.loads(t))
  else:
   for a,b,q,s in spans(t):
    if KANA.search(s):res.append({'file':str(p.relative_to(WORK)),'path':f'string@{a}','text':s})
(OUT/'unresolved_runtime_japanese.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),'utf-8')
z=OUT/'translated_repository_subset.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as f:
 for p in WORK.rglob('*'):
  if p.is_file():f.write(p,p.relative_to(WORK).as_posix())
report.update({'finished':time.time(),'source_files':len(files),'modified_files':len(modified),'cache_entries':len(cache),'errors':errors,'json_errors':jsonerr,'runtime_kana_residue_count':len(res),'methods':dict(report['methods'])})
(OUT/'translation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
sys.exit(0 if not errors and not jsonerr else 2)
