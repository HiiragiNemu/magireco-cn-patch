# 外部作品剧情导入魔纪（story-import）

把 **PSP《魔法少女小圆携带版》** 与 **PS Vita《战斗的五芒星》** 的剧本转成
魔纪的 ADV 剧情，随 `cn_scenario_update.zip` 下发，在游戏里播出来。

```
携带版 ISO ─┐                         ┌─ magireco_cast.json（立绘/表情映射）
           ├→ 各自仓库的 extract_ir.py ─→ story IR ─→ ir_to_adv.py ─→ adv json
五芒星 .asb ┘                                              │
                                                           ↓
                     madomagi/resource/scenario/json/adv/scenario_8/<storyId>.json
                                                           ↓
                              cn_scenario_update.zip（sync-and-upload.yml）
                                                           ↓
                          客户端解包到 <files>/madomagi/resource/scenario/json/
                                                           ↓
                       JS：nativeCommand.startStory("<storyId>") → 原生 ADV 播放器
```

解包与 IR 抽取在另外两个仓库：

* [`PuellaMagia-Pocket-Unpack-and-Research`](https://github.com/CyberNova2333/PuellaMagia-Pocket-Unpack-and-Research)
  —— 733 个 block / 23454 条台词（简中，汉化版 ISO 自带）
* [`theBattlePentagram-Unpack-and-Research`](https://github.com/CyberNova2333/theBattlePentagram-Unpack-and-Research)
  —— 119 条路线 / 3106 条台词（日文原文或英文译文；**简中拿不到**，见该仓库
  `docs/02-asb-script.md` 的码表问题）

## 一、跑一遍

```bash
# 1. 抽 IR（在对应的解包仓库里）
python3 tools/extract_ir.py work/archive out/ir --lang zh-Hans

# 2. 转成魔纪剧情
python3 tools/story-import/ir_to_adv.py out/ir/Chapter01/01/00_00.json \
    --bg bg_adv_20361.jpg --bgm bgm03_story06 \
    --out madomagi/resource/scenario/json/adv/scenario_8/881011-1.json

# 3. 自检
python3 tools/story-import/test_ir_to_adv.py
```

`ir_to_adv.py` 退出码非 0 表示写出的立绘 id / 表情文件名不在映射表里——
**这种文件发出去会让原生 ADV 播放器加载失败**，别提交。

## 二、storyId 怎么分配

文件名就是 storyId，目录是 `adv/scenario_<storyId 首位数字>/`
（10469 个现存文件无一例外）。

线上 2482 个 sectionId 里，`8` 开头的**只有 `809010` 一个**。所以 8 号段基本
是空的，建议：

| 段 | 用途 |
|---|---|
| `881xxx` | 携带版（`8810NN-M` = Chapter01 的第 NN 场第 M 段，依此类推） |
| `882xxx` | 五芒星 |
| `809010` | ⚠ 已被线上占用，绕开 |

**不要**用 `_XXXXX` 后缀。10469 个文件里 5733 个带 5 位随机后缀，那是主线
剧情由服务端下发全名时用的；`eventStoryList.json` 里能直接播的 230 条全是
无后缀的裸名。我们自己发起的播放走裸名。

## 三、怎么让它播出来

原生播放器的入口是 `magica/js/_common/nativeCommand.js`：

```js
b.startStory = function (a, c) {                    // a = storyId
  var f = {}; f.storyId = a; …
  this.sendCommand(b.SCENE_PUSH_STORY + "," + JSON.stringify(f));  // SCENE_PUSH_STORY = 261
};
```

`SCENE_PUSH_STORY` 一送过去，原生侧就按 storyId 去
`<files>/madomagi/resource/scenario/json/adv/scenario_<首位>/<storyId>.json`
取文件播放。**这一步不经过服务端**，所以只要文件在本地就能播。

两种接法：

1. **直接调用（最小改动）**
   ```js
   nativeCommand.startStory('881011-1');
   ```
   在任何一个 View 里挂个按钮即可。适合先验证。

2. **走剧情收藏的活动剧情页**
   `magica/js/libs/eventStoryList.json` 是纯客户端表
   （`[{"storyIds": "501011-1", "storyTitle": "1话"}]`），
   `collection/StoryCollection.js` 用它渲染「活动」页签。加条目 + 加一个
   新的分组入口就能把外传挂进剧情收藏里。这张表随
   **`cn_js_update.zip`** 走，与剧情包是两个版本通道。

⚠ `_common/backboneCommon.js` 的 `playStory()` 会先
`ajaxPost(userQuestAdventureRegist, {adventureId: storyId})` 向服务端登记。
外传 id 服务端不认识，会失败。**要么直接用 `nativeCommand.startStory`
绕开登记，要么先在服务端把 id 注册好。**

## 四、发布

剧情包的内容就是仓库里的 `madomagi/resource/scenario/json/` 整棵树
（`sync-and-upload.yml` 的 `pack-scenario`：`cp -r … && zip -r`）。所以：

1. 把 adv json 提交到 `main`；
2. 跑 `🔄 打包热更并上传到 object-storage`，`package_scope=scenario`；
3. 确认无误后 `publish_hotfix=true` 把 `_new` 转正，`version_scenario.json` 抬版本。

### 🔴 进了包的文件拿不出来

`RestClient.unzip` 只写不删。**一个错误的剧情 json 一旦下发，设备上那份就永远
存在**，只能用同名文件覆盖，不能删除，而且本地永远赢过服务端（见根 README
「客户端怎么消费它」）。所以：

* 先用 `--out` 到临时目录 + 真机侧载验证，再往仓库里放；
* id 一旦发出去就固定，不要改名重发（改名 = 旧文件永久留在设备上）；
* 大批量导入分批发，每批先发一话验证观感。

## 五、立绘映射

`magireco_cast.json` 是唯一的真相来源，由
`asset_main_cn.json`（线上资产清单）+ 全量现存剧情的使用统计生成：

| cast 键 | 魔纪角色 | 默认立绘 | 说明 |
|---|---|---|---|
| `madoka` | 鹿目圆 2001 | 200101 | 另有动画时间线的 scene0 版 2105 |
| `sayaka` | 美树沙耶香 2004 | 200401 | scene0 版 2402 |
| `mami` | 巴麻美 2005 | 200501 | scene0 版 2503 |
| `kyoko` | 佐仓杏子 2006 | 200601 | scene0 版 2601 |
| `homura` | 晓美焰 2002 | 200200 | scene0 版 2301 |
| `homura_glasses` | 晓美焰（眼镜）2003 | 200301 | 携带版/五芒星的回忆段落用得上 |
| `kyubey` | 丘比 | 810000 | **没有任何 exp3 表情文件**，不能写 `face` |
| `hitomi` | 仁美 | 810600 | |
| `kyousuke` | 恭介 | 810500 | |
| `saotome` | 早乙女老师 | 810200 | |
| `junko` | 圆的母亲 | 834500 | |

* 6 位 id = 角色 id ×100 + 服装序号。**服装序号的语义没有权威表**，映射表里
  不猜，默认取「游戏自己用得最多的那个」，要换用 `--cast-override madoka=210500`。
* `faces` / `motions` 是从 `asset_main_cn.json` 抽的**该模型真实存在的**文件。
  转换器只从这里取值，`check_assets()` 在写盘前再核一遍。丘比就是靠这条被自动
  判成「不写 face」。

## 六、表情

IR 带一个 `expression` 类别，转换器按**阶梯**挑该立绘第一个真实存在的表情
文件。魔纪这边每个 `mtn_ex_XXX` 是什么意思，是量出来的不是猜的——adv json 里
`tear` / `cheek` / `eyeClose` / `mouthOpen` 是独立字段，拿它们与 `face` 的
共现率反推（全库 10469 个剧情文件）：

| 编号 | 语义 | 证据 |
|---|---|---|
| `000` / `001` | 无表情 | 各项全库最低 |
| `010` | 普通 / 淡笑 | 笑 1.7× |
| `011` | 笑 | 笑 **4.8×**、！46.9% |
| `013` / `014` | 害羞的笑 | 脸红 43.4% / 15.1% |
| `020`–`022` | 强调 / 喊 | ！35–54%，无笑无泪 |
| `030` | 困扰 / 落寞 | …… 37.3%（最高）、泪 2.3× |
| `031` | 哭 | 泪 **21×**、脸红 38.5% |
| `040` / `042` | 疑惑 / 沉思 | ？+…… 高，！低 |
| `050` / `051` | 惊讶 | ？2.5×、惊 3.8× |
| `060` | 痛苦 | 泪·脸红·闭眼·张嘴·！·悲 **六项全显著** |

阶梯（`EXPRESSION_LADDER`）必须以 `000`/`001` 收尾：**写一个该模型没有的
exp3 文件名，原生播放器会加载失败，而这种错在 json 里看不出来**。
晓美焰 `200200` 就没有 `010`，neutral 自动退到 `000`。

⚠ 两处**未解**，按铁律空着不凑：
* 「怒」——全库七项特征里怒的信号最高只有 1.2%，找不到对应编号；
* 服装序号的语义（`xx00`/`xx01`/`xx02` 分别是什么）没有权威表。

全量核对：29666 步、15372 次表情变更，`check_assets()` **零问题**。
* 没有对应立绘的角色（携带版的路人、五芒星的护士/合唱/究极圆）自动降级成
  `narration` 旁白，姓名照写。

## 六、这一版**没有**做的事

对着源作品的成品比，转出来的东西差这些。都不是死路，只是还没做：

| 缺什么 | 卡在哪 |
|---|---|
| 背景 | 源背景是 GIM / GXT，尺寸与魔纪的 `bg_adv_*.jpg` 不一致；现在全场一张，靠 `--bg` 指定 |
| BGM / SE | 同上，靠 `--bgm` 指定一首 |
| 语音 | 源是 `.ahx` / `.at9`，魔纪 fullvoice 是另一套编码 + 另一套命名（`fullvoice/section_<id>/vo_full_<id>-<n>_<line>`）。没转码前**一个字都不写**，写了就是加载失败 |
| 分支 | 携带版有选项分支（同一场戏里多个 block）；IR 与转换器都还是线性的。魔纪原生支持（`select` + `changeGroup` 跳 `group_N`），补起来不难 |
| 简中的五芒星文本 | 汉化补丁改的是字库码表不是编码，得先 OCR 出码表 |

## 七、文件

```
story_ir.py        IR 的定义与校验
ir_to_adv.py       IR → 魔纪 adv json（含站位调度与资产核对）
magireco_cast.json 立绘/表情映射（生成物，改前先读 _note）
test_ir_to_adv.py  18 项自检
```
