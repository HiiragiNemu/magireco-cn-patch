import os
import json
import shutil

# ================= 相对路径配置 (适配 GitHub Actions 与本地) =================
# 获取当前脚本所在目录作为根目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# 纯净版 jQuery 的存放位置 (你需要建一个 original_source 文件夹放原版 JS)
ORIGINAL_JQUERY_PATH = os.path.join(ROOT_DIR, "original_source", "jquery-3.7.1.min.js")
# JSON 字典和目标 JS 所在的目录
TARGET_DIR = os.path.join(ROOT_DIR, "magica", "js", "libs")
# 生成的目标 JS 文件路径
TARGET_JQUERY_PATH = os.path.join(TARGET_DIR, "jquery-3.7.1.min.js")
# =========================================================================

print(">>>[步骤 1] 正在重置环境...")
if os.path.exists(ORIGINAL_JQUERY_PATH):
    # 使用纯净版覆盖 Target 目录里的旧版，防止多次注入导致文件越来越大
    shutil.copy2(ORIGINAL_JQUERY_PATH, TARGET_JQUERY_PATH)
    print(f"  [√] 已使用原版 jQuery 覆盖至: {TARGET_JQUERY_PATH}")
else:
    print(f"  [X] 致命错误: 找不到纯净版源文件 {ORIGINAL_JQUERY_PATH}")
    exit(1)

# 显式定义所有 23 个文件的主键索引逻辑
list_keys = {
    "cardList":["cardId", "id"], 
    "charaList": ["id", "charaNo"], 
    "chapterList": ["chapterId", "id"], 
    "doppelList": ["id"], 
    "giftList": ["id", "giftId"], 
    "itemList":["itemCode", "id", "itemId"],
    "pieceList": ["pieceId", "id"], 
    "enemyList":["enemyId", "id"], 
    "patrolAreaList": ["patrolAreaId", "id"], 
    "shopItemList": ["shopItemId", "id"],
    "formationSheetList":["formationSheetId", "id"], 
    "sectionList": ["sectionId", "id"], 
    "eventList": ["eventId", "id"], 
    "eventStoryList": ["storyIds"], 
    "arenaClassList": ["arenaBattleFreeRankClass"],
    "charaMessageList":["charaNo_messageId"],
    "live2dList": ["charaId_live2dId"],
    "cardMagiaMap": "MAP", 
    "cardSkillMap": "MAP", 
    "doppelCardMagiaMap": "MAP", 
    "emotionSkillMap": "MAP", 
    "pieceSkillMap": "MAP", 
    "placeSkillMap": "MAP"
}

js_dict = {}
success_count = 0

print(">>> [步骤 2] 正在启动 23 字典全量扫描 (终极金标版)...")

# sorted()：os.listdir 的顺序取决于文件系统，不排序的话同样的输入在不同机器上
# 会生成 key 顺序不同的字典，产物 md5 跟着变——CI 与本地就再也对不上账了。
for filename in sorted(os.listdir(TARGET_DIR)):
    if not filename.endswith(".json"): continue
    key = filename.replace(".json", "")
    try:
        with open(os.path.join(TARGET_DIR, filename), 'r', encoding='utf-8') as f:
            data = json.load(f)
        if key in list_keys and list_keys[key] != "MAP":
            mapped_data = {}
            id_fields = list_keys[key]
            for item in data:
                if key == "charaMessageList":
                    k = f"{item.get('charaNo', '')}_{item.get('messageId', '')}"
                elif key == "live2dList":
                    k = f"{item.get('charaId', '')}_{item.get('live2dId', '')}"
                else:
                    k = ""
                    for field in id_fields:
                        if field in item: k = str(item[field]); break
                if k and k != "_": mapped_data[k] = item
            js_dict[key] = mapped_data
            print(f"  [√] {key.ljust(20)} : 提取 {len(mapped_data)} 条")
        else:
            js_dict[key] = data
            print(f"  [√] {key.ljust(20)} : 提取 {len(data)} 条 (Map)")
        success_count += 1
    except Exception as e:
        print(f"  [X] {key.ljust(20)} : 失败: {e}")

