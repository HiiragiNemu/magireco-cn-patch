# 旧国服 `magica` 素材与覆盖机制分析

生成时间：2026-08-06（Asia/Singapore）  
工作范围：仅 `work/old_cn_overlay/`；未修改主仓库内容。

## 1. 结论先行

1. **旧国服中文化不是运行时“日文→中文词典替换”**。核心做法是把中文后的 JS、HTML 模板和 Web PNG 放回与上游一致的 `/magica/...` 路径，再由 RequireJS 的 `text!template/...` / `text!css/...` 加载。JS 弹窗字符串、HTML 文本节点、图片内嵌文字共同构成中文化。
2. `js/system/replacement.js` 是**缓存指纹表**，不是翻译映射。它把路径映射到 16 位查询 token；对匹配文件，token 等于实际 MD5 的第 9–24 个十六进制字符。该表与归档当前内容已明显漂移，不能据此判断文件可直接覆盖。
3. 旧启动链与 Totentanz 末期启动链不同。旧树的活动入口动态加载 `baseConfig.js`，再依次加载 `replacement → jquery → help → base`；Totentanz 入口直接链接新版公共 CSS、jQuery 3.7.1、`replacement.js`、`baseConfig.js`、`base.js`。**旧 `index.html`、`baseConfig.js`、`help.js`、`base.js` 和旧 CSS 均不应整文件覆盖 Totentanz。**
4. 文本方面，共找到 4,242 条含 CJK 的 JS/HTML 字符串或文本节点；逐字形分类为：
   - 1,802 条强简体中文信号；
   - 1,945 条共享汉字、语种仍需确认；
   - 471 条日文假名残留；
   - 24 条中日混合。
   去除测试文件、缺少 Totentanz 同路径等情况后，有 **879 条同路径、来源合格的强中文文本候选**。
5. 与 Totentanz 对比后有 144 个同路径的中文文本候选文件，且 144 个都不是同字节；其中 128 个在 Totentanz 中没有简体中文强信号。HTML 只有 31/80 保持相同标签序列，JS 只有 9/64 保持相同 `define()` 依赖数组，因此应当**按文字节点/字符串迁移，不应按文件复制**。
6. 已人工核验全局菜单根目录，确认 7 个“旧国服真中文 + Totentanz 同路径 + 同像素几何”PNG：`扭蛋、记忆结晶、任务、商店、队伍、剧情、镜界`。这些是优先图像来源候选，但仍需确认运行时 CSS 当前确实引用根目录路径。
7. `common/global/update2` 的旧 6 张按钮不是中文权威来源：5 张明确为日文假名，`魔法少女` 仅是中日共享汉字；其中仅 `shop/team` 与 Totentanz 维持 184×196，另外 4 张尺寸已经变化。旧公共 CSS 对根目录菜单图标有引用，对 `update2` 引用为 0。
8. `resource/image_web` 与 APK/native 图像不是完全孤立的两套体系。静态 Web 图像走 `/magica/resource/image_web/...`，而 `data-nativeimgkey` / `data-nativebgkey` 会由 Web 模板汇总后通过 native command 请求 native 层数据；两条资源管线不同，但在 WebView 运行时存在明确桥接。

## 2. 输入、完整性与解包结果

| 输入 | 大小 | SHA-256 | 验证 |
|---|---:|---|---|
| `A:\magicaOLD.7z` | 393,240,688 | `ee1f1cf622c245ac45f565f73e88473f4b8b45889941edf2b5646ee8155d1c94` | `7z t`：Everything is Ok |
| `A:\totentanz-frontend.tar` | 412,550,656 | `b8273e94bf832578f7fff89a43e0ff3b206e8d6d210f18c9f10433dce6bcc414` | `tar -tf`：exit 0 |

旧包解出 975 个目录、10,183 个文件、686,629,480 字节。主要分布：

