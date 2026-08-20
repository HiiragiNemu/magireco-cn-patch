# v26 中文译文人工校对指南

## 用户只需要做一件事

打开 `magireco_v26_translation_review_1564.xlsx`，查看同一行的：

| A | B | C |
|---|---|---|
| 日文原文 | 旧中文 | 最终中文 |

**只编辑 C 列“最终中文”。**

- C 列已经全部预填，不需要逐行填写。
- 不修改：表示认可预填文本，直接采用。
- 修改：表示采用你填写的新文本。
- 不需要填写人工决定、人工备注、审核人或时间。
- 保存 XLSX 后交回维护代理；用户不运行脚本、不编辑 TSV，也不判断技术路径。

工作簿只有 `人工审核1564` 一个工作表。D:N 是随行移动的隐藏绑定，用来保证排序、筛选和保存后仍能按稳定 ID 安全回填；用户无需查看或填写。

## 当前预填状态

- 人工校对范围：1,564 条当前仍属低权重机器来源的文本。
- 其中 29 条已经按本轮明确指令采用经过结构校正的建议中文；工作簿 C 列预填该值。
- 其余 1,535 条 C 列预填当前中文。
- 323 条已由官方国服／Wiki／确认人工解决，以及 25 条已被更高权威遮蔽的历史机器文本，均不出现在工作簿中。
- 29 条建议已实际进入低权重 canonical 维护层；其中 24 项已物化为运行时 30 处、23 个文件，5 项仅维护层保存。它们仍保留机器来源标记，不冒充官方、Wiki 或确认人工。

## 维护代理收到工作簿后的流程

维护代理使用显式的“接收已返回工作簿”模式导入。导入结果是 `pass20_human_final_values.tsv`，每个稳定 ID 只记录最终值和机器可验证绑定，不包含决定、备注、审核人或时间。

值的解释固定为：

- 最终值等于预填当前文本：人工确认当前机器来源文本；保留原机器来源记录。
- 最终值等于预填建议：人工确认机器建议；仍标记机器来源。
- 最终值被用户改写：记录为人工修订。

导入必须验证 1,564 个稳定 ID、原文哈希、source-record 哈希、target-contract 哈希、隐藏绑定和非空最终值；任一漂移都停止且不写产品树。

随后维护代理在仓库外副本执行 effective 重建、i18n 应用、片段应用、结构／占位符／HTML-EJS／转义检查、JS／HTML／JSON 检查和逐项回撤演练。全部通过后，才以精确 allowlist 原子提升 canonical i18n 与 `magica/` 产品文件。写入中途、报告落盘或 after 校验失败时恢复所有已改文件。

## 发布门

用户已明确授权把当前 C 列的 1,564 个预填值作为粗译版本用于生产。仓库中的
`pass20_human_final_values.tsv` 现已完整记录这些值，并保留机器低权重来源；这不是人工精修认证。
当前粗译生产门为：

```text
final_values=1564
pending=0
protected_text_changes=0
unresolved=0
```

权威顺序始终是：官方国服文本 > HiiragiNemu Wiki > 已确认人工译文 > 机器／LLM／DS 文本。低层文本不得覆盖前三层。

粗译版本通过全部产品验证后可进入稳定版 `latest`。以后用户修改同一工作簿 C 列并交回时，
再走人工精修模式；新的人工作品只提升对应稳定 ID，不会抹去本次粗译来源记录，也不会覆盖官方、Wiki 或已确认人工文本。

## 维护代理命令参考

以下命令仅由维护代理执行。当前粗译生产使用：

```powershell
python tools/import-pass20-human-review-xlsx.py `
  --xlsx <当前预填XLSX> `
  --accept-prefilled-rough-production `
  --out magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv
```

以后人工精修返回时使用：

```powershell
python tools/import-pass20-human-review-xlsx.py `
  --xlsx <用户返回的XLSX> `
  --accept-returned-workbook `
  --out magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv

python tools/validate-dsv4-human-review.py `
  --source magica/i18n_audit/release_v26_authority/dsv4_terminal_handoff/full_review.tsv
python tools/stage-pass20-human-review-product.py `
  --final-values magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv `
  --review-workbook <用户返回的XLSX> `
  --stage-root <仓库外暂存目录>

python tools/promote-pass20-product-stage.py `
  --stage-root <仓库外暂存目录> `
  --allow-repository-write

python tools/verify-pass20-human-materialization.py `
  --repo-root . `
  --require-release-open
```

所有发布资产还必须通过权威保护、产品结构、ZIP 布局、清单一致性和精确 rollback 验证。`cn_js_update.zip` 根目录只允许平行的 `magica/` 与 `madomagi/engine_i18n.tsv`，scenario 包不得携带该表。
