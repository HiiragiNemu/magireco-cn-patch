# v26 中文权威层最终人工审计指南

本指南对应 `cn_js_update.zip` 的文本生产端。所有命令均在仓库根目录执行；人工审查前先确认当前分支、提交身份和保护清单。本文不把未决译文视为已完成，也不允许低权重文本覆盖官方国服、Wiki 或已确认人工文本。

> **只使用 `magireco_v26_translation_review_1565.xlsx`。旧 `pass20_human_review.xlsx` 仅覆盖早期 199 项，已经停用，不得继续填写、回传或作为发布资产。**

## 1. 当前审查边界

- DSV4 封存审查总量：1,912 条。
- DeepSeek V4 已独立审查：1,472 条（批次 1–74）。
- 因审查服务停止而转人工：440 条。
- 已审结果中仍需人工裁决：37 条 correction、45 条 unresolved。
- DSV4 封存时的旧口径仍为 522 条（258 条当时的当前文本、264 条历史保护确认）；这是 1,472/440/82/522 的历史审查边界，不作为最终产品人工范围。
- Pass20 已用 58 条官方国服精确匹配关闭当前低权重项，并自动保留 264 条历史权威对照；另有 `LOW-MT-01485` 已被既有官方 `キモチ戦は→心魔战` 权威行覆盖，合计关闭 323 条。
- 最终机器来源盘点严格分为：**1,565 条人工语义审核 + 323 条既有权威 resolution + 24 条高权威遮蔽只读证据 = 1,912 条**。24 条仅出现在工作簿的“只读排除347”证据页，不进入两个可填写审核页、不产生人工 decisions、不新增低权重 canonical 候选，也不允许把低权重候选写回产品；若运行时仍残留被遮蔽的低权重字面值，则必须把已选中的官方/Wiki 权威值精确物化并由实文件门验证。
- 当前真正需要人工语义裁决：1,565 条，全部属于当前低权重文本；中文字段为空的翻译 backlog 为 0。
- DS 标记为 correction 的 37 条中，7 条已由本轮官方国服值实际替换并验证，1 条已由既有官方权威行定稿；其余 29 条仍保留旧候选，工作簿会以“DS发现错误／建议修正但尚未应用”醒目标出当前值和 DS 建议。逐项证据见 `pass20_ds_correction_status.tsv` 与 `pass20_ds_correction_status.json`。
- DS 审查建议只存在于最低权重 staging；在人工门关闭前，DS 建议的产品写入数必须保持 0，受保护文本变化数必须保持 0。

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

预期状态：封存文件 17/17；总量 1,912；已审 1,472；人工接管 440；历史 DSV4 人工口径 522；最终人工决策待办 1,565；既有权威 resolution 323；高权威遮蔽只读项 24；官方产品更正 56 条记录/59 处字面替换；另有 2 条 Wiki 遮蔽项完成 9 处权威修复并核验 10 个运行时锚点；保护变化 0。决策表尚未填写时，校验器应明确报告 `release_gate_open=false`，这属于正确的关闭状态。

## 3. 人工逐条校对

### 3.1 审核者只需操作工作簿

使用 Excel 或兼容表格软件打开：

`magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx`

审核者只需完成以下操作：

1. 在“说明”页的黄色单元格填写审核者姓名和审核时间。
2. 先在“①优先审核199”页逐行核对，再在“②DS已审1366”页核对其余机器来源文本；两页都显示原文、当前中文、建议中文、理由和实际使用位置。
3. 只编辑黄色列“人工决定”“最终中文”“人工备注”；选择修改译文时填写“最终中文”，其他情况按表内提示填写。
4. 使用“另存为”保存成一个新的 XLSX 并交回维护代理；仓库中的空白模板保持不变。

稳定 ID、原文、来源、路径、匹配信息和隐藏审计列均为锁定内容。审核者不编辑 TSV、不运行 Python 或其他命令，也不负责判断技术写入路径。

两个可填写审核页都会直接显示每条文本的“维护层类型”“维护表”“原文键”“路径前缀”“产品目标路径”“匹配次数”和“上下文片段”。这些字段的含义是：

- `frontend`：按原文键维护的全局前端字符串映射；
- `overrides`：只在指定路径前缀内生效的文件级覆盖；
- `fragments`：指定文件中的精确代码片段替换；
- `magica`：最终供游戏运行时使用的产品副本。

这些信息用于帮助审核者理解译文出现在哪里；审核者仍只裁决中文语义。1,565 条人工表按维护层分为 **frontend/global 1,549、override 9、fragment 7**；当前目标清单基线为 **1,443 条可精确定位运行时文本、122 条仅维护层项目、2,439 个精确出现位置、0 个目标冲突**。122 条仅维护层项目仍保留人工决定，但在当前产品树中没有满足安全条件的直接写入目标。另有 24 条高权威遮蔽项保存在 `pass20_authority_shadowed_machine_items.json/tsv`，并只展示于工作簿的“只读排除347”证据页：它们保持官方/Wiki effective，`product_write_forbidden=true` 禁止的是人工或低权重候选回填，不妨碍把已选中的高权威值精确物化。`LOW-MT-01134` 已在指定弹窗标题中将 5 处“HP 回复”修为 Wiki“回复HP”（旧值 0、新值 5）；`LOW-MT-01450` 已把 4 处独立 UI“支援”修为 Wiki“辅助”，连同原已正确的 `CardPopup.js` 共验证 5/5 个 UI 锚点（全产品精确“辅助”共 6 处），未全局改写“支援Pt／支援编成／用作支援”等其他语境。`LOW-MT-01485` 保持官方“心魔战”；`LOW-MT-00674` 的两个 raid 运行时路径保持官方路径覆盖；这些旧低权重历史行都只保留 provenance。

