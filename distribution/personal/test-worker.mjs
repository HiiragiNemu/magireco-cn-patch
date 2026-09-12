import assert from "node:assert/strict";
import worker,{route} from "./_worker.js";
let seen=[];let upstreamStatus=206;let thrown=false;
globalThis.fetch=async(url,init)=>{
 seen.push({url,init});
 if(thrown)throw new Error("network");
 return new Response(upstreamStatus===304?null:new Uint8Array([80,75,3,4]),{
 status:upstreamStatus,headers:{"Content-Range":"bytes 0-3/280533335","Content-Length":"4","Content-Type":"application/zip","Accept-Ranges":"bytes"}
 });
};
const call=(path,method="GET",headers={})=>worker.fetch(new Request("https://personal.test"+path,{method,headers}));
assert.equal((await call("/health.json")).status,200);
assert.equal((await call("/secret")).status,404);
assert.equal((await call("/cn_js_update.zip","POST")).status,405);
assert.equal(route("/legacy/config.json"),"https://raw.githubusercontent.com/HiiragiNemu/magireco-cn-patch/main/configures/personal-online-config.json");
assert.equal(route("/https://evil.example/a"),null);
assert.equal(route("/madomagi/resource/image_native/memoria/x.png"),null);
let r=await call("/cn_js_update.zip","GET",{Range:"bytes=0-3",Authorization:"secret"});
assert.equal(r.status,206);assert.equal(r.headers.get("Content-Range"),"bytes 0-3/280533335");
assert.deepEqual([...new Uint8Array(await r.arrayBuffer())],[80,75,3,4]);
assert.equal(seen.at(-1).init.headers.get("Range"),"bytes=0-3");
assert.equal(seen.at(-1).init.headers.get("Authorization"),null);
assert.equal(seen.at(-1).init.cf.cacheTtl,0);
assert.equal((await call("/cn_base_03.zip","HEAD")).body,null);
upstreamStatus=404;assert.equal((await call("/cn_js_update.zip")).status,502);
upstreamStatus=416;assert.equal((await call("/cn_js_update.zip")).status,416);
thrown=true;assert.equal((await call("/cn_js_update.zip")).status,502);
assert.equal((await call("/cn_js_update.zip","OPTIONS")).status,204);
console.log("PASS: 15 transport, range, HEAD, allowlist, source-error and credential-isolation assertions");

