const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..')),base=process.argv[3]&&path.resolve(process.argv[3]);
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'../magica/i18n_audit/existing_text_review_20260923/white-feather-standardization.json'),'utf8'));
const read=rel=>JSON.parse(fs.readFileSync(path.join(root,rel),'utf8')),copy=o=>JSON.parse(JSON.stringify(o));
function replace(v){if(typeof v==='string')return v.replaceAll('白翼','白羽');if(Array.isArray(v))return v.map(replace);if(v&&typeof v==='object'){const r={};for(const k of Object.keys(v))r[k]=replace(v[k]);return r;}return v;}
const cache={},at=(obj,parts)=>parts.reduce((x,k)=>x[k],obj);let fields=0,scenarios=0,positive=0,controls=0;
const s=fs.readFileSync(path.join(root,'magica/js/libs/jquery-3.7.1.min.js'),'utf8'),start=s.lastIndexOf('(function(){',s.indexOf('    var cn = '));assert(start>0);
const c={window:{},XMLHttpRequest:function(){},setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};c.XMLHttpRequest.prototype.open=function(){};
vm.createContext(c);vm.runInContext(s.slice(start),c,{timeout:15000});
const tr=(o,p)=>{c.window.__MAGIACN_TRANSLATE__(o,p);return o;};
for(const change of audit.changes){
 if(change.path){
  const data=cache[change.file]||(cache[change.file]=read(change.file));assert.equal(at(data,change.path),change.after);fields++;
  if(change.file.includes('/scenario/'))continue;
  const table=path.basename(change.file,'.json'),row=data[change.path[0]],field=change.path[1];let input,parent=table;
  if(table==='cardList')input={cardId:row.cardId};
  else if(table==='cardMagiaMap')input={magiaId:Number(change.path[0])};
  else if(table==='charaMessageList')input={charaNo:row.charaNo,messageId:row.messageId};
  else if(table==='itemList')input={itemCode:row.itemCode};
  else if(table==='pieceList')input={pieceId:row.pieceId};
  else if(table==='sectionList')input={sectionId:row.sectionId};
  else throw new Error(table);
  input[field]=change.before;input.untouchedNumeric=17;
  const out=tr(copy(input),parent);assert.equal(out[field],change.after,table+'/'+change.path);assert.equal(out.untouchedNumeric,17);positive++;
  const once=JSON.stringify(out);tr(out,parent);assert.equal(JSON.stringify(out),once);controls++;
  c.input=JSON.stringify({[table]:[input]});const parsed=vm.runInContext('JSON.parse(input)',c);assert.equal(parsed[table][0][field],change.after);positive++;
 }else{
  const lines=fs.readFileSync(path.join(root,change.file),'utf8').split(/\r?\n/);const line=lines.filter(x=>x.startsWith(change.key+'\t'));assert.equal(line.length,1);assert.equal(line[0],change.key+'\t'+change.after);positive++;
 }
}
assert.equal(fields,317);
for(const [rel,data] of Object.entries(cache)){
 assert(!JSON.stringify(data).includes('白翼'),rel);
 if(rel.includes('/scenario/'))scenarios++;
 if(base){const old=JSON.parse(fs.readFileSync(path.join(base,rel),'utf8'));assert.deepStrictEqual(data,replace(old),'exact term-only JSON change '+rel);controls++;}
}
assert.equal(scenarios,128);
const unrelated={id:99999999,name:'白翼',description:'白翼',untouchedNumeric:17};assert.deepStrictEqual(tr(copy(unrelated),'unrelated'),unrelated);controls++;
const card=tr({cardId:71515,cardName:'白翼'},'cardList');assert.equal(card.cardName,'白羽');
const magia=tr({magiaId:90236,name:'白羽根のドッペル'},'cardMagia');assert.equal(magia.name,'白羽的魔女化身');
console.log(JSON.stringify({status:'PASS',jsonFields:fields,scenarioFiles:scenarios,dictionaryFields:22,nativeEntries:2,positive,controls,exactTermOnly:!!base,jsonParseIntegration:true}));
