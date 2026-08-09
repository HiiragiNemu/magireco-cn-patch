# Totentanz `magica` 前端差异、中文注入与 UI 保留报告

## 1. 结论先行

1. **合并方向应固定为“当前 Totentanz 为基线，旧国服只提供翻译增量和经校验的图片增量”**。整文件以旧覆盖新会回退路由、RequireJS 映射、DOM、CSS 选择器、原生桥接协议及新活动页面。
2. 当前归档不是独立完整 Web 根，而是一个**网络/服务端覆盖层**：`index.html` 静态引用的 9 个核心文件中，只有 `js/_common/baseConfig.js` 在当前归档内；其余 8 个依赖由新版 APK/基础层提供。旧包中虽有其中 6 个旧版本，也应放入排除清单，避免把新版 APK 基础层降级。
3. 当前前端有 **54 个旧包没有的文件**，其中生产功能包括新年登录、五周年问答、夏日任务、相扑活动、镜层排位赛和 Puella Historia 最终战；另有新测试页。所有 54 个路径已经写入 `merge_policy.json` 的保护清单。
4. 当前 144 个 CSS 文件应整文件保留。旧包没有的 17 个 CSS 共含大量新 UI 规则；同名 CSS 中还检测到 **4,154 个当前侧独有选择器**以及 **8,984 个同选择器但声明已变化的规则**。
5. 已抽取 **617 组旧中译文候选**：515 组高置信、102 组复核；覆盖 122 个 JS/HTML/CSS 文件。旧包没有对应文件的新 UI 另有 **107 个待翻译文本**，其中生产页面 57 个、测试页面 50 个。
6. 图片方面生成了 **325 条同路径、同像素尺寸、结构高度相似的第一批复制映射**；另有 341 条复核映射。325 条已按源/目标 SHA-256、像素尺寸及模拟复制结果完成校验。
7. `common/global/update2` 的六个小菜单图中，**本次旧包没有“保持新版 update2 画布且直接得到中文”的精确替换件**。当前 `main` 中 `common.css` 末尾把 update2 重定向到旧根目录图片的 7 条规则会丢失新版菜单画布，应删除；其余 3 条同 URL 重复规则也可一并清理。

## 2. 输入与可复现性

| 输入 | 大小 | SHA-256 |
|---|---:|---|
| `A:\totentanz-frontend.tar` | 412,550,656 | `b8273e94bf832578f7fff89a43e0ff3b206e8d6d210f18c9f10433dce6bcc414` |
| `A:\magicaOLD.7z` | 393,240,688 | `ee1f1cf622c245ac45f565f73e88473f4b8b45889941edf2b5646ee8155d1c94` |

来源记录见 `source_provenance.json`。全部分析与解包内容均位于 `work/totentanz_frontend`。

## 3. 文件盘点

### 3.1 总量与交集

| 指标 | 数量 |
|---|---:|
| 当前 Totentanz 文件 | 9,397 |
| 旧国服文件 | 10,183 |
| 路径并集 | 10,237 |
| 路径相同且字节相同 | 2,241 |
| 路径相同但内容不同 | 7,102 |
| 仅当前存在 | 54 |
| 仅旧包存在 | 840 |

按扩展名的关键差异：

| 状态 | CSS | HTML | JS | JSON | PNG |
|---|---:|---:|---:|---:|---:|
| 当前独有 | 17 | 15 | 20 | 0 | 0 |
| 同路径修改 | 123 | 152 | 187 | 7 | 6,631 |
| 完全相同 | 4 | 0 | 0 | 0 | 2,234 |
| 旧包独有 | 37 | 157 | 194 | 449 | 0 |

完整逐文件记录在：

- `inventory.json`：路径、状态、大小、SHA-256、编码、行数、假名/CJK 统计。
- `inventory.csv`：同内容的平面表。
- `text_comparison.csv`：只保留 HTML/JS/CSS/JSON。
- `current_only_ui.csv`：54 个当前独有文件。

### 3.2 当前独有的生产 UI

下列是旧国服没有、合并时必须保护的生产组件：

| 组件 | 当前独有文件/入口 | 当前独有 CSS 规则数 |
|---|---|---:|
| 新年登录 | `campaign/newyear_login/NewYearLogin` | 82 |
| 五周年问答 | `campaign/quiz/CampaignQuizTop` | 135 |
| 夏日任务 | `campaign/summer_mission/CampaignSummerMissionTop` | 106 |
| 相扑活动 | `CampaignSumoTop/CharaSelect/Main` | 159 |
| 镜层排位赛 | `EventArenaRankMatch/Top/Result/RedirectTop` | 348 |
| Puella Historia 最终战 | `GroupRaid/QuestResultMainBoss/QuestResultSubBoss/Router` | 256 |