### 3.2 维护代理的确定性回填流程

工作簿本身不直接修改 `magica/`。维护代理接收另存的完成版 XLSX 后，先严格校验 1,565 个稳定 ID、行数、逐项源文本哈希、完整 source-record 哈希、锁定来源字段及 target-contract 哈希，再把人工决定导入 i18n 审核/维护层。任何占位符、HTML/EJS、转义结构、零匹配、目标漂移、非预期多义或未决决定都会使流程关闭，且不写产品树。1,565 条最终值全部进入 canonical i18n 的 `human-reviewed-*` 输入；其中 1,443 条具有精确运行时目标，122 条当前无安全目标的项目仍永久保存在 canonical i18n 并标记“当前产品未引用”。approve-current 保留原机器来源状态并另记 human-approved；人工 revise 才标记 machine-translated=false。24 条高权威遮蔽项始终不进入人工决定链路；其官方/Wiki winner 的独立运行时物化由 shadow 合同和实文件验证器负责。

以下步骤仅由维护代理执行：

```powershell
$pass20Work = Join-Path $env:TEMP 'magireco-pass20-human-review'
New-Item -ItemType Directory -Force $pass20Work | Out-Null
$completedWorkbook = Join-Path $pass20Work 'magireco_v26_translation_review_1565.completed.xlsx'

python tools/import-pass20-human-review-xlsx.py `
  --xlsx $completedWorkbook `
  --out (Join-Path $pass20Work 'dsv4_human_decisions.tsv')

python tools/build-pass20-product-targets.py

python tools/stage-pass20-human-review-product.py `
  --decisions (Join-Path $pass20Work 'dsv4_human_decisions.tsv') `
  --review-workbook $completedWorkbook `
  --stage-root (Join-Path $pass20Work 'stage')

python tools/promote-pass20-product-stage.py `
  --stage-root (Join-Path $pass20Work 'stage') `
  --allow-repository-write

python tools/verify-pass20-human-materialization.py `
  --repo-root . `
  --report (Join-Path $pass20Work 'pass20_human_materialization_verification.json') `
  --require-release-open
```

第三步只在仓库外的 staging 副本中依次重建 effective 层，并运行 `i18n-apply` 与 `i18n-fragments`。它会生成并检查：

- `stage/staging_verification.json`：总门禁、权威保护、JS/HTML/JSON 结构与目标清单结果；
- `stage/review_application/product.diff`：逐文件、逐项产品差异；
- `stage/review_application/product_patch.json`：稳定项目到精确产品位置的机器清单；
- `stage/rollback/rollback.json`：逐文件回撤清单和 before/after 快照；
- staging 内的 `magica/`：仅供审计的候选运行时副本。

只有当 1,565 条人工决定全部闭合、未决数为 0、权威保护变化为 0、目标清单完全一致、结构/占位符/HTML-EJS/转义、JS 语法、HTML 敏感属性、JSON 解析和逐项 rollback 演练全部通过后，第四步才会在显式写入开关下，将 canonical i18n、人工决策 TSV、审核者填写后的 XLSX 不可变回执以及允许变更的精确 `magica/` 文件原子提升到仓库。提升后物化验证器必须证明完成版 XLSX 可无损回导、1,565 条均进入 human-reviewed canonical/effective、1,443 条运行时项目的 2,439 个目标位置均为最终值、122 条仅维护层项目没有伪造目标，并逐项证明 24 条高权威遮蔽项的低层 canonical 写入与低权重候选产品写入均为 0，同时以实文件证明声明的官方/Wiki winner 锚点全部命中；本轮基线为 2 项、9 处新修复、10 个已验证锚点。任一 before/staged-after/source/target/shadow 哈希漂移、越界路径、报告落盘失败或中途写入失败都会拒绝或恢复全部已写文件。

在上述人工门和产品验证尚未全部通过时，`stable latest` 保持关闭；Draft PR 与预览资产只用于审计。

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

终态 handoff 包含逐项 correction patch、rollback manifest 与执行器。正式应用任何人工修订前，先保存目标文件和源字段哈希；只按稳定业务键应用。回撤必须先校验 before/after SHA 门，再逐项恢复，并重新运行权威保护与产品验证。多文件回撤中途失败时，执行器会把所有目标补偿回精确 after 状态并标记为可重试，禁止留下 before/after 混合树，也禁止用整目录覆盖代替逐项回撤。

## 7. 发布门

功能分支和 Draft PR 可以用于代码审查，但 stable 资产转正必须同时满足：

1. 1,565 条人工决策全部闭合且 unresolved=0；323 条既有权威 resolution 不进入人工队列；
2. 物化验证器证明完成 XLSX、decisions、1,565 条 canonical/effective 与 1,443/122、2,439 处产品合同完全一致；
3. 24 条高权威遮蔽只读项保持官方/Wiki effective，低层 canonical 写入=0、低权重候选产品写入=0；声明的高权威运行时锚点全部由实文件验证，其中本轮 2 项完成 9 处修复并验证 10 个锚点；
4. 官方/Wiki/确认人工保护字段变化=0；
5. 最新 `main` 三方集成和完整回归通过；
6. 两次独立构建哈希相同；
7. `cn_js_update.zip`、版本文件、清单及远端资产事务一致；
8. rollback 演练成功。

任一条件缺失时，发布门应保持关闭，不得用旧 ZIP 或 preview 资产替代 stable 基线。
