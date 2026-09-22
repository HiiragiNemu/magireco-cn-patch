// Personal release transport: only fixed public project resources, no credentials.
const OWNER = "HiiragiNemu/magireco-cn-patch";
const RAW = "https://raw.githubusercontent.com/" + OWNER + "/main/";
const RELEASE = "https://github.com/" + OWNER + "/releases/download/latest/";
const ASSETS = new Set([
"apk-overlay-atlas.zip","cn_base_00_db.zip","cn_base_01_json.zip","cn_base_02.zip",
"cn_base_03.zip","cn_base_04.zip","cn_base_05.zip","cn_base_06.zip",
"cn_js_update.zip","cn_js_update_manifest.json","cn_magica_resource.zip",
"cn_scenario_img.zip","cn_scenario_update.zip","cn_scenario_update_manifest.json",
"cn_voice_01.zip","cn_voice_02_done.zip","magireco-latest-legacy-client.apk",
"magireco-latest-legacy-client.version.json","manifest.json","movie.zip","movie2.zip",
"cn_js_delta.zip","cn_js_delta_manifest.json","version_js_delta.json",
"version_js.json","version_scenario.json"]);
export function route(path) {
  if (path === "/legacy/config.json") return RAW + "configures/personal-online-config.json";
  const name = path.slice(1);
  if (ASSETS.has(name)) return RELEASE + name;
  return null;
}
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, {status:204,headers:{
      "Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"GET, HEAD, OPTIONS",
      "Access-Control-Allow-Headers":"Range, If-Range, If-None-Match"}});
    if (!["GET","HEAD"].includes(request.method)) return new Response("Method not allowed",{status:405,headers:{Allow:"GET, HEAD, OPTIONS"}});
    if (url.pathname === "/health.json") return Response.json({status:"ok",authority:OWNER,
      transport:"public GitHub Release",organizationCredentialsRequired:false},
      {headers:{"Cache-Control":"no-store"}});
    if (url.pathname === "/") return new Response(
      '<!doctype html><meta charset="utf-8"><title>MadeInMagius 更新入口</title><h1>MadeInMagius 更新入口</h1><p>个人仓独立发布：热更新、基础包与客户端下载。</p><p><a href="/magireco-latest-legacy-client.apk">下载客户端</a> · <a href="/legacy/config.json">在线配置</a> · <a href="/version_js.json">JS 版本</a> · <a href="/version_scenario.json">剧情版本</a></p>',
      {headers:{"Content-Type":"text/html; charset=utf-8","Cache-Control":"no-store"}});
    let target = route(url.pathname);
    if (!target) return new Response("Not found",{status:404});
    if (url.pathname.endsWith('.json')) target += '?fresh=' + Math.floor(Date.now()/30000);
    const headers = new Headers({"User-Agent":"MadeInMagius-Personal-Distribution","Accept-Encoding":"identity"});
    for (const name of ["Range","If-Range","If-None-Match"]) {
      const value=request.headers.get(name);if(value)headers.set(name,value);
    }
    try {
      const upstream = await fetch(target,{method:request.method,headers,redirect:"follow",cf:{cacheTtl:0}});
      if (request.method === 'GET' && headers.has('Range') && upstream.status === 200) {
        if (upstream.body) await upstream.body.cancel();
        return new Response('Source ignored byte range; retry another line',{status:502,headers:{'Cache-Control':'no-store'}});
      }
      const out = new Headers();
      for (const name of ["Content-Type","Content-Length","Content-Range","Accept-Ranges","ETag","Last-Modified","Content-Disposition"]) {
        const value=upstream.headers.get(name);if(value)out.set(name,value);
      }
      out.set("Cache-Control","no-store");
      out.set("Access-Control-Allow-Origin","*");
      out.set("Access-Control-Expose-Headers","Content-Length, Content-Range, Accept-Ranges, ETag");
      out.set("X-Release-Authority",OWNER);
      if (!upstream.ok && upstream.status!==304 && upstream.status!==416) {
        return new Response("Release source returned HTTP "+upstream.status,{status:502,headers:out});
      }
      // Keep the original stream and range semantics; never buffer multi-GB base packages.
      return new Response(request.method==="HEAD"||upstream.status===304?null:upstream.body,{status:upstream.status,headers:out});
    } catch (_) {
      return new Response("Release source temporarily unavailable",{status:502,headers:{"Cache-Control":"no-store"}});
    }
  }
};
