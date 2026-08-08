# pass15 最终集成逐字段来源覆盖审计

**字段来源覆盖：PASS（382/382）**

总体状态：`PASS_WITH_RECIPE_EXECUTOR_DEFECT`。产品工作树在审计前后保持稳定，写入数为 0。

## 覆盖结论

- 相对 `20e35db4` 的独立 JSON 变化字段：382。
- 明确配方／账本覆盖：382；未覆盖：0。
- 配方转换行：410；唯一目标：382；连续两步字段：28。
- 应用全部配方后，23 个映射字典与当前产品语义对象完全一致：PASS。
- 整文件复制带来的未覆盖语义回退：0。
- jQuery 为 23 字典确定性派生，SHA-256：`c7a879cf5d13e2a53c83c871cd715e467032199dcbedd93144fdb35aa3ac1cca`。

## 按文件

| 文件 | 变化字段 | 已覆盖 | 未覆盖 | 转换行 |
|---|---:|---:|---:|---:|
| `cardList.json` | 8 | 8 | 0 | 10 |
| `cardMagiaMap.json` | 131 | 131 | 0 | 131 |
| `charaList.json` | 7 | 7 | 0 | 7 |
| `doppelCardMagiaMap.json` | 7 | 7 | 0 | 7 |
| `doppelList.json` | 7 | 7 | 0 | 7 |
| `itemList.json` | 43 | 43 | 0 | 43 |
| `live2dList.json` | 4 | 4 | 0 | 4 |
| `sectionList.json` | 145 | 145 | 0 | 171 |
| `shopItemList.json` | 30 | 30 | 0 | 30 |

## 来源层转换行

- `manual_terms`：7
- `pass11_mechanics`：26
- `pass13_card_identity`：6
- `pass14_special_doppel`：21
- `pass15`：73
- `pass16`：20
- `pass17_first_authority`：3
- `pass22`：22
- `pass28`：179
- `pass29`：42
- `pass30`：9
- `typed_wiki_runtime`：2

## pass11 90360 对齐

- 状态：`EXACT_CHAIN_COVERED`。
- `对敌方单体造成伤害[Ⅴ] & 必定赋予麻痹(敌方单体/3T) & 攻击力提升(自身/3T) & 解除Debuff(自身)` → `对单个敌人造成伤害[Ⅴ] & 必定眩晕(单个敌人/1T) & 攻击力UP(自己/3T) & 解除DEBUFF(自己) `
- 配方：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\pass15_authority\magica\i18n_audit\wiki_authority_pass11_mechanics\mechanics_corrections.json#index=23;id=90360`
- 机械错误类别：`status_and_duration_mistranslated`；Wiki 交叉核对：`https://magireco.moe/wiki/Magia`。

## pass10／pass12 边界

pass10 和 pass12 明确声明 `runtime_text_changed=false`，因此仅作为来源归因上下文，未虚构为产品字节转换行。

## pass14 旧配方执行器

- 配方内容覆盖：21/21 个三方名称字段，当前产品值正确。
- 隔离执行器探针：`FAIL`，退出状态 `1`。
- 缺陷：`dict_runtime_maps_treated_as_row_arrays`。旧脚本把 keyed-object 格式的 `cardMagiaMap`／`doppelCardMagiaMap` 当作记录数组读取。
- 影响边界：不影响当前产品字段覆盖结论；最终可复现发布应使用新的 manifest/ledger 应用器，而不是该旧 pass14 脚本。

逐字段值、完整来源链、权威类型与定位符见 `field_source_coverage.tsv` 和 `field_source_coverage.json`。
