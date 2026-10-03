# 魔法纪录游戏侧：最终校订稿接入与仅更新累计 JS delta 的发布交接

记录日期：2026-10-03。最新维护者要求：**游戏侧以后只更新累计 JS delta；完整 Scenario 和完整 JS 保持既有基线，不因这批剧情重新发行。delta 内已有的落后剧情必须用最新权威源码覆盖，不允许新版本号携带旧正文。** 本要求取代旧交接中“必须同源重建并共同发布 Scenario＋delta”的发布方式；不撤销完整性、防回退、并发锁、基线身份和实际设备验收要求。

## 1. Reader 已经完成的交付

Reader 最终校订输入已经进入既有 main，正文整合提交 `bafe7a64a5b3537302e5d43679448d23c4a7ac8f`，实际构建源码 `b06987d363c8d62976b491f7779df6bd5ab885a0`，正式部署 `2086f41c-5f7d-4ad4-b082-4505679ab7a9`。正式站和 ADV current 已读回该源码；2929 项线上精确字节核验、10项桌面/手机新稿可见检查及11项已验收UI回归通过。601份输入为361份JSON＋240份TXT/网页配对文件，599份需要改变字节。

3,054条目录及路由不变；全文搜索、256个JSON分片和610个正文源分包已从实际部署提交重新生成。27,406个打包源文件逐一解压比对通过。不要把目录文件字节未变理解为没有更新正文。游戏侧无需等待另一个Reader发布。

**游戏包并未由本窗口发布。** Reader上线不等于游戏数据已整合；游戏侧仍须按下面的独立客户端输入操作。`521110-9_xCcbB.json`的两仓图片结构不同，禁止从现网Reader抓取整份JSON替代客户端候选。

## 2. 唯一权威入口与固定内容身份

仓库：`HiiragiNemu/magireco-cn-patch`，既有`main`。累计贡献、完整已处理/待处理清单及历史快照只在此仓；不复制到Reader或ProgettoMagius-1。

- 当前运行指令：`docs/story-quality/client-integration/release-policy.json` 和本文件。
- 当前候选：`docs/story-quality/client-integration/READY.json`、`integration-manifest.json.gz`。
- 字节身份SHA-256：`f4db42783439dc15e2cb94cdcc10857c5e40c8d2e020b4004891bf9e5cc258a1`。
- 361个目标，359个真实变更，11,226条字段操作；另外2个目标本来已与候选相同。候选字节没有因为改成delta-only而改变。
- 只读新鲜度检查：`current_ready_gate.py`；来源检查/隔离生成/整合检查：`client_candidate_tools.py`。
- **新的包验收：`delta_only_guard.py`。旧`client_candidate_tools.py verify-packages`要求新delta等于完整Scenario，不适用于此次冻结Scenario的发布方式，不要调用旧入口验收本次新delta。** 它仍保留为历史模式，不应通过注释掉旧断言来冒充支持delta-only。

旧manifest中的共同发布描述属于冻结的历史说明，不重新改写校订字节清单；当前发布语义以`release-policy.json`为准。开始整合、构建及取得串行发布锁后，都须重新读取远端最新READY及发布政策。

## 3. 本次冻结的完整包基线

| 用途 | 版本 | SHA-256 |
| --- | ---: | --- |
| 完整 Scenario，仅作为既有基线保留 | 3323 | `f268c6e4791b778984db2de934f6bc5e0b0b155b217e198663ec3c34d64ffa6c` |
| 完整 JS，保持原文件 | 103 | `bffc1acc31f65c24cc2f9042a492e4f18c5ba9e41806ed725e1e0730c60a7a9d` |
| 本次接手时最新旧累计 delta | 22 | `7e4d58b2991f3da05d4faefa9f1cae90667cd27c5092a40b23d550dd35ba9df1` |

精确尺寸、MD5、版本及当前源引用保存在`delta-only-baseline-lock.json`；两条普通发布入口与实际既有ZIP已核对。接手时必须刷新公开状态，如果另一个窗口已推进delta，不得继续拿22当最新父代，应核对新父代并重新生成锁定记录。完整基线仍冻结，除非维护者另外授权基线迁移。

新安装或资源修复可以重新下载这两个**同一版本的现有完整基线**，再应用最新累计delta；不等于每次剧情更新都发布新Scenario。早于支持基线的客户端应先到达既定基线或明确阻断，不能默认一个只针对3323/103验收的delta兼容任意古老安装。

## 4. 累计delta内容：保留路径，不保留落后字节

