# cn_js_update v26 人工校对清单

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

权威顺序为：官方旧国服 dump > Wiki > 已验证既有人工 > 新人工／LLM。
未被产品运行时消费的四张迁移 TSV 另按有无逐条复核证据分层，详见仓库根目录
`i18n/generated/`；它们不会自动覆盖 `magica/`。
