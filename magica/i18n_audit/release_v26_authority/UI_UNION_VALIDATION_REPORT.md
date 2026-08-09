# JS v26 UI 三方并集最终只读验证

## 结论

**PASS。** 修复 `magica/template/test/Backdoor.html` 中被 main 污染的技术标识
`FORMATI开启_SHEET_201` 为 `FORMATION_SHEET_201` 后，未发现剩余并集遗漏、槽位错配、
JavaScript 语法错误或 HTML 敏感属性漂移。

验证源：

- common base：`3c983a778429d5e56a2569aa28ea8c622d988c63`
- latest main：`23d21eee1c084ac0f8300cbaca4d9f0833c0440e`
- Pass16：`b59f06d5604ad3c1b90fbad8b6b0fae5efc36c38`
- 集成树 HEAD：`c10f127389e4d5c39842e821e31adb234910c6e3`

## 并集验证

| 检查 | 结果 | 说明 |
|---|---:|---|
| main-only 文件 | 12 / 12 | 11 个 CSS 与 `connecting.png` 均逐字节等同 latest main |
| Pass-only 文件 | 14 / 14 | 6 个 CSS、6 个 update2 图标、`SdCharaTest.js`、`GachaResult.html` 均内容等同 Pass16；其中两个文本文件仅工作树换行符不同 |
| 指定扭蛋文件 | 3 / 3 | `CampaignBoxGachaTop.js` 与独立 `git merge-file` 并集逐字节相同；两个 HTML 的 main 等于 base，集成结果等于 Pass16 |
| 冲突文件 | 14 / 14 | 8 JS + 6 HTML 全部逐槽复算通过 |

14 个冲突文件共复算 **1,510 个结构槽位**：

- base 未变槽：1,163
- main-only 改动槽：55
- Pass-only 改动槽：227
- 双方同值改动槽：46
- 双方异值、人工裁决槽：19

其中原 main-only 的 `FORMATI开启_SHEET_201` 是唯一低质量源污染，已明确拒收并恢复为
`FORMATION_SHEET_201`；其余 54 个 main-only 槽、227 个 Pass-only 槽、46 个同值槽与
19 个裁决槽均落在原结构中的同一位置，最终语义槽错误为 **0**。

`Pickup对象魔法少女` 与 `Pickup对象记忆结晶` 来自已审计扭蛋权威层，并非本轮遗漏。
`任务 Stub` 与 `任务Result SKIP` 是 latest main 的开发测试页标签，本轮仅记录为后续措辞复核项，
不影响并集、选择器或运行时结构。

## 结构与语法

- 产品 JavaScript：198 个（含派生 `jquery-3.7.1.min.js`），`node --check` 失败 **0**。
- 产品 HTML：182 个。
- HTML 敏感属性：12,498 项；与结构基线比较漂移 **0**。
- 已声明的 5 项 `data-mission-name` 文本值例外：观察到 5 / 5；其余 `id`、`class`、
  `href`、`src`、`name`、`data-*` 均未漂移。

## 可复核产物

- `ui_union_validation.json`：完整机器验证结果。
- `conflict_slot_ledger.tsv`：347 个发生来源变化或语义覆盖的槽位明细。
- `validate_ui_union.py`：只读复验脚本；所有输出均写在产品工作树之外。
- `pass16_integrated_verification.json`：旧 Pass16 验证器的组件结果；其中 JSON、jQuery、
  Node 与 HTML 组件均 PASS。该文件顶层 FAIL 只因旧验证器把 latest-main 的新增 CSS/文本视为
  Pass16 保护边界外变化，不用于本次三方并集结论。

复验命令：

```text
python outputs/ui_merge_20260809/validation/validate_ui_union.py \
  --tree work/js_v26_release_integration \
  --out outputs/ui_merge_20260809/validation
```
