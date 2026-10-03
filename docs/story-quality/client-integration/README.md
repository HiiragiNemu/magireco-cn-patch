# 客户端统一发布：第17批后的最新候选接入

本窗口没有写运行资源、发包、触发同步或部署。当前361个目标、11226个显示字段操作，包含第11—17批已验证成果；本批在235个既有目标追加824处残余纠错，不增加全文复核篇数。此前10402条操作逐项保留。当前manifest SHA-256：`f4db42783439dc15e2cb94cdcc10857c5e40c8d2e020b4004891bf9e5cc258a1`。

旧manifest `c05ab3b7383178945fa045d9b3cd0709e4f8cf96e59e1b97f1c3cc9ff5625a72` 及其361目标快照按原SHA保存在history/。不能因数量同为361就继续用旧稿或旧验收回执；本批新增的是候选内容版本，不是新剧情路径。

## 固定最新版本再整合

在客户端CN patch工作树先正常刷新origin/main，再读取本目录READY。先执行current_ready_gate.py检查远端当前main的READY与实际本地manifest是否一致；它不会把旧本地READY当成最新，也不会改文件或发包。示例：

```powershell
$kit = Join-Path $PWD 'docs/story-quality/client-integration'
$ready = Get-Content (Join-Path $kit 'READY.json') -Raw | ConvertFrom-Json
$manifest = Join-Path $kit 'integration-manifest.json.gz'
python (Join-Path $kit 'current_ready_gate.py') --repo $PWD --manifest $manifest --manifest-sha256 $ready.manifest_sha256
python (Join-Path $kit 'client_candidate_tools.py') --manifest $manifest --manifest-sha256 $ready.manifest_sha256 check-source --repo $PWD --ref HEAD
```

需要准备文件时，用同一工具的stage命令，输出必须是Git工作树外尚不存在的新目录。它只构造隔离候选，不合并、不提交、不推送：

```powershell
python (Join-Path $kit 'client_candidate_tools.py') --manifest $manifest --manifest-sha256 $ready.manifest_sha256 stage --repo $PWD --ref HEAD --output 'D:\magia\deliveries\client-story-candidates-through-batch17'
```

全部目标绑定各自客户端原始blob及SHA，521110-9仍保留Reader/客户端原有图片差异，不能复制Reader整文件替代客户端候选。遇到源的第三种版本时停止并逐字段协调。2个already_integrated状态是原文本来已相同，不代表其余359份候选已经合入。

## Scenario和累计JS delta必须同时接入

普通delta的product()不自动选scenario，补充选择提案保留原128项再加361目标，共489项。生产configures/js-delta-baseline.json没有被本窗口改动。客户端须在同一个受审main提交中合入正文与补充路径列表；不得丢弃旧项或从旧delta还原过时剧情。完整JS103本体无需因为本批文本而重制。

整合提交后，再次确认远端最新READY，并执行：

```powershell
python (Join-Path $kit 'client_candidate_tools.py') --manifest $manifest --manifest-sha256 $ready.manifest_sha256 check-integrated --repo $PWD --ref HEAD
```

check-source仅证明可以准备；check-integrated才要求所有候选已合入且delta列表完整。通过后由已有.github/workflows/publish-js-delta.yml统一流程从同一提交构建Scenario和累计JS delta，保留客户端串行发布事务、防回退及元数据身份核验。一次只读新鲜度检查不替代发布锁；开始实际发布事务前还须复核当前清单SHA。

## 验证实际包和设备

工具verify-packages需要真实Scenario、delta、完整JS包，基础包用--base逐个加入。必须检查所有361目标在两个包中均等于当前候选、1125条既有源码保全路径、全部剧情交叠条目，以及Scenario/JS/delta安装和缓存delta重放的最终字节。新版本号里面装旧字节会失败。

本次真实旧源码和留存旧包被拒绝，仅证明它们不含最新候选；没有构建新游戏包，也没有完成新包设备验收。客户端须测试适用的正常更新、全新安装、缓存重放、离线导入、手动重下与设备最终文件，留下带当前manifest SHA、整合提交、Scenario/delta版本与SHA、元数据及设备证据的CLIENT_RECEIPT。

Reader运行源和部署仍是独立未完成交付。累计Reader TXT候选在第17批cumulative-reader-exports.json.gz，仅CN patch存储，不从旧批单份TXT覆盖后续修改。全部累计贡献和已处理/待处理台账仍仅CN patch；历史原译者署名不重新归功。
