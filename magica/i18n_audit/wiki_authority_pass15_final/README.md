# Pass15 最终权威中文层（2026-08-09）

本目录是对 pass8 之后所有可复现权威层的最终合并审计。运行时文本遵循固定优先级：

1. `magireco_cn_dump_20221010_decrypted_json` 的国服正式文本；
2. 冻结提交 `42641f87818b37262032fd4dc5d5c756a48fed7a` 的 `HiiragiNemu/magireco-wiki-data`；
3. 数字、罗马等级、目标、回合、方向均不漂移的封闭等价规则；
4. 人工／LLM 文本只在前三层均无证据时保留。

标点按国服同字段规则处理，不做全局 `・` 替换。CSS、新 UI 与下列三份扭蛋文件保持基准提交 `20e35db411e83d710662c98f12c1374fa8363dda` 的原始字节：

- `magica/js/campaign/box_gacha/CampaignBoxGachaTop.js`
- `magica/template/campaign/box_gacha/CampaignBoxGachaTop.html`
- `magica/template/gacha/GachaTop.html`

## 最终结果

- 相对产品基准变化的独立 JSON 字段：`382`；逐字段来源覆盖 `382/382`。
- 有序来源转换：`410`；其中两步转换字段 `28`，未覆盖回退 `0`。
- post-pass14 权威证据：`892` 行、`863` 个唯一字段；运行时转换 `357` 行、只升级来源 `535` 行。
- pass9 原始 residual：`11,055`；已验证 pass14 residual：`9,643`；最终严格 residual：`8,959`。
- 最终 residual 不是“待翻译字段”，而是仍缺少独立国服／Wiki／封闭等价证据的 LLM 或其他来源候选；其当前中文仍保留。

## 对旧云端计数的纠正

- pass17 有 `5` 项已经由 pass10 的 Doppel 关联等价层扣除，保留更强 Wiki 证据但不重复扣 residual。
- 旧 pass24=`86` 可精确分解为正确 pass24=`73` 加上 pass25 的 `itemList` 13 项；旧算法会把这 13 项在 pass25 再扣一次。
- pass25 有 `52` 条证据，其中 `sectionList/208102/areaDetailName` 已由后续 pass29 顺序转换覆盖，净新增 `51`。
- pass26/27 的旧 `213` 项没有新增 residual：独立重放证明它们已被 pass8 国服层覆盖。
- pass28 中有 `10` 项已由 pass12 覆盖。

因此旧聊天中的 `8,722` 不作为最终数字；本目录用稳定业务键重新逐项相减后得到 `8,959`。

## 关键文件

- `authority_layer_ledger_892.tsv`：最终合并来源账本。
- `authority_layer_summary.json`：计数与层级摘要。
- `remaining_residual_8959.tsv`：严格剩余集合。
- `residual_deduction_steps.tsv`：逐层算术。
- `pass17_pass10_overlap_correction_5.tsv`：pass17 重复扣减纠正。
- `sources/field_source_coverage.*`：当前 382 个运行时字段的逐字段覆盖证据。
- `sources/pass19_rejected_semantic_drift_3.tsv`：因等级／方向冲突而明确保留 residual 的三项。
- `sources/old_pass24_pass25_double_count_signature_13.tsv`：旧 pass24/25 双扣的精确签名。
- `runtime_structure_audit.json`：相对产品基准的完整结构、运行时与敏感字段审计；唯一数值签名变化为 `cardMagiaMap/90360/shortDescription` 从错误的“麻痹3T”修正为“眩晕1T”。
- `scripts/verify_final.py`：只读最终核验入口。

旧 pass14 应用脚本把 keyed-object 字典误当数组，隔离重放会报错；当前产品值本身已由 382/382 来源覆盖审计确认。本轮发布使用新的 manifest/payload 应用器，不再调用该旧脚本。