测试页另有 BackdoorQuestBattle、DeleteDataTest、MailSendTest、SdCharaTest、ShopReworkTest、SubSecondTest 等，应保留但可排在生产翻译之后。

### 3.3 同名 CSS 内的新 UI

只保护“当前独有文件”仍不够；很多新 UI 已进入原有同名 CSS。生产文件中当前侧新增选择器最多的项目包括：

| CSS | 当前独有选择器 | 同选择器但声明变化 | 选择器 Jaccard |
|---|---:|---:|---:|
| `css/arena/ArenaCommon.css` | 327 | 436 | 0.637255 |
| `css/regularEvent/groupBattle/RegularEventGroupBattleTop.css` | 240 | 58 | 0.146154 |
| `css/config/ConfigTop.css` | 170 | 69 | 0.194231 |
| `css/formation/DeckFormation.css` | 136 | 320 | 0.797315 |
| `css/memoria/UserMemoriaList.css` | 131 | 74 | 0.486667 |
| `css/quest/SubQuest.css` | 114 | 31 | 0.262821 |
| `css/collection/StoryCollection.css` | 94 | 72 | 0.573991 |
| `css/quest/QuestBattleSelect.css` | 86 | 62 | 0.546392 |
| `css/gacha/GachaTop.css` | 81 | 176 | 0.774026 |
| `css/quest/QuestResult.css` | 78 | 301 | 0.840491 |

因此 CSS 策略是：**保留当前整文件，只在相同选择器下替换 `content:` 文本值**。选择器/声明差异见 `css_diff.csv` 和 `css_diff.json`。

## 4. APK 基础层与网络覆盖层边界

当前 `index.html` 引用以下核心文件：

| 路径 | 当前归档 | 旧包 |
|---|---|---|
| `css/_common/sanitize.css` | 基础层 | 有旧版 |
| `css/_common/common.css` | 基础层 | 有旧版 |
| `css/_common/base.css` | 基础层 | 有旧版 |
| `css/_common/fonts.css` | 基础层 | 无旧版 |
| `js/system/replacement.js` | 基础层 | 有旧版 |
| `js/libs/jquery-3.7.1.min.js` | 基础层 | 无旧版；旧版 index 使用 2.2.3 |
| `js/libs/require.js` | 基础层 | 有旧版 |
| `js/_common/baseConfig.js` | 当前归档内 | 有旧版 |
| `js/_common/base.js` | 基础层 | 有旧版 |

这解释了两套资源的关系：

- APK/本地基础层提供启动必须的共通 CSS、加载器、框架库、替换器和原生桥接基础。
- Totentanz 的 `magica` 归档提供网络覆盖的页面模块、模板、业务 CSS、资源图片及少量系统映射。
- 当前归档的 `api/paths.txt` 仅声明 `/magica/api/page/`、`CharaEnhancementTree`、`EventDungeonTop`、`ResumeBackground` 等服务端入口，进一步表明页面还依赖后端响应与原生桥接。

旧包里的 `_common` 文件是旧 APK 世代的完整基线，不应拿来填充当前归档的“缺失项”。相关排除路径已经写入 `merge_policy.json`。

依赖审计文件：`dependency_audit.json`、`dependency_audit.csv`、`require_map.csv`。

## 5. 中文文本注入

### 5.1 旧包确实含有大量中译文

同路径修改文件的文本统计：

| 类型 | 当前假名 | 旧包假名 | 当前简体提示字符 | 旧包简体提示字符 |
|---|---:|---:|---:|---:|
| JS | 8,816 | 912 | 136 | 2,231 |
| HTML | 10,909 | 1,139 | 404 | 4,528 |
| CSS | 171 | 73 | 13 | 89 |

这些统计只作为语言方向信号；最终替换仍以结构锚点、占位符、数字和标签骨架为准。

### 5.2 已生成的翻译候选

`translation_candidates.json/csv` 共 617 条：

| 类型 | 高置信 | 复核 |
|---|---:|---:|
| JS 字符串字面量 | 380 | 17 |
| HTML 可见文本 | 116 | 85 |
| 同 CSS 选择器的 `content:` | 19 | 0 |

