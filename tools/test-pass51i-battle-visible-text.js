#!/usr/bin/env node
"use strict";
const fs=require("fs"),path=require("path"),vm=require("vm");
const root=path.resolve(process.argv[2]||path.join(__dirname,"..","candidate-root"));
const libs=path.join(root,"magica","js","libs");
function readJson(p){return JSON.parse(fs.readFileSync(p,"utf8").replace(/^\uFEFF/,""));}
function assert(x,m){if(!x)throw new Error(m);}
function extractPayload(source){const marker="var cn = ";const start=source.indexOf(marker);if(start<0)throw new Error("payload marker missing");let i=start+marker.length,payloadStart=i,depth=0,inString=false,escaped=false;for(;i<source.length;i++){const ch=source[i];if(inString){if(escaped)escaped=false;else if(ch==="\\")escaped=true;else if(ch==='"')inString=false;continue;}if(ch==='"')inString=true;else if(ch==="{")depth++;else if(ch==="}"){depth--;if(depth===0)return JSON.parse(source.slice(payloadStart,i+1));}}throw new Error("payload unterminated");}
function extractFunction(source,name){const marker=`function ${name}(`,start=source.indexOf(marker);if(start<0)throw new Error(`${name} missing`);const body=source.indexOf("{",start);let depth=0,inString=false,quote="",escaped=false;for(let i=body;i<source.length;i++){const ch=source[i];if(inString){if(escaped)escaped=false;else if(ch==="\\")escaped=true;else if(ch===quote)inString=false;continue;}if(ch==='"'||ch==="'"){inString=true;quote=ch;}else if(ch==="{")depth++;else if(ch==="}"){depth--;if(depth===0)return source.slice(start,i+1);}}throw new Error(`${name} unterminated`);}
const engine=fs.readFileSync(path.join(root,"madomagi","engine_i18n.tsv"),"utf8").split(/\r?\n/);
const engineExpected=new Map([["10 4話","第10章 第4话"],["The Revelation Ritual","默示天灾"]]);
for(const [source,target] of engineExpected){const rows=engine.filter(x=>x===`${source}\t${target}`);assert(rows.length===1,`engine exact row mismatch: ${source}`);assert(engine.filter(x=>x.startsWith(source+"\t")).length===1,`engine source conflict: ${source}`);}
const canonical=readJson(path.join(libs,"pieceSkillMap.json"))["15022"];
assert(canonical.name==="通向未来的桥梁(最大解放)","canonical name drift");
assert(canonical.shortDescription==="战斗开始时获得“全Disk效果提升[Ⅱ] & 暴击无效×2回(己全/∞)”的状态","canonical shortDescription drift");
const runtime=readJson(path.join(libs,"runtimeEntityFieldMap.json"));
const key='["PIECE_SKILL","15022"]',bucket=runtime[key];assert(bucket,"stable bucket missing");
const sources={name:"Bridge to the Future (Max Limit Break)",shortDescription:'Activate "All Disk Effect UP [II] / Critical Damage Negated (2 Times) (Team/∞)" at Quest Start'};
for(const field of Object.keys(sources)){const rule=bucket[field]&&bucket[field][sources[field]];assert(rule,`rule missing ${field}`);assert(rule.source===sources[field],`source drift ${field}`);assert(rule.target===canonical[field],`canonical conflict ${field}`);}
const jquerySource=fs.readFileSync(path.join(libs,"jquery-3.7.1.min.js"),"utf8"),payload=extractPayload(jquerySource);assert(JSON.stringify(payload.runtimeEntityFieldMap[key])===JSON.stringify(bucket),"rebuilt payload mismatch");
const sandbox={cn:{runtimeEntityFieldMap:payload.runtimeEntityFieldMap},JSON,Object,String};vm.createContext(sandbox);vm.runInContext(`${extractFunction(jquerySource,"getEntityFieldSlot")};${extractFunction(jquerySource,"applyEntityBucket")};${extractFunction(jquerySource,"applyEntityFieldRules")};this.applyEntityFieldRules=applyEntityFieldRules;`,sandbox);
function apply(o,p){const raw=sandbox.applyEntityFieldRules(o,p,{},true,false);sandbox.applyEntityFieldRules(o,p,raw,false,false);sandbox.applyEntityFieldRules(o,p,raw,false,true);return o;}
const positive=apply({id:15022,groupId:1090,name:sources.name,shortDescription:sources.shortDescription},"maxPieceSkillList");assert(positive.name===canonical.name,"positive name failed");assert(positive.shortDescription===canonical.shortDescription,"positive description failed");
const wrongSource=apply({id:15022,groupId:1090,name:sources.name+"X",shortDescription:sources.shortDescription+"X"},"maxPieceSkillList");assert(wrongSource.name===sources.name+"X","wrong name changed");assert(wrongSource.shortDescription===sources.shortDescription+"X","wrong description changed");
const wrongParent=apply({id:15022,groupId:1090,name:sources.name,shortDescription:sources.shortDescription},"cardSkillList");assert(wrongParent.name===sources.name&&wrongParent.shortDescription===sources.shortDescription,"wrong parent changed");
const unknown=apply({id:99999,groupId:1090,name:sources.name,shortDescription:sources.shortDescription},"maxPieceSkillList");assert(unknown.name===sources.name&&unknown.shortDescription===sources.shortDescription,"unknown id changed");
const messageKey='["CHARA_MESSAGE","1041|45"]',messageSource="汗かいたしベタベタやわ、\n帰りは銭湯にでも寄ろか",messageTarget="出了汗浑身黏糊糊的，回去的时候顺便去澡堂\n吧";
const messageBucket=runtime[messageKey],messageRule=messageBucket&&messageBucket.message&&messageBucket.message[messageSource];assert(messageRule,"message rule missing");assert(messageRule.target===messageTarget,"message target drift");assert(JSON.stringify(payload.runtimeEntityFieldMap[messageKey])===JSON.stringify(messageBucket),"message rebuilt payload mismatch");
const messagePositive=apply({charaNo:1041,messageId:45,message:messageSource},"charaMessageList");assert(messagePositive.message===messageTarget,"message positive failed");
const messageWrongSource=apply({charaNo:1041,messageId:45,message:messageSource+"X"},"charaMessageList");assert(messageWrongSource.message===messageSource+"X","message wrong source changed");
const messageWrongId=apply({charaNo:1041,messageId:44,message:messageSource},"charaMessageList");assert(messageWrongId.message===messageSource,"message wrong id changed");
const messageWrongChara=apply({charaNo:9999,messageId:45,message:messageSource},"charaMessageList");assert(messageWrongChara.message===messageSource,"message wrong chara changed");
console.log("PASS51I_BATTLE_VISIBLE_TEXT=PASS");console.log("ENGINE_EXACT=2");console.log("PIECE_SKILL_FIELDS=2");console.log("CHARA_MESSAGE_FIELDS=1");console.log("POSITIVE=3");console.log("WRONG_SOURCE_UNCHANGED=3");console.log("WRONG_PARENT_UNCHANGED=2");console.log("WRONG_ID_UNCHANGED=1");console.log("UNKNOWN_ID_UNCHANGED=3");