对当前实际源和三个既有ZIP核算：新delta至少需要 **489个剧情载荷＋107个既有非剧情载荷＝596个载荷文件**，另外还有delta自身清单。489＝原128个补充剧情路径＋361个校订目标，包含2个无需改变字节但仍属于验收范围的目标。与冻结Scenario相比，当前361目标中359份确实改变了字节。

这些数字是本次快照，不是以后写死的上限。每次构建都必须取以下集合的并集：

1. 上一版累计delta已经携带的全部路径（包括非剧情修复）。
2. 当前明确纳入的校订目标和生产配置中已登记的补充剧情。
3. 最新受审Git源码相对冻结Scenario基线发生变化或新增的**所有剧情路径**，不能只从本次手填ID名单取材。
4. 最新产品源码相对完整JS103对应源提交的全部有效产品差异。

对集合中的每个文件读取**最新整合提交**的内容；旧delta/完整包只能当缓存，且只有缓存字节与该Git blob完全一致才允许复用。既有`build-cumulative-js-delta.py`已经对缓存实施Git blob匹配，不能改成“有旧文件就直接复用”。未支持删除/重命名迁移时必须报错，不得把从delta消失误当成客户端会删除旧文件。

本次已提供`delta-only-js-delta-baseline.proposed.json`以及`delta-only-plan.json.gz`。普通delta的`product()`不会自动包含scenario，必须保留并更新`configures/js-delta-baseline.json`的`supplemental_product_paths`。新验收器还会从完整Git剧情树对比固定Scenario，检查这个列表有没有遗漏，不再把人工列表当作唯一覆盖范围。

## 5. 现有自动发行脚本还须调整，不能直接触发

**当前生产`.github/workflows/publish-js-delta.yml`仍调用`tools/publish_coherent_resources.py`，会重建/发布完整Scenario；尚不是delta-only。** 本窗口没有改动客户端生产发布代码，也没有启动该工作流。

客户端发布窗口应先在既有main补上明确的delta-only发布路径，再整合正文并执行发行。必须保留原串行锁、两仓latest身份复查、防版本回退、事务日志及失败恢复；源修改提交应带`[skip ci]`，或先以受测试的delta-only流程替换旧触发逻辑，防止合入剧情时旧push触发器提前重打Scenario。不要全局关闭工作流，也不要使用已停用的逐编号scenario发行器。

调整要点：固定读取现有Scenario3323、完整JS103及最新父代delta；只构建新累计delta与它的版本/内容清单。可在隔离构建目录生成差分计算用临时`target.zip`，但不得把它上传成新完整JS，不新建/覆盖Scenario发行资产。仅更新`cn_js_delta.zip`、`version_js_delta.json`、`cn_js_delta_manifest.json`及确实引用新delta的汇总清单；完整Scenario/JS文件、版本号、哈希和未变附件均保持原身份，不为“刷新日期”重传。

旧`resource_layers`把全部重叠剧情要求等于完整Scenario。冻结基线后，**新delta与旧Scenario不同是合法且必要的**。应将判断改为“固定基线＋新delta的最终文件必须等于最新权威源”，不能只删掉一致性检查。基线来源、delta来源和最终安装期望是不同身份，不得把旧Scenario清单伪标成新Git提交。

新工具对14,340个最终权威路径建立核验：14,233个剧情文件及107个有效非剧情覆盖路径。其余完整JS独有文件由固定完整包SHA和严格的delta成员源身份约束保全。

## 6. 可执行接入及验收顺序

先更新CN patch main，保留本地未提交和并行修复，不建分支、PR或强推。PowerShell示例：

```powershell
$CN = $PWD.Path
$K = Join-Path $CN 'docs/story-quality/client-integration'
$R = Get-Content (Join-Path $K 'READY.json') -Raw | ConvertFrom-Json
$M = Join-Path $K 'integration-manifest.json.gz'
python (Join-Path $K 'current_ready_gate.py') --repo $CN --manifest $M --manifest-sha256 $R.manifest_sha256
python (Join-Path $K 'client_candidate_tools.py') --manifest $M --manifest-sha256 $R.manifest_sha256 check-source --repo $CN --ref HEAD
python (Join-Path $K 'client_candidate_tools.py') --manifest $M --manifest-sha256 $R.manifest_sha256 stage --repo $CN --ref HEAD --output 'D:\magia\deliveries\client-final-story-delta-inputs'
```

输出目录必须尚不存在且位于Git工作树之外。按逐字段版本核验把剧情输入与补充路径配置合入同一个受审提交；第三种源版本必须先合并并行修改，不能整文件强盖。

