# Pass16 未中文化内容清零与人工校对报告

## 结论

本轮重新扫描了 197 份产品 JavaScript、182 份 HTML 和 23 份运行时字典。按以下固定优先级处理：

1. `A:\magireco_cn_dump_20221010_decrypted_json`（国服官方文本）
2. `HiiragiNemu/magireco-wiki-data`（指定 Wiki）
3. 人工逐项翻译与语义复核

最终结果：

- 运行时候选：148 种／654 个字段实例
- 国服官方命中：49 种
- 指定 Wiki 可替换命中：88 种
- 人工定译：9 种
- 指定 Wiki 中文字段原样保留：2 种
- 尚待中文化的玩家可见候选：0
- JS 解析错误：0／197
- HTML 敏感属性越界变化：0／182（仅观察到 5 项预先声明的可见 `data-mission-name` 翻译）
- 外部 JSON／jQuery 内嵌字典不一致：0／23
- CSS 变化：0／8
- 三个受保护扭蛋文件变化：0／3

## 权威回收

最终权威查找表共回收 137／148 种可替换文本：国服 49、指定 Wiki 88；另有 2 种当前文本与 Wiki 中文字段逐字等价并原样保留。重要项目包括：

- `調整屋硬币` 采用国服同记录定名 `调整专家币`；225 个币记录的 `name`、`shortDescription`、`description` 已统一，说明统一为 `在「调整专家币」中用于兑换的道具`。
- `七色夏模様` 从 Wiki 压缩归档回收为 `七彩夏日绘`，并同步背景名称与说明。
- `水場` 采用国服同字段旧记录用词 `戏水处`。
- 周年纪念票券中的 `10連扭蛋券` 采用国服组件写法 `10连扭蛋券`。
- `3周年DX福袋(銀)` 采用 Wiki 日中字段确认的 `银`，并按国服标点规则写作 `3周年DX福袋（银）`。
- 同族既有中文项 `3周年DX福袋(金)` 同步规范为 `3周年DX福袋（金）`，避免同一商品族标点混用。
- `魔法少女(日本語)`、`私服(日本語)` 采用 Wiki 同一角色页的语音服装定名 `翻译装置`。
- 技能说明优先采用 Wiki 成对字段的 `UP`／`DOWN`、`自`／`己全` 等既有格式，未自行改写范围、等级或回合。
- 角色名、篇章名、记忆结晶名、活动名均按国服或 Wiki 的显式对应处理。

## 人工定译

真正没有国服或指定 Wiki 直接中文对应的文本只有 9 种，已由本轮逐项人工翻译并列在：

- `準備完了` 结合战斗语音上下文定为 `准备完毕`。
- `神滨市営霊园` 按中文地名语义定为 `神滨市营陵园`，不采用机械字形转换的“灵园”。
- 其余 7 种为 `仏罰！`、`永遠的刻`、泳装票券病句及 3／4／5／6 周年 DX 铜福袋。

- `manual_unique_review_checklist.tsv`

全部 1,158 个实际改动／保留字段的逐实例清单：

- `manual_translation_review_checklist.tsv`
- `manual_translation_review_checklist.summary.json`

## Wiki 原文保留

两条记忆结晶说明虽然含旧式字形 `第2節`、`慟哭`，但当前全文与指定 Wiki 的 `desc_zh` 完全一致。依据既定来源优先级，本轮原样保留，不用人工润色覆盖：

- `pieceList.json` 记忆结晶 1561
- `pieceList.json` 记忆结晶 1973

详见 `authority_preserved_exceptions.tsv`。这两条计入权威原文保留，不计入未完成项。

## 静态页面修正

- 重新审阅 237 条既有静态文本规则，并实际改进 163 个当前仍不理想的槽位。
- 完整统一 `SoundTest.js` 的 75 个语音标签，消除同一列表中的日中混写和“光盘／磁盘／行动盘”串项。
- 修正法律信息弹窗的中日混写、机器式语句、不可见字符和 `<<span` 标签错误。
- 修正 `FriendSearch.html` 中 `<span>` 被 `</p>` 错误闭合的问题。
- 修正记忆结晶保管库移动弹窗的“从 A 移至 B”语序与保管库／持有格术语。
- 修正任务时长单位 `时间` 为 `小时`。
- 测试／后门页面的日文可见文本已经中文化；代码注释、创作者署名、符号和技术标识不作为玩家可见翻译目标。

## 结构保护

以下内容与基线提交 `4db6698623311ee5ab1dce9ebce940e0eb2748f0` 保持一致：

- `magica/css/` 全部 8 份 CSS
- `magica/js/campaign/box_gacha/CampaignBoxGachaTop.js`
- `magica/template/campaign/box_gacha/CampaignBoxGachaTop.html`
- `magica/template/gacha/GachaTop.html`

23 份 JSON 的对象键、数组结构、复合键集合和非字符串标量均未漂移。

## 复现

在基线工作树中执行：

```powershell
python -X utf8 magica/i18n_audit/manual_cn_pass16/scripts/build_runtime_translation_map.py
python -X utf8 magica/i18n_audit/manual_cn_pass16/scripts/apply_manual_cn_pass16.py
python -X utf8 magica/i18n_audit/manual_cn_pass16/scripts/build_review_checklist.py
python -X utf8 magica/i18n_audit/manual_cn_pass16/scripts/post_translation_audit.py
python -X utf8 magica/i18n_audit/manual_cn_pass16/scripts/verify_pass16.py --tree . --out pass16_verification.json
```

`Build_JS_Injector.py` 由应用脚本在 23 份外部字典最终写入后调用；输出固定为 LF，字典顺序固定。
