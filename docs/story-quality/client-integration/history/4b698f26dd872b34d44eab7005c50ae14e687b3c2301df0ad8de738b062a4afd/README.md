# 客户端统一资源发布：三批校订候选接入入口

本目录属于 CN patch 的唯一交接材料。当前 `READY.json` 固定第11、12、13批共255个已验证目标、7447个显示字段更改。其中254个文件实际有改动，1个同源复用目标本来就与审订稿相同。172个目标为新全文校订，83个为已有审订稿精确复用。**均尚未写入生产剧情路径，不能把3323/22当作已经包含它们。**

本窗口不发包、不操作发布工作流、不改客户端代码。此工具只做读取、在新隔离目录准备候选和核验ZIP，不能Git提交、推送、发Release或部署。是否整合、发包由维护者及客户端侧窗口按最新资源审计回执决定。

## 为什么必须同时接入 delta

当前 `tools/build-cumulative-js-delta.py` 的 `product()` 不包含 scenario。剧情依赖 `configures/js-delta-baseline.json` 的 `supplemental_product_paths` 显式纳入。只把修订写入剧情源码然后执行统一工作流，不能保证新路径自动进入 delta。

本次提案完整保留原128个补充剧情路径，并追加255个新目标，总计383个。`js-delta-baseline.proposed.json` **只是一份文档中的提案，生产配置尚未改动**。不要删除原列表，不要拿旧 delta 的剧情覆盖新稿，也不要只上传 delta 而让完整 Scenario 留在旧字节。

正确接续是：检查最新版源码→精确合并候选→保留旧项并扩展补充列表→固定同一个 main 提交→由现有统一资源流程共同构建/发布 Scenario 与累计 delta→验证两仓及所有适用安装路径的最终字节。不要运行旧逐编号 scenario 发布器。

## 来源校验与隔离准备

在已经更新的 CN patch 工作树中运行（PowerShell）：

```powershell
$kit = Join-Path $PWD 'docs/story-quality/client-integration'
$ready = Get-Content (Join-Path $kit 'READY.json') -Raw | ConvertFrom-Json
$tool = Join-Path $kit 'client_candidate_tools.py'
$manifest = Join-Path $kit 'integration-manifest.json.gz'
python $tool --manifest $manifest --manifest-sha256 $ready.manifest_sha256 check-source --repo $PWD --ref HEAD
```

`check-source` 成功仅代表可以安全准备，不代表候选已合入。输出 `staged_only` 的254个路径仍是旧源码；原样复用的1个路径会显示 `already_integrated`，不应因此重复计功。

需要准备文件时，输出目录必须是尚不存在、且不位于Git工作树内的新目录：

```powershell
python $tool --manifest $manifest --manifest-sha256 $ready.manifest_sha256 stage --repo $PWD --ref HEAD --output 'D:\magia\deliveries\client-story-candidates-batch11-13'
```

该命令在隔离目录生成255份源版本锁定的剧情候选、一份保留全部既有配置字段的delta选择提案和 `INTEGRATION_PREFLIGHT.json`。不直接改工作树。客户端窗口再对照清单，按既有main提交纪律合并到自己的工作树；不得复制整个历史工作树覆盖并行修复。

所有目标均绑定旧/新Git blob、SHA-256、中日源版本及逐字段操作。发现第三种源码版本时会阻断，必须先对照并行修改重新合并，不能整文件强行覆盖。基线不变时允许幂等检查；后来追加的补充路径会被保留，但移除旧补充路径或更换JS完整基线必须重新审计。

## 构建前必须检查已整合，而不只是“可整合”

客户端提交合并后的实际main后：

```powershell
python $tool --manifest $manifest --manifest-sha256 $ready.manifest_sha256 check-integrated --repo $PWD --ref HEAD
```

此命令要求所有255目标已经等于候选，并且生产 `supplemental_product_paths` 已包含这些路径。若只准备了文件但没有合并，或只合并正文却忘了delta选择列表，检查会失败。成功后才交给 `.github/workflows/publish-js-delta.yml`（“统一资源包发布”），Scenario 与 delta 必须由这一个固定提交构建。版本号、事务门槛、两仓身份复查和串行锁继续由客户端现有工具负责，本材料不绕过它们。

## 检查实际包：版本号新不等于内容新

客户端构建后，向此工具提供真实完整包和完整JS；所有会参加安装的基础包可重复传入 `--base`：

```powershell
python $tool --manifest $manifest --manifest-sha256 $ready.manifest_sha256 verify-packages --scenario 'D:\path\cn_scenario_update.zip' --delta 'D:\path\cn_js_delta.zip' --full-js 'D:\path\cn_js_update.zip' --base 'D:\path\cn_base_01_json.zip'
```

核验要求：

1. 255个新目标必须同时存在于完整Scenario与累计delta，并与已审稿SHA-256一致。即使delta版本号比以前大，只要里面是旧字节仍然拒绝。
2. delta和完整JS内**所有**剧情重叠路径都必须与完整Scenario相同；原128个delta剧情路径不能丢失。
3. 为981个历史已发布修订路径和原补充路径保存的1105个当前权威源码守卫继续有效。它们来自当前CN patch源码，不从旧3322包取回较旧文本。
4. 按基础包→Scenario→完整JS→delta，以及重装后再次重放delta的顺序检查最终字节。重复ZIP条目、危险路径、漏收新稿、旧delta/完整JS撤回新稿均会阻断。

这是静态ZIP覆盖校验，不代替客户端的实际 `CNHotUpdateTx` / `CNJsDelta` 执行及设备读回。正式交付仍需覆盖普通更新、全新安装、缓存补充包重放、离线导入和手动重下，并按现有统一发布流程（详见 `docs/RESOURCE_PUBLICATION.md`）验证两仓latest、Cloudflare、version/manifest、下载字节与安装字节。**本窗口没有用这些新候选生成真实资源包，也没有声称这次的新稿已经实机验收。**

## 回执和后续批次

请客户端窗口把实际整合提交、两个新版本及包SHA-256、配套元数据和最终设备/安装核验写到本目录的 `CLIENT_RECEIPT.json` 或独立回执文档，并明确包含本次 `manifest_sha256`。在回执入库前，未发布总账仍不转换为已发布。不要手工把校订计数直接加到游戏“人工翻译”署名中。

第11/12/13批的逐篇台账和恢复材料仍只在 CN patch 的 `docs/story-quality/contributions/`、`docs/story-quality/unreleased/`。Reader暂未更新运行源，后续Reader整合和部署须作为独立交付状态核验；不能因玩家包发布成功就宣称Reader也已上线。

本工具通过28项合成反例测试，真实当前源码255目标及历史守卫已只读预检。测试中发现的ZIP异常分支未关闭句柄问题已经修正，首次失败日志仍在本批恢复证据里；没有放宽覆盖断言。
