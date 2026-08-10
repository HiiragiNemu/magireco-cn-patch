# 上游服务器运行状态

[![API server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-api.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-api.yml)
[![Downloadable assets server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-downloadable.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-downloadable.yml)
[![Web assets server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-web.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-web.yml)

# Actions 运行状态

### 自动触发下游仓库们更新：
[![⚙️ 触发下游更新](https://github.com/HiiragiNemu/patch-front/actions/workflows/call-downstream-action.yml/badge.svg)](https://github.com/HiiragiNemu/patch-front/actions/workflows/call-downstream-action.yml)

### 自动更新组织下游并上传S3：
[![🔄 同步上游并上传到 S3](https://github.com/MagirecoCN-Revival-Project/patch-front/actions/workflows/sync-and-upload.yml/badge.svg)](https://github.com/MagirecoCN-Revival-Project/patch-front/actions/workflows/sync-and-upload.yml)

> 同步分「object-storage 系」与「Doge 系」两条独立流水线：
> - **object-storage 系**：上传到 object-storage 桶，刷新 edge / 阿里云 ESA / CDN 三 CDN
> - **Doge 系**：在 **hk 的 Docker 自托管 runner** 上执行 `doge-sync.yml`
>   的 `scripts/sync-dogecloud.py` —— 经 `/auth/tmp_token.json` 换三段式
>   STS 临时密钥后走 boto3（仅 Virtual Hosted Style）上传到多吉云并刷新
>   其 CDN。因 GitHub runner → 腾讯 COS 直连极慢，而 hk → GitHub ~8.6MB/s、
>   hk → COS 快，故把 runner 装在 hk（Docker 容器，`--cpus=2 --memory=2g`
>   限资源；自建镜像仅含官方 runner 二进制，配置用 bind-mount 持久化、免
>   PAT）。主工作流用 `gh workflow run` 调起 doge-sync 并实时转发日志、
>   反馈成败。同步指纹存 Doge 桶 `__doge_fingerprint.json`，
>   `confirm_cleanup=true` 才删过时文件
>
> 多吉云相关密钥见 GitHub Secrets（`DOGE_ACCESS_KEY` / `DOGE_SECRET_KEY` /
> `DOGE_BUCKET` / `DOGE_DOMAIN`）。

### 清除CDN缓存（手动）：
[![🧹 清空CDN缓存](https://github.com/MagirecoCN-Revival-Project/patch-front/actions/workflows/purge-all-cache.yml/badge.svg)](https://github.com/MagirecoCN-Revival-Project/patch-front/actions/workflows/purge-all-cache.yml)

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

解毒只有一条路：把服务端现役内容原样放回包里再发一次。`magica/css/` 下那 13 个
文件就是干这个的——**只覆盖出过问题的那几个页面，不是全站 188 个**：

| 文件 | 为什么在这儿 |
|---|---|
| `_common/common.css` | 我们自己的覆盖版（服务端原文 + cn-patch 段） |
| `_common/fonts.css` | 我们自己的覆盖版（`src` 指向包内 GB 字体） |
| `quest/MainQuest.css` | **事故现场**——`#toPuellaHistoriaTopButtonWrap` 的规则在这里 |
| `quest/QuestCommon.css` | `MainQuest.js` 与 `puellaHistoria/Top.js` 都随页面一起加载 |
| `quest/PuellaHistoriaTop.css` | 历史篇主页 |
| `quest/PuellaHistoriaLastBattle/{GroupRaid,SingleRaid,QuestResultMainBoss,QuestResultSubBoss}.css` | 历史篇末战四页 |
| `quest/QuestBattleSelect.css` | 历史篇档案关卡跳这里（`#/QuestBattleSelect/<sectionId>`） |
| `collection/StoryCollection.css` | 历史篇「回顾」tab |
| `user/MyPage.css`、`top/Top.css` | 主页 / 标题页 |

这份名单是逐个查各页模块的 `text!css/...` 依赖得出的，不是拍脑袋圈的范围。
`_common/GlobalMenu.css` 虽然在服务端 `fileTimeStamp` 里，但全站没有任何模块
require 它，是死文件，不带。

> **代价说清楚**：只覆盖这 13 个，意味着别的页面若也被冻住，它仍然冻着，而且要
> 等有人报症状才会知道。这是有意换来的——冻 188 个等于把全站 CSS 都钉死，服务端
> 以后改任何一处玩家端都吃不到，还是静默的。范围小 = 未来的债少；新症状出现时
> 按同样方法（查该页 `text!css` 依赖 → 把服务端现役内容放进包）补进来即可。

代价是这 13 个 CSS 从此**冻在仓库里**，服务端改了玩家端吃不到。所以 CI 里
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
的静止中文。生成脚本在 legacy-client 的
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


## 新一轮译文进来时：合并，不要覆盖

`scripts/merge_translations.py`。**每轮 LLM 重译都必须过这一步。**

覆盖率不是单调的：新一轮往往在 A 处译得更好、在 B 处却漏译，整包覆盖就会把 B 处
**退回日文**。v3（authoritative-cn-dump pass6）直接盖上去的实测后果：

- 29 个前端文件里假名反而变多，合计 **1520 个字符**退回日文；
- `js/libs/*.json` 那 23 张表里 **11735 处字段**退回日文（道具名、记忆结晶名、
  关卡标题、商店条目……条目一个没少，但内容退了）。

```bash
python3 scripts/merge_translations.py --old <上一版 cn_js_update.zip> --new magica --report
python3 scripts/merge_translations.py --old <上一版 cn_js_update.zip> --new magica --write
python3 Build_JS_Injector.py        # 合并完必须重跑，字典要重新注入
```

判据（对每个字符串单元，旧值 o / 新值 v）：

1. v 没有这个单元 → 用 o
2. `o == v` → 用 v
3. **v 的假名比 o 多** → 用 o（新版退回日文了）
4. v 是纯 ASCII 且含字母、而 o 里有汉字 → 用 o（新版退回英文了）
5. 其余 → 用 v（**新版权威**）

第 3 条比的是假名**数量**不是有无：有无只能抓住「旧版全译、新版全没译」，而实测
更常见的是旧版译了一半、新版整句日文——两边都有假名，按有无判就放过去了。

> **例外：比较用的字符串一律听新版的。** `APPopup2.html` 里
> `item.itemName === "マギアストーン"` 是判据键不是文案；旧版把它译成「Magia 石材」，
> 而 itemList 里根本没有这个条目、运行时字典不会改写 `item.itemName`，那个分支
> 因此永远不成立——**旧版那处是 bug**。脚本按上下文（`===`/`!==`/`case`/`indexOf(`
> 等紧邻）识别并跳过。

切分粒度：JSON 按主键索引后逐字段；JS 抠出字符串字面量、其余当骨架（实测 196 个
里 194 个骨架一致）；HTML 按 `<...>` 切成标签/文本段（181 个里 167 个标签序列一致）；
对不上的少数走 difflib token 级对齐，且只在 `replace` 块上套判据——`insert`/`delete`
是结构变化，一律听新版的。

CSS 不参与合并：那里面没有译文，`magica/css/` 是原样复刻服务端的，一个字节都不能动。


## movie 包（`.usm`）：解密 / 加密 / 拆流

`scripts/usm_crypt.py`。`movie.zip` + `movie2.zip` 里是 516 个 CRI Sofdec2
`.usm`，全在 `madomagi/resource/movie/char/` 下（角色 Magia、魔女化身的演出动画），
载荷加密。不解密就既看不了内容，也判断不了「里面到底有没有需要汉化的文字」。

```bash
python3 scripts/usm_crypt.py info     a.usm                 # 块结构，不需要密钥
python3 scripts/usm_crypt.py selftest a.usm --key 0x…       # 解密→加密 是否逐字节还原
python3 scripts/usm_crypt.py demux    a.usm --key 0x… -o out
python3 scripts/usm_crypt.py decrypt  a.usm --key 0x… -o plain.usm
python3 scripts/usm_crypt.py encrypt  plain.usm --key 0x… -o a.usm
```

**密钥不在本仓库里**，用 `--key` 传。算法源自 CRI Sofdec2（公开描述见 bnnm 的
`crid-mod` / `usm_demuxer` 一系），本文件按算法重新实现，未抄第三方源码。

关键点：**视频不是静态 XOR，带反馈环**——尾段 `[0x100,n)` 的掩码用**明文**滚动
推进，头段 `[0,0x100)` 的掩码又由后段明文异或而来。所以解密必须先尾后头，
加密时两段互不依赖。按静态掩码去解是解不开的。音频则是从载荷 `0x140` 起的静态
XOR，自逆。

掩码表有两条独立验证：一是从密钥派生，二是拿真机素材里 ADX 开头的静音段做已知
明文反推（明文全 0 时密文就等于掩码），两者逐字节一致，奇数位正好是 `URUC` 循环。

### 已经验证到哪一步

- `selftest`：49 个视频块 + 64 个音频块解密→加密全部逐字节还原，整文件也逐字节相同；
- `demux` 出的裸码流能被 ffmpeg 解码出正常画面（1920×1088）。

抽查 `movie_1001_1.usm`（环彩羽 Magia）解出的帧：**纯动画，画面里一个字都没有**，
也**没有 `@SBT` 字幕流**。所以真要做 movie 汉化，第一步应该是逐个抽帧筛出「哪些
片子真有烧录文字」——`movie/char/` 这一批大概率整批不用动。

### ⚠ 重新压制回去还差什么

本脚本只做密码学与容器解析。把**重编码后**的视频塞回 USM 还差两步：

1. 容器重建：`CRID` 的 `filesize/datasize/avbps`、`@SFV` 头的
   `total_frames/max_picture_size/ixsize`、以及 `chunkType=2` 的 seek 表，
   帧长一变全要重算。可编程。
2. **CriMana 认不认 ffmpeg 编出来的流**——它不是通用解码器，对 GOP 结构、profile、
   VP9 的封装约定有自己的假定。ffmpeg 能播 ≠ 引擎能播。**只能在真机上判定。**

所以验证顺序是：先「零改动回环」（`decrypt` 再 `encrypt` 得到与原文件逐字节相同的
USM，装机播），再「不加字幕的同参数重编」，最后才谈烧字幕。另外这批片子**编解码
不统一**（有 H.264 也有 VP9），重编要逐个按原编码走。

> 如果只是要字幕，**native 侧叠 Cocos Label + 外部时间轴表仍然更划算**：改一句话
> 下一版热更就修好（几 KB），而重压 USM 意味着 516 个文件、约 400 MB 两个包全量
> 重发，玩家全体重下。重压只在「画面里烧死了日文、非改画面不可」时才值得。


### 重打包：`scripts/usm_mux.py`

`usm_crypt.py` 只做加解密，把**重编码后**的视频塞回 USM 由这个负责。

```bash
python3 scripts/usm_mux.py selftest <in.usm> --key 0x…      # 原样重打包，必须逐字节回到原文件
python3 scripts/usm_mux.py extract  <in.usm> --key 0x… -o work/
#   … 用 ffmpeg 解码 work/video.bin、烧字幕、按原参数重编 …
python3 scripts/usm_mux.py rebuild  <in.usm> --key 0x… --video new.ivf -o out.usm
```

容器比预想的简单：**没有逐帧 seek 表**——那几个 `chunkType=2` 的块只是 32 字节的
ASCII 段标记（`#HEADER END` / `#METADATA END` / `#CONTENTS END`），不含偏移量。
所以帧长变了不需要重算索引，这是重打包可行的关键。

要重算的只有 `@UTF` 表里几个定宽数值列，就地改，不重排版：

| 字段 | 怎么算 |
|---|---|
| `CRIUSF_DIR_STREAM.filesize` row0 | 整个文件字节数 |
| 同上 row1/row2 | 该流全部数据块的**载荷**长度之和 |
| 同上 `minbuf` row1 | 该流**最大载荷**长度 |
| `VIDEO_HDRINFO.ixsize` | 该流**最大整块**长度（含块头与补零） |

`minbuf` 与 `ixsize` 差一个块头加补零，很容易写混（实测 `ixsize=276896`、
`minbuf=276845`，差 51 = 32 + 19）——identity 测试就是卡在这里才把两者分开的。
`avbps` / `minchk` 不动：音频侧的取值规律没摸清，而我们本来就不改音频。

还有个例外要小心：**CRID 头块被固定补到 2048 字节**（384 载荷 + 1632 补零），
不服从「整块 32 对齐」的通用式。载荷没换过的块一律照抄原 padding。

**硬约束：新视频的帧数必须与原片一致。** 这是刻意把变量压到最少——交织顺序、
音视频同步、时间戳全都不动，真机上万一播不了就只可能是编码器产物的问题，
不会和「容器拼错了」混在一起。ffmpeg 同帧率、不丢帧地重编即可满足。

**自证**：`selftest` 与 `extract → rebuild` 两条路径在 `op_movie2.usm`（VP9，
4870 块）和 `movie_1001_1.usm`（H.264，116 块）上都**逐字节回到原文件**；
不给 `--frames` 让它按 Annex-B AUD 自动切帧，结果同样一致。这说明块框架、补零、
`@UTF` 改值、加密四件事都没写错——换成重编码的流之后，唯一的变量就只剩编码器。
