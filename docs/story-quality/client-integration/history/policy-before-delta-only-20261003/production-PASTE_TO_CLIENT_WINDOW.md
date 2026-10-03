# 发给客户端资源发布窗口的接续内容

请从 `HiiragiNemu/magireco-cn-patch` 最新main读取：

- `docs/story-quality/production-handoff/README.md`、`READY.json`
- `docs/story-quality/client-integration/READY.json`

已确认AI校订待办为0；361个已验证目标等待正式整合/发行，最新客户端manifest SHA256是 `f4db42783439dc15e2cb94cdcc10857c5e40c8d2e020b4004891bf9e5cc258a1`，11,226条字段操作。生产交付提交`d8c3e6a1106e67e8854e5346b3486fdfa883fd56`。目标数量相同不能代替manifest新鲜度检查。

不要从现网Reader下载正文来发包：线上Reader仍是15d2ee95/f271c901旧稿。游戏侧直接使用CN patch的客户端manifest，保留128旧delta补充路径并纳入361目标，共489。先current_ready_gate，再check-source/stage；把正文和补充路径表合入同一个受审main，check-integrated通过后，用既有统一发布流程共同构建完整Scenario与累计JS delta。不能只发delta或只发Scenario，也不要用旧编号发布器。

对实际版本/manifest/ZIP/交叠文件以及正常安装、缓存delta重放、离线导入、手动重下的最终文件进行核验；完成后在CN patch留包含当前manifest SHA、实际整合提交、配套版本及包SHA的CLIENT_RECEIPT。已修复的资源链规则继续保留。

Reader另有601个独立输入及经过实际生成/校验的目录、全文搜索、语音/来源清单、JSON分片/分包；入口在production-handoff。本地隔离产物不是已发布Reader。游戏侧不依赖Reader先上线，且521110-9的两仓原图片不同，禁止跨仓整文件覆盖。Reader的整合/完整应用构建/部署/ADV登记须独立完成。累计贡献和完整台账只在CN patch，保留全部接手前成果。
