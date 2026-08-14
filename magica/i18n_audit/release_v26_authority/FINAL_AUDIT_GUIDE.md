# v26 中文权威层最终人工审计指南

本指南对应 `cn_js_update.zip` 的文本生产端。所有命令均在仓库根目录执行；人工审查前先确认当前分支、提交身份和保护清单。本文不把未决译文视为已完成，也不允许低权重文本覆盖官方国服、Wiki 或已确认人工文本。

## 1. 当前审查边界

- 全量低权重历史清单：1,912 条。
- DeepSeek V4 已独立审查：1,472 条（批次 1–74）。
- 因审查服务停止而转人工：440 条。
- 已审结果中仍需人工裁决：37 条 correction、45 条 unresolved。
- 原始人工决策总数：522 条；其中 258 条涉及当前低权重产品文本，264 条仅用于确认受保护历史权威值。
- Pass20 已用 58 条官方国服精确匹配关闭当前低权重项，并自动保留 264 条历史权威对照；合计关闭 322 条。
- 当前真正需要人工语义裁决：200 条，全部属于当前低权重文本；中文字段为空的翻译 backlog 为 0。
- DS/LLM 结果只存在于最低权重 staging；在人工门关闭前，产品写入数必须保持 0，受保护文本变化数必须保持 0。

## 2. 先验证封存证据

```powershell
python tools/verify-dsv4-terminal-handoff.py
python tools/validate-dsv4-human-review.py `
  --source magica/i18n_audit/release_v26_authority/dsv4_terminal_handoff/full_review.tsv `
  --decisions magica/i18n_audit/release_v26_authority/dsv4_human_decisions.tsv `
  --authority-resolutions magica/i18n_audit/release_v26_authority/pass20_authority_resolutions.tsv
python tools/pass20_official_static.py verify --state applied
python tools/verify-v26-authority-protection.py --json
```

预期状态：封存文件 17/17；总量 1,912；已审 1,472；人工接管 440；Pass20 权威关闭 322；人工决策待办 200；官方产品更正 56 条记录/59 处字面替换；保护变化 0。决策表尚未填写时，校验器应明确报告 `release_gate_open=false`，这属于正确的关闭状态。

## 3. 人工逐条校对

使用表格软件打开：

`magica/i18n_audit/release_v26_authority/dsv4_human_decisions.tsv`

可先用 `magica/i18n_audit/release_v26_authority/pass20_remaining_manual_review.tsv` 作为只读的 200 条精简工作队列；最终决定仍写回上面的全量决策表。

不要编辑稳定 ID、原文、旧译、权威层级、证据路径、受保护值及产品写入许可等来源列。只填写人工决策列：

- `parent_verdict=approved` 的 1,390 条无需人工决策，其 `human_decision`、`reviewer`、`timestamp`、`final_value`、`human_revision`、`human_notes` 必须全部保持空白。
- 只处理未被 `pass20_authority_resolutions.tsv` 关闭、且 `parent_verdict` 为 `manual-required`、`correction` 或 `unresolved` 的 200 条。
- 当前低权重项：`approve-current`、`revise` 或 `unresolved`。
- 受保护历史项：`keep-authority` 或 `unresolved`。
- 每个已决项必须填写 reviewer 和 ISO 8601 时间。
- `approve-current` 的 `final_value` 必须等于 `current_cn`；`revise` 必须填写与 `current_cn` 不同的 `final_value`；`unresolved` 不得填写 `final_value` 或 `human_revision`。
- `keep-authority` 的 `final_value` 必须等于该行 `wiki_cn` 或 `current_cn` 中已有的权威值，且不得填写 `human_revision`。

优先筛选真实存在的列：`parent_verdict`、`review_kind`、`allowed_action`、`review_status`、`highest_authority_tier`、`authority_status` 和 `product_write_allowed`。对照依据顺序固定为：官方国服文本 > HiiragiNemu Wiki > 已确认人工译文 > DS/LLM。

保存后文件必须仍为 UTF-8 无 BOM、LF 换行；若表格软件自动改成 CRLF 或加入 BOM，校验器会按设计拒绝该文件，需以 UTF-8 无 BOM、LF 重新导出。

再次运行第 2 节的人工表校验命令。只有剩余 200 条全部完成且 unresolved 为 0 时，`release_gate_open` 才允许变为 true。

## 4. 结构、权威与确定性构建审计

```powershell
python tools/test-v26-audit-byte-clean.py
python tools/verify-runtime-layer.py
python tools/verify-v26-product.py --out v26_product_verification.json
python tools/build-v26-package.py --out cn_js_update.audit-a.zip
python tools/build-v26-package.py --out cn_js_update.audit-b.zip
Get-FileHash cn_js_update.audit-a.zip -Algorithm SHA256
Get-FileHash cn_js_update.audit-b.zip -Algorithm SHA256
```

两个 ZIP 的 SHA-256 必须完全相同。ZIP 中只允许 `magica/` 产品树以及精确路径 `madomagi/engine_i18n.tsv`；不得包含 scenario 文件、审计目录或临时文件。

## 5. 完整验证记录

使用 `tools/run-v26-final-validation.py` 与 `tools/v26-final-validation-plan.json` 生成最终记录。记录必须证明：所有命令退出码为 0、Git index 防并发保护完整、双构建字节一致、权威保护哈希不变、ZIP 合同通过。

## 6. 回撤验证

终态 handoff 包含逐项 correction patch、rollback manifest 与执行器。正式应用任何人工修订前，先保存目标文件和源字段哈希；只按稳定业务键应用。回撤必须先校验 before/after SHA 门，再逐项恢复，并重新运行权威保护与产品验证。禁止用整目录覆盖代替逐项回撤。

## 7. 发布门

功能分支和 Draft PR 可以用于代码审查，但 stable 资产转正必须同时满足：

1. Pass20 关闭 322 条后，剩余 200 条人工决策全部闭合且 unresolved=0；
2. 官方/Wiki/确认人工保护字段变化=0；
3. 最新 `main` 三方集成和完整回归通过；
4. 两次独立构建哈希相同；
5. `cn_js_update.zip`、版本文件、清单及远端资产事务一致；
6. rollback 演练成功。

任一条件缺失时，发布门应保持关闭，不得用旧 ZIP 或 preview 资产替代 stable 基线。