| 顶层 | 文件数 | 字节 | 作用判断 |
|---|---:|---:|---|
| `resource/` | 8,874 | 399,080,645 | 全部位于 `image_web`；Web 图片/视频资源 |
| `js/` | 386 | 3,732,180 | 页面模块、视图、加载器、运行时命令；主要中文来源 |
| `template/` | 308 | 978,759 | Underscore/Backbone HTML 模板；主要中文来源 |
| `css/` | 164 | 2,948,325 | 旧布局样式；仅供布局/字体参考 |
| `json/` | 290 | 52,986,109 | `file:///` 本地模式数据夹具 |
| `api/` | 157 | 226,800,790 | 抓取/服务端响应夹具，不是静态覆盖层 |

扩展名计数：8,865 `.png`、456 `.json`、381 `.js`、309 `.html`、164 `.css`、1 `.jpg`、1 `.mp4`，另有 3 个无扩展名文件及辅助清单/脚本。

## 3. 旧覆盖/加载机制

### 3.1 启动链

- `extracted/index.html:23-35` 是实际活动 `<head>`：只直接加载 `require.js`，再以 `window.compile` 作为查询参数写入 `baseConfig.js`。文件开头 `index.html:1-22` 的旧 CSS/JS 直链被整段注释。
- `extracted/js/_common/baseConfig.js:48-201` 定义 persistent `pathBlackList` 和 page `pathWhiteList`；机器清单解析出 128 个模块 ID→路径映射。
- `baseConfig.js:207-235` 定义 `fileTimeStamp`、`getMd5()` 和 RequireJS `baseUrl: '/magica/'`。
- `baseConfig.js:237-247` 的实际加载顺序为：

```text
replacement -> jquery -> js/_common/help -> js/_common/base -> js/_common/log
```

### 3.2 CSS/模板装载

- `extracted/js/_common/help.js`（单行压缩文件）末尾定义：
  - `text!css/_common/sanitize.css`
  - `text!css/_common/common.css`
  - `text!css/_common/base.css`
  - 然后用 `createStyle()` 把 CSS 文本插在 `#headStyle` 前。
- 同文件把 `$.fn.html` / `$.fn.text` 包装为 `jQueryReset`，给 `/resource/image_web/...` URL 追加缓存 token；这是 URL 缓存处理，不是语言替换。
- 页面 JS 通常形如：

```js
define([
  "text!template/top/TopPage.html",
  "text!css/top/Top.css"
], function (..., pageTemp, css) {
  // _.template(pageTemp), common.setStyle(css)
});
```

- `dependencies.json` 记录了 381 个 JS 文件；其中 284 个使用 `text!`，共 539 条引用边、456 个唯一模板/CSS 路径。旧树有 16 条 `text!` 引用目标缺失，合并时应由 Totentanz 当前树补齐，而不是回退旧逻辑。

### 3.3 中文文本实际位置

代表性证据：

- `template/config/ConfigTop.html`：`游戏设定、推送通知、数据管理、玩家名、清空缓存` 等大量可见文本。
- `template/top/TopPage.html`：`清空缓存、继承・绑定ID、密码、请输入玩家名`。
- `js/view/user/GlobalMenuView.js`：`关闭支付、返回标题、关于魔法少女、关于记忆结晶、关于扭蛋、关于商店`。
- `js/_common/ajaxControl.js`：连接、错误、维护、下载等弹窗字符串。
- `js/user/MyPage.js`：`登录奖励、来自魔法纪录运营事务局、确认接收` 等。

这些文本都已逐条写入 `text_literal_authority.csv/json`，并标记 `strong_simplified_cn`、`japanese_residue`、`shared_han_ambiguous` 或 `mixed_cn_japanese`。

### 3.4 `replacement.js` 的真实作用

`replacement.js` 是纯 `window.fileTimeStamp = {...}` 对象：

- 表项：8,558；
- 与归档实际文件 token 匹配：570；
- 路径存在但 token 不匹配：6,121；
- 清单列出但归档缺失：1,867；
- 归档实际存在但清单未列：3,492。

例如 `css/_common/GlobalMenu.css` 的实际 MD5 为 `40304df2599f14e5bfbc70b5...`，表中 token 为中间 16 位 `599f14e5bfbc70b5`。由于大多数表项已漂移，它仅能作为历史缓存清单，不能当作“官方原版/国服改版”判定依据。

