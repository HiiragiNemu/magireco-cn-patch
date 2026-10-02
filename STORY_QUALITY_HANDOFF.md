# 剧情质量固定接手入口

## 2026-10-02 资源发布入口更正（优先于下方历史批次说明）

实际线上已推进至 Scenario 3322，但旧 JS delta 21 会在最后安装/缓存重放时覆盖四份后续修订，另有124份早期有效补充尚未合入完整剧情包。不要再次调用公开资源仓的编号 Scenario 发布器，也不要直接删除补充包中的剧情文件。

后续校订依旧提交本仓 main；运行资源统一使用本仓 Actions **“统一资源包发布”**（`.github/workflows/publish-js-delta.yml`），从同一提交构建 Scenario 与累计 delta，并同步两仓已有 latest。入口、反例、保持事项和真实发布回执见 `docs/RESOURCE_PUBLICATION.md`。尚未取得实际发布成功回执时，不得把候选版本写成已交付。累计贡献、全部已处理/待处理台账继续仅在本仓原位置维护；不改 Reader 或 L2D。

下方3311记录为历史，不能再作为当前下载版本或发布方式使用。


最新维护者译名：**海异光小阿鲁**。アマビエ小阿鲁／此前阿玛比埃小阿鲁均映射为该名称；原始日文和历史记录不重写。

当前运行源码 `ac2d4ece37f3ca5377df47f7dceffa0c9c47ce95` 已交付 **3311**。2026-09-30T13:34:06Z公开工作流36722423893完成固定归档和latest的完整匿名校验。包193597583字节，SHA256 b0a1d47d61c883dc0a25f83d6aa134c697fbc189dfb5e52de3b7bd7efced9fe6，MD5 36982a0946fdd3c388966e7585d67af6。回执在ProgettoMagius-1/story-quality/releases/3311.json。12个目标运行文件、14221个其他文件不变；43份已验收V4稿不变。

Reader实质修订 `54af872e57c79443b22f5a5c4b6c41bbb5935c72` 已入main。本断点Reader正在独立目录构建包含该修订的新版本，**尚未把这批网站和ADV登记写成完成**；此前正式站仍为149208c9/3b9549f2。后续状态以Reader根STORY_QUALITY_HANDOFF.md及docs/story-quality/CONTINUATION_STATE.json中的现场验收为准，不凭文档提交推断上线。

本批已解决原25控制候选中的17项，余8项/5文件登记于Reader的remaining-control-work.json。四节Another Daze采用固定日文执行布局与逐条核对中文，229个发言复核、58处源义校正、171条旧中文载荷复用；不要重新运行旧3310发布器，也不要再发同内容3312。

每个中途断点和每轮都更新接手文件；只main、无新分支/PR/强推，保留中文颜色、exp兼容及43份已验收V4，不改L2D/AIO或原开发工作树。当前恢复目录D:\magia\deliveries\reader-production-20260930-1226\haiyiguang-20260930；progress.json记录本批实际状态，checkpoint.py为本批新入口，禁止运行旧的硬编码3310 checkpoint主函数覆盖新状态。
