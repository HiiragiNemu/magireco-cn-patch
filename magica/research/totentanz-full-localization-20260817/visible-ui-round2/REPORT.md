# 可见 UI 文本第二轮闭合报告

## 结果

- 本轮在 4 份实际模板中完成 5 项路径限定、字面精确替换。
- 102 份非测试模板的 403 个候选可见文本完成复核后，剩余可操作英文／日文项为 **0**。
- 未修改 JS；本轮不涉及 Node 语法检查。
- 4 份 HTML 均保持 UTF-8；EJS 定界符计数在替换前后完全一致。
- `id`、`class`、`href`、`src`、`name`、`data-*` 等敏感属性零漂移。
- 已完成 `apply -> verify -> rollback -> check-before -> apply -> verify` 演练，最终处于已应用状态。

## 实际改动

| 稳定 ID | 文件 | 旧可见文本 | 最终中文 | 来源层 |
|---|---|---|---|---|
| VISIBLE-object-storage-0001 | `magica/template/collection/StoryCollection.html` | CLEAR | 已通关 | 同文件已确认人工上下文等价 |
| VISIBLE-object-storage-0002 | `magica/template/collection/StoryCollection.html` | LOCK | 未解锁 | 新人工精译 |
| VISIBLE-object-storage-0003 | `magica/template/regularEvent/accomplish/RegularEventAccomplishTop.html` | Stage | 关卡 | 项目确认术语 |
| VISIBLE-object-storage-0004 | `magica/template/event/raid/EventRaidTop.html` | COMBO！ | 连击！ | 新人工精译 |
| VISIBLE-object-storage-0005 | `magica/template/memoria/MemoriaComposeTop.html` | NEXT | 距升级 | 新人工精译（该字段表示升到下一级所需经验） |

`A:\magicaOLD` 对应文件仍保留上述英文，因此不能提供更高层的直接中文；`A:\totentanz-frontend` 中现有对应文件也保留英文。逐文件计数及 SHA-256 见 `source_comparison.json`。

## 有意保留

- AP、BP、HP、ATK、DEF、MP、Magia、Connect、Charge、Accele、Blast、EX、VER、Lv、SD 等正式游戏缩写／术语。
- 玩家名、公会名及运行时动态字典名称不属于本轮静态 HTML/JS 字面扫描。
- 浏览器调试控件、测试模板、代码枚举、类名、路径和注释不作为玩家可见汉化目标。
- `Ban.html` 中的 `・` 是已中文句子的项目符号，不是日文残留。

## 可复现证据

- `visible_ui_round2_manifest.json`：精确替换合同。
- `check_after_rollback.json`、`apply_final.json`、`verify_final.json`：回滚复原、最终应用、最终核验。
- `html_sensitive_attributes_verification.json`：HTML 敏感属性零漂移。
- `verification.json`：UTF-8、EJS、属性、残留总门。
- `residual_review.tsv`、`residual_summary.json`：全候选逐项分类及零可操作残留。
- `source_comparison.json`：旧国服、美服抓包和最终产品逐文件对照。