## 4. 与 Totentanz 末期树的兼容性结论

### 4.1 启动层必须保留 Totentanz

Totentanz `index.html:10-21` 直接引用：

- `_common/sanitize.css`
- `_common/common.css`
- `_common/base.css`
- 新增 `_common/fonts.css`
- `jquery-3.7.1.min.js`
- `replacement.js`、`require.js`、`baseConfig.js`、`base.js`

但传入的 Totentanz tar 本身仅包含上述 9 个入口依赖中的 `baseConfig.js`，其余 8 个不在 tar 内。这表明 tar 是**叠加层/部分前端树**，运行时还依赖另一个基础层。机器审计见 `totentanz_index_dependencies.csv/json`。

模块映射比较：

- 125 个模块 ID 路径相同；
- Totentanz 新增 41 个模块映射；
- 旧树独有 2 个；
- 1 个路径发生变化：`jquery` 从 `js/libs/jquery-2.2.3.min` 变为 `js/libs/jquery-3.7.1.min`。

Totentanz 新增项包括 `SecondPartLast*`、`PuellaHistoria*`、`Scene0*`、`EventWitch*`、`EventWalpurgis*`、`RegularEventExtermination*`、`CampaignQuizTop`、`CampaignSumo*`、`NewYearLogin` 等。整文件复制旧 `baseConfig.js` 会直接丢失这些新页面入口。

### 4.2 文本迁移粒度

`authoritative_text_candidates.csv/json` 中有 144 个同路径候选：

| 指标 | 结果 |
|---|---:|
| JS 候选 | 64 |
| HTML 候选 | 80 |
| 旧树强中文文件 | 112 |
| 旧树中日混合文件 | 17 |
| 旧树共享汉字、语种不确定 | 15 |
| Totentanz 简体强信号为 0 | 128 |
| HTML 标签序列相同 | 31 / 80 |
| JS `define()` 依赖数组相同 | 9 / 64 |
| JS `text!` 引用集合相同 | 56 / 64 |

推荐规则：

1. 以 Totentanz 当前 JS/HTML 为目标文件。
2. 从 `strong_cn_text_literals.csv/json` 逐条迁移中文 literal/text node。
3. `html_tag_signature_equal=false` 时按 DOM 节点/模板变量位置手工合并。
4. `define_dependencies_equal=false` 时只迁移可见文字，不迁移函数体、模块依赖、路由或事件绑定。
5. `japanese_residue` 不进入中文补丁；`shared_han_ambiguous` 必须人工审义。

### 4.3 CSS 策略

旧 CSS 默认全部标记为 `preserve_new_css`：

- 保留 Totentanz 新 CSS 与 `fonts.css`；
- 旧 CSS 只用于确认旧中文文字是否需要额外宽度、行高、字体回退；
- 不用旧 `help.js` 的“CSS 文本内联”方式替换 Totentanz 的直接 `<link>` 链；
- 如果个别中文标签溢出，只追加最小选择器补丁，不替换整张样式表。

## 5. Web PNG 权威来源候选

### 5.1 已人工确认的 7 张强候选

| 相对路径 | 旧可见文字 | 旧尺寸 | Totentanz 尺寸 | 几何 |
|---|---|---:|---:|---|
| `resource/image_web/common/global/global_gacha.png` | 扭蛋 | 208×246 | 208×246 | 相同 |
| `resource/image_web/common/global/global_memoria.png` | 记忆结晶 | 208×246 | 208×246 | 相同 |
| `resource/image_web/common/global/global_mission.png` | 任务 | 208×246 | 208×246 | 相同 |
| `resource/image_web/common/global/global_shop.png` | 商店 | 208×220 | 208×220 | 相同 |
| `resource/image_web/common/global/global_team.png` | 队伍 | 352×382 | 352×382 | 相同 |
| `resource/image_web/common/global/global_quest.png` | 剧情 | 352×382 | 352×382 | 相同 |
| `resource/image_web/common/global/global_battle.png` | 镜界 | 352×382 | 352×382 | 相同 |

