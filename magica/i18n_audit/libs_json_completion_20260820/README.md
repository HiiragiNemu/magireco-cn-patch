# `magica/js/libs` JSON 汉化补全（2026-08-20）

## 当前结论

本目录最初用于记录 `pieceList.json` 中 3 条 Ashley Taylor 记忆结晶说明正文的 Wiki 权威补全。随后已完成独立记忆结晶标题的专项汉化，因此本文件同步更新，废止旧版“英文卡名应保留”的判断。

当前有效结果如下：

- `pieceId=1603/1604/1605` 的 `description`：继续采用固定 Wiki 提交 `2a27d64e3c59c893c177c5349b3a6c8134117aea` 中同记录的 `desc_zh`。
- 两轮标题专项提交 `66da7cbac7f5db215a17077bcb85b081ccf1d2c2`、`41966e9f5c9fe03c7ce490a40718c958577857c3` 共将 **30 个**纯英文独立 `pieceName` 改为中文。
- `pieceId=1603/1604/1605` 的标题现分别为“熊乃介的卡哇伊视频”“我的胜利姿势也很卡哇伊唷”“卡哇伊收藏”。
- `pieceList.json::pieceName` 的纯英文独立标题余量为 **0**。

完整标题采用清单、逐条语境与验证见相邻目录：

`../piece_title_localization_20260820/`

## 语义边界

“正文”不是 `scenario` 的同义词。这里需要区分：

- `scenario`：剧情脚本正文；
- `pieceList.json::description`：记忆结晶说明或风味文本；
- `charaMessageList.json::message`：角色语音/短句文本；
- `pieceList.json::pieceName`：独立显示的记忆结晶标题。

本轮标题汉化只修改 `pieceName`。`scenario`、角色语音、对白及 `description` 均没有因标题专项而改变。

角色说话方式中的刻意英语夹杂不能仅凭含拉丁字母就判定为缺译。例如阿莉娜台词中的 `body`、`show`、`fool girl` 属于角色化表达，应结合台词语境保留。与之不同，`Different Story：Rookies`、`As a fashion model`、`Begin a Hunt`、`Splash party!`、`Three geniuses` 等是独立标题，已按权威来源或逐条语境中文化。

## 原始 3 条说明正文

### pieceId=1603

- 标题：熊乃介的卡哇伊视频
- `description` 来源：`memoria.json::kumanosuke-s-kawaii-vid::number=9003::desc_zh`

### pieceId=1604

- 标题：我的胜利姿势也很卡哇伊唷
- `description` 来源：`memoria.json::my-victory-pose-is-kawaii-too::number=9001::desc_zh`

### pieceId=1605

- 标题：卡哇伊收藏
- `description` 来源：`memoria.json::kawaii-collection::number=9002::desc_zh`

## 已废止的旧判断

旧版 `RETAINED_BY_POLICY.tsv` 将上述 3 个标题归类为“游戏内英文专名，保留”。这一结论与 Wiki 已有中文标题、用户明确的标题汉化边界以及当前产品数据均冲突，现已删除，不得作为恢复英文的依据。

## 验证

- 原始说明正文补全：3 个 `description` 字段；
- 后续标题专项：30 个 `pieceName` 字段；
- 标题专项未修改任何 `description`、scenario、语音、对白、ID 或其他字段；
- 当前 `pieceList.json` SHA-256：`dc1c40d9111716c6ced7a5d3de15a40a61562b5cb25a332dcac07ebca3baf6fd`；
- 当前纯英文独立 `pieceName`：0。
