const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..')),base=process.argv[3]&&path.resolve(process.argv[3]);
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'../magica/i18n_audit/existing_text_review_20260923/batch08-corrections.json'),'utf8'));
const fix=audit.changes[0];assert.equal(audit.changes.length,1);assert.equal(fix.id,'1040|11');
const copy=o=>JSON.parse(JSON.stringify(o));
function runtime(dir){
 const s=fs.readFileSync(path.join(dir,'magica/js/libs/jquery-3.7.1.min.js'),'utf8');const at=s.indexOf('    var cn = '),start=s.lastIndexOf('(function(){',at);assert(at>0&&start>0);
 const c={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};c.XMLHttpRequest.prototype.open=function(){};
 vm.createContext(c);vm.runInContext(s.slice(start),c,{timeout:15000});
 return {tr:(o,p)=>{c.window.__MAGIACN_TRANSLATE__(o,p);return o;},parse:o=>{c.input=JSON.stringify(o);return JSON.parse(JSON.stringify(vm.runInContext('JSON.parse(input)',c)));}};
}
const read=dir=>JSON.parse(fs.readFileSync(path.join(dir,'magica/js/libs/charaMessageList.json'),'utf8'));
const rows=read(root),tr=runtime(root),old=base?runtime(base):null;
assert.equal(rows.find(x=>x.charaNo===1040&&x.messageId===11).message,fix.after);
let positive=0,controls=0,idempotence=0;
for(const input of [{charaNo:1040,messageId:11,message:fix.ja},{charaNo:'1040',messageId:'11',message:fix.ja},{charaNo:1040,messageId:11,message:fix.before}]){
 const x=tr.tr(copy(input),'charaMessageList');assert.equal(x.message,fix.after);positive++;
 assert.equal(x.charaNo,input.charaNo);assert.equal(x.messageId,input.messageId);
 const once=JSON.stringify(x);tr.tr(x,'charaMessageList');assert.equal(JSON.stringify(x),once);idempotence++;
}
const nested={userCharaList:[{chara:{charaMessageList:[{charaNo:1040,messageId:11,message:fix.ja}]}}]};
assert.equal(tr.parse(nested).userCharaList[0].chara.charaMessageList[0].message,fix.after);positive++;
for(const input of [{charId:1040,endMessageId:11,endMessage:fix.ja},{miniCharId:104000,endMessageId:11,endMessage:fix.ja}]){
 assert.equal(tr.tr(copy(input),'result').endMessage,fix.after);positive++;
}
for(const input of [{charaNo:99999,messageId:11,message:fix.ja},{charaNo:1040,messageId:99999,message:fix.ja},{messageId:11,message:fix.ja},{charaNo:1040,message:fix.ja},{id:1040,messageId:11,message:fix.ja}]){
 assert.deepStrictEqual(tr.tr(copy(input),'unrelated'),input);controls++;
}
if(base){
 const before=read(base);assert.equal(rows.length,before.length);
 for(let i=0;i<rows.length;i++){
  const expected=copy(before[i]);if(expected.charaNo===1040&&expected.messageId===11)expected.message=fix.after;
  assert.deepStrictEqual(rows[i],expected,'only selected existing message changes');
  if(expected.charaNo===1040&&expected.messageId===11)continue;
  const input={charaNo:expected.charaNo,messageId:expected.messageId,message:'UNCHANGED_CONTROL'};
  assert.deepStrictEqual(tr.tr(copy(input),'charaMessageList'),old.tr(copy(input),'charaMessageList'));controls++;
 }
}
console.log(JSON.stringify({status:'PASS',corrections:1,positive,controls,idempotence,voiceRecords:rows.length,jsonParseIntegration:true,audioTranscription:false}));
