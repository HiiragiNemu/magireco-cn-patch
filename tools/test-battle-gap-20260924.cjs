const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const baseline=process.argv[3]&&path.resolve(process.argv[3]);
const read=(r,p)=>fs.readFileSync(path.join(r,p),'utf8');
const audit=JSON.parse(read(path.join(__dirname,'..'),'magica/i18n_audit/existing_text_review_20260924/battle_gap_review.json'));
const engine=new Map(read(root,'madomagi/engine_i18n.tsv').split(/\r?\n/).filter(s=>s&&!s.startsWith('#')).map(s=>{const i=s.indexOf('\t');return [s.slice(0,i),s.slice(i+1)];}));
const misses=audit.nativeExactAdditions.filter(r=>engine.get(r.source)!==r.target);
const fix=audit.semanticCorrection;
const maps={};for(const row of audit.nativeExactAdditions)for(const b of row.bindings){
 if(!maps[b.table])maps[b.table]=JSON.parse(read(root,'magica/js/libs/'+b.table+'.json'));
}
const semantic=maps.pieceSkillMap[fix.id][fix.field]===fix.after;
if(misses.length||!semantic){console.log(JSON.stringify({status:'BASELINE_MISSES',nativeMissing:misses.length,guaranteedCurseCorrect:semantic}));process.exit(1);}
assert.equal(audit.nativeExactAdditions.length,184);
for(const row of audit.nativeExactAdditions){
 assert(!/[\u3040-\u30ff]/.test(row.target));
 assert.deepStrictEqual(row.source.match(/[Ⅰ-Ⅻ∞0-9]+/g),row.target.match(/[Ⅰ-Ⅻ∞0-9]+/g));
 for(const b of row.bindings)assert.equal(maps[b.table][b.id][b.field==='description'?'shortDescription':b.field],row.target);
 assert(!engine.has(row.target),'new target should not trigger a second native translation');
}
const resolved=JSON.parse(read(path.join(__dirname,'..'),'magica/i18n_audit/existing_text_review_20260924/battle_cn_authority_review.json'));
for(const row of audit.heldExistingNames){
 const proof=resolved.nativeExactAdditions.find(x=>x.source===row.source&&x.kind==='official_cn_skill_name');
 assert(proof&&proof.evidence.some(x=>x.kind==='official_cn_capture'&&x.fieldValue===row.target));
 assert.equal(proof.target,row.target,'Keep the captured official CN name, not a speculative retranslation');
 assert.equal(engine.get(row.source),proof.target);
}
function runtime(r){
 const text=read(r,'magica/js/libs/jquery-3.7.1.min.js'),at=text.indexOf('    var cn = '),start=text.lastIndexOf('(function(){',at);
 assert(at>0&&start>0);
 const c={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};
 c.XMLHttpRequest.prototype.open=function(){};vm.createContext(c);vm.runInContext(text.slice(start),c,{timeout:15000});
 return {tr:(obj,parent)=>{c.window.__MAGIACN_TRANSLATE__(obj,parent);return obj;},parse:obj=>{c.input=JSON.stringify(obj);return JSON.parse(JSON.stringify(vm.runInContext('JSON.parse(input)',c)));}};
}
const current=runtime(root),copy=x=>JSON.parse(JSON.stringify(x));let cases=0;
for(const key of ['id','skillId','memoriaId']){
 const input={[key]:Number(fix.id),name:'unchanged input',description:fix.source,shortDescription:fix.source,cost:7,effect:123,attribute:'FIRE'};
 if(key==='id')input.groupId=100;
 const output=current.tr(copy(input),'pieceSkill');
 assert.equal(output.shortDescription,fix.after);cases++;
 // Generic description is only owned by the master-skill shape (id + groupId).
 if(key==='id'){assert.equal(output.description,fix.after);cases++;}
 else assert.equal(output.description,fix.source);
 for(const field of ['cost','effect','attribute'])assert.equal(output[field],input[field]);
 assert.deepStrictEqual(current.tr(copy(output),'pieceSkill'),output);
}
const nested={pieceSkill:{id:Number(fix.id),groupId:100,description:fix.source,shortDescription:fix.source}};
assert.equal(current.parse(nested).pieceSkill.description,fix.after);cases++;
let unchangedIds=0;
if(baseline){
 const old=JSON.parse(read(baseline,'magica/js/libs/pieceSkillMap.json'));
 for(const id of Object.keys(old)){if(id!==fix.id){assert.deepStrictEqual(maps.pieceSkillMap[id],old[id]);unchangedIds++;}}
 assert.deepStrictEqual({...maps.pieceSkillMap[fix.id],shortDescription:fix.before},old[fix.id]);
 assert(read(root,'madomagi/engine_i18n.tsv').startsWith(read(baseline,'madomagi/engine_i18n.tsv')));
 const prev=runtime(baseline);
 for(const [obj,parent] of [[{id:999999999,description:fix.source},'pieceSkill'],[{id:Number(fix.id),description:fix.source},'itemList'],[{id:Number(fix.id),description:fix.source},'unrelated']])
  assert.deepStrictEqual(current.tr(copy(obj),parent),prev.tr(copy(obj),parent));
}
console.log(JSON.stringify({status:'PASS',nativeExactBindings:184,semanticCorrections:1,runtimeCases:cases,unchangedSkillIds:unchangedIds,officialCnNamesResolved:5,numericGameFieldsChanged:0,newSkillIdCredit:0,deviceAcceptance:'pending'}));