旧 `css/_common/common.css` 对上述根目录路径各有 1 次实际引用。由于 Totentanz tar 缺少当前 `_common` CSS，仍需在最终基础层中再次确认引用路径后再复制。

人工对照图：

- `global-root-comparison.png`
- 机器表：`strong_cn_png_candidates.csv/json`、`curated_global_icons.csv/json`

其余 8,858 个同路径 PNG 未逐张人工确认。总体上：8,865 个 PNG 有 Totentanz 同路径，8,827 个尺寸相同；**同路径/同尺寸只代表兼容概率，不代表中文，也不代表可直接复制**。全部几何清单见 `web_png_geometry_candidates.csv/json`。

### 5.2 `common/global/update2` 明确结论

| 文件 | 旧文字 | 语种结论 | 旧尺寸 | Totentanz 尺寸 | 复制为中文？ |
|---|---|---|---:|---:|---|
| `global_gacha.png` | ガチャ | 日文残留 | 184×196 | 208×246 | 否 |
| `global_memoria.png` | メモリア | 日文残留 | 184×196 | 208×246 | 否 |
| `global_mission.png` | ミッション | 日文残留 | 184×196 | 208×246 | 否 |
| `global_shop.png` | ショップ | 日文残留 | 184×196 | 184×196 | 否 |
| `global_team.png` | チーム | 日文残留 | 184×196 | 184×196 | 否 |
| `global_unit.png` | 魔法少女 | 中日共享汉字，不能证明中文 | 184×196 | 208×246 | 否 |

旧树 HTML/JS/CSS 对 `update2` 路径的引用数均为 0；它更像未启用/兼容保留素材。人工对照图见 `update2-comparison.png`。

## 6. Web 与 native/APK 图像边界

旧归档的 `resource/` 下只有 `image_web/`，没有 `image_native/`：

- Web 层：CSS `url(/magica/resource/image_web/...)`、模板 `<img>`、JS `Image.src`，并由 `help.js` 追加缓存 token。
- Native 层：`nativeCommand.js::changeBg()` 将背景映射为 `resource/image_native/bg/web/`、`.../story/`、`.../quest_top/` 等路径；这些文件不在本旧 Web 归档。
- 桥接：模板上的 `data-nativeimgkey` / `data-nativebgkey` 被 `backboneCommon.js::getNativeObj()` 收集，页面调用 `cmd.getBaseData(common.getNativeObj())`，native 层再通过 `#baseReceive` 等回调交还数据。
- 数据请求：`base.js` 在 `file:///` 模式把 API 映射到 `/magica/json/*.json`，正常 WebView/在线模式映射到 `/magica/api/*`。

因此可把两套资源理解为：

1. **Web 静态/UI 管线**：HTML/JS/CSS/`image_web`，可由服务器或 URL 拦截层提供；
2. **Native/APK/下载资源管线**：`image_native`、Live2D、背景、语音等，由 native command 控制；
3. 两者通过 native key/base64 回调互通，并非完全互不干涉。

对 `magirecocn-image-callgraph-l2d-reuse-final.zip` 与 `magirecocn-images-complete.zip` 的最终归属，应继续以 ZIP 内相对路径和调用图为准；本旧树证据已经能确定 `resource/image_web/...` 属 Web 侧，而 `image_native`/L2D/native key 属 native 侧。

## 7. 推荐注入顺序

1. **P0：冻结 Totentanz 启动层和 CSS。** 不覆盖 `index.html`、`baseConfig.js`、公共 CSS、jQuery、RequireJS、路由与 native command。
2. **P1：文本合并。** 从 `strong_cn_text_literals` 开始，以 Totentanz 当前 JS/HTML 为底逐条迁移；优先 `ajaxControl`、`GlobalMenuView`、`TutorialUtil`、`MyPage`、配置/队伍/任务/活动模板。
3. **P2：7 张已确认根目录全局菜单 PNG。** 先在实际基础 CSS 中确认路径，再按原路径放入补丁。
4. **P3：其余 Web PNG。** 从 `web_png_geometry_candidates` 中筛选 `same_geometry=true && same_bytes=false`，逐张视觉确认；不依据文件名、同路径或同尺寸自动认定中文。
5. **P4：共享汉字/中日混合清理。** 使用 `text_literal_authority` 中的 `japanese_residue` 和 `mixed_cn_japanese` 做残留审核。
6. **排除默认项。** `api/`、`json/`、`js/test/`、`template/test/`、第三方库和旧 `replacement.js` 不进入默认注入集。

