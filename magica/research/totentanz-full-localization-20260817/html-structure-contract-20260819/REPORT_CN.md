# HTML 冻结结构合同

## 结论

- 产品 HTML：225 个
- 严格与逐路径结构源一致：213 个
- 版本差异、冻结最终产品结构：12 个
- 源路径缺失：0
- 产品结构漂移：0
- 源结构漂移：0
- 来源分布：`{"git-head-baseline": 83, "magicaOLD": 8, "totentanz-current-us": 122, "version-divergent-frozen-product": 12}`

只忽略可见文字，以及 `title`、`placeholder`、`value`、`data-title`
的可翻译值；标签序列、EJS 控制骨架和其余敏感属性严格比较。

## 12 个版本差异模板

这些模板仅把旧国服文件作为中文参考，不声称旧结构等于当前结构；当前最终
产品结构已独立冻结，后续任一标签、敏感属性或 EJS 控制骨架改变都会失败。

- `magica/template/arena/ArenaCurePop.html`
- `magica/template/arena/ArenaTop.html`
- `magica/template/collection/CharaCollectionDetail.html`
- `magica/template/follow/FollowPopup.html`
- `magica/template/follow/FollowTop.html`
- `magica/template/item/ItemListTop.html`
- `magica/template/memoria/MemoriaPopup.html`
- `magica/template/mission/MissionTop.html`
- `magica/template/present/PresentList.html`
- `magica/template/quest/MainQuest.html`
- `magica/template/quest/QuestResult.html`
- `magica/template/quest/SubQuest.html`
