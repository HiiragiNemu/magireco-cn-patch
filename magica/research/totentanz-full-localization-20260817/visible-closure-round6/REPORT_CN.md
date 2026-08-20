# 可见文本闭合 Round 6

## 结果

- 产品目标：6 个文件。
- 精确文本操作：15 条。
- 来源：国服同节点结构 4 条；已复核中文 11 条。
- 操作状态：已完成 `apply → verify → rollback → reapply → verify`。
- JavaScript：新增的 `js/quest/secondPartLast/Router.js` 已通过 `node --check`。
- HTML：5 个文件的 EJS token 序列与改前完全一致。
- 全局替换：0；路径外写入：0。

## 实际修改

1. `template/arena/ArenaTop.html`：`NEXT...` → `下一镜层…`。
2. `template/follow/FollowTop.html`：7 档 `RankN〜` → `等级N～`，`value` 不变。
3. `template/memoria/MemoriaPopup.html`：`NEXT` → `距升级`。
4. `template/quest/MainQuest.html`：两处章节前缀按国服同节点结构移除；挑战提示译为 `※该挑战无法再次进行。`。
5. `template/quest/SubQuest.html`：两处章节前缀按国服同节点结构移除。
6. `js/quest/secondPartLast/Router.js`：从当前上游文件引入，只把 `LAST BATTLE` 改为 `最终战`。

## Connect 权威裁决

稳定 skillId `10014, 10015, 10025, 10045, 10184, 10185, 10193, 10194, 10195`
已在完整国服数据中逐项核验。官方 `shortDescription` 字面本身均使用 `Connect后`，
因此按“国服官方 > Wiki > 已确认人工 > 新译文”保留。独立 `cardSkillMap.json` 与内嵌
`jquery-3.7.1.min.js` 均未因本轮发生修改。逐项证据见 `official_connect_retained_9.tsv`。

## 可复现证据

- `runtime/manifest.json`：固定路径、原件/成品字节路径及 15 条操作。
- `runtime/before/`：5 个原文件和 Router 上游源字节。
- `runtime/after/`：6 个最终成品字节。
- `runtime/visible_closure_round6.patch`：精确补丁。
- `runtime/rollback.json`：可执行回撤合同。
- `runtime/verification.json`：最终产品验证及命令字面输出。
- 工具：`tools/apply-visible-closure-round6.py`。
- 独立测试：`tools/test-apply-visible-closure-round6.py`。

本轮未提交、未推送、未发布。