## 8. 机器可读成果

主要文件位于本报告同目录：

| 文件 | 内容 |
|---|---|
| `inventory.csv/json` | 10,183 个旧文件的路径、大小、SHA-256/MD5、语言统计、角色、注入级别、依赖与 PNG 几何 |
| `candidate_inventory.csv/json` | 旧树注入候选视图 |
| `summary.json` | 旧树总计与 replacement 审计摘要 |
| `replacement_manifest.json` | 从 `replacement.js` 提取的 8,558 路径表 |
| `replacement_manifest_audit.csv` | token 匹配/漂移/缺失审计 |
| `module_path_map.csv/json` | 旧 RequireJS 模块 ID→路径映射 |
| `dependencies.json` | JS `define()` 与 `text!` 引用图 |
| `localizable_strings.csv/json` | 旧 JS/HTML CJK 字符串原始清单 |
| `text_literal_authority.csv/json` | 带中/日/共享汉字分类和来源资格的逐条清单 |
| `strong_cn_text_literals.csv/json` | 879 条同路径、来源合格的强中文文本候选 |
| `authoritative_text_candidates.csv/json` | 144 个同路径文本文件的结构/依赖兼容性 |
| `old_vs_totentanz_inventory.csv/json` | 旧树与 Totentanz 同路径字节/几何比较 |
| `web_png_geometry_candidates.csv/json` | 8,865 个同路径 PNG 的几何/哈希与审核提示 |
| `curated_global_icons.csv/json` | 21 张 root/update2 图标人工语言分类 |
| `strong_cn_png_candidates.csv/json` | 7 张强中文、同几何 PNG 候选 |
| `module_map_comparison.csv/json` | 旧/末期模块映射差异 |
| `totentanz_index_dependencies.csv/json` | Totentanz 入口依赖与 tar 缺失状态 |
| `artifact_hashes.json` | 主要成果 SHA-256 |
| `source_hashes.json` | 两个输入归档 SHA-256 |
| `commands.log`、`extract.log`、`archive-test.log` | 实际命令与验证记录 |

## 9. 实际成功命令（摘要）

```powershell
Get-FileHash -LiteralPath 'A:\magicaOLD.7z' -Algorithm SHA256
& 'C:\Program Files\7-Zip\7z.exe' l -slt 'A:\magicaOLD.7z'
& 'C:\Program Files\7-Zip\7z.exe' x 'A:\magicaOLD.7z' -o'<work>\extracted' -y
& 'C:\Program Files\7-Zip\7z.exe' t 'A:\magicaOLD.7z'
tar -tf 'A:\totentanz-frontend.tar'
python analyze_old_magica.py
python compare_totentanz.py
Get-FileHash -LiteralPath 'A:\totentanz-frontend.tar' -Algorithm SHA256
```

退出状态和完整绝对路径见 `commands.log`。早期三次分析器调用在性能调优时终止，未采纳其产物；最终 `analyze_old_magica.py` 与 `compare_totentanz.py` 均 exit 0。

## 10. 限制与下一步验证点

- Totentanz tar 缺少入口所引用的公共 CSS、`base.js`、`replacement.js` 和库文件；最终合并前必须把真实运行基础层纳入比较。
- 除 `common/global` 与 `update2` 外，其余数千 PNG 尚未逐张 OCR/人工审图；机器表明确保留为 `unreviewed_visual`。
- 简体中文信号是保守字形启发式；`商店、魔法少女` 等共享汉字必须结合上下文人工判断。
- 本阶段只做隔离分析和候选表，没有修改或打包最终补丁。
