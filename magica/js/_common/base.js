window.isDebug||(window.console.log=function(){});
(function(){
var retryKey="__MAGIACN_JS_ERROR_RETRY_V2__",lastKey="__MAGIACN_LAST_JS_ERROR_V2__",retryWindow=120000;
function asText(value){try{return value==null?"":String(value)}catch(ignore){return""}}
function storageGet(key){try{return window.localStorage?window.localStorage.getItem(key):null}catch(ignore){return null}}
function storageSet(key,value){try{window.localStorage&&window.localStorage.setItem(key,value)}catch(ignore){}}
function storageRemove(key){try{window.localStorage&&window.localStorage.removeItem(key)}catch(ignore){}}
function saveRecord(record){try{storageSet(lastKey,JSON.stringify(record))}catch(ignore){}}
if(window.setTimeout)window.setTimeout(function(){storageRemove(retryKey)},30000);
window.onerror=function(message,source,line,column,error){
if(window.isBrowser)return false;
if(window.__MAGIACN_JS_ERROR_ACTIVE__)return true;
window.__MAGIACN_JS_ERROR_ACTIVE__=true;
var now=Date.now?Date.now():(new Date).getTime();
var route=window.location&&window.location.hash?asText(window.location.hash):"#/TopPage";
var stack=error&&(error.stack||error.message)?asText(error.stack||error.message):"";
var signature=[asText(message),asText(source),asText(line),asText(column),route].join("|");
var previous=null;
try{previous=JSON.parse(storageGet(retryKey)||"null")}catch(ignore){}
var repeated=!!(previous&&previous.signature===signature&&now-Number(previous.time)>=0&&now-Number(previous.time)<=retryWindow);
storageSet(retryKey,JSON.stringify({signature:signature,time:now}));
var target=repeated?"#/TopPage":route;
var record={schema:"MagiaCNClientError/v2",time:now,message:asText(message),file:asText(source),line:Number(line)||0,column:Number(column)||0,error:asText(error),stack:stack,route:route,page:route,repeated:repeated,recoveryTarget:target};
saveRecord(record);
function directReload(){
window.__MAGIACN_JS_ERROR_ACTIVE__=false;
try{
if(window.location){
if(target!==route)window.location.hash=target;
if(typeof window.location.reload==="function")window.location.reload();
else window.location.href=target
}
}catch(ignore){}
}
try{
require(["underscore","backbone","backboneCommon","ajaxControl","command"],function(underscore,backbone,common,ajax,command){
function reload(){
window.__MAGIACN_JS_ERROR_ACTIVE__=false;
try{
if(command&&typeof command.nativeReload==="function")command.nativeReload(target);
else directReload()
}catch(ignore){directReload()}
}
try{
if(common&&common.location)record.page=asText(common.location);
saveRecord(record)
}catch(ignore){}
try{
if(command&&typeof command.setWebView==="function")command.setWebView(true);
if(common&&typeof common.tapBlock==="function")common.tapBlock(false);
if(common&&common.loading&&typeof common.loading.hide==="function")common.loading.hide();
var base=common&&common.doc&&typeof common.doc.querySelector==="function"?common.doc.querySelector("#baseContainer"):null;
if(base&&base.style)base.style.display="none";
if(common)common.androidKeyStop=true
}catch(ignore){}
try{
if(ajax&&typeof ajax.ajaxPlainPost==="function"&&common&&common.linkList&&common.linkList.jsErrorSend)ajax.ajaxPlainPost(common.linkList.jsErrorSend,JSON.stringify(record),null)
}catch(ignore){}
try{
if(common&&typeof common.PopupClass==="function"){
new common.PopupClass({title:"错误",popupId:"resultCodeError",content:repeated?"发生错误。即将前往首页。":"发生错误。将重新载入当前页面。",decideBtnText:repeated?"返回首页":"重新载入",canClose:false},null,function(){
var jq=window.jQuery||window.$;
if(jq){
var button=jq("#resultCodeError .decideBtn");
button.off();
button.on(common.cgti||"click",reload)
}else{
var node=common&&common.doc&&typeof common.doc.querySelector==="function"?common.doc.querySelector("#resultCodeError .decideBtn"):null;
if(node)node.onclick=reload;
else reload()
}
})
}else reload()
}catch(ignore){reload()}
})
}catch(handlerError){
record.handlerError=asText(handlerError&&handlerError.stack||handlerError);
saveRecord(record);
directReload()
}
return true
}
})();window.app_ver="";window.webInitTime="";window.sendHostName=location.hostname;
var nativeJsonObj={},nativeCallback=function(a){console.log("nativeCallback:function:",a);$("#commandDiv").trigger("nativeCallback",a)},saveDataCallback=function(a){$("#commandDiv").trigger("saveDataCallback",a)},appVersionGet=function(a){window.app_ver=a},getBaseData=function(a){$("#baseReceive").trigger("getBaseData",a)},fontDataGet=function(a){var e=[],f=document.styleSheets.item(1);e.push("@font-face {font-family: 'motoya'; src: url('data:font/ttf;base64,"+String(a.motoya)+"');}");e.push("@font-face {font-family: 'mbm'; src: url('data:font/ttf;base64,"+
String(a.motoya)+"');}");_.each(e,function(a,b,e){f.insertRule(a,f.cssRules.length)})},purchaseCallback=function(a){$("#commandDiv").trigger("purchaseCallback",a)},androidBackKey=function(a){$("#androidBackKey").trigger("androidBackKey",a)},questRetire=function(a){$("#questRetire").trigger("questRetire",a)},configCallback=function(a){$("#configCallback").trigger("configCallback",a)},suspendAwake=function(a){$("#suspendAwake").trigger("suspendAwake",a)},setDeviceInfo=function(a){window.modelName=a.modelName;
window.osVersion=a.osVersion;window.bootCount=a.bootCount};
require("jquery underscore backbone router backboneCommon ajaxControl command apiPathMapping searchPathMapping backboneCustom commonEvent".split(" "),function(a,e,f,l,b,h,g,m,d,n){if(!window.isBrowser||window.isDebug){var c=document.body;c.scrollTop=1;window.addEventListener("touchmove",function(a){"range"!==a.target.type&&(a.target===c&&0!==c.scrollTop&&c.scrollTop+c.clientHeight!==c.scrollHeight?a.stopPropagation():a.preventDefault())},{useCapture:!0,passive:!1});c.addEventListener("scroll",function(a){0===
c.scrollTop?c.scrollTop=1:c.scrollTop+c.clientHeight===c.scrollHeight&&--c.scrollTop});a("#curtain").on(b.cgti,function(){});a=window.clientInformation.platform;var k=function(){if(!window.isBrowser||window.isDebug)window.isBrowser&&window.isDebug&&require(["isBrowser"]),window.isDebug&&!window.g_token&&g.getAccessToken(),g.getAppVersion(),g.getDeviceInfo("setDeviceInfo"),b.baseObj={init:function(){new l;f.history.start();var a=window.parent.screen,c=a.height>a.width?a.height:a.width,a=a.height>a.width?
a.width:a.height,d=a/c;b.scaleHeight=!1;b.displayWidth=1024;b.longSize=c;b.shortSize=a;b.displayHeight=0;window.app_ver.split(".").join("");b.ua.isIphoneXOrMore=!1;b.ua.ios?b.addClass(b.doc.getElementsByTagName("body")[0],"ios"):b.addClass(b.doc.getElementsByTagName("body")[0],"android");b.ua.ios&&.53>d&&(b.scaleHeight=!0,b.doc.getElementById("viewport").setAttribute("content","width\x3d1280, user-scalable\x3dno"),b.displayWidth=1280,c=b.scaleHeight?1.25*window.innerHeight|0:window.innerHeight|0,
""===b.doc.getElementsByTagName("html")[0].style.height&&0!==c&&(b.doc.getElementsByTagName("html")[0].style.height=c+"px",b.displayHeight=c),b.scaleHeight&&b.doc.getElementById("baseContainer")&&(c=(c-36)/c,b.doc.getElementById("baseContainer").style.cssText+="-webkit-transform:scale("+c+");-webkit-transform-origin:0 0;left:-webkit-calc((100% - 1024px * "+c+") / 2);overflow:visible;"),b.ua.isIphoneXOrMore=!0);g.getFontData()}},m.pathSet(),d.pathSet()};"Win32"===a||"Win64"===a?(window.isBrowser=!0,
k()):"MacIntel"===a?(g.getSNS(),setTimeout(function(){window.g_sns?b.ua.ios=!0:window.isBrowser=!0;k()},500)):(g.getSNS(),k())}});
