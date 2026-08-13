# DSV4 Terminal Assembly：522 条人工队列只读分析

生成时间：`2026-08-13T11:32:00.052932+00:00`  
输入目录：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\dsv4_terminal_assembly_20260813_final_a`  
输出目录：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\manual_queue_analysis_20260813`

## 1. 边界与结论

- 本报告只读解析 terminal assembly；未运行 Git，未写入产品树，未应用译文，也未发布。
- terminal assembly 自证状态：`terminal-manual-handoff-verified-staging-only`；verification：`PASS`；模式：`manual_handoff`；受保护文本变化：`0`。
- **522 条全部仍未填写 `human_decision/reviewer/timestamp/final_value`，当前可直接批准数为 0。**
- 522 = **258 条当前低权重产品候选** + **264 条受保护历史对照**。
- 258 条都标为 `legacy_unverified_ai_assisted`，且 `authority_status=no_per_entry_official_or_wiki_pair`；官方、Wiki、确认人工逐条证据均为空，因此不能从现有证据自动晋级。

## 2. 522 条精确拆分

| 队列 | 数量 | 允许的人工作出决定 | 产品写入 |
|---|---:|---|---|
| 当前低权重候选 | 258 | `approve-current` / `revise` / `unresolved` | 当前全部 `false` |
| 受保护历史对照 | 264 | `keep-authority` / `unresolved` | 永远保持 `false` |
| 合计 | 522 | 所有决定栏当前为空 | 0 条允许写产品 |

父结论：`manual-required=440`、`unresolved=45`、`correction=37`。

### 2.1 当前 258 条的路径、字段与结论

| source_path | source_field | parent_verdict | 数量 |
|---|---|---|---:|
| i18n/fragments.tsv | candidate_cn | unresolved | 1 |
| i18n/frontend-strings.tsv | candidate_cn | correction | 37 |
| i18n/frontend-strings.tsv | candidate_cn | manual-required | 167 |
| i18n/frontend-strings.tsv | candidate_cn | unresolved | 44 |
| i18n/overrides.tsv | candidate_cn | manual-required | 9 |

进一步展开：

- `i18n/frontend-strings.tsv / candidate_cn`：248（167 未审、44 unresolved、37 correction）。
- `i18n/overrides.tsv / candidate_cn`：9（全部未审）。
- `i18n/fragments.tsv / candidate_cn`：1（unresolved）。
- 258 条的最高来源层全部为 `legacy_unverified_ai_assisted`；逐项官方/Wiki/确认人工对照均为 0。

### 2.2 受保护历史 264 条

| source_path | source_field | 数量 |
|---|---|---:|
| magica/js/libs/doppelList.json | description | 114 |
| magica/js/libs/doppelList.json | name | 35 |
| magica/js/libs/doppelList.json | title | 114 |
| magica/js/libs/itemList.json | name | 1 |

- `doppelList.json` 263 条；`itemList.json` 1 条。
- 字段：description 114、title 114、name 36。
- 权威状态：`resolved_to_wiki_or_wiki_equivalent=153`、`resolved_to_wiki_plus_official_cn_term=110`、`resolved_by_wiki_context_fix=1`。
- 154 条 current 与 Wiki 字面一致；110 条因加入官方术语而与 Wiki 字面不同。
- 这些行是 **comparison-only**；人工只能记 `keep-authority` 或 `unresolved`，不能通过低权重通道修改。

## 3. 当前 258 条：批准与裁决分类

| 分类 | 数量 | 含义 |
|---|---:|---|
| 可直接批准 | **0** | 现有合同中没有一条已填人工决定，也没有逐项官方/Wiki证据。 |
| 独立语言审查 | **176** | 认证中断后未经过角色审查。 |
| 语言裁决 | **40** | 已审，但语义有 correction/unresolved，或语义与格式同时冲突。 |
| 仅格式裁决 | **41** | 日文语义角色已 approved；格式角色要求修正。仍须人工决定。 |
| 仅 provenance 确认 | **1** | 语言和格式已 approved，但命中受保护子串。 |

校验：`176 + 40 + 41 + 1 = 258`。

仅 provenance 项：`LOW-MT-00507`（`現代神浜編 ストーリー解放` → `现代神滨篇 剧情解放`）；语言和格式均通过，但“现代神滨篇”属于受保护文本，须确认保持原值。

