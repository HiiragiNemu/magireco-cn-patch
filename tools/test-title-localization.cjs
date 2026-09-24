// 使用完整已生成注入器检查称号的三种实际载体，负例与基线逐项比较。
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const base=process.argv[3]&&path.resolve(process.argv[3]);
const audit=path.join(root,'magica/i18n_audit/title_battle_delta_20260923');
const titles=JSON.parse(fs.readFileSync(path.join(audit,'jp-title-master.json'),'utf8'));
const expected=new Map(JSON.parse(fs.readFileSync(path.join(audit,'title-review.json'),'utf8')).map(x=>[x.id,x]));
const clone=x=>JSON.parse(JSON.stringify(x));
function runtime(dir){
 const s=fs.readFileSync(path.join(dir,'magica/js/libs/jquery-3.7.1.min.js'),'utf8');
 const p=s.indexOf('    var cn = '),start=s.lastIndexOf('(function(){',p);
 assert(p>0&&start>0);
 const ctx={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};
 ctx.XMLHttpRequest.prototype.open=function(){};
 vm.createContext(ctx);vm.runInContext(s.slice(start),ctx,{timeout:15000});
 return (o,p)=>{ctx.window.__MAGIACN_TRANSLATE__(o,p);return o;};
}
const tr=runtime(root),old=base?runtime(base):null;
let fields=0,controls=0,baselineMissing=0;
assert.equal(titles.length,967);assert.equal(expected.size,967);
for(const t of titles){
 const e=expected.get(t.id);
 if(old){const b=old(clone(t),'titleList');for(const f of ['name','description'])if(b[f]!==e[f])baselineMissing++;}
 for(const parent of ['titleList','title','displayTitle']){
  const x=tr(clone(t),parent);
  for(const f of ['name','description']){assert.equal(x[f],e[f],`${t.id}/${parent}/${f}`);fields++;}
  for(const k of Object.keys(t))if(k!=='name'&&k!=='description')assert.deepStrictEqual(x[k],t[k],`非文本字段 ${k}`);
  const first=JSON.stringify(x);tr(x,parent);assert.equal(JSON.stringify(x),first,'重复翻译应不变');
 }
 if(old){
  for(const [o,p] of [[{...t,baseImage:'other_100'},'titleList'],[t,'itemList'],[t,'unrelated'],[{...t,name:t.name+'__changed',description:t.description+'__changed'},'titleList']]){
   assert.deepStrictEqual(tr(clone(o),p),old(clone(o),p),`负例变动 ${t.id}/${p}`);controls++;
  }
 }
}
const response={titleList:clone(titles),userTitleList:titles.map(t=>({titleId:t.id,title:clone(t)})),gameUser:{displayTitle:clone(titles[0])}};
tr(response,null);
for(let i=0;i<titles.length;i++){
 assert.equal(response.titleList[i].name,expected.get(titles[i].id).name);
 assert.equal(response.userTitleList[i].title.description,expected.get(titles[i].id).description);
 assert.equal(response.userTitleList[i].titleId,titles[i].id);
}
assert.equal(response.gameUser.displayTitle.name,expected.get(titles[0].id).name);
console.log(JSON.stringify({status:'PASS',titles:titles.length,positiveFields:fields,negativeControls:controls,baselineUntranslatedFields:baselineMissing,nestedTitleCarriers:titles.length*2+1,idempotence:true}));
