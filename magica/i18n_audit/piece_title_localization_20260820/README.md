# 独立记忆结晶标题汉化（2026-08-20）

本轮只处理 `pieceList.json` 的 `pieceName` 独立标题。`scenario` 剧情、角色对白、语音、`description` 正文均不在写入范围内。

## 语义边界

- `body`、`show`、`fool girl` 等出现在阿莉娜说话方式中的英语夹杂，属于角色塑造，不按“残留英文”处理。
- `Different Story：Rookies`、`As a fashion model`、`Begin a Hunt`、`Splash party!`、`Three geniuses` 等作为完整标题独立显示，属于应中文化内容。
- 优先采用 Wiki 同一条记录中的人工中文标题；只有本轮用户明确点名且 Wiki 无可用中文时，才启用五项限定人工兜底。
- 不做子串替换，不改说明正文，不改任何 ID。

两轮合计写入标题字段：**30**；剩余纯英文独立标题：**0**；Wiki 映射冲突：**0**。

## 第二轮：剩余 20 项

第二轮读取每条记忆结晶的现有中文正文及 Wiki 同记录字段逐条判断。其中 `Miracle Heroines` 与 `The Great Escape` 采用 Wiki 繁中字段转简体；`Mikoto in Mirrors` 的角色名采用当前 `charaList.json` 的“濑奈命”；其余为有上下文记录的人工翻译。完整决策见 `MANUAL_CONTEXT_APPLIED.tsv`。

两轮均未修改 `description`、scenario、角色语音、对白或任何非 `pieceName` 字段。
