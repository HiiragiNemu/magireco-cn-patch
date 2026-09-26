# 合成素材图补发（2026-09-26）

用户已明确确认 `compose_item_xxx_b.png` 是过去仅在本地存在、需要进入新发布包的修复。

- 运行路径：`madomagi/resource/image_native/item/compose_item_xxx_b.png`。
- 采用已确认的原有文件，未生成或重绘图像。
- 原公开基础包版本 SHA256：`f9b4204fc3f73e1c0114baefffff0166a3f10cb3ac4ca303a76505448fe96162`。
- 已确认修复版本 SHA256：`a5ea45b39484a2a0aa3e36b5a47a2f3485877fa6bffc20bf490162cb8d08c481`。
- 加入公开累计补充包，不要求重新下载 APK，不以本地设备注入代替发布。
- 累计包延续前版所有内容；重装旧基础包后，由已发布客户端的缓存补充层恢复修复。
- 发布前运行 `python tools/test-compose-item-public-repair.py --root .`，发布后核对公开包及安装路径。

本次仅补发已确认图像。其他包的存在性核查，不等于每项原定翻译校对或用户验收全部完成。
