# 游戏窗口接手指令：只更新累计JS delta

Reader已正式采用最终校订稿，构建源码`b06987d363c8d62976b491f7779df6bd5ab885a0`、部署`2086f41c-5f7d-4ad4-b082-4505679ab7a9`；无需再等待Reader上线，也不要从Reader抓取JSON替代客户端稿。

请实际接手`HiiragiNemu/magireco-cn-patch`既有main，先读`docs/story-quality/client-integration/DELTA_ONLY_HANDOFF.md`、`release-policy.json`和实时`READY.json`。固定内容manifest SHA-256：`f4db42783439dc15e2cb94cdcc10857c5e40c8d2e020b4004891bf9e5cc258a1`。361个目标/11,226条字段操作已经校订，359个有实际字节变化。按当前源逐字段合入，保留521110-9的客户端专用图片结构、人工保护及所有并行修改。

维护者要求以后游戏只更新**累计JS delta**。完整Scenario3323与完整JS103保持现有文件/版本/哈希，不共同重发。现有`publish-js-delta.yml`仍通向共同发布器，先在main适配并验证delta-only流程及客户端回退保护，再触发生产。不要直接运行旧共同发行或已停用的编号Scenario发行器。

累计delta必须保留旧修复路径并用最新同一Git提交的内容刷新，纳入新校订目标以及全部相对固定基础包变化的剧情。初步489剧情＋107非剧情＝596个载荷；保留原128补充剧情并扩展，不能仅加入新文件而留着delta内同名落后剧情。运行新鲜度/已整合检查，以及`delta_only_guard.py`全源计划和真实ZIP验收；新delta与旧Scenario不同是必要的，验收标准是基础包＋新delta最终等于最新权威源。

必须实测普通delta更新、跳版本更新、固定基础包重装后重放最新delta、离线导入、手动重下、安装中断。旧缓存21/22不能在新delta后回写；拒绝旧版本、同版本不同哈希和错误基线，安装全程串行/事务化，所有文件验证成功后才更新偏好中的版本。静态ZIP模拟不能冒称设备成功。

发包前重新获取两仓latest/Cloudflare身份和父代delta版本，遵循当前串行锁及防回退检查；仅更新新累计delta及真实引用它的元数据，所有不变完整包和无关附件保持。验收后在CN patch留下带当前manifest和政策SHA的CLIENT_RECEIPT，包含整合/构建提交、新delta版本/哈希、入口读回、基线未变证据和设备最终字节检查。不得将Reader上线或材料就绪当作游戏已发布。全部贡献和完整清单仅CN patch，不复制到Reader或公开发行仓。无分支、无PR、无强推，不清理未知本地改动。
