# 当前游戏发行要求：仅更新累计 JS delta

完整执行交接：[DELTA_ONLY_HANDOFF.md](DELTA_ONLY_HANDOFF.md)。机器可读规则：`release-policy.json`。此规则取代旧共同发布Scenario/delta的说明。361目标与11,226字段的内容manifest未改变，但包验收必须改用`delta_only_guard.py`；当前生产工作流仍需客户端窗口适配delta-only，不能直接触发旧共同发行流程。

Reader已正式部署源码`b06987d363c8d62976b491f7779df6bd5ab885a0`、部署`2086f41c-5f7d-4ad4-b082-4505679ab7a9`，全部新稿与索引/搜索/分包及ADV已验收。游戏运行源和delta尚未由本窗口整合或发布。原Scenario3323/JS103固定不更新，当前父代delta22须在接手时重新核验。

旧READY和旧操作说明保存在`history/policy-before-delta-only-20261003/`；旧内容manifest保持不可变，其内部历史发行文字不覆盖最新发布政策。`current_ready_gate`验证内容身份，发布方还必须核对当前政策文件的SHA。
