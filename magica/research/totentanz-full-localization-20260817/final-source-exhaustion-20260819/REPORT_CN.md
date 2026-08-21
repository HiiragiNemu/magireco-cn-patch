# 最终来源耗尽聚合报告（2026-08-21）

## 终态

**PASS：在封存的 A:\magicaOLD、A:\totentanz-frontend、权威层、图像与 native/engine 证据范围内，仍可安全物化的权威中文或已审核新译增量为 0。**

本报告组合已完成证据，并记录本轮从国服双 ABI native 稳定源键物化到 engine 表的 85 项变更；没有重新扫描 A 盘大树。

## 文本

- 旧国服/美服独有文本路径：**928/928**，剩余 **0**。
- 缺依赖 CSS：**62**，固定可见汉化价值 **0**。
- 缺依赖 JSON：**12**，稳定固定 UI 汉化价值 **0**。
- 缺依赖 HTML：**48 = 已物化 11 + 明确排除或无固定文本 37**。
- RulePopup：**146** 条记录，意外日文假名 **0**。
- Round6：**15/15** 条可见文本已物化并验证。

### 已物化 HTML

- `magica/template/arena/ArenaCurePop.html`
- `magica/template/config/deleteUserData/popupComplete.html`
- `magica/template/config/deleteUserData/popupConfirm.html`
- `magica/template/config/deleteUserData/popupError.html`
- `magica/template/config/deleteUserData/popupInputPlayerID.html`
- `magica/template/config/deleteUserData/popupReConfirm.html`
- `magica/template/etc/RulePopup.html`
- `magica/template/event/EventWitch/parts/MemoriaDetailPopup.html`
- `magica/template/quest/MainQuest.html`
- `magica/template/quest/QuestDetailPopup.html`
- `magica/template/quest/SubQuest.html`

## 图像

- 同路径图：**8,868**；可行动项 **160/160** 闭合，无价值 **8,708**。
- 动态官方中文图：**681/681** 已进入产品并通过解码验证。
- native quest 图集：**9/9** 帧闭合，目标框外像素变化 **0**。

## 明确保留

- `Puella Historia`、`Magia`、正式机制名、角色刻意口癖/自称。
- `Inkyubus`、`Kyubi*` 等玩家自定义名称。
- 9 个稳定 skillId 的旧国服原文自身使用 `Connect`；普通 UI 仍按规则使用“连携”。

## engine_i18n 消费者边界

- 当前表：**621 条逻辑规则 / 622 物理行**；无 `~` 伪规则。
- 国服 native：运行时可分配区含中文的 **349/349** 项已分类；得到 **189** 条稳定映射记录，接受 **182** 个源键，实际表变更 **85** 项（含新增源键 **6**），调试/不稳定源注入 **0**。
- 历史最终语义复审：原 **212/212** 绑定仍可追溯；其中 **124** 项现由更高权威覆盖，保留原最终复审接管 **88** 项。历史 **40/40** 项修正的应用及回撤证据仍保留。
- 终态分区：官方 **207** / 已确认人工动态 AP 规则 **301** / 根任务复审 **110** / Wiki **2** / 刻意结构规则 **1**；未验证 **0**。
- 当前消费者只支持 exact 与 `^prefix`。两段 AP 动态文本已通过 **301 条有限前缀**覆盖首段倒计时 `0:00..5:00`，并保留末段完整回复时间后缀：

- ` AP will recover in ` → ` AP恢复倒计时：`（`ENGINE-AP-TIMER-001`，已闭合）
- ` / AP will be fully recovered in ` → ` / AP全满倒计时：`（`ENGINE-AP-TIMER-002`，已闭合）

## 证据纪律

没有采用旧 316 行 engine 快照、闭合前错误 24 项清单或闭合前 RulePopup 拒绝结论。`summary.json` 记录当前产品、国服 native 闭合证据及外部只读证据的路径与字节数。
