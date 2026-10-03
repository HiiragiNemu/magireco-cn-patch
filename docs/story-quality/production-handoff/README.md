# 最终校订稿：生产产物与跨窗口交付入口

核验时间：2026-10-03T04:38:55.076165+00:00。这是数据生成和交付准备，不是游戏资源发行或Reader部署。累计贡献、完整清单及候选只保存在CN patch。本次没有新增翻译贡献数量。

## 校订剩余

最新Reader main的10,907个中文JSON与第17批来源审计逐路径/版本相同，未发现新增已确认AI目标。已登记的1,079个历史来源池片段：694为原发布复核记录、361为已备稿、23为已有人译恢复而排除重译、1已有历史完整复核证据。已确认待首次校订0；第17批明确列出的残余字段复查待办0。这不等于对未确认来源的稿件或整仓绝对无错作保证。

361待发目标及11,226字段操作仍锁定客户端manifest `f4db42783439dc15e2cb94cdcc10857c5e40c8d2e020b4004891bf9e5cc258a1`，原始来源、保护字段、旧498登记及接手前贡献不变。

## 当前线上Reader并没有读取最终新稿

实际HTTP读回：Reader源码 `15d2ee951514ea13e67d68a6864707a7f926fa98`，部署 `https://f271c901.magireader.pages.dev`。这次更新是独立UI发布，不是第11—17批新稿整合。五个普通正文接口（水族馆、镜中映出的真正的我、莎奈服装、神滨MVD、夜鹤记忆）全部匹配旧源，而不是最终候选。详见live-body-checks.json。

361个目标均已存在于当前目录。359个确有改字节的目标在Reader和客户端运行源里都尚未应用；2个无需改字节的目标不算新上线。240份TXT/网页导出此前已经备妥，但没有写进正式运行资源。

## 本轮已经实际生产的内容

以Reader main `afc37211ca1eb6c6970c4dce7b2ff0d3e9c8c7d6` 加上已验证的361个Reader剧情JSON及240份TXT导出，在完全隔离的本地候选源码树生成数据。11项现有生成/校验命令全部成功，源内容、路由和实际gzip成员另行独立核验。

| 产物 | 本轮实测 |
|---|---|
| Reader剧情输入 | 361份，保留Reader自身图片/非文本结构；不得拿它们代替客户端版本 |
| TXT与网页配对输入 | 240份，含此前所有批次修改，共601个Reader输入文件 |
| story_index / story_ids | 3,054个目录条目；ID、别名、路径、源列表保持；story_index与线上逐字节相同 |
| JSON目录分片 | 256份，已绑定候选源版本和新源分包 |
| 正文源分包 | 全部27,406个源文件逐一解压比对通过，361个目标均匹配最终稿 |
| Magireco全文搜索 | 4,681条记录、68个物理分块；新SHA `4089c83c2b5026e051c66589060e2c5561888d6830dd584b65145bb53b5f5b0b` |
| Exedra全文搜索 | 903条记录、13个分块；没有重译其内容 |
| 语音/来源清单 | 按现有生产生成器重建、相关校验通过 |

**story_index不变是预期结果**：本批不增删目录、路径或JSON顺序。真正变动的是正文、TXT、全文搜索和携带正文哈希/源版本的分片。只刷新目录文件不可能让旧正文变新。所有601个最终输入在生成之后仍逐字节匹配；JSON分包覆盖的27,406个源文件已独立校验。生产产物清单共11522个文件（包括源TXT/JSON、搜索大文件及物理分块等不同用途文件），哈希完整保存在production-file-manifest.json.gz，不可把它们统统塞进游戏资源包。

本地数据目录：`D:\magia\deliveries\reader-production-20260930-1226\production-readiness-20261003\reader-build`。
本地候选Git对象 `662e24f62f656ec9e71edd1ae7b4f096ca4d14fb` 仅用于固定此次验证来源，**不在远端main，也不是可发布源版本**。没有新建或推送远端分支。正式Reader整合后必须针对真实main提交重新生成版本相关产物，再执行完整检查、Next/OpenNext构建、部署和线上验收；不能把本目录的本地版本标记直接发布。

## 客户端窗口：无需从现网Reader抓剧情或等待Reader先上线

请使用CN patch的 `docs/story-quality/client-integration/READY.json` 和其引用的 `integration-manifest.json.gz`。当前固定361个目标、359个真实变更、11,226条字段操作。已经使用实际交付CLI在新隔离目录生成客户端文件和delta配置提案：`D:\magia\deliveries\reader-production-20260930-1226\production-readiness-20261003\staged-client-delivery`。

