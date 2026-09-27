const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const read=n=>JSON.parse(fs.readFileSync(path.join(root,'magica/js/libs/'+n+'.json'),'utf8'));
const chars=read('charaList'),cards=read('cardList');
const variants=[
 [1103,'谣鹤乃','',[11033,11034,11035],'传闻鹤乃'],
 [1104,'谣莎奈','',[11044,11045],'传闻莎奈'],
 [1303,'谣鹤乃','动画ver.',[13034,13035],'传闻鹤乃'],
 [3043,'万年樱之谣','',[30434,30435],'万年樱的传闻'],
 [3502,'万年樱之谣','泳装ver.',[35024,35025],'万年樱的传闻']];
const s=fs.readFileSync(path.join(root,'magica/js/libs/jquery-3.7.1.min.js'),'utf8');
const start=s.lastIndexOf('(function(){',s.indexOf('    var cn = '));assert(start>0);
const ctx={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};ctx.XMLHttpRequest.prototype.open=function(){};
vm.createContext(ctx);vm.runInContext(s.slice(start),ctx,{timeout:15000});
const tr=(o,p)=>{ctx.window.__MAGIACN_TRANSLATE__(o,p);return o;};
let cardCount=0,runtimeCases=0;
for(const [id,name,title,ids,old] of variants){
 const c=chars.find(x=>x.id===id);assert(c,'missing character '+id);assert.equal(c.name,name);assert.equal(c.kana,name);
 if(title)assert.equal(c.title,title,'variant title '+id);
 for(const parent of ['charaList','chara']){
  const out=tr({id,name:old,kana:old,title:c.title,untouched:19},parent);
  assert.equal(out.name,name);assert.equal(out.kana,name);assert.equal(out.title,c.title);assert.equal(out.untouched,19);runtimeCases++;
 }
 for(const cardId of ids){
  const card=cards.find(x=>x.cardId===cardId);assert(card,'missing card '+cardId);assert.equal(card.cardName,name);cardCount++;
  for(const parent of ['cardList','card']){
   const input={cardId,cardName:old,untouched:19};tr(input,parent);assert.equal(input.cardName,name);assert.equal(input.untouched,19);runtimeCases++;
  }
  ctx.input=JSON.stringify({cardList:[{cardId,cardName:old}]});
  assert.equal(vm.runInContext('JSON.parse(input)',ctx).cardList[0].cardName,name);runtimeCases++;
 }
}
assert.equal(chars.filter(x=>(x.name||'').includes('传闻')).length,0);
assert.equal(cards.filter(x=>(x.cardName||'').includes('传闻')).length,0);
assert.equal(chars.find(x=>x.id===1144).name,'谣命');
assert.equal(cards.find(x=>x.cardId===65014).cardName,'神滨圣女之谣');
const unrelated={id:9999999,name:'调查传闻',text:'传闻'};assert.deepStrictEqual(tr({...unrelated},'unrelated'),unrelated);
console.log(JSON.stringify({status:'PASS',characterRows:chars.length,cardRows:cards.length,renamedVariants:variants.length,renamedCards:cardCount,runtimeCases,variantLabelsPreserved:true,oldCharacterNamesRemaining:0}));
