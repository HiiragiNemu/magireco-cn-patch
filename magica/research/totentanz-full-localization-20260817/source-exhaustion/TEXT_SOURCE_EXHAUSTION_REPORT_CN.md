# 旧国服／美服网络文本穷尽审计（只读）

- 当前分支：`release/js-v26-authority-final-20260813`
- 基线提交：`d204454ea1fe74cfa984a7db1f68a0f5d70fc4b1`
- 审计模式：**只生成研究报告，不修改任何产品 JS／HTML／CSS／JSON**

## 结论

- **unresolved-actionable：11 个记录，合计 49 处字面位置。**
- **exhausted-no-value：26 个审计记录。** 其中 18 个仍有界面汉化价值，但旧国服没有可直接回收的中文，只能进入 Wiki／新人工译文层。
- CSS 已由现有选择器级审计闭合：41 个运行时 CSS、540 个 `content` 声明、110 个已中文化声明、非预期残留 0。
- 同路径 JSON 为 0；这只说明无法按路径直接复用，不否定项目现有 23 份运行时字典的 ID／来源权威流程。

## 可直接回收但尚未应用（unresolved-actionable）

| ID | 当前路径／定位 | 当前值 | 旧国服权威值 | 处数 | 判定 |
|---|---|---|---|---:|---|
| TXT-A001 | `magica/template/formation/DeckFormation.html；script#DeckNameChangeTemp #commentDecide; line 679` | `OK` | `确定` | 1 | 旧国服同一模板、同一 ID 提供确定按钮译文。 |
| TXT-A002 | `magica/template/formation/DeckFormation.html；script#TeamRemovePop .decideBtn; line 697` | `OK` | `确定` | 1 | 旧国服同一弹窗模板同一确认按钮为“确定”。 |
| TXT-A003 | `magica/template/formation/FormationQuest.html；script#DeckNameChangeTemp #commentDecide; line 90` | `OK` | `确定` | 1 | 旧国服同一模板、同一 ID 提供确定按钮译文。 |
| TXT-A004 | `magica/template/formation/DeckFormation.html；#nextPageBtnLoop; line 66` | `自动<br>播放` | `自动<br>续战` | 1 | 该按钮控制 quest loop/继续战斗；“播放”把循环战斗误译成媒体播放。 |
| TXT-A005 | `magica/template/mission/PanelMissionTop.html；script#missionParts .missionBtn when model.isLast; line 100` | `领取全部收集奖励` | `获得任务完成报酬` | 1 | コンプリート指任务完成而非收集；旧国服同一结构已有准确译文。 |
| TXT-A006 | `magica/js/formation/DeckFormation.js；deckCopyRun PopupClass; lines 47-48` | `<source><destination>已复制到。` | `<source>已被复制到 <destination>。` | 1 | 当前译文把“已复制到”错误黏在目标队名后，源/目标语序失真。旧国服提供相同功能的正确动态结构。 |
| TXT-A007 | `magica/template/chara/CharaDetail.html；#charaSetting .discSetting .common_title_frame; line 644` | `圆盘` | `行动盘` | 1 | 旧国服同一字段为“行动盘”；当前文件 line 281 也已使用“行动盘”，现状文件内不一致。 |
| TXT-A008 | `magica/template/formation/FormationQuest.html；script#DeckDetailPartsTemp p (disc); line 214` | `圆盘` | `行动盘` | 1 | 旧国服同一详情字段为“行动盘”。 |
| TXT-A009 | `magica/template/formation/FormationSupport.html；script#DeckDetailPartsTemp p (disc); line 140` | `圆盘` | `行动盘` | 1 | 旧国服同一详情字段为“行动盘”。 |
| TXT-A010 | `magica/js/_common/nativeCommand.js；battle tutorial tips; lines 14-17` | `圆盘（20处）` | `行动盘（旧国服同文件22处，当前另有3处已正确使用）` | 20 | 可见战斗提示内同一概念混用；旧国服及当前文件自身均确立“行动盘”。这是术语级替换，不声称新增句子整句来自旧国服。 |
| TXT-A011 | `magica/js/_common/nativeCommand2.js；battle tutorial tips; lines 268-394` | `圆盘（20处）` | `行动盘（旧国服同文件23处，当前另有3处已正确使用）` | 20 | 未压缩版战斗提示与 nativeCommand.js 同样混用；旧国服同文件和当前既有用词均支持“行动盘”。 |

重点结构错误：`TXT-A006` 必须维持 `e.name` 为源队伍、`u.name` 为目标队伍，显示为“源队伍已被复制到目标队伍”，不能做无上下文全局替换。

## 已穷尽且本轮没有可回收价值（exhausted-no-value）

