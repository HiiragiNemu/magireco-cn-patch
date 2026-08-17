# v26 全套机翻／LLM 人工校对清单

本目录由 `tools/build-v26-machine-review.py` 可复现生成；生成器只读取产品与审计证据，不创建或改写中文译文。
`inputs/` 固化了 pass8 与 Wiki 的最小必要来源快照，干净检出不依赖其他本地仓库／工作树。

## 总览

- 全量统一主表：**12,933** 行（`full_machine_translation_review.tsv`）
- runtime residual／非 residual：**9,665**
- static JS／HTML：**303**
- frontend：**1,685**（含 **53** 条空候选）
- Wiki glossary 支撑层：**955**
- overrides／fragments：**16**
- engine runtime：**306**（原 303 条保持原来源状态；另新增 3 条截图实证 exact 规则，来源分别为官中 native、Wiki/稳定业务键和本轮粗译）
- battle miss 候选但未进入 runtime：**3**
- battle runtime 全量采样：**20** 个唯一 miss，含 **8** 条语言决策；7 条 actionable、1 条国服原样保留、12 条中文／非语言项
- Pass18：**939**，其中 **12** 条 root 亲译仍待人工复核
- pass8 明确 LLM 历史：**264**

## 筛选

统一主表可按 `source_bucket` 筛选：`official`、`wiki`、`legacy-ai`、`new-root-human`、`unknown`。每行均含原文、当前中文、建议中文、产品／引用位置、来源层级、证据、是否机翻、置信度与复核状态。

frontend 历史空候选 53 条按精确证据闭合：18 条 `runtime-absent/not-backlog`、33 条 `visible-cn-compatible-identity`、1 条 `identity-punctuation`；“属性相性”由国服同路径同 DOM 节点精确命中“属性克制”，状态为 `official-source-verified`。生成器没有写入产品译文。

## 子表

- `runtime_translation_review.tsv`：运行时 23 字典的 residual 与非 residual 全集。
- `static_js_html_review.tsv`：静态 JS／HTML。
- `frontend_all_1685.tsv`：四表中的 frontend 全量，含空候选。
- `glossary_wiki_955.tsv`：Wiki 第二权威支撑层。
- `overrides_fragments_16.tsv`：路径／跨节点混合来源补丁。
- `engine_i18n_review_306.tsv`：native 直接读取的 engine 表。
- `battle_miss_needs_review.tsv`：仅供根任务复核、未进入 runtime 的候选。
- `battle_runtime_language_decisions_8.tsv`：实战 8 条语言决策的来源／机翻状态。
- `battle_runtime_unique_misses_20.tsv`：持久日志 20 个唯一 miss 的无遗漏分类。
- `pass18_authority_corrections_939.tsv`：Pass18 before／after 与最终产品复核。
- `explicit_llm_history_264.tsv`：pass8 明确 LLM 历史。
- `proper_name_priority_review.tsv`：专名优先人工校对视图。
- `SHA256SUMS.txt`：所有产物及生成器哈希。
