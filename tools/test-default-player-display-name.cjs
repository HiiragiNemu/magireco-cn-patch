'use strict';
// Exercise the shipped injector, not a separate mock implementation.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const source=fs.readFileSync(path.join(root,'magica/js/libs/jquery-3.7.1.min.js'),'utf8');
const p=source.indexOf('    var cn = '),start=source.lastIndexOf('(function(){',p);
assert(start>0);
function XHR(){this.listeners={};}
XHR.prototype.open=function(method,url){this.method=method;this.url=url;};
XHR.prototype.addEventListener=function(event,callback){this.listeners[event]=callback;};
const ctx={window:{},XMLHttpRequest:XHR,setInterval:()=>1,clearInterval:()=>{},console:{warn:()=>{}}};
vm.createContext(ctx);vm.runInContext(source.slice(start),ctx,{timeout:15000});
const tr=ctx.window.__MAGIACN_TRANSLATE__;
let checks=0;
const eq=(a,b,message)=>{assert.deepStrictEqual(a,b,message);checks++;};
for(const field of ['loginName','userName','username','topUserName']){
  const o={[field]:'TOTENTANZ',userId:'TOTENTANZ',inviteCode:'TOTENTANZ',id:'TOTENTANZ'};
  tr(o,null);eq(o,{[field]:'小丘比',userId:'TOTENTANZ',inviteCode:'TOTENTANZ',id:'TOTENTANZ'},field);
  tr(o,null);eq(o[field],'小丘比','idempotence');
  for(const name of ['自定义名字','TOTENTANZ2','myTOTENTANZ','Totentanz',' TOTENTANZ','',null,17]){
    const custom={[field]:name};tr(custom,null);eq(custom[field],name,'exact default only');
  }
}
for(const parent of ['gameUser','/magica/api/gameUser','/magica/json/gameUser.json?time=1']){
  const o={name:'TOTENTANZ',userId:'TOTENTANZ',inviteCode:'TOTENTANZ'};
  tr(o,parent);eq(o,{name:'小丘比',userId:'TOTENTANZ',inviteCode:'TOTENTANZ'},parent);
}
for(const parent of [null,'itemList','title','userEventGroup','gameUserSettings']){
  const o={name:'TOTENTANZ',description:'TOTENTANZ',message:'TOTENTANZ',url:'https://totentanz.example/TOTENTANZ'};
  const before=JSON.stringify(o);tr(o,parent);eq(JSON.stringify(o),before,'unrelated content');
}
const wire=JSON.stringify({user:{loginName:'TOTENTANZ',id:'TOTENTANZ'},gameUser:{name:'TOTENTANZ',inviteCode:'TOTENTANZ'},profile:{userName:'TOTENTANZ'},members:[{loginName:'TOTENTANZ',userId:'TOTENTANZ'},{loginName:'Kyubello',userId:'other'}],leader:{topUserName:'TOTENTANZ'},search:[{username:'TOTENTANZ'}]});
const expected=JSON.parse(wire);
expected.user.loginName=expected.gameUser.name=expected.profile.userName=expected.members[0].loginName=expected.leader.topUserName=expected.search[0].username='小丘比';
ctx.wire=wire;
eq(JSON.stringify(vm.runInContext('JSON.parse(wire)',ctx)),JSON.stringify(expected),'JSON.parse nested response');
for(const responseType of ['json','text','']){
  const x=new ctx.XMLHttpRequest();x.responseType=responseType;x.readyState=4;
  if(responseType==='json')x.response=JSON.parse(wire);else{x.responseText=wire;x.response=wire;}
  x.open('GET','/magica/api/page/TopPage');x.listeners.readystatechange.call(x);
  const result=responseType==='json'?x.response:JSON.parse(x.responseText);
  eq(JSON.stringify(result),JSON.stringify(expected),'XHR '+responseType);
}
const inherited=Object.create({loginName:'TOTENTANZ'});tr(inherited,null);
eq(Object.keys(inherited),[],'do not introduce inherited fields');
// The native scenario bridge already consumes user.loginName; no APK or story rewrite is needed.
const bridge=fs.readFileSync(path.join(root,'magica/js/_common/nativeCommand.js'),'utf8');
assert(bridge.includes('userName=e.storage.user.toJSON().loginName'));checks++;
const profile=fs.readFileSync(path.join(root,'magica/template/user/MyProfilePopup.html'),'utf8');
assert(profile.includes('_.escape(profile.userName)') && profile.includes('model.inviteCode'));checks++;
console.log(JSON.stringify({status:'PASS',checks,defaultDisplay:'小丘比',idsUnchanged:true,customNamesUnchanged:true,jsonParse:true,xhrText:true,xhrJson:true,nativeScenarioBridgeExisting:true}));