高置信依据包括：

- 当前与旧文件中，目标字符串两侧存在相同字面量锚点；
- 替换段数量一致；
- CSS 使用完全相同的选择器；
- 数字、嵌入标签骨架和格式化占位符一致。

数字或标签骨架变化的候选自动降入复核。例如当前提示含“100 枠”而旧译文含“1 个”的条目已经标记为 `numeric tokens differ`，不会进入无条件替换。

### 5.3 新 UI 的新增翻译工作

`new_ui_strings.json/csv` 列出 107 个旧包没有对应文本的项目：

- 生产页面 57 个：主要来自五周年问答、镜层排位赛、Puella Historia 最终战、新年登录和新 CSS `content:`。
- 测试页面 50 个：MailSendTest、SdCharaTest、ShopReworkTest 等。

生产翻译优先级建议：镜层排位赛错误/结果弹窗 → Puella Historia 按钮与结果 → 新 CSS 文本 → 五周年问答长文本 → 新年登录活动文案。

## 6. 图片安全复制映射

### 6.1 第一批直接落地映射

`safe_copy_map.json/tsv` 含 325 条第一批映射，全部满足：

- 旧→新为同相对路径；
- PNG 像素宽高一致；
- 目标路径名称具有按钮、标题、菜单、结果、活动等文本/UI 倾向；
- 至少 72% 渲染像素保持一致；
- Alpha 变化比例不高于 3.5%；
- 视觉 MAE 不高于 7；
- dHash 距离不高于 0.14；
- 源与目标 SHA-256 固定在映射内。

`review_copy_map.json/tsv` 另含 341 条较宽阈值候选，适合截图复核后加入第二批。

验证方式：

```powershell
python verify_safe_copy.py
python verify_safe_copy.py --staged-root verification_stage
```

两次均检查通过：325 条，0 错误。`verification_stage` 是按映射执行的模拟复制结果。

### 6.2 `global/update2` 六个菜单图专项核对

| 菜单 | 当前 update2 | 旧同路径 update2 | 旧根目录中文图 | 结论 |
|---|---:|---:|---:|---|
| unit | 208×246 | 184×196 | 208×246 | 同路径尺寸不符；根目录虽同尺寸，但缺少新版 update2 画布 |
| memoria | 208×246 | 184×196 | 208×246 | 同上 |
| gacha | 208×246 | 184×196 | 208×246 | 同上；当前图为新版 `Fate Weave` 画布 |
| mission | 208×246 | 184×196 | 208×246 | 同上 |
| team | 184×196 | 184×196 | 352×382 | 旧同路径写的是日文“チーム”，没有中文收益；根目录中文图尺寸和造型均不同 |
| shop | 184×196 | 184×196 | 208×220 | 旧同路径写的是日文“ショップ”，没有中文收益；根目录中文图尺寸不同 |

逐对尺寸、哈希及视觉指标见 `global_update2_audit.json/tsv`。

**精确替换结论：本次旧包中为 0/6。** `team`、`shop` 只有像素尺寸精确，但内容仍为日文；另外四张的同路径旧图尺寸不同。把旧根目录中文图跨路径塞入 update2 会改变新版横向衬底、边框和按钮造型，不属于“保留新 UI”的精确替换。

后续制作方向是以六张当前 update2 PNG 为画布，仅重绘文字层，保留当前透明区、边框和中心图形；生成后再把同路径资源加入映射。

### 6.3 当前 `main` 的 `common.css` 末尾覆盖清理

在现有 `work/patch-front/magica/css/_common/common.css` 尾部发现 10 条追加规则。

应删除的 7 条行为改变规则：

```css
#sideMenu #menuBtns .unit
#sideMenu #menuBtns .innocent
#sideMenu #menuBtns .team
#sideMenu #menuBtns .gacha
#sideMenu #menuBtns .mission
#sideMenu #menuBtns .shop
#sideMenu #menuBtns .shop2
```

基础 CSS 本来分别指向 `common/global/update2/global_*.png`；尾部规则把它们改指旧根目录图片，正是新版 UI 被旧画布替换的来源。

还可删除 3 条同 URL 重复规则：

```css
#sideMenu #sideBigBtns .globalBigBtn.globalQuestBtn
#sideMenu #sideBigBtns .globalBigBtn.globalBattleBtn
#globalMenu #globalBackBtn
```

