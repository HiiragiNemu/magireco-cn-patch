// Exercise generated production translation code, rather than only the dictionary files.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const base=process.argv[3]&&path.resolve(process.argv[3]);
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'../magica/i18n_audit/existing_text_review_20260923/batch04-corrections.json'),'utf8'));
const copy=o=>JSON.parse(JSON.stringify(o));
function runtime(dir){
 const s=fs.readFileSync(path.join(dir,'magica/js/libs/jquery-3.7.1.min.js'),'utf8');
 const at=s.indexOf('    var cn = '),start=s.lastIndexOf('(function(){',at);assert(at>0&&start>0);
 const c={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};
 c.XMLHttpRequest.prototype.open=function(){};vm.createContext(c);vm.runInContext(s.slice(start),c,{timeout:15000});
 return {tr:(o,p)=>{c.window.__MAGIACN_TRANSLATE__(o,p);return o;},parse:o=>{c.input=JSON.stringify(o);return JSON.parse(JSON.stringify(vm.runInContext('JSON.parse(input)',c)));}};
}
const tr=runtime(root),old=base?runtime(base):null;let positive=0,controls=0;
for(const f of audit.changes){
 if(f.table!=='pieceSkillMap')continue;
 const lib=JSON.parse(fs.readFileSync(path.join(root,'magica/js/libs/pieceSkillMap.json'),'utf8'))[f.id];
 assert.equal(lib.shortDescription,f.after,'dictionary '+f.id);
 for(const input of [{id:Number(f.id),groupId:100,shortDescription:f.ja,description:f.ja,name:'original',eventDescription:'event original',cost:17},{skillId:Number(f.id),shortDescription:f.ja,name:'original'},{memoriaId:Number(f.id),shortDescription:f.ja,name:'original'}]){
  const x=tr.tr(copy(input),'pieceSkill');assert.equal(x.shortDescription,f.after,'runtime '+f.id);positive++;
  if(input.description!==undefined){assert.equal(x.description,f.after);positive++;}
  for(const key of Object.keys(input))if(!['shortDescription','description','name','eventDescription'].includes(key))assert.deepStrictEqual(x[key],input[key]);
  const first=JSON.stringify(x);tr.tr(x,'pieceSkill');assert.equal(JSON.stringify(x),first,'idempotence');
 }
 const nested={userPieceList:[{pieceId:Math.floor(Number(f.id)/100),piece:{pieceSkill:{id:Number(f.id),groupId:100,shortDescription:f.ja,description:f.ja,name:'original'}}}]};
 assert.equal(tr.parse(nested).userPieceList[0].piece.pieceSkill.shortDescription,f.after,'JSON.parse nested');positive++;
 if(old){
  for(const [obj,parent] of [[{id:99999999,shortDescription:f.ja},'pieceSkill'],[{id:Number(f.id),shortDescription:f.ja},'itemList'],[{id:Number(f.id),shortDescription:f.ja},'unrelated'],[{id:Number(f.id),shortDescription:f.ja},'cardSkill'],[{id:Number(f.id),name:'x',eventDescription:'x'},'pieceSkill']]){
   assert.deepStrictEqual(tr.tr(copy(obj),parent),old.tr(copy(obj),parent),'control '+f.id+'/'+parent);controls++;
  }
  const before=JSON.parse(fs.readFileSync(path.join(base,'magica/js/libs/pieceSkillMap.json'),'utf8'))[f.id];
  assert.equal(lib.eventDescription,before.eventDescription,'event bonus retained');assert.equal(lib.name,before.name);
 }
}
const f=audit.changes.find(x=>x.table==='pieceList');assert(f);
for(const parent of ['pieceList','piece','memoria']){
 const x={pieceId:1713,pieceName:'original',description:f.ja,rarity:4};tr.tr(x,parent);assert.equal(x.description,f.after,'memoria text');assert.equal(x.rarity,4);positive++;
 const first=JSON.stringify(x);tr.tr(x,parent);assert.equal(JSON.stringify(x),first);
}
if(old){
 const before=JSON.parse(fs.readFileSync(path.join(base,'magica/js/libs/pieceSkillMap.json'),'utf8'));
 const changed=new Set(audit.changes.filter(x=>x.table==='pieceSkillMap').map(x=>x.id));
 for(const id of Object.keys(before))if(!changed.has(id)){
  const input={id:Number(id),name:'unchanged-control',shortDescription:'unchanged-control',groupId:100};
  assert.deepStrictEqual(tr.tr(copy(input),'pieceSkill'),old.tr(copy(input),'pieceSkill'),'unrelated skill '+id);controls++;
 }
}
console.log(JSON.stringify({status:'PASS',corrections:audit.changes.length,positive,controls,jsonParseIntegration:true,idempotent:true,eventBonusPreserved:true,numericGameFieldsChanged:0}));
