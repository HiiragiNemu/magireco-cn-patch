# v26 全套机翻／LLM 人工校对清单

本目录由 `tools/build-v26-machine-review.py` 可复现生成；生成器只读取产品与审计证据，不创建或改写中文译文。
`inputs/` 固化了 pass8 与 Wiki 的最小必要来源快照，干净检出不依赖其他本地仓库／工作树。

## 总览

- 全量统一主表：**15,976** 行（`full_machine_translation_review.tsv`）
- runtime residual／非 residual：**12,399**
- static JS／HTML：**303**
- frontend：**1,685**（含 **53** 条空候选）
- Wiki glossary 支撑层：**955**
- overrides／fragments：**16**
- engine runtime：**615**（58 条国服权威／权威术语、252 条 root 语义审查定稿、3 条 Wiki、1 条结构片段、未核验 0 条）；schema-2 最终审查覆盖历史未知来源 212 条，其中 2 条由既有更高权威继续接管，实际接管 210 条（35 条双 ABI 官中精确文本、175 条 root-reviewed）
- battle miss 候选但未进入 runtime：**3**
- battle runtime 全量采样：**20** 个唯一 miss，含 **8** 条语言决策；7 条 actionable、1 条国服原样保留、12 条中文／非语言项
- Pass18：**939**（938 条 runtime + 1 条 static）；runtime 中 **536** 条仍直接等于 Pass18 after，**402** 条由 `Pass18 after -> visible-term closure -> current` 精确链解释；其中 **12** 条 root 亲译仍待人工复核
- 当前 runtime 术语闭合：**3,136** 条，均以稳定业务键／字段核对产品值并保留既有 Pass18 历史链
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
- `engine_i18n_review_615.tsv`：native 直接读取的 engine 表（含 301 条动态 AP 倒计时前缀闭合规则）。
- `battle_miss_needs_review.tsv`：仅供根任务复核、未进入 runtime 的候选。
- `battle_runtime_language_decisions_8.tsv`：实战 8 条语言决策的来源／机翻状态。
- `battle_runtime_unique_misses_20.tsv`：持久日志 20 个唯一 miss 的无遗漏分类。
- `pass18_authority_corrections_939.tsv`：Pass18 before／after 与最终产品复核。
- `visible_term_closure_3136.tsv`：当前 3,136 条术语闭合的稳定键、来源层和历史继承。
- `explicit_llm_history_264.tsv`：pass8 明确 LLM 历史。
- `proper_name_priority_review.tsv`：专名优先人工校对视图。
- `SHA256SUMS.txt`：所有产物及生成器哈希。
