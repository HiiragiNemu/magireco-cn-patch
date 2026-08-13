# 汉化对照表

游戏里的一句日文，要改哪里，取决于它是**谁渲染的**。这是三条完全不同的链路，
用错一条，活白干：

| 谁渲染 | 改哪里 | 怎么下发 | 唯一维护源 |
|---|---|---|---|
| WebView（前端） | 本目录四张迁移表经 `tools/i18n-*.py` 明确回填进 `magica/`；核验后的高权重候选另进 reviewed 审计层 | `cn_js_update.zip` 的 `magica/` | 本仓库 `i18n/`、`tools/` 与 `magica/` |
| cocos2d 原生引擎 | `madomagi/engine_i18n.tsv`（文本 hook 的翻译表） | 同一个 `cn_js_update.zip` 的 `madomagi/engine_i18n.tsv` | 本仓库 `madomagi/engine_i18n.tsv` |
| 烘焙进 PNG／plist 图集的文字 | 只能改图片资源 | 资源包 | 无 |

本仓库同时拥有前两条翻译数据与构建工具，但两条运行时链路仍然独立：四张迁移 TSV
只是生成输入，只有显式运行工具、审阅差异并把结果写入 `magica/` 后才影响 WebView；
它们绝不在客户端运行时自动覆盖 `magica/`。引擎表则由 native hook 直接消费。

`MagirecoCN-Revival-Project/legacy-client` 只保留 hook、调试开关、读取
`<files>/madomagi/engine_i18n.tsv` 的运行时合同与回归测试，不维护第二份四表、工具或
引擎译文源。两个产品树的共同点只有：最终由同一个 JS 热更包下发。

### 权威顺序与防回流

发生冲突时固定采用以下顺序，低层不得覆盖高层：

1. 官方旧国服客户端 dump；
2. `HiiragiNemu/wiki-data`；
3. 仓库既有且能确认是人工完成的译文；
4. 新人工／LLM 翻译。

“官方 dump 未命中”必须记录为**官方缺失**，不可把随后采用的 Wiki 译文误标成
官方来源。对照表或术语表的变化必须先产出来源/冲突审计，再显式物化进 `magica/`；
禁止把四张 TSV 当作运行时覆盖层，也禁止从 legacy 仓库离线回写本产品树。

---

## 一句日文该归哪一层：不要猜，有判据

补 `madomagi/engine_i18n.tsv` 和改 `magica/` 是两个运行时方向完全不同的修法，
虽然最终由同一个 JS 热更包下发，仍不能混用。
2026-08-08 之前这件事**没有判据可用**：文本 hook 只在命中时打日志，未命中一声不吭，
所以串不在表里时，它有没有流经 native 标签，日志长得一模一样。

现在有了。`logI18nMiss` 调试开关会把「流经 hook 却没翻到」的串打出来：

```bash
adb shell "run-as io.kamihama.totentanz mkdir -p debug"
adb shell "run-as io.kamihama.totentanz touch debug/logI18nMiss"
# 重启游戏，把要查的流程走一遍，然后：
adb logcat -d -s MagiaCN_Legacy | sed -n 's/.*\[i18n-miss\]\[[^]]*\] //p' | sort -u
```

- **清单里有这句** → 走 native 标签，补 `madomagi/engine_i18n.tsv`，而且热重载生效。
- **没有** → 不经过 native 标签，去前端热更包或服务端那层找。

开关有两个：`logI18nMiss` 只记**含假名**的串（默认，噪音低）；`logI18nMissAll`
不筛内容，用来确认拉丁字母/纯数字的串走没走 native 标签。详见 README 的
「调试开关目录」一节。

正式签名包通常没有 `android:debuggable`，这时 `run-as` 会报
`package not debuggable`。可 root 的测试模拟器应改用应用真实 UID 建开关，避免用
root 建出属主/权限错误、导致客户端把所有开关误判为关闭：