dict_json_str = json.dumps(js_dict, ensure_ascii=False, separators=(',', ':')).replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')

# === 注入代码模板 ===
#
# 这段 JS 会被追加到纯净版 jQuery 后面，是整个运行时汉化的全部逻辑：
# 把 JSON.parse 与 XMLHttpRequest 挂钩，对每个解析出来的对象按 id 查上面
# 那 23 张字典，就地改写字段。
#
# ⚠ 改这段时守住两条铁律（都是踩过的坑）：
#
#  1. **每一次赋值都要 if 保护**。写 `o.title = t.title` 而字典里没有
#     `title`，o.title 就变成 undefined；下面的 XHR 钩子会
#     JSON.stringify 重新序列化响应，而 stringify 会把值为 undefined 的键
#     **整个删掉**。原本好好的字段就这么无声消失了。
#  2. **不要靠裸 o.id 猜类型**。任何带 {id, name} 的对象都可能撞上某张字典
#     的 key。要匹配 id，必须同时用父键名（pk）或该类型独有的字段把作用域
#     限定住，例如 pk.indexOf('shopitem')>=0、o.shopId!==undefined。
#
js_code = """
(function(){
    var cn = """ + dict_json_str + """;
    function applyRuntimeSkill(o,m){
        if(!m) return;
        if(m.name) o.name=m.name;
        if(m.shortDescription){
            if(o.shortDescription!==undefined) o.shortDescription=m.shortDescription;
            if(o.description!==undefined) o.description=m.shortDescription;
        }
    }
    function tr(o,p){
        if(Array.isArray(o)){ for(var i=0;i<o.length;i++) tr(o[i],p); }
        else if(o && typeof o==='object'){
            var pk=String(p||'').toLowerCase();
            var t=null,m=null,id=null;
            var live2dHit=false,doppelSkillHit=false;

            if(o.charaId!==undefined && o.live2dId!==undefined){
                id=String(o.charaId)+'_'+String(o.live2dId); t=cn.live2dList[id];
                if(t && t.description){ o.description=t.description; live2dHit=true; }
            }

            id=o.charaNo||o.charaId||((pk.indexOf('chara')>=0 && o.id!==undefined)?o.id:null);
            if(id!==null && id!==undefined && cn.charaList[id]){
                t=cn.charaList[id];
                if(t.name){ o.name=t.name; o.charaName=t.name; if(o.kana!==undefined)o.kana=t.kana||t.name; }
                if(t.title && o.title!==undefined)o.title=t.title;
                if(t.school)o.school=t.school;
                if(t.designer)o.designer=t.designer;
                if(t.voiceActor)o.voiceActor=t.voiceActor;
                if(t.description && !live2dHit && o.live2dId===undefined)o.description=t.description;
            }

            if(o.doppelId!==undefined && o.description!==undefined && o.id===undefined &&
               (pk.indexOf('doppel')>=0 || o.doppelMagiaId!==undefined)){
                id=Math.floor(Number(o.doppelId)/100)*10+8;
                m=cn.doppelCardMagiaMap[id];
                if(m){ applyRuntimeSkill(o,m); doppelSkillHit=true; }
            }

            id=(o.id!==undefined && (pk.indexOf('doppel')>=0 || (o.title!==undefined && o.designer!==undefined && o.description!==undefined)))?o.id:null;
            if(!doppelSkillHit && id!==null && cn.doppelList[id]){
                t=cn.doppelList[id];
                if(t.name)o.name=t.name;
                if(t.title)o.title=t.title;
                if(t.description)o.description=t.description;
                if(t.designer)o.designer=t.designer;
            }

            if(o.sectionId!==undefined && cn.sectionList[o.sectionId]){
                t=cn.sectionList[o.sectionId];
                if(t.areaDetailName)o.areaDetailName=t.areaDetailName;
                if(t.title)o.title=t.title;
                if(t.charaName)o.charaName=t.charaName;
                if(t.message)o.message=t.message;
                if(t.outline)o.outline=t.outline;
            }
            if(o.cardId!==undefined && cn.cardList[o.cardId]){
                t=cn.cardList[o.cardId]; if(t.cardName)o.cardName=t.cardName;
                if(t.illustrator)o.illustrator=t.illustrator;
            }

            id=o.enemyId||((pk.indexOf('enemy')>=0 && o.id!==undefined)?o.id:null);
            if(id!==null && id!==undefined && cn.enemyList[id]){
                t=cn.enemyList[id]; if(t.name)o.name=t.name; if(t.title)o.title=t.title;
                if(t.description)o.description=t.description; if(t.designer)o.designer=t.designer;
            }
            id=o.pieceId||((pk.indexOf('piece')>=0 && o.pieceName!==undefined && o.id!==undefined)?o.id:null);
            if(id!==null && id!==undefined && cn.pieceList[id]){
                t=cn.pieceList[id]; if(t.pieceName){o.pieceName=t.pieceName;if(o.name!==undefined)o.name=t.pieceName;}
                if(t.description)o.description=t.description; if(t.illustrator)o.illustrator=t.illustrator;
            }
            id=o.itemCode||o.itemId||((pk.indexOf('itemlist')>=0 && o.id!==undefined)?o.id:null);
            if(id!==null && id!==undefined && cn.itemList[id]){
                t=cn.itemList[id]; if(t.name)o.name=t.name; if(t.shortDescription)o.shortDescription=t.shortDescription;
                if(t.description)o.description=t.description; if(t.unit)o.unit=t.unit; if(t.parameter)o.parameter=t.parameter;
            }
            id=o.shopItemId||((((pk.indexOf('shopitem')>=0)||o.shopId!==undefined||o.shopItemType!==undefined)) && o.id!==undefined?o.id:null);
            if(id!==null && id!==undefined && cn.shopItemList[id]){
                t=cn.shopItemList[id]; if(t.name)o.name=t.name; if(t.description)o.description=t.description;
            }

            m=null;
            if(o.doppelMagiaId!==undefined)m=cn.doppelCardMagiaMap[o.doppelMagiaId];
            else if(o.magiaId!==undefined)m=cn.cardMagiaMap[o.magiaId];
            else if(o.connectId!==undefined)m=cn.cardSkillMap[o.connectId];
            else if(o.memoriaId!==undefined)m=cn.pieceSkillMap[o.memoriaId];
            else if(o.skillId!==undefined){
                if(pk.indexOf('emotion')>=0)m=cn.emotionSkillMap[o.skillId];
                else if(pk.indexOf('piece')>=0 || pk.indexOf('memoria')>=0)m=cn.pieceSkillMap[o.skillId];
                else if(pk.indexOf('place')>=0)m=cn.placeSkillMap[o.skillId];
                else m=cn.cardSkillMap[o.skillId]||cn.emotionSkillMap[o.skillId]||cn.pieceSkillMap[o.skillId]||cn.placeSkillMap[o.skillId];
            }else if(o.id!==undefined && (o.shortDescription!==undefined||o.name!==undefined)){
                if(pk.indexOf('doppel')>=0)m=cn.doppelCardMagiaMap[o.id];
                else if(pk.indexOf('magia')>=0)m=cn.cardMagiaMap[o.id];
                else if(pk.indexOf('emotion')>=0)m=cn.emotionSkillMap[o.id];
                else if(pk.indexOf('piece')>=0 || pk.indexOf('memoria')>=0)m=cn.pieceSkillMap[o.id];
                else if(pk.indexOf('place')>=0)m=cn.placeSkillMap[o.id];
                else if(pk.indexOf('skill')>=0 || pk.indexOf('connect')>=0)m=cn.cardSkillMap[o.id];
            }
            applyRuntimeSkill(o,m);

            id=o.formationSheetId||(((o.sheetType!==undefined || pk.indexOf('formationsheet')>=0)) && o.id!==undefined?o.id:null);
            if(id!==null && id!==undefined && cn.formationSheetList[id]){
                t=cn.formationSheetList[id]; if(t.name)o.name=t.name; if(t.description)o.description=t.description;
            }
            id=o.giftId||((pk.indexOf('gift')>=0 && o.id!==undefined && o.type!==undefined && o.rank!==undefined && o.name!==undefined)?o.id:null);
            if(id!==null && id!==undefined && cn.giftList[id] && cn.giftList[id].name)o.name=cn.giftList[id].name;
            if(o.patrolAreaId!==undefined && cn.patrolAreaList[o.patrolAreaId]){
                t=cn.patrolAreaList[o.patrolAreaId]; if(t.areaName)o.areaName=t.areaName;
                if(t.conditionDescription)o.conditionDescription=t.conditionDescription;
            }

            if(o.chapterId!==undefined && cn.chapterList[o.chapterId]){
                t=cn.chapterList[o.chapterId]; if(t.title)o.title=t.title;
                if(t.chapterNoForView)o.chapterNoForView=t.chapterNoForView;
            }
            if(o.eventId!==undefined && cn.eventList[o.eventId] && cn.eventList[o.eventId].eventName)o.eventName=cn.eventList[o.eventId].eventName;
            if(o.storyIds!==undefined && cn.eventStoryList[o.storyIds]){
                t=cn.eventStoryList[o.storyIds]; if(t.storyTitle)o.storyTitle=t.storyTitle; if(t.pointTitle)o.pointTitle=t.pointTitle;
            }
            if(o.charaNo!==undefined && o.messageId!==undefined){
                id=String(o.charaNo)+'_'+String(o.messageId); if(cn.charaMessageList[id] && cn.charaMessageList[id].message)o.message=cn.charaMessageList[id].message;
            }
            if(o.endMessageId!==undefined && o.endMessage!==undefined){
                id=o.charId||(o.miniCharId?String(o.miniCharId).substring(0,4):null);
                if(id){var endKey=String(id)+'_'+String(o.endMessageId);if(cn.charaMessageList[endKey]&&cn.charaMessageList[endKey].message)o.endMessage=cn.charaMessageList[endKey].message;}
            }
            if(o.arenaBattleFreeRankClass!==undefined && cn.arenaClassList[o.arenaBattleFreeRankClass]){
                t=cn.arenaClassList[o.arenaBattleFreeRankClass]; if(t.className)o.className=t.className;
                if(t.nextClassName)o.nextClassName=t.nextClassName; if(t.storyTitle)o.storyTitle=t.storyTitle;
            }

            for(var key in o){if(o.hasOwnProperty(key)&&o[key]!==null)tr(o[key],key);}
        }
    }
    var _op = JSON.parse; JSON.parse = function(text, r){ var j = _op(text, r); if(j && typeof j === 'object'){ try { tr(j, null); } catch(e){} } return j; };
    var _ox = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function(){ this.addEventListener('readystatechange', function(){ if(this.readyState === 4 && (this.responseType === '' || this.responseType === 'text') && this.responseText){ try { var fc = this.responseText.trim().charAt(0); if(fc === '{' || fc === '['){ var jo = JSON.parse(this.responseText); var ts = JSON.stringify(jo); Object.defineProperty(this, 'responseText', { value: ts, configurable: true }); if(this.response !== undefined) Object.defineProperty(this, 'response', { value: ts, configurable: true }); } } catch(e){} } }); return _ox.apply(this, arguments); };
    console.warn("MagiaCN 终极金标版运行中 (23字典全开)");

    window.__MAGIACN_RUNTIME_I18N__ = {packageId:"v3-authoritative-cn-dump-pass6-llm-batch1",schema:1,authority:"CN-APK-2.2.1+CN-DUMP-2022-10-10",machineTranslation:false};
})();
"""

# 读取刚才复制过去的原版 JS
with open(TARGET_JQUERY_PATH, 'r', encoding='utf-8') as f:
    jquery_base = f.read()

# 写入注入后的 JS
with open(TARGET_JQUERY_PATH, 'w', encoding='utf-8') as f:
    f.write(jquery_base + "\n" + js_code)

print(f"\n>>> [步骤 3] 终极金标版注入成功！共计打包 {success_count}/23 个文件。")