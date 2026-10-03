# 魔法纪录中文资源补丁

维护源：[HiiragiNemu/magireco-cn-patch](https://github.com/HiiragiNemu/magireco-cn-patch)。
组织镜像：[MagirecoCN-Revival-Project/magireco-cn-patch](https://github.com/MagirecoCN-Revival-Project/magireco-cn-patch)，跟随维护源 `main`，不单独生产另一套资源。
玩家下载统一使用 [ProgettoMagius-1 最新正式下载页](https://github.com/HiiragiNemu/ProgettoMagius-1/releases/latest)，无需自行拼装历史迭代包。

## 当前正式配套（2026-10-03 核验快照）

| 内容 | 正式版本 | 维护方式 |
|---|---|---|
| Android 客户端 | **1.0.204** | 独立构建、实测、按验收身份发布 |
| `cn_scenario_update.zip` | **3323** | 固定完整基线，保留原文件、版本和摘要 |
| `cn_js_update.zip` | **103** | 固定完整基线，保留原文件、版本和摘要 |
| `cn_js_delta.zip` | **26** | 最新累计补充层，承载后续剧情、JS、图片、CSS 等更新 |

这是有日期的交付快照，后续版本以正式入口的版本文件与配套清单为准，不能仅靠 README 或上传时间判断。
累计 delta 26 共 **638 个载荷：489 个剧情文件及 149 个非剧情文件**。
本轮 361 个剧情目标的客户端整合已交付（359 份文件实际改变，共 11,226 项字段操作）；
Reader 与游戏各自正确的图片结构保留，未直接用 Reader 整份 JSON 覆盖游戏。

- delta 26 相对 25 只改变默认玩家名显示逻辑：未自定义的 `TOTENTANZ` 显示为「小丘比」。
  不替换玩家 ID、邀请码、存档标识或其他自定义名字；这不是新增改名功能，也不承诺未经实测的改名持久化。
- 其余 637 个载荷逐字节保留，包括全部剧情及已验收的蛋白石、钻石图标。
- 最终 APK 1.0.204 的手动重下 delta、JS 后重下 delta、Scenario 后重下 delta 已做设备测试。
  delta 25 的设备最终落盘校验为 16,758/16,758 文件通过，用户已确认正常进入游戏。
- delta 26 已通过回归、公开包完整下载和逐载荷校验；默认名显示尚未另做设备验收。
  **发布校验、设备校验和用户视觉验收分别记录，不互相代替。**

交付依据：[游戏交付回执](docs/story-quality/client-integration/GAME_DELIVERY_RECEIPT.json)、
[默认玩家名修订回执](docs/story-quality/client-integration/DEFAULT_PLAYER_NAME_20261003.json)。
前者保留 delta 25 的设备证据，后者记录 delta 26；不是两个相互竞争的当前版本。
贡献及完整处理台账只在本资源仓保存，见 [翻译贡献统计](docs/TRANSLATION_STATISTICS.md)。

## 日常发布：只更新累计 delta

**不要为新剧情或零星资源修订重打完整 Scenario／完整 JS。**
当前约定见 [发布策略](docs/story-quality/client-integration/release-policy.json) 和
[累计 delta 交接说明](docs/story-quality/client-integration/DELTA_ONLY_HANDOFF.md)。
旧的完整包共同发布说明 `docs/RESOURCE_PUBLICATION.md`、旧打包器及早期 R2／Doge 操作记录是历史资料，
涉及同时重打 Scenario、提高完整 JS 版本或要求 delta 与旧 Scenario 同路径字节一致的做法，已被本节取代。

1. 在维护源 `main` 集成已审产品修改，保留原有正确功能、翻译及来源记录。
   剧情按客户端专用清单逐字段应用，不从 Reader 复制整份 JSON。
2. 构建器从**同一个固定受审 Git 提交**读取每个载荷；旧 delta 用于确定应保留的路径，
   不作为同名路径正文的最终权威。自动纳入权威源码相对固定基线的全部差异。
3. `tools/build_delta_only.py` 构建，`tools/publish_delta_only.py` 负责发布。
   保留既有补丁路径，同时用最新受审内容刷新；不靠清空剧情目录或简单追加新文件掩盖回退。
4. 验收判据是：**固定基线 + 最新累计 delta 的最终文件 = 最新受审权威源码**。
   delta 与基线的剧情不同是正常情况；仅提高版本号、保留旧正文，或漏掉旧修复，都不算通过。
5. 新安装只需完整固定基线和最新累计 delta，无需逐版安装 22、23、24 等历史补充包。
   包、逐文件清单和分块清单先就位，再更新版本门槛；无内容变化的附件不重传。
6. 发布后核对源仓与公开仓的实际附件、匿名完整下载内容和版本身份；源码同步成功不等于资源已发布。

已提交的 `magica/`、允许发布的 `madomagi/` 产品路径及配套规则是当前构建输入。
历史 `Build_JS_Injector.py` 不是现行发包前置步骤：未经差异核对直接重跑旧模板会覆盖后续修复。
修改字典或注入逻辑时，应维护外部字典与实际运行时注入内容的一致性，复核后再提交产品文件。

### 当前 Actions 入口

- [累计 JS delta 发布](https://github.com/HiiragiNemu/magireco-cn-patch/actions/workflows/publish-js-delta.yml)：产品路径更新、手动或既有联动入口；不重建冻结完整包。
- [公开资源同步](https://github.com/HiiragiNemu/magireco-cn-patch/actions/workflows/mirror-public-resources.yml)：核对文件身份后同步到玩家公开入口。
- [个人主线同步组织镜像](https://github.com/HiiragiNemu/magireco-cn-patch/actions/workflows/sync-personal-to-organization.yml)：维护源更新后让组织 `main` 对齐。
- [已验收客户端发布](https://github.com/HiiragiNemu/magireco-cn-patch/actions/workflows/publish-verified-client.yml)：仅发布明确批准、APK SHA-256 与源码 SHA 匹配的既有构建；不顺带改资源。

APK 发布需先完成最终包实测并显式提供验收身份，不以构建成功自动代替批准。
文档修改不需要重打游戏包。历史提前发布流程失误的审计保留，不用后来的验收结果改写先后顺序。

### 下载、重下与防回退

客户端现有 **16 个下载项**：13 个基础资源包，加 Scenario、完整 JS 和累计 delta。
基础包下载可有限并行，文件提交串行；热更新链按固定基线先、累计 delta 最后执行。
在 1.0.204 中，手动重下 Scenario 或完整 JS 会重置 delta 的进度显示，
基线写入后先按保护机制重放有效缓存，再从网络取得最新 delta、校验并应用。
手动重下 delta 本身也会显示排队／下载／安装状态，不仅弹出提示。

旧 delta、同版本不同摘要、错误基线及损坏缓存均由安装校验拒绝；
版本及完成标记在相关文件校验成功后才记录。离线导入和缓存重放不绕过这些规则。
TLS 证书校验保持开启，已退役的旧 CDN 不会作为内置备用线路自动恢复。

### 公开分发与源仓私有化边界

玩家当前使用公开 GitHub 下载仓与独立 Cloudflare 分发，无需访问维护源或取得访问令牌。
跨仓工作流通过维护端凭据读取源仓，凭据不进入 APK、在线公开配置或玩家附件。
组织源码镜像与公开资源同步是两条职责不同的流程。

私有化后的设计路径已准备；**尚未实际切换仓库可见性并完成切换后的端到端复验**。
将来切换后仍需核对 Actions 凭据、组织同步、公开附件与匿名下载，不能把当前公开状态下的成功当作该项实测。

## 翻译维护输入与产品树的关系

`i18n/frontend-strings.tsv`、`glossary.tsv`、`overrides.tsv`、`fragments.tsv`
以及 `tools/i18n-*.py` 现在都由本仓库维护。上述四张迁移 TSV 是**生成／审计输入**，不是
运行时文件，也不会被 CI 自动套用到 `magica/`；只有维护者显式运行回填、检查差异、
完成人工复核并提交产品文件后，译文才会进入热更新包。因此别的仓库中的同名表不会
隔空改写这里的 JS、HTML 或 JSON。

`i18n/reviewed-candidates.tsv` 是四张迁移表之外的**显式高权重证据覆盖层**，只收录
已经逐项核验的官方／Wiki／确认人工候选。它不属于 legacy 迁移四表，也不是第五张
运行时替换表；`tools/i18n-build-effective.py` 只把它加入 effective、conflicts 与
provenance 审计。要改变产品，仍须另有带前像、目标文件、来源定位和 SHA-256 的应用
清单，并通过保护门和回滚验证。这样既保留四表原始来源，也避免把新核验结论伪装成
legacy 既有译文。

维护者显式运行 `tools/i18n-apply.py` 回填 canonical `frontend-strings.tsv` 时，工具
不会直接相信冻结表中的遗留 AI 候选，而会强制读取 `i18n/generated/effective.tsv`。
`summary.json` 必须把 effective 逐字绑定到当前五份输入、policy、迁移摘要和生成器
哈希；任一文件缺失或陈旧都会在写产品树之前失败。因而原始四表仍保留迁移证据，
但其中已被高权重证据否决的旧译文不会经重跑回流。

冲突时固定按“官方旧国服 dump > `HiiragiNemu/magireco-wiki-data` > 已有人工译文
> 新人工／LLM 译文”选择。`i18n/authority-policy.json` 与
`i18n/authority-provenance.tsv` 保存权重、缺失证据和选择结果；
`tools/i18n-authority-guard.py` 在发包前阻断低权重覆盖、同权重冲突、错名回流及
外部字典／jQuery 内嵌字典不一致。

迁移来的四表另行细分：只有带逐条复核证据的条目才可进入“已有人工译文”；
目前 `frontend-strings.tsv` 的 1632 条译文、`overrides.tsv` 的 9 条与
`fragments.tsv` 的 7 条均归入“遗留未验证 AI 辅助”，低于已验证人工、高于尚未
复核的新提案。`tools/i18n-build-effective.py` 只生成审计层，并以同权重冲突直接失败；
它不会写入 `magica/`。


## 分块清单与客户端落盘

`configures/manifest.json` 提供 16 MiB 分块哈希，客户端可按坏块重下。
现行累计发布器只更新发生变化的 delta 及其清单；固定基础包和完整 JS／Scenario 的原有身份保持不动。
分块下载校验、压缩包身份校验及安装后的逐文件 SHA-256 校验是不同层级，不能用其中一项替代全部验收。

热更新解压到 `/data/data/io.kamihama.totentanz/files/`。
WebView 本地拦截按路径读取 `<files>/magica/` 下的前端文件，包含图片、CSS、JS 等；
查询串不改变本地路径。`madomagi/engine_i18n.tsv` 仍由原生 Label hook 读取，
已核定的原生图片修复也继续保留。现在新增或修订这些内容通过累计 delta，不重打完整 JS。

从源码或打包列表去掉文件，不等于可靠撤销所有设备上的旧覆盖。
客户端事务的孤儿清理有明确路径白名单，不能据此任意删除历史修复；
需撤销错误覆盖时按受审计划交付正确内容，并验证最终落盘及相关功能。

## 产品清单与历史台账

当前发布检查以 `cn_js_delta_manifest.json`、固定基线锁和受审 Git 提交为依据，
记录包身份及逐文件路径、大小、SHA-256，并核对最终叠加结果。
`manifests/` 中早期完整包路径台账用于追溯已下发内容，不替代当前累计 delta 清单。
旧源码里独有的文件也不自动视为有价值，先核实来源和当前功能，再决定保留、修正或显式撤销。

`magica/resource/` 中只维护已核定需要下发的覆盖资源，而不是整个游戏资源解包目录。
放行范围以实际 `.gitignore` 和 Git 跟踪产品文件为准，已不局限于 `image_web/common/global/`。
新增图标应检查原图长宽比、透明边界、实际显示尺寸及原图／旧图／新图对照，再进入发布清单。

## 新译文与新剧情的合入

保留正确旧修订，但不盲目保留旧错误。来源核对优先采用同义国服译文，结合稳定字段、
原文语境和人工验收；假名数量减少或文件更晚生成都不是正确性的充分证据。
本轮 967 项称号已完成来源核对，不代表每项都存在可直接套用的国服完整同名称号。

历史 `scripts/merge_translations.py` 的字符数量启发式仅适合发现候选冲突，
不再作为“每轮必须自动合并并重跑旧注入器”的发布指令。
历史事故曾出现 29 个前端文件、1,520 个假名字符，以及 23 张字典中 11,735 个字段回退；
这些是历史反例，不能当成当前待办或贡献总数。

应用新候选前核对字段前像、来源与客户端结构，保留运行时比较键和正确图片结构；
提交后用固定基线加累计 delta 复验最终文件，并做相关功能回归。
CSS 修改同样需保留有效规则；不以整站日文快照覆盖已有正确本地化。

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

这次历史事故通过恢复正确规则解决。下表记录的是**早期 19 个 CSS 的范围**：
13 个历史冻结修复和 6 个已审计的本地化样式，不是当前产品文件总数。当前范围以
已审产品树及累计 delta 清单为准；不要把未经筛选的全站 CSS 快照整体加入补丁：

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
| `campaign/newyear_login/NewYearLogin.css` | 新年登录活动页的已审计本地化样式 |
| `campaign/quiz/CampaignQuizTop.css` | 问答活动页的已审计本地化样式 |
| `campaign/summer_mission/CampaignSummerMissionTop.css` | 夏日任务页的已审计本地化样式 |
| `event/EventArenaRankMatch/Result.css` | 排位赛结果页的已审计本地化样式 |
| `test/SdCharaTest.css`、`test/ShopReworkTest.css` | Totentanz 测试页的已审计本地化样式 |

这份名单是逐个查各页模块的 `text!css/...` 依赖得出的，不是拍脑袋圈的范围。
`_common/GlobalMenu.css` 虽然在服务端 `fileTimeStamp` 里，但全站没有任何模块
require 它，是死文件，不带。

> 覆盖范围越大，后续维护负担越大。新增 CSS 前先查页面的 `text!css` 依赖，
> 保留服务端现役规则与已有正确本地化，再验证页面显示。文件独有或翻译字数更多，
> 都不等于内容正确。

下面是早期 CSS 冻结排查工具，保留供调查使用；它不是当前累计 delta 的完整
发布验收，也不能要求有意本地化的 CSS 与日文服务端完全相同：

```bash
python3 scripts/check_css_freeze.py            # 查 magica/css/
python3 scripts/check_css_freeze.py --zip <待审补丁包.zip>
```

该历史工具的判据取自服务端 `js/system/replacement.js` 的 `fileTimeStamp` 表（`index.html`
的 `?<hash>` 就是从这来的）：包里每个 CSS 的 md5 必须与清单一致；`fonts.css`
在豁免名单（我们故意改 `src` 指向包内 GB 字体），`common.css` 按「前 N 字节
== 服务端原文」校验（它是服务端原文 + 末尾追加 cn-patch 段）。

## 上游服务器运行状态

[![API server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-api.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-api.yml)
[![Downloadable assets server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-downloadable.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-downloadable.yml)
[![Web assets server status](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-web.yml/badge.svg)](https://github.com/Puella-Care/totentanz-meta/actions/workflows/watchdog-web.yml)


以下 movie 包内容保留为历史研究记录，不构成日常重打包指令。

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

### 密钥破解：`scripts/usm_crack.py`（2026-08-14 实破）

不需要知道密钥也能拿到它——音频的 ADX 流开头是静音（明文全 0），那一段密文
**就等于 audio_mask 本身**。`gen_masks` 的 seed 派生是仿射/异或链，给了掩码的
偶位就能逐字节反推密钥：

```bash
python3 scripts/usm_crack.py a.usm            # 自动破解，输出密钥与等价族
python3 scripts/usm_crack.py a.usm --dump-mask # 只抠 audio_mask(hex)
```

**等价密钥**：`gen_masks` 只用 k[0..6] 派生 seed，**k[7] 从不参与**——所以任意
密钥的第 8 字节改多少都不影响掩码，等价密钥正好 **256 个**（`0xXX…`，XX 任意）。
破解脚本会打印通式。若静音段混入非零样本（个别段偶位 1-2 字节污染），脚本按
「逐段×逐相位找 seed 自洽 + gen_masks 回验全一致」自动避开污染段。

**当前已知密钥**（`movie_1001` / `op_movie2` 都用它，画面与音频经真机播放确认）：
等价族通式 `0xXX00000143484a86`，其中 k[7]=0x00 的规范形是
`0x0000000143484a86`。

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
