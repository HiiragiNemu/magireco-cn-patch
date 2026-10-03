# Reader正式新稿与游戏delta-only接手：中断恢复终检

核验时间：2026-10-03T06:15:45.209057+00:00。本次恢复不重新部署Reader，也不构建或发布游戏包。

## Reader已经完成

正式源码`b06987d363c8d62976b491f7779df6bd5ab885a0`，部署`2086f41c-5f7d-4ad4-b082-4505679ab7a9`。已重新检查当前main中的601份输入，全部等于最终校订候选；其中361份JSON、240份TXT/网页配对文件。主域名构建信息、ADV current、校对配置三个入口均指向该构建源。

恢复后重新请求全部新稿普通接口及别名、网页正文、目录分片和搜索产物，共888项，888通过、0失败，1项使用重试。不是只看部署版本号。原2,929项全量验收结果逐条与原始预期哈希核对，并完整保留；原生产构建、测试和浏览器记录仍归属于那次固定源码，不冒称在本次重复运行。

## 游戏仍须完成的工作

现网仍是Scenario3323、完整JS103、累计JS delta22。361个客户端目标中359个需要改字节的文件仍未合入，2个原本无需改字节；没有新CLIENT_RECEIPT。Reader上线不能结算游戏待发稿。当前确认AI首次校订和已列残余复查均已闭合，游戏侧待交付仍为361个。

必须使用CN patch当前`docs/story-quality/client-integration/READY.json`、`release-policy.json`、`DELTA_ONLY_HANDOFF.md`。内容manifest `f4db42783439dc15e2cb94cdcc10857c5e40c8d2e020b4004891bf9e5cc258a1`；政策SHA `21b682d4ddf813901063608e6b88401677ad772a0eea2c44b428fe3183dad896`。

新的发布方式只有累计JS delta，固定现有Scenario3323和JS103。现有生产工作流还会共同重建完整Scenario，必须先实现delta-only路径，不能直接触发旧流程。源码整合、构建、两仓/Cloudflare发布和设备验收由游戏窗口完成；本次没有修改对方工作流或客户端代码。

累计路径需包含旧delta全部有效修复、新校订目标、当前权威剧情相对固定基础包的全部差异和新增，以及完整JS基线之后的有效产品差异。每个载荷都取同一个最新受审Git提交的字节，不能保留旧delta中对应文件的旧内容。本次快照至少489剧情＋107非剧情＝596载荷，数字不是未来上限。旧路径应保留，落后字节应替换。

包验收使用`delta_only_guard.py`：允许新delta有意覆盖固定Scenario，但最终基础包＋最新delta必须等于权威源；不能使用要求delta字节等于旧Scenario的旧验收入口。已从当前远端取回工具并校验哈希，重新运行21项反例测试，全部通过。静态反例验证不等于客户端已经实现缓存阻断或设备已验收。

**旧缓存重放、离线导入、手动重下和异步安装的防回退仍必须在客户端生产实现并实测。** 比较版本、包哈希与固定基线；拒绝旧版本、同版本异哈希、错误基线；同一资源安装事务串行；完整基线重装后最后应用当前最新累计delta；全部最终文件验证成功后才记录新版本。不能只以界面显示版本或下载成功作为验收。

全部贡献、完整清单和恢复材料只留CN patch。原工作树状态和21份贡献记录已验证保全。未知来源/确认人工稿未重新翻译。

正式接手文档：`docs/story-quality/client-integration/DELTA_ONLY_HANDOFF.md`。
一段式交接：`docs/story-quality/client-integration/PASTE_TO_GAME_WINDOW.md`。
本次原始复验：`docs/story-quality/reader-final-20261003/resume-verification.json`和`resume-live-recheck.json.gz`。