```bash
adb root
adb shell 'd=/data/user/0/io.kamihama.totentanz; u=$(stat -c %u "$d"); \
  mkdir -p "$d/debug"; chown "$u:$u" "$d/debug"; chmod 700 "$d/debug"; \
  touch "$d/debug/logI18nMiss"; chown "$u:$u" "$d/debug/logI18nMiss"; \
  chmod 600 "$d/debug/logI18nMiss"'
```

采样结果先与官方旧国服 dump 对齐；官方缺失时再查 Wiki，之后才允许查看既有人工
译文或新增翻译。核对结果必须保留“运行时逐字命中、来源层、源键、冲突选择”证据，
经人工复核后再改本仓库唯一的 `madomagi/engine_i18n.tsv`。采样或对齐过程不得直接
改产品树，也不得在 legacy-client 中落第二张运行时表。

---

## 战斗相关文本怎么汉化

### 结论（2026-08-08 实测）

战斗中与战斗结束的角色台词**走 native 标签**，补 `madomagi/engine_i18n.tsv`
即可；不需要重出 APK，也不触发 scenario 包，但需要发布新版 `cn_js_update.zip`。

判定过程留档，因为这类结论没有实证就会被反复重新猜一遍：

1. 现象：战斗结束（Battle Clear，WAVE 2/2）时说话人的台词
   「カーテンコールで終いやな」是日文，而**同一场战斗中**的台词
   （焰「（几乎跟魔女之夜一样……）」）是中文。
2. 排除机制故障：日志里 `[i18n] 已加载 295 条 + 2 前缀规则`、6 个 hook 全部
   `✓`、本局实际替换 10 次；台词包 `server=3214 local=3214` 已是最新。
   所以不是「汉化没生效」，是**这句不在任何一张表里**。
3. 判定链路：往设备 `<files>/madomagi/engine_i18n.tsv` 追加一行，3 秒内热重载，再打一场
   —— 变成中文了。**证毕：走 native 标签。**

> 顺带一个还没查的：截图里说话人名字显示为拉丁字母 `Livia Medeiros`，
> 既不是日文原文（リヴィア・メデイロス）也不是中文译名。`logI18nMiss` 看不见
> 它（不含假名），需要开 `logI18nMissAll` 跑一局确认它走不走 native 标签。
> 若不走，它多半属于「服务端直接返回、未经注入器的字段」——README 那张分层表里
> 唯一标「未做」的一行。

### 操作步骤

```bash
# 1. 收集这一局所有该翻没翻的串（骨架已经是 tsv 行格式）
adb shell "run-as io.kamihama.totentanz touch debug/logI18nMiss"
# 重启，打一场，然后：
adb logcat -d -s MagiaCN_Legacy | sed -n 's/.*\[i18n-miss\]\[[^]]*\] //p' | sort -u \
  > /tmp/miss.tsv

# 2. 填译文。每行形如  #原文<TAB>   —— 翻一条，去掉行首的 #，把译文补在 TAB 后

# 3. 推回设备验证（表每 3 秒查一次 mtime，不用重启游戏）
adb push /tmp/miss.tsv /sdcard/miss.tsv
adb shell "run-as io.kamihama.totentanz sh -c \
  'cat /sdcard/miss.tsv >> files/madomagi/engine_i18n.tsv'"
```

> 🔴 **行首那个 `#` 不是装饰。** 这张表里「译文为空」的语义是**删除该串**，
> 不是「还没翻」。所以未填译文的骨架行不是惰性的——不带 `#` 直接追加，这些串会
> 当场从界面上消失，而且是在没人改过译文的情况下悄悄发生。所以日志输出默认带
> `#`，翻一条放开一条。

这不是理论上的脚坑，本仓库权威表的第 41–42 行正用着：

| 行 | 原文 | 译文 |
|---|---|---|
| 41 | `敵から受けるダメージが ` | `受到敌方的伤害提升 ` |
| 42 | `上昇する` | *（空）* |

