<!-- HELD-BATCH16-AMENDMENTS -->
## 第16批：361目标不变，追加90处漏改机翻

30个既有候选已改进，累计10402字段。旧10312记录的值/顺序保留；活动候选版本在active-candidate-generations.json，旧361行索引快照在客户端history/5ee54cc0da1ac2681219affd5366517fced58cfdd1606fc34155f694b90e5207/ledger-snapshot/。不是新增90篇或新增30篇；694发布账、361未发布目标、24已核销来源项不变。

[本批记录](../unreleased/20261003-semantic-batch16-ai-only-held/README.md)；[客户端最新READY](../client-integration/READY.json)，整合前必须使用current_ready_gate.py与远端main核对SHA，不只比较目标数。运行资源和发布均未改动。
<!-- /HELD-BATCH16-AMENDMENTS -->

<!-- HELD-BATCH15-UNRELEASED -->
## 当前未发布进度：第15批与人工来源边界复核

2026-10-02T21:07:04.587276+00:00。本轮26片段1383正文全文核对，638字段修订；五批361目标、10312字段。原335目标/9674条原样保留。旧50待办中的23项已有固定人译、1项已有全文复核，另列来源豁免，不伪报新稿。历史694/385及498登记未改；本冻结范围待校订AI为0，不等于全库或发布完成。

[第15批记录](../unreleased/20261003-semantic-batch15-ai-only-held/README.md)；[客户端入口](../client-integration/README.md)及READY.json。生产源和delta配置未改，提案128+361=489。注意MVD一份文件的Reader/客户端图片不同，必须使用独立原文身份，见repository-baseline-overrides.json。下一步为刷新新来源审计以及单独的客户端/Reader整合交付，不得重译24项豁免原稿。
<!-- /HELD-BATCH15-UNRELEASED -->

<!-- HELD-BATCH14-UNRELEASED -->
## 第14批与客户端接入准备

更新：2026-10-02T19:15:12.162473+00:00。新增80完整复核，四批累计335未发布目标（252新全文＋83精确复用），50尚未准备，累计9674字段。原255目标/7447字段逐项保留，已发布694/385与旧498登记未改。

[第14批](../unreleased/20261003-semantic-batch14-ai-only-held/README.md)；[客户端接入](../client-integration/README.md)及READY.json。旧255目标清单保留不可变快照。生产资源/配置未动，Scenario和delta须同源整合，提案保留128旧项并扩展至463。客户端正式回执前不转为已发布。
<!-- /HELD-BATCH14-UNRELEASED -->

<!-- HELD-BATCH13-UNRELEASED -->
## 当前未发布进度：第13批及客户端接入准备

更新：2026-10-02T18:14:49.108627+00:00。本批新增51完整复核候选；三批累计255已备稿（172新全文＋83同源复用），130尚未准备。7447未发布字段记录，原204候选/5688字段逐项原样保留，已发布694/385总账和旧498登记不变。

[第13批记录](../unreleased/20261003-semantic-batch13-ai-only-held/README.md)；[客户端接入入口](../client-integration/README.md)与`../client-integration/READY.json`。只读预检通过不代表已发布；客户端必须同源更新Scenario与delta，并把原128补充路径保留扩展至383。完整清单、候选和恢复材料仍只在本仓。
<!-- /HELD-BATCH13-UNRELEASED -->

<!-- HELD-BATCH12-UNRELEASED -->
## 当前未发布进度（第12批追加）

更新：2026-10-02T17:20:05.202538+00:00。本批新增71个全文校订候选；累计204个待处理目标已准备（121新全文、83同源复用），另181个尚未准备。已发布694／385总账保持原字节，不将未发布候选冒充上线成果。之前133目标和3560条字段依据逐项原样保留，合计5688条未发布字段记录。

