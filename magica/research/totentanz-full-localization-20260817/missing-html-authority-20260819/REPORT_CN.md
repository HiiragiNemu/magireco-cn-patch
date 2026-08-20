# 缺失 HTML 权威回收与结构保护报告

## 已落实

- 产品树新增 10 份此前缺失、且运行时会请求的 HTML。
- 固定文本记录 30 条：国服权威 10 条，人工精译 20 条。
- `ArenaCurePop`、5 份删除账号弹窗、`MainQuest`、`SubQuest` 使用 Totentanz 当前上游结构；上游固定在 `Puella-Care/en-text@5c149cb829ea3d8ee5a71cac174419fb45a1fdbc`。
- `MemoriaDetailPopup`、`QuestDetailPopup` 当前上游仓库没有对应文件，因此采用 `A:\magicaOLD` 国服文件，并以 EJS 令牌和必需节点门保护运行结构。
- `MainQuest`、`SubQuest` 保留当前的赛季 2、Puella Historia 与参数节点，只把章节列表中的 `Ep.` 表示改成国服使用的 `话` 后缀。

## 产品文件

1. `magica/template/arena/ArenaCurePop.html`
2. `magica/template/config/deleteUserData/popupComplete.html`
3. `magica/template/config/deleteUserData/popupConfirm.html`
4. `magica/template/config/deleteUserData/popupError.html`
5. `magica/template/config/deleteUserData/popupInputPlayerID.html`
6. `magica/template/config/deleteUserData/popupReConfirm.html`
7. `magica/template/event/EventWitch/parts/MemoriaDetailPopup.html`
8. `magica/template/quest/QuestDetailPopup.html`
9. `magica/template/quest/MainQuest.html`
10. `magica/template/quest/SubQuest.html`

## 验证与回撤

- `runtime/manifest.json`：逐文件来源、结构锚点、EJS 数量和逐条文本来源。
- `runtime/translations.tsv`：30 条文本的可读逐条来源对照；这些条目已经审核落地，不进入待人工 XLSX。
- `runtime/verification.json`：10/10 产品字节及结构验证记录。
- `runtime/rollback.json`：逐文件回撤合同；这些文件此前均不存在，因此回撤动作是通过精确字节门后删除本轮创建文件。
- `runtime/rollback.ps1`：可直接执行的事务回撤入口。
- `tools/test-apply-missing-html-authority.py`：覆盖正常应用、目标已存在拒绝、准备文件漂移拒绝、产品漂移拒绝、应用中途失败补偿、回撤中途失败补偿和结构漂移拒绝。

已实测一次完整的“应用 → 验证 → 回撤 → 确认全数移除 → 再应用 → 再验证”，最终产品树保持应用状态。

## 未强行物化的原 48 项

本轮 10 项落地后，原缺失清单还剩 38 项：29 项只有动态节点/结构而无固定可译文本，6 项为测试或调试页面，2 项在现有国服和 Totentanz 抓包中都没有源文件，1 项为 `RulePopup.html`。

`RulePopup.html` 没有套用旧国服法律文本：当前结构新增 `rulePolicyLink` 和 `ruleLinkAdjust`，且服务主体与旧国服不同。把旧国服整页覆盖过去会同时破坏节点合同和法律语义。

## 边界

按本轮约束，`MainQuest.html` 中当前上游自带的 `Ch.` 和 `You cannot retry the challenge.` 没有在此步骤扩译；它们应由全局可见文本闭合层另行处理，不能伪标为国服直接对应文本。
