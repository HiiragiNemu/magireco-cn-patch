# 当前接入版本：第16批残余复查后候选

候选目标仍是361，字段已由10312增加到10402；30个既有候选追加90处机翻纠正，新增完整剧情数为0。前10312条操作的地址、原文、修订值逐项保留。不要因目标数量相同继续使用旧包。当前manifest SHA256 `c05ab3b7383178945fa045d9b3cd0709e4f8cf96e59e1b97f1c3cc9ff5625a72`；上一版`5ee54cc0da1ac2681219affd5366517fced58cfdd1606fc34155f694b90e5207`及配套材料保存在history/下，不得混用。

## 新增必查：远端最新READY

整合/构建之前，以及客户端的串行发布事务开始前，先刷新CN patch main，运行：

```powershell
$kit = Join-Path $PWD 'docs/story-quality/client-integration'
$ready = Get-Content (Join-Path $kit 'READY.json') -Raw | ConvertFrom-Json
python (Join-Path $kit 'current_ready_gate.py') --repo $PWD --manifest (Join-Path $kit 'integration-manifest.json.gz') --manifest-sha256 $ready.manifest_sha256
```

该检查实际读取origin当前main引用，再读取该提交的READY，而不是只相信本地旧文件。即使旧稿与新稿都是361目标，只要SHA已经被替代就拒绝。远端在核验中移动、最新提交本地不可读时也停止，要求刷新；不会自动抓取、改工作树、降低权限检查或发包。它仅验证新鲜度，不能替代check-source、check-integrated、真实ZIP和设备最终文件核验；最终发布仍由客户端既有串行锁/事务保证，不能把一次只读检查说成永久无竞争。

原补充路径128＋361目标＝489，生产配置仍未写入。Reader导出也有新候选，但未部署，权威累计导出文档在第16批的cumulative-reader-exports.json.gz，仅CN patch留存。

以下是沿用的集成步骤（数字已更新；历史背景不作为本轮已发布声明）：

# 客户端统一资源接入：第11—15批361目标

当前READY.json固定361个未发布目标、10402个显示字段操作，其中359文件有字节更改、2个本来已相同。278个目标为新增全文复核，83个为已有审订稿精确复用。运行资源尚未整合。本目录不是发包许可，不代表实际包或设备已经包含新稿。

## 先固定最新清单

本次在旧335个目标上追加26个，旧335条候选、逐字段操作及来源完全未变。旧清单/工具的不可变快照由READY的immutable_previous_snapshot指明。开始整合以及正式构建前，均须读回最新READY并固定manifest_sha256；不要在执行期间自动混用另一个版本的清单。旧回执只能证明它固定的旧范围。

历史“剩余50”中另有23个已恢复人译和1个先前完成的全文复核，均不属于新增26，不得按AI机翻重译。历史发布账保持不变，来源豁免见第15批authority-exclusions.json。零待校订只指冻结历史范围，不是发布完成。

## 必须保留客户端自己的图像和控制

521110-9_xCcbB在Reader与客户端包含不同的两处既有漫画内嵌图片。本清单中的该候选从客户端自己的原始字节构造，只修1个fallback正文，原图完全保留。不要从Reader复制整份JSON到客户端。其Reader前后blob以reader_identity_not_for_client_overwrite标注；累计台账的repository-baseline-overrides.json也保存双方身份。

## 读取和隔离准备

在已更新的CN patch工作树中运行：

```powershell
$kit = Join-Path $PWD 'docs/story-quality/client-integration'
$ready = Get-Content (Join-Path $kit 'READY.json') -Raw | ConvertFrom-Json
$tool = Join-Path $kit 'client_candidate_tools.py'
$manifest = Join-Path $kit 'integration-manifest.json.gz'
python $tool --manifest $manifest --manifest-sha256 $ready.manifest_sha256 check-source --repo $PWD --ref HEAD
```

check-source成功只表示可安全构造候选。当前359项仍为staged_only；2个原文字节已相同而显示already_integrated，不能把它们当作新稿已经上线。

准备候选时，输出目录必须尚不存在，并且位于任何Git工作树之外：

```powershell
python $tool --manifest $manifest --manifest-sha256 $ready.manifest_sha256 stage --repo $PWD --ref HEAD --output 'D:\magia\deliveries\client-story-candidates-batch11-15'
```

这只在隔离目录写入361份候选、一份delta配置提案和预检结果，不直接改工作树。遇到源blob第三版本、历史守卫变化或JS完整基线改变，须先协调重审，不能整文件强盖。

## 正文和delta选择列表一起整合

普通product()筛选不自动收录scenario。必须保留configures/js-delta-baseline.json原128个supplemental_product_paths并加入361目标，共489。提案只位于本目录，生产配置未被本窗口修改。

由客户端在同一个受审main提交中合入候选和补充列表，随后检查这个确定提交：

```powershell
python $tool --manifest $manifest --manifest-sha256 $ready.manifest_sha256 check-integrated --repo $PWD --ref HEAD
```

仅有隔离文件、正文未合并或漏更新补充列表都会失败。通过后才按维护者授权使用.github/workflows/publish-js-delta.yml的统一资源流程，从同一已整合源共同构建完整Scenario与累计JS delta。版本、并发事务、APK实播/发布确认等客户端现行门槛全部保留；不要运行旧逐编号Scenario发布器。

## 真实包及最终覆盖验收

```powershell
python $tool --manifest $manifest --manifest-sha256 $ready.manifest_sha256 verify-packages --scenario 'D:\path\cn_scenario_update.zip' --delta 'D:\path\cn_js_delta.zip' --full-js 'D:\path\cn_js_update.zip' --base 'D:\path\cn_base_01_json.zip'
```

所有361目标须同时进入Scenario和delta且SHA一致。原delta成员不丢失，任一旧delta/完整JS后装回退正文都会失败。历史及新识别的人译保全路径以当前客户端权威源码为准，不从旧包倒灌。重复ZIP条目、路径穿越和缺少成员也会拒绝。

以上是静态ZIP重放检查，不等同实际CNHotUpdateTx/CNJsDelta、普通更新、全新安装、缓存重放、离线导入、手动重下和设备最终字节读回。正式交付须同时核验两仓latest、Cloudflare传输、version/manifest和实际下载/安装哈希。

请在本目录留下CLIENT_RECEIPT.json或独立回执，明确当前manifest SHA、整合main提交、Scenario/delta版本及包哈希、配套元数据和已覆盖的真实设备/安装路径。未收到回执前仍是未发布分账。Reader整合与部署另行核验，不能由客户端发包成功推断。

接入工具通过28项反例测试，361个真实当前源及全部保全守卫已只读预检；新资源包和实际安装尚未由本窗口构建或验证。