见 [第12批记录](../unreleased/20261003-semantic-batch12-ai-only-held/README.md)、`unreleased-summary.json`、`unreleased-scripts.tsv`、`pending-status-with-unreleased.tsv`。下方第11批说明为历史批次记录，其133／252数字不再是当前累计。仅本仓保存累计清单和恢复材料，发包仍暂停。
<!-- /HELD-BATCH12-UNRELEASED -->

# 剧情校订与累计贡献台账

核定快照：玩家剧情包 **3322**。Reader `9f881c9bbb1bf9283130f9d36caa433e12797dcd`；CN patch `199c127de4ff6e628ddac2a86e4e23b0f9404590`；发行仓 `657bdc658ce47e5bfdf10be9debe6eea2939c08a`。

确认 AI／机翻来源的独立运行片段共 **1079**，全文复核 **694**，尚待 **385**（已含未索引 24）。完成中接手前已有 **48**，接手后 **646**；前一个 AI 的成果没有清零。

自 3301 至 3322 的已发布改动按运行 JSON 路径去重，共涉及 **981** 个片段。其中存在正文校订的 **663** 个片段、**19477** 个不同字段地址；历史重复校订计 **19477** 次操作，不能把操作次数当新句数。姓名修正、运行结构对齐和原稿恢复另列，不能都声称为原创翻译或全文复核。

## 固定文件与统计口径

`processed-runtime-scripts.tsv`：全部已发布修改的运行片段，含剧情 ID、标题、Reader 路径、首次／最近版本和累计版本；同一剧情镜像不重复计数。

`full-reviewed-ai-scripts.tsv` 与 `pending-ai-scripts.tsv`：逐片段完整复核／剩余清单，附当前中日文 blob、来源和复核证据。

`indexed-chapters.tsv`：整话与片段关系，区分触及部分片段、AI 部分完成、整话所有片段均有完整证据。

`batches.json`：接手前后每批发布数、原始报告口径、剧情列表和提交 SHA。`ledger.json.gz`：完整字段级前后文字、地址、历史事件、来源台账与发行回执；可用于核对实际贡献范围。

正文字段数是按当前JSON地址记录的显示字段修改数，并非新译句数。它也可能包含称呼、字词、文本错位归位、换行和标点修正；例如3309的102502-1_lDVQb存在台词与内嵌标签一起归位的历史记录，完整前后文字和same_executable_tags标志都已保留，不能据此声称新增了同等数量的原创翻译。

## 更早的历史登记同样保留

旧 `manual_retranslation/PROCESSED_STORY_TITLES.md` 登记 507 个候选条目、498 个唯一剧情 ID。原档不删除；本台账把 498 个 ID 全部保存在 `legacy-registered-stories.tsv`，去掉不同段落重复列举的条目。该旧档的“剩余 0”指译文写入和结构校验，不代表当前逐句质量审查已完成。不得与本台账的片段数直接相加，也不得据文件名中的“人工”重写原作者署名。

## 贡献署名边界

可据此核定维护者主导、AI 辅助的剧情校订、姓名规范、运行兼容、来源恢复与整合发布工作。原国服、官方、Wiki 和确认人工译者的原文贡献继续归原作者；本台账只记录实际新增改动与复核，不把保留的原译据为己有。具体展示署名由维护者确认，当前未修改游戏贡献 UI／APK。

另有 Reader 128 个与客户端独有 35 个正文仅属于来源调查；没有把未知来源自动算为 AI、待重译或已完成。43 份既有 V4 兼容和 196 份授权中文是保全范围，不因保全而新增翻译贡献数。

## 接手前后批次