日文把一句话拆成「受到的伤害」+ 句尾动词「上昇する」两段拼接；中文的「提升」
已经并进第一段，第二段**必须删掉**，否则界面上会多出一个「上昇する」。这就是
`loadEngineI18n()` 里 `if (!ja.empty()) fresh[ja] = zh;`——`zh` 是空串也照存，
两条查找路径随后都会拿它当译文塞回引擎。**每次加载都在执行这个语义**，
所以一个手滑的空译文和一次有意的删除，在加载器眼里没有任何区别。

> 上面这套是**在设备上就地验证**，改的是设备上那份副本，下次热更会被覆盖。
> 验证通过之后，把同样的行提交到补丁仓库 `HiiragiNemu/patch-front` 的
> `madomagi/engine_i18n.tsv`（去掉 `#`），推上去就会自动重打 JS 热更包并下发——
> 见下一节。

---

## `engine_i18n.tsv` 的源与下发链路

**唯一源就在本仓库**：

```
HiiragiNemu/patch-front  →  madomagi/engine_i18n.tsv     ← 译文改这里
```

发布流水线 `.github/workflows/sync-and-upload.yml` 将它视为 JS 热更输入。整条
链路必须保持：

```
改 madomagi/engine_i18n.tsv
  └─ 检测为 JS 更新，不标记 scenario 更新
      └─ 重打 cn_js_update.zip
          ├─ magica/**
          └─ madomagi/engine_i18n.tsv
              └─ version_js.json 递增；version_scenario.json 保持不变
                  └─ 客户端下载 JS 包并解到 <files>/
                      └─ native hook 从 <files>/madomagi/engine_i18n.tsv 热重载
```

也就是说**改一句引擎译文只改本仓库这一行**，不重出 APK，也不让用户为几 KB 的
TSV 下载数百 MB 的 scenario 包。`tools/i18n-package.py --base <旧 JS 包>` 支持只改
此表仍复构建完整 JS 包，并强制包内根路径精确为
`madomagi/engine_i18n.tsv`（与 `magica/` 平行）。

迁移时不重打线上历史 scenario v3217：该旧资产仍含迁移前副本，但新版 JS 包会在
同一路径原子覆盖；后续 producer 生成的 scenario 包由合同测试强制禁含此表。这样
完成运行时所有权迁移，同时避免用户只为移除旧副本下载约 194 MB 剧情包。

> 🔴 **不要再建 `i18n/engine_i18n.tsv` 或 legacy-client 副本。** 那会造出第二个源，两边一分叉，
> 谁也说不清哪份是真的——而这张表「译文为空 = 删除该串」的语义会让分叉直接表现为
> 界面上的文字消失。要改译文只改本仓库 `madomagi/engine_i18n.tsv`。

### 旧国服权威译文怎么回收

旧国服客户端 dump 是第一权威：可用原生库或 `(charaNo, messageId)` 对齐角色台词
字典；未命中项必须记为“官方缺失”，再降级查 Wiki。生成的多列 TSV 只供来源与冲突
审阅，**不是第二份运行时表**；验证通过的条目最终只写回
`madomagi/engine_i18n.tsv`。

几条对得上的旁证（2026-08-08 核对）：

- 漏译修复前的补丁表 298 行 = 1 行注释 + 295 条精确条目 + 2 条前缀规则；当时
  设备日志是 `[i18n] 已加载 295 条 + 2 前缀规则（第 298 行止，坏行 0）`，逐字吻合。
  加入「カーテンコールで終いやな」后，当时的表为 299 行 = 1 行注释 + 296 条
  精确条目 + 2 条前缀规则。v26 最终权威表为 304 行 = 1 行注释 + 301 条精确条目
  + 2 条前缀规则；设备收到新包后的期望日志相应为 301 + 2、第 304 行止、坏行 0。
- 解压根是 `/data/data/io.kamihama.totentanz/files/`（`CNHotUpdateCheck.FILES_DIR`），
  所以包内路径 `madomagi/engine_i18n.tsv` 正好落到 `MagiaLegacy.cpp` 的
  `ENGINE_I18N_PATH`。
- 它**不会被孤儿清理误删**：`CNHotUpdateTx.cleanupPrefixes("scenario")` 只清
  `madomagi/resource/scenario/json/` 前缀，这个文件在该前缀之外。

