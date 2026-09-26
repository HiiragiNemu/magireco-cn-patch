// Verify the existing production translator as well as the source dictionary.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const auditFile=process.argv[3]?path.resolve(process.argv[3]):path.join(root,'magica/i18n_audit/nanoha_memoria_review_20260926/review.json');
const expected=process.argv[4]||'after';assert(['before','after'].includes(expected));
const baseline=process.argv[5]?path.resolve(process.argv[5]):null;
const audit=JSON.parse(fs.readFileSync(auditFile,'utf8'));
const copy=o=>JSON.parse(JSON.stringify(o));
function runtime(dir){
 const s=fs.readFileSync(path.join(dir,'magica/js/libs/jquery-3.7.1.min.js'),'utf8');
 const at=s.indexOf('    var cn = '),start=s.lastIndexOf('(function(){',at);assert(at>0&&start>0);
 const c={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};
 c.XMLHttpRequest.prototype.open=function(){};vm.createContext(c);vm.runInContext(s.slice(start),c,{timeout:15000});
 return {tr:(o,p)=>{c.window.__MAGIACN_TRANSLATE__(o,p);return o;},parse:o=>{c.input=JSON.stringify(o);return JSON.parse(JSON.stringify(vm.runInContext('JSON.parse(input)',c)));}};
}
const current=JSON.parse(fs.readFileSync(path.join(root,'magica/js/libs/pieceList.json'),'utf8'));
const rows=new Map(current.map(x=>[x.pieceId,x]));const tr=runtime(root);let runtimeCases=0;
assert.equal(audit.records.length,10);assert.equal(audit.records.filter(x=>x.before!==x.after).length,5);
for(const r of audit.records){
 assert.equal(rows.get(r.id).description,r[expected],'dictionary '+r.id);
 assert.equal(rows.get(r.id).pieceName,r.name,'name preserved '+r.id);
 assert.equal(r.before.split('＠').length,r.after.split('＠').length,'line breaks '+r.id);
 for(const parent of ['pieceList','piece','memoria']){
  const input={pieceId:r.id,pieceName:'original',description:r.japanese,rarity:4,level:40,hp:1530,attack:1530,defense:0};
  const out=tr.tr(copy(input),parent);assert.equal(out.description,r[expected],parent+'/'+r.id);
  for(const key of ['pieceId','rarity','level','hp','attack','defense'])assert.equal(out[key],input[key]);
  assert.equal(out.pieceName,r.name);const once=JSON.stringify(out);tr.tr(out,parent);assert.equal(JSON.stringify(out),once);runtimeCases++;
 }
 const alias=tr.tr({id:r.id,pieceName:'original',description:r.japanese},'piece');assert.equal(alias.description,r[expected]);runtimeCases++;
 const nested={userPieceList:[{pieceId:r.id,piece:{pieceId:r.id,pieceName:'original',description:r.japanese}}]};
 assert.equal(tr.parse(nested).userPieceList[0].piece.description,r[expected]);runtimeCases++;
 const unknown={pieceId:99999999,pieceName:'unchanged',description:r.japanese};assert.deepStrictEqual(tr.tr(copy(unknown),'piece'),unknown);runtimeCases++;
}
let unchangedRecords=0;
if(baseline){
 const oldRows=JSON.parse(fs.readFileSync(path.join(baseline,'magica/js/libs/pieceList.json'),'utf8'));const old=runtime(baseline);
 assert.equal(current.length,oldRows.length);const changed=new Map(audit.records.filter(r=>r.before!==r.after).map(r=>[r.id,r]));
 for(const before of oldRows){
  const want=copy(before),r=changed.get(before.pieceId);if(r){assert.equal(want.description,r.before);want.description=r.after;}
  assert.deepStrictEqual(rows.get(before.pieceId),want,'only approved field changes '+before.pieceId);
  if(!r){const input={pieceId:before.pieceId,pieceName:'original',description:'control',rarity:3};assert.deepStrictEqual(tr.tr(copy(input),'piece'),old.tr(copy(input),'piece'));unchangedRecords++;}
 }
}
console.log(JSON.stringify({status:'PASS',expect:expected,reviewedDescriptions:10,correctedDescriptions:5,runtimeCases,unchangedRecords,numericGameFieldsChanged:0}));
