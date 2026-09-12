# 个人 main 自动更新

只发布 main，不创建 PR，也不进行分支发布。个人 main 的运行资源变更触发既有双包构建与事务式 Release 转正；组织镜像独立执行，R2/EdgeOne/ESA 不再阻塞个人发布。

JS 范围为 WebView 运行文件、公告/活动 JSON、引擎翻译表以及完整清单约束的 image_native；明确排除 memoria。Scenario 只收剧情 JSON，保持 JP/CN 结构修复，不夹带引擎表。所有已存在的校验仍保留；资源成员字节未变化时复用正式 ZIP，避免仅因压缩时间戳升级。

发布成功后回写七个最终资产指纹；个人 Pages 入口实时读取 personal main 配置和 latest Release，并由后续任务对七个实际 HTTP 文件全文校验。main 的自动发布和手动发布共用串行锁。手动默认仍是预览，正式发布须 publish_hotfix=true。

旧 api.magireco.top 的部署仍属旧服务控制面，仅更新配置仓库不代表域名已经生效。新原生客户端仍须完成源码签名、APK 构建和验证后再提升版本门槛。