---

## `engine_i18n.tsv` 格式

每行 `原文<TAB>译文`，UTF-8，被 `MagiaLegacy.cpp` 的 `loadEngineI18n()` 读取。

| 写法 | 含义 |
|---|---|
| `日文<TAB>中文` | 精确替换 |
| `^日文前缀<TAB>中文前缀` | **前缀规则**：命中后换掉前缀、保留后缀。用于尾部带变量的文案，如「ネットワーク接続に失敗しました。\nエラーコード：1」 |
| `日文<TAB>`（译文为空） | **删除该串**。拼接式文案调语序时用，**不是**「还没翻」 |
| `#` 开头 | 注释，整行跳过 |
| `\n` `\t` `\\` | 换行／制表／反斜杠的转义（原文和译文两侧都适用） |

行为要点：

- **热重载**：启动时加载一次，之后每 3 秒节流检查一次 mtime，改完免重启。
- **没有 TAB 的行**算坏行，会计入启动日志的「坏行 N」，但不影响其余条目。
- 命中的 hook 入口共 6 个：`cocos2d::Label::setString`、`LabelAtlas::setString`、
  `MenuItemLabel::setString`、`LoadingSceneLayerInfo::setText` / `setTitle`、
  `LbUtility::initLabel`。前五个收 `std::string`，最后一个收 `const char*`。

---

## 前端四张表

由 `tools/i18n-*.py` 消费，链路是
`i18n-extract.py`（抽串）→ 人工／`i18n-glossary.py` 填译文 → `i18n-apply.py`
（回填进前端代码）→ `i18n-fragments.py`（片段改写）→ `i18n-package.py`
（打成 `cn_js_update.zip`）。

| 文件 | 列 | 干什么 |
|---|---|---|
| `frontend-strings.tsv` | 原文／译文／风险／出现次数／出现于 | 主表。前端所有日文字面量，1686 行 |
| `glossary.tsv` | 日文／中文 | 术语表，从中文 Wiki 的术语模板提取，955 个有效项（含表头共 956 行） |
| `overrides.tsv` | 文件前缀／原文／译文 | 同一原文在不同界面含义不同时按文件点名覆盖（如「サポート」= 辅助／支援） |
| `fragments.tsv` | 文件前缀／原始片段／替换片段 | 跨节点整段改写，解决整串替换够不到的语序问题（日文宾语前置、「数+动」） |

每张表的表头注释里写了它自己的判据和存在理由，改之前先读那几行。

### 四表之外的 reviewed 权威层

`reviewed-candidates.tsv` 不计入上面的 legacy 四表。它只记录已经找到逐项证据的
高权重候选，至少包含来源层、稳定来源定位、来源文件 SHA-256、匹配方法、是否机翻、
置信度和复核状态。官方候选必须是 `machine_translated=false`，并通过官方证据合同；
Wiki 或确认人工候选也必须保留自己的真实层级，不得升级冒充官方。

该表只参与 `i18n-build-effective.py` 生成的只读选择／冲突／provenance 审计，不会
由 CI 自动回填 `magica/`。维护者显式执行 canonical `i18n-apply.py` 时，工具必须先
验证 `generated/summary.json`：当前五份输入、policy、迁移摘要、生成器与
`effective.tsv` 的哈希须全部一致，然后才以 effective 选择覆盖冻结表里的低权重
候选；缺失或陈旧会在任何产品写入前失败。实际产品改动仍须验证前像、应用后值、
受保护文本零漂移，并提供逐项回滚。低权重 LLM／DS 结果只能进入 staging 或人工复核
清单，不能写入 reviewed 层覆盖官方、Wiki 或确认人工文本。

回填铁律是**只换整条字面量**（见 `i18n-apply.py`）：不做子串替换，否则汉化会
渗进变量名和 URL 里。语序问题一律走 `fragments.tsv`，不要手改压缩后的 JS
——那些改动会被流水线重跑冲掉。
