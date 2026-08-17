# 原生战斗技能弹窗控制源审计（2026-08-17）

## 截图结论

截图中的文字不是同一种来源，必须分开处理：

| 可见内容 | 控制源 | 本轮处理 | 权威结论 |
|---|---|---|---|
| `Magia Drain [VI]` | native 动态 `Label::setString`；业务键 `emotionSkillMap:1007113.name` | 加入 `madomagi/engine_i18n.tsv` exact 规则 | 未找到官中／Wiki 名称，沿用当前产品粗译，最低权重，后续仍可人工精修 |
| 完整 `Magia Damage DOWN...` | native 动态标签；业务键 `emotionSkillMap:1007113.shortDescription` | 加入 exact 规则 | Wiki 稳定 ID 1007113 支撑 |
| `発動` | native 动态按钮标签 | 加入 exact `発動→发动` | 旧国服 native 同一战斗技能上下文有精确 `发动` |
| `Skill Effect` | `quest_image0.png` 的 `skill_title_02.png` frame | 不写入 engine；记录为 APK 图集任务 | 旧国服对应像素为“技能内容” |
| `Turn(s) Until Available` | `quest_image0.png` 的 `skill_title_03.png` frame | 不写入 engine；记录为 APK 图集任务 | 旧国服对应像素为“冷却回合数” |
| `Not Equipped` | 原生 quest 图集 frame；旧国服素材位于 `quest_image1` | 不伪造 engine 键；记录为 APK 图集任务 | 旧国服对应像素为“未装备” |
| `Charge`、`DISK` | 原生 quest 图集像素 | 保留 | 旧国服正式素材同样保留这些拉丁术语，不属于普通漏翻 |

## 为什么不能把旧国服整张图覆盖过去

- 现役 Totentanz：`D:\magia\MyProducts\MagiaRe\Magia_CN_Project\totentanz_unpacked\assets\package\quest\quest_image0.{png,plist}`。
- 旧国服：`D:\magia\MyProducts\MAGIA RECORD CN\origin_apktool_decoded\assets\package\quest\quest_image0.{png,plist}` 与 `quest_image1.{png,plist}`。
- 现役 `quest_image0.png` 为 2048×1024；旧国服图集为 1024×1024，frame 坐标和尺寸也不同。

因此旧图集只能作为中文像素来源，必须逐 frame 迁入现役图集并重建 plist/纹理；整张替换会破坏大量战斗资源。该图集属于 APK 原生资源，不是 `cn_js_update.zip` 的 WebView `magica/` 内容。

## native 实际负责的中文化范围

当前 legacy native hook 从设备 `<files>/madomagi/engine_i18n.tsv` 读取 exact/prefix 规则，并覆盖 cocos2d 动态标签入口：`Label::setString`、`LabelAtlas::setString`、`MenuItemLabel::setString`、加载场景文本及 `LbUtility::initLabel`。因此它适合网络／下载提示、战斗状态、动态技能名／说明、按钮文字和部分战斗台词；它不改 atlas 内已经烘焙成像素的英文／日文。

既有 native 研究是 arm64-v8a 与 armeabi-v7a 的有界 ELF 字符串、交叉引用与公共函数对齐，不是把两份 200 MB 以上 `.so` 完整反编译，也没有从二进制中抽出一整张官方中文 TSV。后续只对真实设备 miss 做定点检索。
