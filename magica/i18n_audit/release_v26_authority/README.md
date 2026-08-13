# cn_js_update v26 权威层与人工校对清单

本目录只保存审计证据，不进入 `cn_js_update.zip`。

- `manual_review_checklist.tsv`：Pass16 的 1,158 个逻辑条目与 Pass17 的 25 个
  专名权威化条目合并，共 1,183 条。
- `manual_review_checklist.summary.json`：状态、风险、类别、来源层统计及清单哈希。
- `pass17_name_authority_manual_review.tsv`：针对赫露迦、台与、阿玛琉莉丝、卓玛、
  爱生眩等 25 处最终变更的高优先级复核表。
- `pass17_targeted_authority_verification.json` 与
  `pass17_verification_record.json`：Pass17 变更的逐项结果与验证命令记录。
- `runtime_layer_manifest.json` 与 `RUNTIME_LAYER_SHA256SUMS.txt`：最终 23 张
  独立字典及生成后 jQuery 的 LF 字节、大小与 SHA-256；由
  `Build_JS_Injector.py` 确定性重建，并由 `tools/verify-runtime-layer.py` 复核。
- `UI_UNION_VALIDATION_REPORT.md`、`ui_union_validation.json` 与
  `conflict_slot_ledger.tsv`：最新 main 的 UI/CSS、Pass16 中文层及三个指定扭蛋文件
  的三方并集复验；14 个冲突文件、1,510 个文本槽位均已逐项记账，遗漏与敏感属性
  漂移为 0。
- `pass18_authority_corrections.tsv`：939 个最终可见字段的 before／after、稳定键、
  权威层、证据、置信度与复核状态；其中 12 项由根任务亲译并明确保留人工复核标记。
- `pass18_engine_official_additions.tsv`：5 条本轮写入 `engine_i18n.tsv` 的国服精确
  稳定 ID、精确 art-ID 拼接或国服 UI 原样保留项；均明确标为非机翻。
- `pass18_battle_miss_review.tsv`：6 条 battle miss 的处置总表；3 条进入运行时，
  3 条仅保留为 `needs-review/root-translation-required`，不冒充国服译文。
- `machine_translation_review/battle_runtime_language_decisions_8.tsv` 与
  `battle_runtime_unique_misses_20.tsv`：legacy-client 实战持久日志的 8 条语言决策
  与全部 20 个唯一 miss；7 条 actionable、1 条国服原样保留、12 条已中文／
  非语言项均逐条保留，三条 review-only 候选未写入最终 engine 表。
- `machine_translation_review/`：12,930 行全量统一对照表，以及 runtime、静态
  JS／HTML、四张维护 TSV、engine、Pass8 明确 LLM 历史和专名优先复核子表。
  每行均可按 `source_bucket`、`machine_translated` 与 `review_status` 筛选。
- `dsv4_terminal_handoff/`：本轮低权重译文独立复审的确定性终态交接。范围共
  1,912 条，DSV4 已完成 74/96 批、1,472 条：1,390 条 approved、37 条
  correction、45 条 unresolved；余额耗尽后另有 440 条转人工。人工决策总表
  `nonapproved_review.tsv` 共 522 条，其中 258 条是当前产品低权重译文，264 条
  只用于确认 Pass8 历史高权重文本未被回流覆盖。该目录原样保存完整对照、来源、
  父／子审查结论、人工决策栏、staging-only patch 与逐项 rollback；所有决策栏
  当前留空，`product_tree_writes=0`、`protected_text_changes=0`。
- `tools/verify-dsv4-terminal-handoff.py`：逐字节重开上述 17 个交付文件，核对
  1,912/1,472/440/522 分区、37 条 patch/rollback 双射、决策枚举、来源字段、
  保护边界和 SHA-256。终态材料只供审计，不进入运行时包。
- `dsv4_human_decisions.tsv`：供人工实际填写的 1,912 行副本；其中 1,390 行
  DSV4 approved 保持只读留空，522 行填 `human_decision/reviewer/timestamp/final_value`。
  `manual_queue_analysis/` 提供 522 行逐项风险分类：258 条当前产品文本没有任何一条
  可免审直接批准，另 264 条是受保护历史确认；结构硬风险 8 条、现有建议补丁自身
  风险 13 条，因此禁止整包执行 37 条 correction patch。
- `pass18_verification.json`：939/939 后像、43 条禁回流规则、303 条 engine、
  25 份 CSS、静态标签和 12 条根任务译文的机器验证记录。
- `pass18_product.patch`、`pass18_rollback_verification.json` 与
  `tools/rollback-v26-pass18.ps1`：可读变更、隔离回滚实测与可运行回滚。

权威顺序为：官方旧国服 dump > Wiki > 已验证既有人工 > 新人工／LLM。
未被产品运行时消费的四张迁移 TSV 另按有无逐条复核证据分层，详见仓库根目录
`i18n/generated/`；它们不会自动覆盖 `magica/`。

当前发布硬门为 **manual handoff**：未完成 522 项人工决策前，只允许构建候选包、
推送功能分支和建立 Draft PR；不得将该状态表述为低权重译文审查全部完成，也不得
执行 stable promotion。完整人工表副本填写并通过
`tools/validate-dsv4-human-review.py`
后，还必须重跑权威保护、运行时结构、双构建和事务发布回归。
