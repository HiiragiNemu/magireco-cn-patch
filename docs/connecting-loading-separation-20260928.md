# Connecting 与原生加载提示分离

用户已撤销全局替换 Connecting 的要求。2026-09-28 反馈确认，v20 仍携带
2026-09-26 恢复的奔跑 APNG。旧测试还强制要求该 APNG，导致撤销没有进入发布包。

- 只恢复 Web `magica/resource/image_web/common/global/connecting.png` 为历史
  `19af55f8` 的国服原图，5466 字节，334×54，显示 `Connecting…`。
- 原生 `assets/package/loading/` 的中文“数据加载中”及丘比动画保持不变。
- 不改 JS、CSS、原生加载分支、字幕、角色名称、音乐或字体。
- 累计补充包仍携带该路径，即使等同某个基础包也要覆盖旧 v20 的奔跑图。
- `test-running-connecting.py` 保留旧文件名以复用现有工作流入口，测试内容
  改为检查两种加载提示分离，拒绝再次用奔跑 APNG 替换 Web Connecting。
- 本地与包校验不代替用户实际画面验收。
