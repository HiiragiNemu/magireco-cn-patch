// Stable-ID name corrections exercised through the shipped injector, not a mock lookup.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const base=process.argv[3]&&path.resolve(process.argv[3]);
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'../magica/i18n_audit/existing_text_review_20260923/batch05-corrections.json'),'utf8'));
const copy=x=>JSON.parse(JSON.stringify(x));
function runtime(dir){
 const s=fs.readFileSync(path.join(dir,'magica/js/libs/jquery-3.7.1.min.js'),'utf8');
 const at=s.indexOf('    var cn = '),start=s.lastIndexOf('(function(){',at);assert(at>0&&start>0);
 const c={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};
 c.XMLHttpRequest.prototype.open=function(){};vm.createContext(c);vm.runInContext(s.slice(start),c,{timeout:15000});
 return {tr:(o,p)=>{c.window.__MAGIACN_TRANSLATE__(o,p);return o;},parse:o=>{c.input=JSON.stringify(o);return JSON.parse(JSON.stringify(vm.runInContext('JSON.parse(input)',c)));}};
}
const tr=runtime(root),old=base?runtime(base):null;
const read=dir=>JSON.parse(fs.readFileSync(path.join(dir,'magica/js/libs/pieceSkillMap.json'),'utf8'));
const lib=read(root),before=base?read(base):null;
const changed=new Set(audit.changes.map(x=>x.id));let positive=0,controls=0;
assert.equal(changed.size,11);
for(const f of audit.changes){
 assert.equal(lib[f.id].name,f.after,'dictionary '+f.id);
 for(const input of [{id:+f.id,groupId:100,name:f.ja,shortDescription:'original description',eventDescription:'original event',cost:17},{skillId:+f.id,name:f.ja},{memoriaId:+f.id,name:f.ja}]){
  const x=tr.tr(copy(input),'pieceSkill');assert.equal(x.name,f.after,'runtime '+f.id);positive++;
  for(const key of Object.keys(input))if(!['name','shortDescription','description','eventDescription'].includes(key))assert.deepStrictEqual(x[key],input[key]);
  const first=JSON.stringify(x);tr.tr(x,'pieceSkill');assert.equal(JSON.stringify(x),first,'idempotence');
  if(old){const expected=old.tr(copy(input),'pieceSkill');expected.name=f.after;assert.deepStrictEqual(x,expected,'only name changed '+f.id);controls++;}
 }
 const nested={userPieceList:[{pieceId:Math.floor(+f.id/100),piece:{pieceSkill:{id:+f.id,groupId:100,name:f.ja}}}]};
 assert.equal(tr.parse(nested).userPieceList[0].piece.pieceSkill.name,f.after,'nested JSON.parse');positive++;
 if(old){
  for(const parent of ['itemList','cardSkill','unrelated']){
   const input={id:+f.id,name:f.ja,shortDescription:'unrelated'};
   assert.deepStrictEqual(tr.tr(copy(input),parent),old.tr(copy(input),parent),'foreign table '+parent);controls++;
  }
  const input={id:99999999,name:f.ja,shortDescription:'unrelated'};
  assert.deepStrictEqual(tr.tr(copy(input),'pieceSkill'),old.tr(copy(input),'pieceSkill'),'unknown ID');controls++;
 }
}
// Both true charm effects and inherited official names must survive; no blanket replacement.
for(const [id,name] of [['116100','魅惑之刃[Ⅱ]'],['116101','魅惑之刃[Ⅲ]'],['122200','迷人幻象[Ⅲ]'],['122201','迷人幻象[Ⅳ]'],['162200','魅力的双眼[Ⅹ]'],['162201','魅惑之眼[XI]'],['168400','幻惑免疫'],['204301','知己精通[Ⅳ]']]){
 assert.equal(tr.tr({id:+id,name:'original'},'pieceSkill').name,name,'protected sibling '+id);controls++;
}
if(before){
 assert.deepStrictEqual(Object.keys(lib),Object.keys(before));
 for(const id of Object.keys(before)){
  const want=copy(before[id]);if(changed.has(id))want.name=audit.changes.find(x=>x.id===id).after;
  assert.deepStrictEqual(lib[id],want,'exact fields '+id);
  if(!changed.has(id)){
   const input={id:+id,groupId:100,name:'unchanged-control',shortDescription:'unchanged-control',eventDescription:'unchanged-control'};
   assert.deepStrictEqual(tr.tr(copy(input),'pieceSkill'),old.tr(copy(input),'pieceSkill'),'unrelated skill '+id);controls++;
  }
 }
}
console.log(JSON.stringify({status:'PASS',corrections:changed.size,positive,controls,jsonParseIntegration:true,idempotent:true,descriptionsAndNumbersUnchanged:true}));
