#!/usr/bin/env node
"use strict";
const fs=require("fs"),path=require("path");
const root=path.resolve(process.argv[2]||path.join(__dirname,".."));
const denominatorPath=path.resolve(process.argv[3]||path.join(root,"..","evidence","battle-skill-settlement-denominator.json"));
function readJson(p){return JSON.parse(fs.readFileSync(p,"utf8").replace(/^\uFEFF/,""));}
function assert(x,m){if(!x)throw new Error(m);}
const lines=fs.readFileSync(path.join(root,"madomagi","engine_i18n.tsv"),"utf8").split(/\r?\n/).filter(x=>x&&!x.startsWith("#"));
const pairs=new Map();
for(const line of lines){const i=line.indexOf("\t");assert(i>0,"malformed engine row");const s=line.slice(0,i),t=line.slice(i+1);assert(!pairs.has(s),`duplicate source: ${s}`);pairs.set(s,t);}
assert(pairs.size===702,`engine rule count ${pairs.size}`);
const added=new Map([
  ["Bridge to the Future (Max Limit Break)","通向未来的桥梁(最大解放)"],
  ['Activate "All Disk Effect UP [II] / Critical Damage Negated (2 Times) (Team/∞)" at Quest Start',"战斗开始时获得“全Disk效果提升[Ⅱ] & 暴击无效×2回(己全/∞)”的状态"],
  ["呪い付与攻撃(アビリティ) & スタン付与攻撃(アビリティ)","诅咒攻击(能力) & 眩晕攻击(能力)"],
  ["攻撃時に確率で呪い(1T)を付与 ＆ 攻撃時に確率でスタン(1T)を付与","攻击时概率给予诅咒状态(1T) & 攻击时概率给予眩晕状态(1T)"],
  ["デバフ解除 ＆ 攻撃力アップ","解除减益 & 攻击力提升"],
  ["これは魔法少女の\\n歴史がつかんだ勝利よ","这是魔法少女的\\n历史所取得的胜利。"],
]);
for(const [s,t] of added){assert(pairs.get(s)===t,`exact row mismatch: ${s}`);assert(lines.filter(x=>x===`${s}\t${t}`).length===1,`exact row count: ${s}`);assert(!pairs.has(s+"X"),`wrong source admitted: ${s}`);}
assert(pairs.get("クリティカル無効")==="暴击无效","inherited critical exact row drift");
assert(lines.filter(x=>x.startsWith("クリティカル無効\t")).length===1,"critical row duplicated");
assert(!pairs.has("呪い付与攻撃(アビリティ)＆スタン付与攻撃(アビリティ)"),"screenshot typography alias admitted");
assert(!pairs.has("攻撃時に確率で呪い(1T)を付与＆攻撃時に確率でスタン(1T)を付与"),"unproven spacing alias admitted");
function lookup(s){return pairs.has(s)?pairs.get(s):s;}
for(const [s,t] of added){assert(lookup(s)===t,"positive exact lookup failed");assert(lookup(s+"X")===s+"X","wrong source changed");}
const libs=path.join(root,"magica","js","libs");
const piece=readJson(path.join(libs,"pieceSkillMap.json"))["15022"];
assert(piece.name===added.get("Bridge to the Future (Max Limit Break)"),"PIECE name canonical drift");
assert(piece.shortDescription===added.get('Activate "All Disk Effect UP [II] / Critical Damage Negated (2 Times) (Team/∞)" at Quest Start'),"PIECE description canonical drift");
const runtime=readJson(path.join(libs,"runtimeEntityFieldMap.json"));
const pieceBucket=runtime['["PIECE_SKILL","15022"]'];assert(pieceBucket,"PIECE stable bucket missing");
for(const field of ["name","shortDescription"]){const source=field==="name"?"Bridge to the Future (Max Limit Break)":'Activate "All Disk Effect UP [II] / Critical Damage Negated (2 Times) (Team/∞)" at Quest Start';const rule=pieceBucket[field]&&pieceBucket[field][source];assert(rule&&rule.source===source&&rule.target===piece[field],`PIECE exact field rule ${field}`);}
const messageSource="これは魔法少女の@歴史がつかんだ勝利よ",messageTarget="这是魔法少女的@历史所取得的胜利。";
const messageBucket=runtime['["CHARA_MESSAGE","1502|45"]'];const messageRule=messageBucket&&messageBucket.message&&messageBucket.message[messageSource];assert(messageRule&&messageRule.target===messageTarget,"victory composite rule drift");
const messages=readJson(path.join(libs,"charaMessageList.json")).filter(x=>Number(x.charaNo)===1502&&Number(x.messageId)===45);assert(messages.length===1&&messages[0].message===messageTarget,"victory canonical row drift");
const den=readJson(denominatorPath);assert(den.summary.total===10,"denominator count drift");assert(den.summary.newEngineExact===6,"new exact count drift");assert(den.summary.deviceWrites===0,"device write boundary drift");
const voice=den.records.find(x=>x.stableIdentity==="CHARA_MESSAGE|1502|45");assert(voice&&voice.messageId===45&&voice.voiceSlot==="vo_char_1502_00_45","voice slot not proven");
const battle=den.records.find(x=>x.stableIdentity.startsWith("NATIVE_RESULT_ASSET|"));assert(battle&&battle.exactBefore==="Battle Clear"&&battle.target==="Battle Clear"&&battle.action==="AUTHORITY_PRESERVED","Battle Clear authority drift");
assert(den.records.every(x=>!String(x.changedPath||"").match(/\.(?:png|vfxt)$/i)),"image path entered manifest");
console.log("PASS51L_BATTLE_SKILL_SETTLEMENT=PASS");
console.log("DENOMINATOR=10");
console.log("NEW_ENGINE_EXACT=6");
console.log("ENGINE_RULES=702");
console.log("WRONG_SOURCE_UNCHANGED=6");
console.log("PIECE_COMPOSITE_FIELDS=2");
console.log("VICTORY_COMPOSITE=CHARA_MESSAGE|1502|45");
console.log("VOICE_SLOT=vo_char_1502_00_45");
console.log("BATTLE_CLEAR=AUTHORITY_PRESERVED");
console.log("IMAGE_WRITES=0");
