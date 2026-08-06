# Wiki 权威中文层（pass9）

本目录记录 `magica/js/libs/` 中文运行时字典的来源、替换与独立复核结果。产品层只更新 23 份独立 JSON 和由同一批字典重建的 `jquery-3.7.1.min.js`；Totentanz 当前 UI、CSS、字体、图片、路由与页面代码均保留。

## 输入与固定版本

| 输入 | SHA-256 / commit |
|---|---|
| `A:\cn_js_update_v3.zip`（v3 baseline） | `d2ecfe9418b8e3b64bc39610ed645d9f65786df1987c081be134d3ea4efc97c4` |
| pass8 覆盖包 | `e4b466d6cb6c16ec018b61c7d074e2d213601889e758ef6db4dc4dd041c54e53` |
| 2022-10-10 国服解密 dump | `30eec8ab72947521f7e6c8593c7adeb3e9b107c5528701faa50f32cdfdb5f4db` |
| `magireco-wiki-data` 工作提交 | `42641f87818b37262032fd4dc5d5c756a48fed7a` |
| Wiki i18n reference 提交 | `186326575607a98c1f1810fa09ada67016420145` |
| 两个 Wiki 提交共同的 `data/` tree | `9495350e70fbdbf03970b008c05aa006a823c11d` |
| 本分支基点 `main` | `3c983a778429d5e56a2569aa28ea8c622d988c63` |

## 来源优先级

1. 同 ID、同字段的国服 dump 锁定值；
2. baseline 中未被补译触及的既有值及创作者字段；
3. Wiki 的类型化 ID 对照（角色、Doppel、记忆结晶、精神强化等）；
4. 同一角色页内、保持数值／作用域／连接项签名的一对一 Wiki 映射；
5. 规范化日文完全相同且 Wiki 中文唯一的对照；
6. 找不到独立权威来源的 pass8 文本原样保留并列入残余清单。

Doppel 名称另有强制一致性规则：国服 dump 锁定值优先；无锁定值时，以 Wiki 专用 `doppelList` 条目为 canonical，再同步到两份 Magia 字典。裸 ID 不跨技能字典猜测，歧义 ID `1001101` 继续要求类型上下文。

## 结果

- Wiki 提案：5,678；独立复核接受 5,678，拒绝 0。
- 114 个 LLM Doppel：342 个字段全部覆核；189 个改用 Wiki，153 个已经与 Wiki 等价。
- 217 个 Doppel 三字典组：缺失／名称分裂 0。
- 结构化 JSON：23 份、29,008 条记录、120,084 个字段；结构错误 0。
- 国服 dump 权威字段：57,056；不一致 0。
- 运行时字典：23；独立 JSON／jQuery 内嵌字典不一致 0。
- Node 语法：197 个 JS，失败 0；运行时用例 29,008，字段断言 73,014，失败 0。
- HTML：181；标签骨架及敏感属性漂移 0。
- LLM／其他非权威候选：16,742 降至 11,055；解决 5,687 个唯一字段，下降 33.97%。残余占全部 88,325 个跟踪 JSON 字段的 12.52%。该“残余”是保守来源分类，不代表已证实错误。

Wiki 源自身的缺引号、HTML 注释、标点旁空格、`Blu-ray` 缺字和日文字形在写入前做了最小结构修复。`家常便贩` 是 `日常自販機 / 日常茶飯事` 的有意双关；记忆结晶 1749 的 `(ry` 是源文本网络省略语，均保留。

## 研究文件

- `applied_wiki_proposals.tsv`：全部实际 Wiki 替换及证据。
- `residual_llm_or_other_candidates.tsv`：仍缺独立 Wiki／国服匹配的保守残余。
- `doppel_equivalence_report.tsv`：114 个 LLM Doppel 的 342 字段逐项结果。
- `doppel_consistency_reconciliations.tsv`：Doppel 三字典 canonical 决策。
- `release_verification.json`：完整结构、语法、运行时、ZIP 与回滚验证。
- `review_summary.json`、`RISKS.md`：独立复核与推断方法边界。
- `branch_comparison_summary.md`：当前 `main` 与自动化分支比较。
- `preserve_paths.txt`：合并时不要用旧覆盖包清理的 Totentanz 文件。

`build_release.py` 与 `review_proposals.py` 是本次冻结工作区的可复跑脚本，需要原始三份归档、Wiki checkout 和报告目录保持脚本中记录的相对布局；它们对关键输入执行 SHA-256 fail-closed 校验。

## 合并边界

可直接作为中文权威层的是：`magica/js/libs/*.json`（23 份）和同目录 `jquery-3.7.1.min.js` 的内嵌字典块。不要用 401 文件覆盖包覆盖或删除 `preserve_paths.txt` 所列的新 CSS、中文字体、国服 UI 图片、版本／路由／manifest 文件。
