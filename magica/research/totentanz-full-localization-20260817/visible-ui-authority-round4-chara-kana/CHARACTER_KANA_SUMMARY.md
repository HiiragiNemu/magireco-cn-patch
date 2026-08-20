# 角色详情英文名（`chara.kana`）权威化清单

## 结论

- 运行时模板 `magica/template/chara/CharaDetail.html:13` 会直接显示 `model.chara.kana`。
- `charaList.json` 共 231 条角色记录，其中 **139 条** `kana` 含英文罗马字；这就是角色详情页仍显示英文名的直接来源。
- 建议只把这 139 条的 `kana` 改为**同一稳定 ID 记录已有的中文 `name`**；不改 `name`、`title`、描述、声优、设计师或任何代码字段。
- 其中 **118 条**中文 `name` 可在 Wiki `characters.json.nameZh` 找到逐字相同值；另 **21 条**使用同一稳定 ID 记录的中文 `name` 继承，Wiki 稳定 ID 页面提供组合／版本构成证据，但其完整 `nameZh` 与现产品把版本名拆到 `title` 的结构不逐字相同。
- 旧国服 `Decoded_MyPage.json` 的 65 个唯一角色记录全部满足 `kana == name == 中文名`，证明这种显示结构符合国服惯例。
- 模拟应用后，231 条记录的 `kana` 中英文罗马字由 **139 降为 0**；逐项验证仅 `kana` 字段变化。
- 本审计**没有修改产品树**。

## 可交付文件

- `character_kana_visible_candidates.tsv`：139 条人工可读逐项清单。
- `character_kana_apply_manifest.json`：根代理可直接消费的 fail-closed 应用合同。
- `character_kana_verification.json`：计数、来源和只改 `kana` 的模拟验证。

## 来源边界

- `wiki-nameZh-literal-exact` 仅表示中文值在 Wiki 中逐字出现；并不把不同版本角色页面误报成稳定 ID 精确匹配。
- `stable-id-same-record-name-inheritance` 不创造新译名，而是复用产品同一角色记录现有中文 `name`，并保留 Wiki 稳定 ID 页面作为组合／版本证据。
- 应用时必须先验证 `charaList.json` 的 before SHA；若父工作区已并发修改此文件，应重新生成合同，不能强套。
