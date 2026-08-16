# Pass22 粗译生产闭环

本目录记录用户于 2026-08-17 明确批准“先使用当前最终中文生产粗译版，后续再进行人工精修”后的完整落盘证据。

## 当前口径

- 输入工作簿：`A:\magireco_v26_translation_review_1565.xlsx`
- 稳定条目：1,565
- 空最终中文：0
- 保留现有机器译文：1,536
- 采用既有机器审查建议：29（其中 27 条相对旧值发生字面变化，2 条与旧值相同）
- 精确运行时目标：1,443 项 / 2,439 个位置
- 当前产品未引用、仅维护层保留：122 项
- 人工复核声明：0
- provenance 模式：`rough-production`
- 粗译候选层：`new_proposal`；有效运行时来源仍为 `legacy_unverified_ai_assisted`
- 官方国服 / Wiki / 已确认人工保护字段：2,777，变化 0

工作簿没有丢失定位信息。可见页只保留日文、旧中文、最终中文；稳定 ID、来源哈希和目标合同保存在隐藏绑定列及 `pass20_product_targets.json`。本次导入和物化已按这些绑定逐项验证。

## 为什么本轮产品差异为 0

工作簿中的 29 条建议已在前一提交按用户指令写入维护表和产品树；其余 1,536 条最终中文等于当前产品值。因此本轮新增的是 1,565 条完整粗译发布回执和最低权重 provenance，未再次改写运行时文本。最终包仍包含这些已落地译文。

## 证据

- `workbook_import_verification.json`：A 盘工作簿的 1,565 项导入结果
- `staging_verification.json`：仓库外暂存、结构、JS/HTML/JSON、保护字段与回滚演练
- `promotion_verification.json`：5 个维护层 / 审计文件的原子提升
- `materialization_verification.json`：1,443 项、2,439 个运行时位置及 122 项维护层文本闭合
- `release_gate_verification.json`：粗译生产门开启，pending=0、unresolved=0
- `product_patch.json` / `product.diff`：本轮运行时增量为 0 的机器记录
- `rollback/`：逐文件 before/after 快照和清单
- `rollback.ps1`：精确回滚入口

## 后续人工精修

未来人工修改同一 1,565 个稳定键时，使用人工导入模式；新记录写入 `#human-review:ITEM`，粗译记录保留为历史 provenance。人工层权重高于粗译层，仍低于官方国服和 Wiki 保护文本。