JS delta提案保留128旧路径并追加361目标，共489。不得删旧项、不得拿旧delta回写新稿，完整Scenario和累计JS delta必须从同一个实际整合后的CN patch main提交构建。遵循当前统一资源工作流 `.github/workflows/publish-js-delta.yml`；不运行旧逐编号scenario发布器。

顺序：读取远端最新READY及其SHA -> current_ready_gate.py -> client_candidate_tools.py check-source/stage -> 按逐路径结果合入正文与补充路径表 -> check-integrated -> 统一构建Scenario/delta -> verify-packages及实际版本/清单/设备安装、缓存重放、离线导入、手动重下最终字节核验 -> 写带本次manifest SHA的CLIENT_RECEIPT。

实际检查证明，当前未整合源码会被check-integrated拒绝；不能因已有READY就对旧main直接发包。旧完整JS103不应仅为更新时间而重打。版本号以客户端的最新事务/防回退规则分配，本窗口没有抢占下一个版本。

## Reader窗口：使用独立的601份输入，不能从客户端复制整文件

本目录 `READY.json` 指向 `reader-input-manifest.json.gz` 和 `reader_inputs.py`。输入清单SHA：`1972b526cbfc2029c3d1782661e334f7c35d8f3e9c81d4b7467cae4f8faa122c`；601份输入（361 JSON+240 TXT），599份实际需要改字节。`521110-9_xCcbB.json`在Reader与客户端存在既有图片内容差异，两个版本已分别保留，所以必须使用各自清单。

已用同一个交付工具对实际Reader源检验、在新目录生成全部输入：`D:\magia\deliveries\reader-production-20260930-1226\production-readiness-20261003\staged-reader-delivery`。脚本只允许读取Git或向不存在的隔离目录写文件；不写工作树、不提交、不部署。它会核对远端CN patch最新client READY，Reader路径原始/候选双重Git blob与SHA，并拒绝第三种并行版本。

在已同步的CN patch工作树中，例如：

```powershell
$CN = $PWD.Path
$H = Join-Path $CN 'docs/story-quality/production-handoff'
$C = Join-Path $CN 'docs/story-quality/client-integration'
$ready = Get-Content (Join-Path $H 'READY.json') -Raw | ConvertFrom-Json
$reader = 'D:\magia\deliveries\reader-production-20260930-1226\repo'
python (Join-Path $H 'reader_inputs.py') --manifest (Join-Path $H 'reader-input-manifest.json.gz') --manifest-sha256 $ready.reader_input_manifest_sha256 --patch-repo $CN --reader-repo $reader --ref HEAD check-source
```

需要导出时使用相同参数、`stage --output <新的仓库外目录>`。只把清单确认的路径合入现有Reader main，保留并行UI和其他内容。实际整合之后先运行同工具的check-integrated，再按当前Reader部署工作流顺序重建：generate_story_index、apply_tw_official_metadata、generate_story_voice_manifest及validate-only、generate_machine_translation_manifest、build_split_search_indexes及validate-only、search_chunk_delivery materialize/verify-tree、build-story-json-catalog（源分包）、完整应用构建。随后分别核验Reader和ADV的源码/目录/目标正文以及搜索分块。

不要把Reader的目录/搜索文件当作游戏剧情包的必要前置：两侧共享校订证据，但有不同运行格式、图片保全和发布验证。

## 验证边界与交付记录

本次12项Reader输入防漂移/路径检查测试，以及38项既有客户端接入/新鲜度测试通过；真实CLI成功导出两侧隔离输入，未整合的Reader/CN patch源均按预期拒绝。数据生成11项命令成功，所有源分包实际解压校验通过。不沿用旧批次611/730测试数字。本轮没有运行完整Next/OpenNext应用构建、线上新稿浏览器验收或设备安装新包验证。

普通玩家入口仍为Scenario3323 / delta22，未包含这些待发新稿。当前无针对本次manifest的CLIENT_RECEIPT；Reader当前部署同样不是校订稿交付。原工作树、原生产JSON/TXT/索引、生产delta配置、旧贡献账均保持。累计记录和完整产物输入只留CN patch；Reader只更新交接指针，公开发行仓无副本。

本地验证首次遇到Git alternates换行格式及git archive的Windows行尾转换；只在自建隔离副本修复并按Git原始blob复核50,516文件，未修改系统Git设置或生产行尾。原失败日志保留在生成证据中。