| 版本 | 阶段 | 类型 | 修改片段 | 有正文校订片段 | 正文字段地址 | 数据提交 |
|---|---|---|---:|---:|---:|---|
| 3301 | 接手前 | text_correction | 14 | 14 | 956 | `8e02baee9e` |
| 3302 | 接手前 | text_correction | 4 | 0 | 0 | `f7d1736c17` |
| 3303 | 接手前 | text_correction | 8 | 7 | 487 | `30f2aefb06` |
| 3304 | 接手前 | text_correction | 7 | 7 | 512 | `7b8dc4495c` |
| 3305 | 接手前 | text_correction | 4 | 4 | 298 | `a45c6fc6f5` |
| 3306 | 接手前 | text_correction | 160 | 1 | 1 | `3c4439fc7a` |
| 3307 | 接手前 | text_correction | 27 | 4 | 294 | `c9fa878d33` |
| 3308 | 接手前 | text_correction | 19 | 7 | 222 | `3201c963cb` |
| 3309 | 接手前 | text_correction | 2 | 2 | 93 | `f280b61751` |
| 3310 | 接手前 | runtime_alignment | 130 | 0 | 0 | `149208c9a6` |
| 3311 | 接手前 | runtime_alignment_and_name | 12 | 0 | 0 | `54af872e57` |
| 3312 | 接手前 | source_restoration | 5 | 0 | 0 | `0982d3040c` |
| 3313 | 接手前 | text_correction | 5 | 5 | 405 | `bb7e164a45` |
| 3314 | 接手后 | text_correction | 30 | 30 | 1713 | `6e9965e76d` |
| 3315 | 接手后 | text_correction | 59 | 59 | 1800 | `39a0d94391` |
| 3316 | 接手后 | text_correction | 44 | 44 | 163 | `93305879d4` |
| 3317 | 接手后 | text_correction | 61 | 61 | 720 | `f1955c691d` |
| 3318 | 接手后 | text_correction | 72 | 72 | 2523 | `0d04f7adc9` |
| 3319 | 接手后 | text_correction | 96 | 96 | 3033 | `4c2eb16d22` |
| 3320 | 接手后 | text_correction | 91 | 91 | 2310 | `d5b1442cbb` |
| 3321 | 接手后 | text_correction | 70 | 70 | 2217 | `20c748f726` |
| 3322 | 接手后 | text_correction | 89 | 89 | 1730 | `9f881c9bbb` |

各阶段修改片段合计需要扣除跨阶段重复：当前有 9 个运行片段在接手前后均有改动，累计总数已经去重。

## 后续维护

每批发布并完成当前来源核对后，用 `tools/story_quality_contributions.py` 重新生成以上记录。先刷新三仓 main 和已发布版本，固定 Reader、patch、public 引用；有并行改动或中日文 blob 漂移时必须中止核算并刷新来源。不得删除历史批次，不得只改汇总数字，未发布的暂存校订单独留在当前批次交接中。

示例：`python tools/story_quality_contributions.py --reader . --patch-git <patch.git> --public-git <public.git> --reader-ref <SHA> --patch-ref <SHA> --public-ref <SHA> --last-version 3322 --output <staging-directory>`。生成器只读 Git、只写指定报告目录，不触碰剧情与贡献展示。

## 唯一保存位置

按维护者要求，累计贡献、完整已复核/待处理台账及包含这些信息的恢复包只保存在 HiiragiNemu/magireco-cn-patch。Reader 和 ProgettoMagius-1 只保留接续指针和必要的单批校订/发布证据，不提交生成目录副本，也不在ZIP内夹带台账。前一位AI和接手前的已确认贡献持续保留。


<!-- HELD-BATCH11-UNRELEASED -->
## 尚未整合／发布的校订候选

本批新增50个全文校订目标与83个既有校订稿精确复用目标，共133个待办目标已有候选。**不是新增已发布剧情**，运行源尚未应用，未分配版本号。已发布694／385总账和历史贡献不变；385待办中尚有252个未准备。

见 [未发布批次11](../unreleased/20261002-semantic-batch11-ai-only-held/README.md)、`unreleased-summary.json`、`unreleased-scripts.tsv`、`pending-status-with-unreleased.tsv`、`unreleased-field-changes.json.gz`。复用不是新翻译；所有累计与完整清单仅保存在CN patch。资源审计修正对齐后须重新核对源版本和最终安装覆盖，再单独决定是否整合发布。
