const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const b=fs.readFileSync(path.join(root,'magica/js/user/MyPage.js')),s=b.toString('utf8');
assert.equal(crypto.createHash('sha256').update(b).digest('hex'),'8456e851de34dd9a06aa69358343db4e238d0b3256ad00b54e745a32d4167e86','must publish device-3 accepted bytes');
new vm.Script(s);
const match=s.match(/function cnDoubleHomeCaptionV1\(cmd\)\{[\s\S]*?return cmd;\s*\}/);assert(match);
const cases=[['single',false,0,'MyPage',false,false,1024,undefined],['double',true,0,'MyPage',false,false,1024,-160],['wide',true,0,'MyPage',false,false,1138,-175],['costume',true,1,'MyPage',false,false,1024,undefined],['hidden',true,0,'MyPage',true,false,1024,undefined],['portrait',true,0,'MyPage',false,true,1024,undefined],['ADV',true,0,'Story',false,false,1024,undefined],['title',true,0,'TopPage',false,false,1024,undefined]];
for(const [name,doubleUnitFlg,live2dIndex,location,hidden,portrait,displayWidth,want] of cases){
 const ctx={a:{location,displayWidth,doc:{getElementById:()=>({classList:{contains:()=>hidden}})}},c:{chara:{doubleUnitFlg},live2dIndex},f:{live2dPortrait:portrait}};
 vm.createContext(ctx);vm.runInContext(match[0],ctx);
 for(const entry of ['initial','touch','menu-return']){
  const cmd={id:'111800',subId:'111802',x:540,y:288,subX:-60,subY:0,fontSize:24};const expected={...cmd};
  if(want!==undefined)expected.txtAdjustX=want;
  assert.strictEqual(ctx.cnDoubleHomeCaptionV1(cmd),cmd);assert.deepStrictEqual(cmd,expected,name+'/'+entry);
 }
}
assert.equal((s.match(/cnDoubleHomeCaptionV1\(/g)||[]).length,7);
console.log('PASS 24 home-caption scope/control cases; exact device-3 accepted bytes; 6 entry points');