它们与基础声明指向相同路径，只增加维护和缓存判断复杂度。清理计划已编码进 `merge_policy.json`。

## 7. 可自动化的合并流程

1. **创建输出树**：完整复制当前 Totentanz `magica` 作为基线。
2. **锁定当前结构**：保护 `merge_policy.json` 中 54 个当前独有路径及全部 144 个当前 CSS。
3. **JS/HTML 翻译**：按 `translation_candidates.json` 修改当前文件的字符串字面量/文本节点，不复制旧整文件；先应用 `high`，再处理 `review`。
4. **CSS 翻译**：只修改相同选择器下的 `content:` 字符串；保留当前选择器及所有声明。
5. **新增 UI 翻译**：填写 `new_ui_strings.csv` 的 `cn_text`，按路径与字符串精确替换。
6. **图片第一批**：按 `safe_copy_map.json` 复制，并运行 `verify_safe_copy.py --staged-root TARGET_MAGICA_ROOT`。
7. **图片第二批**：对 `review_copy_map` 做 1024 宽截图复核，通过后追加映射。
8. **旧包独有项**：840 个旧独有文件默认排除；按明确的当前路由/依赖需求逐项加入。旧 API JSON 快照、退役活动、测试工具和旧 APK 核心文件不进入默认输出。
9. **清理菜单重定向**：删除 `common.css` 尾部 10 条规则，update2 维持新版路径。
10. **执行静态与运行时测试**。

机器可读策略在 `merge_policy.json`。

## 8. 测试入口与验收项

### 8.1 静态验证

```powershell
python static_smoke_test.py
```

本次结果见 `verification_record.json`：

- Node 语法检查：207/207 JS 通过；
- CSS 解析：144/144 文件通过，共解析 16,225 个规则键；
- APK 基础层边界：8 个预期基础依赖与审计一致；
- 安全复制映射：325/325 基线与模拟复制均通过；
- 总退出状态：0。

### 8.2 运行时入口

运行时需把“新版 APK 基础 `magica` 层 + 当前 Totentanz 覆盖层 + 后端 API/原生桥接”叠加。入口格式：

```text
http://HOST:PORT/magica/index.html#/TopPage
```

重点路由：

```text
#/TopPage
#/MyPage
#/CampaignQuizTop
#/CampaignSumoTop
#/NewYearLogin
#/CampaignSummerMissionTop/TEST_MISSION_ID
#/RegularEventArenaRankMatchTop
#/EventPuellaRaidTop
#/PuellaHistoriaGroupRaidQuestResultMainBoss
#/PuellaHistoriaGroupRaidQuestResultSubBoss
```

每个路由至少检查：

1. 控制台没有 RequireJS 模块、模板或 CSS 404；
2. `/magica/api/page` 及页面专用 API 返回匹配的 fixture；
3. 菜单六图请求仍为 `/common/global/update2/global_*.png`；
4. DOM、按钮点击区、滚动区和原生桥接事件正常；
5. 中文文本未改变数字、HTML 标签、占位符及业务条件；
6. 1024 宽基准截图与当前 Totentanz 对比，只出现文字/获批图片变化，不出现布局回退。

## 9. 产物索引

| 文件 | 用途 |
|---|---|
| `report.md` | 本报告 |
| `inventory.json`, `inventory.csv` | 完整逐文件盘点 |
| `summary.json` | 盘点摘要 |
| `text_comparison.csv` | 文本文件差异 |
| `current_only_ui.csv` | 当前独有 UI 文件 |
| `css_diff.json`, `css_diff.csv` | 选择器级 CSS 差异 |
| `dependency_audit.json`, `dependency_audit.csv` | 静态依赖边界 |
| `require_map.csv` | RequireJS 模块映射 |
| `translation_candidates.json`, `translation_candidates.csv` | 旧中译文候选 |
| `new_ui_strings.json`, `new_ui_strings.csv` | 新 UI 待翻译文本 |
| `safe_copy_map.json`, `safe_copy_map.tsv` | 第一批图片复制映射 |
| `review_copy_map.json`, `review_copy_map.tsv` | 第二批复核映射 |
| `global_update2_audit.json`, `global_update2_audit.tsv` | 六个菜单图专项核对 |
| `verify_safe_copy.py` | 映射与复制结果校验 |
| `merge_policy.json` | 自动合并策略 |
| `static_smoke_test.py`, `verification_record.json` | 静态验收与记录 |
| `source_provenance.json` | 输入哈希 |