```powershell
python (Join-Path $K 'client_candidate_tools.py') --manifest $M --manifest-sha256 $R.manifest_sha256 check-integrated --repo $CN --ref HEAD
```

这只验证目标和原始补充列表，随后要用delta-only全源计划检查自动发现的额外差异。下面三个既有ZIP必须先按锁定记录和实时发布入口核实；路径按实际下载位置替换：

```powershell
$Common = @('--manifest', $M, '--manifest-sha256', $R.manifest_sha256,
  '--repo', $CN, '--ref', (git rev-parse HEAD),
  '--baseline-lock', (Join-Path $K 'delta-only-baseline-lock.json'),
  '--scenario', 'D:\packages\cn_scenario_update.zip',
  '--full-js', 'D:\packages\cn_js_update.zip',
  '--previous-delta', 'D:\packages\previous\cn_js_delta.zip')
python (Join-Path $K 'delta_only_guard.py') @Common plan --out 'D:\magia\deliveries\delta-final-plan.json.gz'
```

`plan`本身不会整合或发包。若新计划要求补充路径，先完善生产配置、重新固定提交并重新计划。`production_ready=false`不可当作可发布。本窗口保存的计划因游戏源尚未整合而明确为false。

由已经适配的delta-only构建流程生成新ZIP及两个JSON，版本按实时父代递增，不抢占固定数字。随后：

```powershell
python (Join-Path $K 'delta_only_guard.py') @Common verify `
  --new-delta 'D:\packages\new\cn_js_delta.zip' `
  --version-json 'D:\packages\new\version_js_delta.json' `
  --manifest-json 'D:\packages\new\cn_js_delta_manifest.json'
```

该检查要求目标已经实际合入、生产列表完整、未发生相关源码漂移；检查每个delta成员的当前Git身份、包内/外清单及版本文件、冻结基线、全部旧载荷路径，以及最终覆盖和最新delta重放结果。两个完整包作为只读基线传入，**不是要求重新生产它们**。

21项独立合成反例测试通过；还基于实际旧ZIP目录在内存中模拟“只加版本号”和“路径都齐全但仍放旧正文”，两种情况均被明确拒绝。未生成游戏新包，这些验证不替代下一窗口的真实ZIP和设备测试。

## 7. 安装/缓存回退必须在客户端闭合

仅让服务端新ZIP正确还不够。最低验收集：普通安装只更新delta；跨过中间若干delta后直接安装最新版；新装/完整基线修复后再应用最新版delta；离线导入；手动重下；中途失败恢复。

已安装更高delta版本后，旧缓存21/22不得再次覆盖文件。缓存必须同时绑定版本、包哈希和受支持基线；旧版本、相同版本不同哈希、来自其他基线的缓存都必须拒绝或重新获取。每次重装完整基线后，最后重放当前已验证累计delta。不要让后台异步任务在新delta完成之后再次写入旧包。

下载、校验、暂存、切换和已安装版本记录应是同一事务：全部文件写入并核验后才更新版本偏好；失败不得先标新版本。包里旧路径对应新字节逐项读取验证，不能只查界面显示的版本号。

客户端窗口应在实际受测设备读回本次361目标、原128剧情覆盖路径及107非剧情修复的最终文件哈希，并保留所有差异/失败记录。条件允许时沿用先前全量16,729路径设备核验，不能把静态ZIP重放说成已经实机成功。

## 8. 发行回执和贡献分账

更新两仓latest、Cloudflare普通入口与汇总元数据之后，再次核对：新delta文件与版本/清单同一身份；Scenario3323与JS103仍为上述原文件；实际安装后的新稿等于客户端候选。回执保存到CN patch的`docs/story-quality/client-integration/CLIENT_RECEIPT.json`或同目录明确关联文件，至少包含：

- 当前内容manifest SHA及本次`release-policy.json` SHA；实际整合/构建提交。
- 新delta版本、SHA-256、尺寸、包内/外清单和普通入口读回结果。
- 未变Scenario/完整JS的版本与SHA，完整基线并未再次发行的证明。
- 旧路径全部保留且内容刷新、14,340路径最终静态覆盖结果、实际设备/缓存/离线/重下验收边界。

Reader交付状态已经单列。原694已发布复核记录、旧498剧情ID、接手前贡献和361目标的校订/复用区别均保留；新游戏delta实际验收完成前，不把这361个游戏待交付目标结算为已发布，不重算翻译贡献。