| ID | 路径／定位 | 类别 | 当前值 | 原因 |
|---|---|---|---|---|
| TXT-E001 | `magica/template/chara/CharaDetail.html；visible Magia labels (e.g. lines 128,274,334)` | `formal-term-retained` | `Magia` | 项目既定正式术语保留 Magia；旧国服“魔法”不作为回退覆盖。 |
| TXT-E002 | `magica/template/formation/FormationQuest.html；script#DeckDetailPartsTemp .pointFrame; line 234` | `formal-term-retained` | `Magia` | 项目既定正式术语保留 Magia；语义已中文环境可理解。 |
| TXT-E003 | `magica/template/formation/FormationSupport.html；script#DeckDetailPartsTemp .pointFrame; line 160` | `formal-term-retained` | `Magia` | 项目既定正式术语保留 Magia；语义已中文环境可理解。 |
| TXT-E004 | `magica/template/user/APPopup2.html；item.itemName equality predicate; line 14` | `code-key-not-visible` | `マギアストーン` | 这是判断服务器 itemName 的程序键，不是直接显示文案；用旧国服“魔法石”替换会改变分支逻辑。 |
| TXT-E005 | `magica/template/user/APPopup2.html；item.itemName inequality predicate; line 16` | `code-key-not-visible` | `マギアストーン` | 这是判断服务器 itemName 的程序键，不是直接显示文案；用旧国服“魔法石”替换会改变分支逻辑。 |
| TXT-E006 | `magica/template/collection/MagiRepo.html；btnText array; line 5` | `numeric-equivalent-generated` | `["1",...,"9"]` | 最终显示为“第1部”等，和旧国服中文数字仅风格差异，无未汉化语义。 |
| TXT-E007 | `magica/template/test/backdoorList.html；NativeSandBox test link; line 24` | `test-debug-only` | `NativeSandBox` | 仅开发后门测试页，且新旧条目结构/用途已经漂移；不纳入游戏玩家可见汉化回收。 |
| TXT-E008 | `magica/template/collection/StoryCollection.html；commented popup button; line 162` | `dormant-comment` | `OK` | 位于 HTML 注释内，不会显示；旧国服同功能也保留 OK，缺少可回收中文。 |
| TXT-E009 | `magica/template/arena/ArenaSimulate.html；script#codeMachingPopParts #codeBattleStartBtn; line 115` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E010 | `magica/template/config/ConfigTop.html；script#dataPopInner .dataDecide; line 228` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E011 | `magica/template/formation/DeckFormation.html；script#autoFormationTemp #autoFormationBtn; line 820` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E012 | `magica/template/formation/DeckFormation.html；script#autoFormationSupportTemp #autoFormationBtn; line 854` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E013 | `magica/template/formation/DeckFormation.html；script#autoFormationGroupTemp #autoFormationBtn; line 888` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E014 | `magica/template/memoria/MemoriaComposeTop.html；script#formationEquipCautionPop .decideBtn; line 253` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E015 | `magica/template/memoria/MemoriaSetList.html；script#SetNameChangeTemp #commentDecide; line 79` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E016 | `magica/template/memoria/PieceArchive.html；script#formationEquipCautionPop .decideBtn; line 123` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E017 | `magica/template/memoria/PieceArchive.html；script#SetNameChangeTemp #commentDecide; line 256` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E018 | `magica/template/memoria/UserMemoriaList.html；script#formationEquipCautionPop .decideBtn; line 117` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E019 | `magica/template/memoria/UserMemoriaList.html；script#SetNameChangeTemp #commentDecide; line 197` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E020 | `magica/template/user/MyProfilePopup.html；script#emblemSettingTemp #settingDecideBtn; line 208` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E021 | `magica/template/user/MyProfilePopup.html；script#arenaDecideTemp #arenaDecideBtn; lines 216-218` | `source-insufficient-visible` | `OK` | 仍是可汉化的活动按钮，但旧国服同字段保留 OK 或不存在同一新字段，无法由本次“旧国服权威回收”直接解决；应进入后续新人工译文层。 |
| TXT-E022 | `magica/js/view/memoria/PieceArchiveView.js；PopupClass decideBtnText; line 23` | `source-insufficient-visible` | `OK` | 运行时可见按钮，旧国服同文件也保留 OK；无旧国服中文可回收，应由后续新人工译文层处理。 |
| TXT-E023 | `magica/js/view/memoria/PieceArchiveView.js；PopupClass decideBtnText; line 24` | `source-insufficient-visible` | `OK` | 运行时可见按钮，旧国服同文件也保留 OK；无旧国服中文可回收，应由后续新人工译文层处理。 |
| TXT-E024 | `magica/js/view/memoria/PieceArchiveView.js；PopupClass closeBtnText; line 26` | `source-insufficient-visible` | `OK` | 运行时可见按钮，旧国服同文件也保留 OK；无旧国服中文可回收，应由后续新人工译文层处理。 |
| TXT-E025 | `magica/js/view/memoria/PieceArchiveView.js；PopupClass closeBtnText; line 28` | `source-insufficient-visible` | `OK` | 运行时可见按钮，旧国服同文件也保留 OK；无旧国服中文可回收，应由后续新人工译文层处理。 |
| TXT-E026 | `magica/template/collection/StoryCollection.html；tab .puellaHistoria; line 10` | `source-insufficient-visible` | `Puella Historia` | 这是旧国服文件不存在的新标签；旧文件的“魔法少女剧情”属于另一个 data-wrap=chara 标签，不能错位复用。需 Wiki/新人工来源。 |

## 范围与边界

- 旧国服输入：1310 个 JS／HTML／CSS／JSON；当前运行时树（排除 research/i18n_audit）：457 个。
- 旧国服与当前运行时同路径：382 个；美服与当前同路径：237 个；三方同路径：214 个。
- 旧国服相对当前运行时独有路径：928 个。它们**没有被宣称为无价值**，因为旧活动、旧结构和不同打包路径需要另一套按功能/ID 的审计，不能凭路径缺失直接复制。
- `Magia` 等正式术语按项目既定合同保留；`APPopup2.html` 的日文 itemName 是程序判断键，替换会破坏逻辑。
- `Puella Historia` 是旧国服不存在的新功能标签；不得把旧的“魔法少女剧情”错位套用。
- 18 个 source-insufficient-visible 项只是“旧国服直接回收已穷尽”，仍应在后续 Wiki／人工翻译阶段解决。

## 证据文件

- 机器清单：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\js_v26_release_final_20260813\magica\research\totentanz-full-localization-20260817\source-text-exhaustion\source_text_exhaustion_manifest.json`
- 既有 CSS 审计：`C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3\work\js_v26_release_final_20260813\magica\research\totentanz-full-localization-20260817\visible-ui\css_visible_content_audit.json`