### 3.1 需要语言裁决的 40 条

`LOW-MT-00312`、`LOW-MT-00363`、`LOW-MT-00371`、`LOW-MT-00417`、`LOW-MT-00441`、`LOW-MT-00482`、`LOW-MT-00495`、`LOW-MT-00540`、`LOW-MT-00566`、`LOW-MT-00570`、`LOW-MT-00574`、`LOW-MT-00581`、`LOW-MT-00601`、`LOW-MT-00620`、`LOW-MT-00627`、`LOW-MT-00638`、`LOW-MT-00666`、`LOW-MT-00672`、`LOW-MT-00674`、`LOW-MT-00685`、`LOW-MT-00703`、`LOW-MT-00784`、`LOW-MT-01015`、`LOW-MT-01239`、`LOW-MT-01248`、`LOW-MT-01294`、`LOW-MT-01378`、`LOW-MT-01426`、`LOW-MT-01446`、`LOW-MT-01485`、`LOW-MT-01496`、`LOW-MT-01519`、`LOW-MT-01538`、`LOW-MT-01540`、`LOW-MT-01580`、`LOW-MT-01584`、`LOW-MT-01591`、`LOW-MT-01672`、`LOW-MT-01685`、`LOW-MT-01699`

### 3.2 仅格式裁决的 41 条

`LOW-MT-00315`、`LOW-MT-00317`、`LOW-MT-00322`、`LOW-MT-00323`、`LOW-MT-00343`、`LOW-MT-00350`、`LOW-MT-00355`、`LOW-MT-00369`、`LOW-MT-00388`、`LOW-MT-00402`、`LOW-MT-00422`、`LOW-MT-00423`、`LOW-MT-00427`、`LOW-MT-00431`、`LOW-MT-00439`、`LOW-MT-00449`、`LOW-MT-00452`、`LOW-MT-00460`、`LOW-MT-00467`、`LOW-MT-00474`、`LOW-MT-00486`、`LOW-MT-00501`、`LOW-MT-00506`、`LOW-MT-00521`、`LOW-MT-00526`、`LOW-MT-00527`、`LOW-MT-00535`、`LOW-MT-00550`、`LOW-MT-00569`、`LOW-MT-00583`、`LOW-MT-00594`、`LOW-MT-00622`、`LOW-MT-00631`、`LOW-MT-00683`、`LOW-MT-00684`、`LOW-MT-00688`、`LOW-MT-00700`、`LOW-MT-00852`、`LOW-MT-01090`、`LOW-MT-01095`、`LOW-MT-01200`

### 3.3 尚未独立语言审查的 176 条

完整稳定 ID、原文、现译与风险标记位于 `analysis.json -> current_258.items`；不要用“看起来通顺”批量批准。

## 4. 高风险专名、错位与格式

### 4.1 专名/术语

- 这 258 条中未检出明确角色人名或 `ちゃん/くん/さん` 人物称呼候选；这不等于术语无风险。
- 检出 **56 条领域术语承载项**，逐项及命中术语在 `analysis.json -> current_258.domain_terminology_index`。
- 已确认的退役错词：`LOW-MT-01485`，日文 `キモチ戦は`，当前 `心情战`，建议 `心魔战`。
- 术语重点还包括 `マギア`、`ドッペル`、`ミラーズ`、`メモリア`、`デスティニージェム`、`Charge/Blast/Accele` 等；它们没有逐项官方/Wiki配对，必须按项目术语表复核。

### 4.2 当前值的结构/错位风险

共 **8 条**命中可复现的源文—现值结构或对齐不一致：

`LOW-MT-00312`、`LOW-MT-00631`、`LOW-MT-00852`、`LOW-MT-01090`、`LOW-MT-01095`、`LOW-MT-01200`、`LOW-MT-01888`、`LOW-MT-02958`

重点：

- `LOW-MT-00312`：JS 拼接操作数由 `l+e` 变为 `e+l`。
- `LOW-MT-00631`：高亮 `span` 范围错位。
- `LOW-MT-00852`、`LOW-MT-01200`、`LOW-MT-01888`：换行转义反斜杠宽度不一致。
- `LOW-MT-01090`：现值多出一个 `@`。
- `LOW-MT-01095`：换行标签断句位置改变。
- `LOW-MT-02958`：日文助词 `を` 被映射为 `<DELETE>` 哨兵，必须连同相邻节点审查。

