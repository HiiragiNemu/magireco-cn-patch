# 歼灭战确认页魔女名称显示

仅在 `RegularEventExterminationBattleConfirm.html` 的 `#bossParamArea #name` 进行完整名称映射；不写回 API 对象，不改活动号、敌人号、槽号、属性、战力、图像或其他页面。

此前按活动/难度/槽位建立 API 数据补丁的方案因缺少原始响应而停留在候选阶段。本次采用独立的确认页显示修复：完整日文名称本身已经有对应译名依据，不需要为此推断运行时编号。

|精确原名|显示译名|依据|
|---|---|---|
|子守の魔女|照看孩子的魔女|ENEMY_COLLECTION|131|name；FULL_RAW_DUMP_V2_SAME_CATALOG_FIELD|
|流浪の魔女|流浪魔女|ENEMY_COLLECTION|149|name；FULL_RAW_DUMP_V2_SAME_CATALOG_FIELD|
|屋上の魔女|屋顶魔女|ENEMY_COLLECTION|111|name；FULL_RAW_DUMP_V2_SAME_CATALOG_FIELD|
|獄門の魔女|狱门的魔女|ENEMY_COLLECTION|163|name；LOCAL_WIKI_EXACT_ENEMY_ARTICLE|
|砂場の魔女|沙地魔女|ENEMY_COLLECTION|103|name；FULL_RAW_DUMP_V2_SAME_CATALOG_FIELD|

未知名称、英文变体、已有中文均原样保留。本次仅覆盖这五个已确认名称，不宣称整个活动所有动态名称已穷尽。游戏内效果由用户验收。
