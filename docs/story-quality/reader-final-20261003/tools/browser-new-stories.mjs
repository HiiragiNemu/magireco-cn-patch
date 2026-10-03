import { chromium } from 'file:///C:/Users/proje/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const rev=fs.readFileSync(path.join(root,'source-revision.txt'),'utf8').trim();
const index=JSON.parse(fs.readFileSync(path.join(root,'reader/website/public/story_index.json')));
const packet=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root,'kit/docs/story-quality/client-integration/integration-manifest.json.gz'))));
const targets=[];
for(const prefix of ['512710-1','513510-1','514710-1','710044-1','720091-1','730131-1','420131-1','521110-9']) {
 const entry=packet.files.find(e=>path.posix.basename(e.path).startsWith(prefix));assert(entry,prefix);
 const story=index.find(s=>s.json_sources_cn?.[0]===entry.reader_path);
 if(!story)continue; // Only first-section DOM tests; all other targets are separately exact-HTTP checked.
 let sample;
 for(const [,before,after] of entry.operations){
  const chunks=after.match(/[\u4e00-\u9fff，。！？、…「」“”]{8,}/gu)||[];
  sample=chunks.find(s=>!before.includes(s));if(sample)break;
 }
 assert(sample,'No distinct reviewed text for '+prefix);
 targets.push({id:story.id,title:story.title_cn||story.title,path:entry.reader_path,sample});
}
assert(targets.length>=5);
fs.writeFileSync(path.join(root,'browser-story-targets.json'),JSON.stringify(targets,null,2));
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});const results=[];
try {
 for(const viewport of [{width:1280,height:900},{width:390,height:844}]){
  const context=await browser.newContext({viewport});
  await context.addInitScript(()=>localStorage.setItem('magi_theme','paper'));
  for(const item of targets){
   const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto('https://magireader.pages.dev/reader/'+encodeURIComponent(item.id),{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(sample=>document.body.innerText.replace(/\s+/g,'').includes(sample.replace(/\s+/g,'')),item.sample,{timeout:90000});
   const actual=await page.evaluate(()=>({title:document.title,bodyLength:document.body.innerText.length,balloons:document.querySelectorAll('.magi-balloon-rain,.magi-balloon-host').length}));
   assert.equal(actual.balloons,0);assert.deepEqual(errors,[]);
   if(item===targets[0])await page.screenshot({path:path.join(root,'new-story-'+viewport.width+'.png')});
   results.push({...item,viewport,actual,errors,newReviewedTextVisible:true});
   fs.writeFileSync(path.join(root,'browser-new-stories.json'),JSON.stringify({source_revision:rev,passed:false,results},null,2));
   console.log('VISIBLE_NEW_STORY',item.id,viewport.width,item.sample);await page.close();
  }
  await context.close();
 }
 fs.writeFileSync(path.join(root,'browser-new-stories.json'),JSON.stringify({source_revision:rev,passed:true,checks:results.length,results},null,2));
} finally {await browser.close();}