### 4.3 建议补丁本身的风险

共有 **13 条** suggested_cn 命中结构宽度、占位符或日文残留风险：

`LOW-MT-00622`、`LOW-MT-00627`、`LOW-MT-00631`、`LOW-MT-00666`、`LOW-MT-00672`、`LOW-MT-01200`、`LOW-MT-01239`、`LOW-MT-01248`、`LOW-MT-01294`、`LOW-MT-01378`、`LOW-MT-01446`、`LOW-MT-01580`、`LOW-MT-01672`

其中：

- 12 条建议把 `\x3c/\x3e` 前的双反斜杠缩成单反斜杠；不得把“显示相同”当成字节等价。
- `LOW-MT-00666` 的建议新增源文没有的 `{0}`。
- `LOW-MT-01294` 的建议残留日文 `の`。
- `LOW-MT-01200` 的源文是二反斜杠、现值是三反斜杠，但建议值是一反斜杠，仍未恢复源结构。
- 因此，现有 37 条 `correction_patch.json` **不适合整包直接执行**；必须逐项批准并重新生成受哈希保护的补丁。

### 4.4 语义与格式审查索引

- 语义 correction：36 条：`LOW-MT-00417`、`LOW-MT-00482`、`LOW-MT-00495`、`LOW-MT-00540`、`LOW-MT-00566`、`LOW-MT-00570`、`LOW-MT-00574`、`LOW-MT-00581`、`LOW-MT-00601`、`LOW-MT-00620`、`LOW-MT-00627`、`LOW-MT-00638`、`LOW-MT-00666`、`LOW-MT-00672`、`LOW-MT-00674`、`LOW-MT-00685`、`LOW-MT-00703`、`LOW-MT-00784`、`LOW-MT-01015`、`LOW-MT-01239`、`LOW-MT-01248`、`LOW-MT-01294`、`LOW-MT-01378`、`LOW-MT-01426`、`LOW-MT-01446`、`LOW-MT-01485`、`LOW-MT-01496`、`LOW-MT-01519`、`LOW-MT-01538`、`LOW-MT-01540`、`LOW-MT-01580`、`LOW-MT-01584`、`LOW-MT-01591`、`LOW-MT-01672`、`LOW-MT-01685`、`LOW-MT-01699`
- 语义 unresolved：4 条：`LOW-MT-00312`、`LOW-MT-00363`、`LOW-MT-00371`、`LOW-MT-00441`
- 格式 correction：53 条（完整列表见 JSON）。
- 格式 unresolved：2 条：`LOW-MT-00312`、`LOW-MT-00674`

## 5. 建议人工处理顺序

1. **先处理结构硬风险**：第 4.2、4.3 节项目，逐字比对反斜杠、`@`、HTML/转义标签、拼接操作数和哨兵。
2. **再处理 40 条语言裁决**：核对日文语义、片段前后节点、术语和谓词省略；证据不足记 `unresolved`。
3. **处理 41 条格式裁决**：国服中文标点优先；标签、属性、占位符和反斜杠必须字节级保持。
4. **处理 176 条未审文本**：独立逐项审查，不继承“看似通顺=通过”。
5. **最后处理 264 条历史对照**：仅记 `keep-authority` 或 `unresolved`，不得把历史 LLM 候选回流进当前值。

## 6. 完成门

在以下条件同时满足前，258 条低权重文本仍属于人工队列：

- 522 条全部填写合法 decision、reviewer、ISO-8601 timestamp；
- `approve-current` 的 final_value 与 current_cn 完全一致；`revise` 有非空且不同的新值；`unresolved` 不携带可应用值；
- 264 条受保护历史项只使用 `keep-authority/unresolved`，保护文本变化为 0；
- 258 条中 unresolved 清零，或发布流程明确把未决项排除在可应用集合外；
- 所有标签、属性、转义宽度、占位符、拼接顺序通过字节级验证；
- 正式补丁必须从已批准决定重新生成，不能直接复用当前 37 条 correction patch。

机器可读逐项结果：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\manual_queue_analysis_20260813\analysis.json`。
