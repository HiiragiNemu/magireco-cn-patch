// Reproduce the reported title overflow/misses and retain the user's Magia label.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const base=process.argv[3]&&path.resolve(process.argv[3]);
const read=(r,p)=>fs.readFileSync(path.join(r,p));
const clone=x=>JSON.parse(JSON.stringify(x));
const audit=JSON.parse(read(root,'magica/i18n_audit/title_cn_style_20260924/review.json'));
const master=JSON.parse(read(root,'magica/i18n_audit/title_battle_delta_20260923/jp-title-master.json'));
function runtime(r){
 const s=read(r,'magica/js/libs/jquery-3.7.1.min.js').toString('utf8');
 const p=s.indexOf('    var cn = '),start=s.lastIndexOf('(function(){',p);
 const ctx={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};
 ctx.XMLHttpRequest.prototype.open=function(){};
 vm.createContext(ctx);vm.runInContext(s.slice(start),ctx,{timeout:15000});
 return (o,p)=>{ctx.window.__MAGIACN_TRANSLATE__(o,p);return o;};
}
const tr=runtime(root),old=base?runtime(base):null;
let positives=0,controls=0,oldMisses=0;
for(const [index,rule] of audit.sharedExactNames.entries()){
 // Synthetic unknown ID tests the missing-ID behavior, not a claimed live ID.
 const original=master.find(x=>x.id===rule.originalIds[0]);
 const fixture={...original,id:99000001+index};
 if(old){assert.equal(old(clone(fixture),'titleList').name,rule.source);oldMisses++;}
 for(const parent of ['titleList','title','displayTitle']) for(const id of [fixture.id,String(fixture.id)]){
  const input={...fixture,id},x=tr(clone(input),parent);
  assert.equal(x.name,rule.target);assert(!/[\u3040-\u30ff]/.test(x.name));
  assert.deepStrictEqual({...x,name:input.name},input,'fallback must only change name');
  assert.deepStrictEqual(tr(clone(x),parent),x,'idempotence');positives++;
 }
 for(const [input,parent] of [
  [fixture,'itemList'],[fixture,'unrelated'],[{...fixture,baseImage:'other_100'},'titleList'],
  [{...fixture,name:fixture.name+'__changed'},'titleList'],
  [{...fixture,id:null},'titleList'],[{...fixture,id:'unknown'},'titleList'],
  [{...fixture,description:null},'titleList'],[{...fixture,id:undefined},'titleList']]){
  const x=tr(clone(input),parent);
  if(old)assert.deepStrictEqual(x,old(clone(input),parent));
  else assert.equal(x.name,input.name);
  controls++;
 }
}
assert.equal(audit.sharedExactNames.length,12);
for(const row of audit.correctedTitles){
 const t=master.find(x=>x.id===row.id);
 assert.equal(tr(clone(t),'titleList').name,row.after);
 assert(!/[A-Za-z（）]/.test(row.after));
 if(old)assert.equal(old(clone(t),'titleList').name,row.before);
}
assert.equal(audit.correctedTitles.length,66);
const paradox=master.filter(x=>x.name==='白昼夢に溶けるパラドクス');
assert.equal(paradox.length,5);assert.equal(new Set(paradox.map(x=>x.id)).size,5);
const html=read(root,'magica/template/chara/CharaData.html').toString('utf8');
assert(html.includes('<span>Lv</span>'));
assert(html.includes('<p class="c_gold title">魔力解放</p>'));
assert(html.includes('<p class="c_gold title">Magia等级 </p>'));
assert(html.includes('<p class="c_gold title">剧情等级</p>'));
if(base){
 const prior=read(base,'magica/template/chara/CharaData.html').toString('utf8');
 assert.equal(html,prior.replace('<span>等级</span>','<span>Lv</span>')
   .replace('<p class="c_gold title">魔力解放等级</p>','<p class="c_gold title">魔力解放</p>'));
}
const png=read(root,'magica/resource/image_web/common/chara/lv_max.png');
assert.equal(crypto.createHash('sha256').update(png).digest('hex'),'b547105776ac01effa34b468f217a7c4973d88609c73d282fc8d36f99bacdcae');
assert.equal(png.readUInt32BE(16),74);assert.equal(png.readUInt32BE(20),22);
console.log(JSON.stringify({status:'PASS',matchingNames:66,sharedNames:12,positiveCases:positives,
 negativeControls:controls,baselineMissingSharedNames:oldMisses,originalParadoxIds:paradox.map(x=>x.id),
 labels:{level:'Lv',max:'LvMAX',release:'魔力解放',magia:'Magia等级 (unchanged)',episode:'unchanged'},deviceAcceptance:'pending'}));
