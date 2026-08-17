# Totentanz 选择性中文化来源审计（2026-08-17）

## 目的与边界

本目录记录本轮从当前美服前端结构中**只选择具有实际汉化价值的文件**进入 `cn_js_update.zip` 的依据。它不是 `A:\totentanz-frontend` 或 `A:\magicaOLD` 的整树导入清单。

- `A:\totentanz-frontend`：抓包得到的现役美服前端结构参考。抓包不是完整服务端快照；缺失文件由现有产品树或只读服务端留档补齐结构证据。
- `A:\magicaOLD`：旧国服官方前端；只回收能映射到现役结构的中文文本或同尺寸权威图片，不用旧文件覆盖新结构。
- 中文来源优先级：旧国服官方文本／解密数据 > Wiki > 已确认人工译文 > 本轮人工补译。
- 美服结构、选择器、EJS、事件节点、资源尺寸和动画几何始终优先；只替换可见文字。

`selected_files.tsv` 逐项记录结构来源、中文来源层级、选择理由和是否进入包。产品树文件不在本目录内复制，避免形成第二份运行时源。

## 本轮精选内容

1. **HTML**：只收录仍有可见日文、英文或不规范旧译的页面模板；保留现役 EJS/DOM 结构。
2. **CSS**：20 个抓包 CSS、现有 `common.css`/`MainQuest.css`，以及抓包未包含但截图实证需要的 Group Battle Boss/Result CSS。只覆盖非空 `content:` 或烘焙图片文字的显示层。
3. **PNG**：仅 `result_title_header.png` 采用旧国服同路径、同尺寸的“心魔战”权威原图进入包。其余八张含字 PNG 只作为定位证据，当前由 CSS 文本层覆盖，不把原日文／英文 PNG 复制进包。
4. **engine TSV**：修正四个无法命中的日文源键标点，并根据原生技能弹窗截图增加 3 条 exact 规则：技能名、技能说明和 `発動→发动`。三条来源分别标成最低权重粗译、Wiki 稳定业务键和旧国服 native 精确上下文，没有混标成同一权威层。

## 明确排除

- 不整树导入 `A:\totentanz-frontend` 的 JS/HTML/CSS/JSON/PNG。
- 不把 `A:\magicaOLD` 的旧结构、旧选择器或旧运行逻辑覆盖到现役文件。
- 不收录没有可见文字、只有布局／动画／图片引用的文件。
- 不把注释、变量名、路由、`id`、`class`、`data-*`、URL 或资源键当作可见残留。
- 不自动翻译用户自定义的小组名和登录名（例如截图中的 `Inkyubus`、`Kyubi*`）。
- 不翻译官方国服仍保留的正式术语或通用缩写，例如 `Magia`、`Connect`、`Lv`、`HP`、`ATK`、`DEF`、`EXP`、`GP`、`BONUS`。
- 不收录 test/debug 页面，除非它同时是实际产品入口并有独立运行时证据；本轮20个新增CSS清单已排除 test CSS。
- 不因服务端清单存在就导入没有汉化价值的文件。

## `engine_i18n.tsv` 权威度结论

当前表有 306 条规则：304 条 exact、2 条 prefix。目标列中 289 条含中文，16 条是正式保留或无须翻译的值，另 1 条是有文档依据的跨节点空目标结构规则。

原 303 条可证明的证据维度包括：

- official direct/context：17 条；
- 两个 ABI 的 native 字面量命中：62 条；
- Wiki additional：19 条；
- Wiki conflicts：2 条；
- structural：1 条；
- remaining unknown/low：202 条。

这些维度**可能重叠，禁止相加后冒充303条的互斥来源总数**。尤其“两 ABI 字面量命中”只证明日文源键确实出现在两个 native 二进制中，不证明中文目标来自官方，也不等于逆向提取了官方翻译。新增 3 条另行逐项记载：1 条官中 native 精确上下文、1 条 Wiki 稳定 ID、1 条经用户允许进入粗译生产的最低权重 LLM 候选。

本项目没有完整反编译两份 200 MB 以上的 `libmadomagi_native.so`，也没有从 native 中抽取出一整张官方中文 TSV；但确实做过**有界的 ELF 字符串／函数对齐逆向**：以 `pyelftools`、Capstone 对 arm64-v8a（277,065,000 字节）与 armeabi-v7a（221,488,240 字节）执行目标字符串、交叉引用和 30,205 个公共动态函数的对齐。该工作证明了一部分日文源键在双 ABI 中存在，并为少量上下文映射提供证据；它不证明对应中文目标都是官中。

因此当前表实际来自运行时 miss 驱动维护、稳定 ID／上下文官中核验、Wiki 比对，以及既有人工／低权重译文。鉴于有效表仅306条，本轮不再扫描 native，也不把成本很高的完整 native 逆向作为中文化前置条件；以后仅在设备出现新 miss 时做定点检索。

详细机器可读结论见 `engine_i18n_authority_summary.json`。

## 现有绝对证据

- 美服抓包树：`A:\totentanz-frontend`
- 旧国服前端：`A:\magicaOLD`
- 旧国服客户端解码树：`D:\magia\MyProducts\MAGIA RECORD CN\origin_apktool_decoded`
- 旧国服稳定 ID 样本：`D:\magia\MyProducts\MAGIA RECORD CN\Decoded_MyPage.json`
- Wiki 数据：`D:\magia\MyProducts\magireco-wiki-data`
- 截图、现役 Group Battle CSS/PNG/API 留档：`D:\magia\AuditSnapshots\runtime_source_audit_20260817`
- engine 306 条逐项审计：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\js_v26_release_final_20260813\magica\i18n_audit\release_v26_authority\machine_translation_review\engine_i18n_review_306.tsv`
- 原生技能弹窗逐项控制源：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\js_v26_release_final_20260813\magica\research\totentanz-selective-localization-20260817\native_battle_popup_audit.md`
- engine 官中新增证据：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\js_v26_release_final_20260813\magica\i18n_audit\release_v26_authority\pass18_engine_official_additions.tsv`
- native 两 ABI 原文件（仅既有字面量证据来源；本轮不扫描）：
  - `D:\magia\MyProducts\MAGIA RECORD CN\origin_apktool_decoded\lib\arm64-v8a\libmadomagi_native.so`
  - `D:\magia\MyProducts\MAGIA RECORD CN\origin_apktool_decoded\lib\armeabi-v7a\libmadomagi_native.so`
- native/runtime 既有审计快照：`D:\magia\AuditSnapshots\20260809-181134360-author-correction-native-abi-checkpoint`
- 定点 ELF 对齐脚本：`D:\magia\AuditSnapshots\2026-08-08-official-cn-recovery\align_engine_table.py`
- 定点 ELF 对齐报告：`D:\magia\AuditSnapshots\2026-08-08-official-cn-recovery\engine-table-official-cn-audit.json`
- 双 ABI 严格复核：`D:\magia\AuditSnapshots\2026-08-09-official-cn-recovery-current-table-v2\run-a\manifest.json`

## 使用方式

构建与复核以 `selected_files.tsv` 为允许清单：只有 `package_inclusion=yes` 的产品路径可进入本轮包。标为 `evidence-only` 的 PNG 只用于证明截图残留来自何处；不得被误当成需要复制的产品资产。
