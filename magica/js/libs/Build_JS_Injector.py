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

for filename in os.listdir(TARGET_DIR):
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

# === 完全保留你原版的 JS 排版，一字未改 ===
js_code = """
(function(){
    var cn = """ + dict_json_str + """;
    function tr(o, p){
        if(Array.isArray(o)){ for(var i=0; i<o.length; i++) tr(o[i], p); }
        else if(o && typeof o === 'object'){
            var isTranslated = false;

            // 1. 服装/Live2D (高优先级独立逻辑，防止冲突)
            if(o.charaId && o.live2dId){
                var lk = o.charaId + "_" + o.live2dId;
                if(cn.live2dList[lk]){ o.description = cn.live2dList[lk].description; isTranslated = true; }
            }

            // 2. 角色档案 (CV、学校、名字)
            var chId = o.charaNo || o.charaId || (p==='chara'?o.id:null);
            if(chId && cn.charaList[chId]){ 
                var t = cn.charaList[chId]; 
                if(t.name){ o.name = t.name; o.charaName = t.name; if(o.kana) o.kana = t.name; }
                if(t.school) o.school = t.school; if(t.designer) o.designer = t.designer; if(t.voiceActor) o.voiceActor = t.voiceActor;
                if(t.description && !isTranslated && !o.live2dId) o.description = t.description; 
            }

            // 3. 魔女化身 (Doppel - 强力匹配)
            var dId = o.doppelId || (p==='doppel'?o.id:null) || (o.id && cn.doppelList[o.id] ? o.id : null);
            if(dId && cn.doppelList[dId]){ 
                var t = cn.doppelList[dId]; 
                if(t.name) o.name = t.name; if(t.title) o.title = t.title; if(t.description) o.description = t.description; if(t.designer) o.designer = t.designer; 
            }

            // 4. 关卡与卡片
            if(o.sectionId && cn.sectionList[o.sectionId]){ var t=cn.sectionList[o.sectionId]; if(t.areaDetailName) o.areaDetailName=t.areaDetailName; if(t.title) o.title=t.title; if(t.charaName) o.charaName=t.charaName; if(t.message) o.message=t.message; if(t.outline) o.outline=t.outline; }
            if(o.cardId && cn.cardList[o.cardId]){ var t=cn.cardList[o.cardId]; o.cardName=t.cardName; if(t.illustrator) o.illustrator=t.illustrator; }

            // 5. 记忆结晶/使魔/道具/商店
            var eId = o.enemyId || (p==='enemy'?o.id:null);
            if(eId && cn.enemyList[eId]){ var t=cn.enemyList[eId]; o.name=t.name; o.title=t.title; o.description=t.description; o.designer=t.designer; }
            var pId = o.pieceId || (p==='piece'?o.id:null);
            if(pId && cn.pieceList[pId]){ var t=cn.pieceList[pId]; if(t.pieceName){ o.pieceName=t.pieceName; if(o.name)o.name=t.pieceName; } if(t.description) o.description=t.description; if(t.illustrator) o.illustrator=t.illustrator; }
            var ic = o.itemCode || o.itemId || (p==='item'?o.id:null);
            if(ic && cn.itemList[ic]){ var t=cn.itemList[ic]; o.name=t.name; o.shortDescription=t.shortDescription; o.description=t.description; o.unit=t.unit; }
            var sid = o.shopItemId || (p==='shopItem'?o.id:null);
            if(sid && cn.shopItemList[sid]){ o.name=cn.shopItemList[sid].name; o.description=cn.shopItemList[sid].description; }

            // 6. 技能/魔法/加护/阵型/礼物/巡逻 (全量覆盖)
            var skId = o.skillId || o.magiaId || o.doppelMagiaId || (o.id && (o.shortDescription!==undefined || o.name!==undefined)?o.id:null);
            if(skId){ var m = cn.cardMagiaMap[skId]||cn.doppelCardMagiaMap[skId]||cn.cardSkillMap[skId]||cn.emotionSkillMap[skId]||cn.pieceSkillMap[skId]||cn.placeSkillMap[skId]; if(m){ if(m.name) o.name=m.name; if(m.shortDescription) o.shortDescription=m.shortDescription; } }
            var fId = o.formationSheetId || ((o.name && o.description)?o.id:null);
            if(fId && cn.formationSheetList[fId]){ o.name=cn.formationSheetList[fId].name; o.description=cn.formationSheetList[fId].description; }
            var gId = o.giftId || (p==='gift'?o.id:null);
            if(gId && cn.giftList[gId]) o.name=cn.giftList[gId].name;
            if(o.patrolAreaId && cn.patrolAreaList[o.patrolAreaId]){ o.areaName=cn.patrolAreaList[o.patrolAreaId].areaName; o.conditionDescription=cn.patrolAreaList[o.patrolAreaId].conditionDescription; }

            // 7. 章节/台词/活动/镜层
            if(o.chapterId && cn.chapterList[o.chapterId]) o.title=cn.chapterList[o.chapterId].title;
            if(o.eventId && cn.eventList[o.eventId]) o.eventName=cn.eventList[o.eventId].eventName;
            if(o.storyIds && cn.eventStoryList[o.storyIds]){ var t=cn.eventStoryList[o.storyIds]; o.storyTitle=t.storyTitle; if(t.pointTitle) o.pointTitle=t.pointTitle; }
            if(o.charaNo && o.messageId){ var k=o.charaNo+"_"+o.messageId; if(cn.charaMessageList[k]) o.message=cn.charaMessageList[k].message; }
            if(o.endMessageId && o.endMessage){ var bId = o.charId || (o.miniCharId?String(o.miniCharId).substring(0,4):null); if(bId){ var bk=bId+"_"+o.endMessageId; if(cn.charaMessageList[bk]) o.endMessage=cn.charaMessageList[bk].message; } }
            if(o.arenaBattleFreeRankClass && cn.arenaClassList[o.arenaBattleFreeRankClass]){ var t=cn.arenaClassList[o.arenaBattleFreeRankClass]; o.className=t.className; o.nextClassName=t.nextClassName; o.storyTitle=t.storyTitle; }

            for(var key in o){ if(o.hasOwnProperty(key) && o[key] !== null) tr(o[key], key); }
        }
    }
    var _op = JSON.parse; JSON.parse = function(text, r){ var j = _op(text, r); if(j && typeof j === 'object'){ try { tr(j, null); } catch(e){} } return j; };
    var _ox = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function(){ this.addEventListener('readystatechange', function(){ if(this.readyState === 4 && (this.responseType === '' || this.responseType === 'text') && this.responseText){ try { var fc = this.responseText.trim().charAt(0); if(fc === '{' || fc === '['){ var jo = JSON.parse(this.responseText); var ts = JSON.stringify(jo); Object.defineProperty(this, 'responseText', { value: ts, configurable: true }); if(this.response !== undefined) Object.defineProperty(this, 'response', { value: ts, configurable: true }); } } catch(e){} } }); return _ox.apply(this, arguments); };
    console.warn("MagiaCN 终极金标版运行中 (23字典全开)");
})();
"""

# 读取刚才复制过去的原版 JS
with open(TARGET_JQUERY_PATH, 'r', encoding='utf-8') as f:
    jquery_base = f.read()

# 写入注入后的 JS
with open(TARGET_JQUERY_PATH, 'w', encoding='utf-8') as f:
    f.write(jquery_base + "\n" + js_code)

print(f"\n>>> [步骤 3] 终极金标版注入成功！共计打包 {success_count}/23 个文件。")