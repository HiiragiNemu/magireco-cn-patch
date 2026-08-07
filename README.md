# 上游服务器运行状态

[![API server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-api.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-api.yml)
[![Downloadable assets server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-downloadable.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-downloadable.yml)
[![Web assets server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-web.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-web.yml)

# Actions 运行状态

### 自动触发下游仓库们更新：
[![⚙️ 触发下游更新](https://github.com/HiiragiNemu/magireco-cn-patch/actions/workflows/call-downstream-action.yml/badge.svg)](https://github.com/HiiragiNemu/magireco-cn-patch/actions/workflows/call-downstream-action.yml)

### 自动更新组织下游并上传S3：
[![🔄 同步上游并上传到 S3](https://github.com/MagirecoCN-Revival-Project/magireco-cn-patch/actions/workflows/sync-and-upload.yml/badge.svg)](https://github.com/MagirecoCN-Revival-Project/magireco-cn-patch/actions/workflows/sync-and-upload.yml)

### 清除CDN缓存（手动）：
[![🧹 清空CDN缓存](https://github.com/MagirecoCN-Revival-Project/magireco-cn-patch/actions/workflows/purge-all-cache.yml/badge.svg)](https://github.com/MagirecoCN-Revival-Project/magireco-cn-patch/actions/workflows/purge-all-cache.yml)

---

# cn_js_update.zip 是怎么产出的

`magica/` 这棵树**就是**包的内容，CI 里 `zip -r cn_js_update_new.zip magica/`
一步打完；打包前先跑 `Build_JS_Injector.py`，把 `magica/js/libs/*.json` 那
23 张字典和运行时汉化代码注入到 `original_source/jquery-3.7.1.min.js` 的副本
里，写成 `magica/js/libs/jquery-3.7.1.min.js`。所以那个 4 MB 的 jQuery 是
**产物不是源码**，别手改——改注入逻辑请改 `Build_JS_Injector.py` 的模板。

`version_js_new.json` 的 version 由 `configures/version_js.json` 的当前值 +1
得出，size/md5 由 CI 现算。

## 客户端怎么消费它

热更包解压到 `/data/data/io.kamihama.totentanz/files/`，而
`WebViewImpl$WebViewClientImpl.shouldInterceptRequest` 把所有
`/magica/<path>`（`api/` 开头的除外）重定向到 `<files>/magica/<path>`，
按扩展名给 MIME（`.png`→image/png、`.css`→text/css、`.js`→application/javascript）。
**它只认路径，会把 `?<md5>` 查询串丢掉。**

推论有两条，都很硬：

1. **任何前端静态资源都能走这个包**——图片、CSS、字体，不只是 js 和模板。
   同一个包里的东西是原子生效的（一次性解压覆盖）。
2. **进过包的文件拿不出来。** 解压只写不删（`RestClient.unzip`），包里没有的
   文件既不删也不还原。从包里移除某个文件，只是「以后不再更新它」——设备上
   那份**永远留着、永远赢过服务端**。

## 🔴 CSS 尤其危险

每个页面的 CSS 不走 `<link>`，而是 requirejs 的 text 插件当**文本**读进来再
注进 `<style id="headStyle">`：

```js
// js/quest/MainQuest.js
define("… text!css/quest/MainQuest.css text!css/quest/QuestCommon.css …",
       function(…){ … a.setStyle(k + l); … })
```

照样被拦截，照样是本地优先。**已经出过一次事故**：有人为了改样式把某个页面
CSS 整份放进包里，那份快照缺了 `#QuestMap #toPuellaHistoriaTopButtonWrap`
的规则；这个 div 在 `template/quest/MainQuest.html` 里是无条件渲染的，尺寸/
背景图/定位全靠 CSS 给——规则一没就塌成 0 高度空 div，**历史篇（Puella
Historia）入口无声消失**，模板、js、图片、控制台全都正常。

解毒只有一条路：把服务端现役内容原样放回包里再发一次。`magica/css/` 下现在
那 188 个文件就是干这个的。

代价是这 188 个 CSS 从此**冻在仓库里**，服务端改了玩家端吃不到。所以 CI 里
加了闸门（也可以本地跑）：

```bash
python3 scripts/check_css_freeze.py            # 查 magica/css/
python3 scripts/check_css_freeze.py --zip cn_js_update_new.zip
```

判据取自服务端 `js/system/replacement.js` 的 `fileTimeStamp` 表（`index.html`
的 `?<hash>` 就是从这来的）：包里每个 CSS 的 md5 必须与清单一致；`fonts.css`
在豁免名单（我们故意改 `src` 指向包内 GB 字体），`common.css` 按「前 N 字节
== 服务端原文」校验（它是服务端原文 + 末尾追加 cn-patch 段）。

## magica/resource/ 的 .gitignore

这个路径在别处是几百 MB 资源包的解包产物，所以默认忽略；只放行
`image_web/common/global/`——里面是我们主动下发的国服图标和中文
`connecting.png`（334×54 的 8 帧 APNG，替换原版英文 "Connecting..."，
同名同尺寸同 MIME 原地替换，不需要动 CSS；旧 WebView 不认 APNG 就显示第 1 帧
的静止中文。生成脚本在 magirecocn-legacy-client 的
`tools/make-connecting-sprite.py`）。

## 文件清单与账本（manifests/）

`scripts/build_manifest.py` 在每次打包后跑，产出两样东西：

| 文件 | 内容 | 去处 |
|---|---|---|
| `<package>_manifest.json` | 这一版的完整清单：路径 / 大小 / crc32，以及 zip 的 size/md5 | `_artifacts/`（workflow artifact） |
| `manifests/<package>_ledger.json` | **累计账本**：每个路径首次/最后出现在哪一版、当前是否还在包里 | 入库，由 CI 提交回来 |

账本是**已经写进玩家设备的路径全集**。因为热更只写不删，任何一条从包里消失
（`current: false`）都意味着它**留在所有设备上并继续盖住服务端的版本**——脚本会在
这时候把名单打出来，CI 也会在 Job Summary 里标红。

客户端那边（`CNHotUpdateTx`）现在会自己记清单、在下一次热更时把「上一版有、这一版
没有」的孤儿删掉，但删除范围限死在白名单前缀内（`magica/js|template|css|fonts/`、
`madomagi/resource/scenario/json/`），而且**只对装了新客户端之后下发的版本有效**。
所以账本里 `current: false` 且不在白名单前缀下的那些，只能靠「把服务端现役内容
原样发一次覆盖」来撤销。

> `cleanup_prefixes` 也写进 manifest，但**只是留档给人看**——客户端用的是它自己
> 硬编码的白名单，不读这个字段。不然「服务端下发的数据能扩大客户端的删除范围」。

账本的初始值是从**线上现役包**播下去的（js v20 = 415 条，scenario v3211 = 14235 条），
不是从仓库树，因为要记的是设备上真实有什么。
