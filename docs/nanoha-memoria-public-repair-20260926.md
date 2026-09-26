# 奈叶联动记忆结晶空白大图修复

- 范围：1356—1365，共10张大图；不改正常缩略图、既有中文文本或其他卡面。
- 原因：公开 `cn_base_02.zip` 的同路径大图均为652×990全透明PNG；详情页实际读取 `_c.png`，点击放大复用同一图片。
- 来源：用户本轮提供的 `A:\assets\resource\image_native\memoria`，逐字节采用，不重绘、不压缩、不改图内文字。
- 保留：原图中日文标题；游戏文字层的中文标题、说明与技能。
- 分发：`madomagi/resource/image_native/memoria/memoria_<ID>_c.png`，进入累计补充包。保留原来208个补充文件，增加10个，共218个。
- 回归：`python tools/test-nanoha-memoria-public-repair.py --root .`；发布流程执行相同检查。
- 验收：文件及安装流程测试与用户的手机/游戏画面验收分开。

|编号|中文标题|原文件SHA256|
|---|---|---|
|1356|准备就绪|`5139764bc68de5fdaad7f9ae0af6c58381d45117ea45d6b305f85347689f3467`|
|1357|两束魔力光|`73b1d12da466084165e902f331a8b8413d522cd08f457ae17d7d62adaee4f773`|
|1358|唯一的宝物|`9782d3f3b75aba54375e3eb71ff4e12ab6d4c2d7af6c6f0cd0c0d9a24f2c1ea3`|
|1359|汇聚吧，星之光……|`97d624203b44399df72b53daf994e89d1a81c8c11e44d2cb6d4bc4a83b675a37`|
|1360|我们的魔法|`073d507d9987bb7016644c4502aa4c50eaafb05d8f416ffcc7f5109f42964f27`|
|1361|奏响吧 终结之笛|`eb3272b9b54d6f7d7ca073be26a46a12f77858e2a9023189c06ad60e3c3f09e3`|
|1362|照亮黑暗的光|`7c0feb8970516a33c80ac7f989ebbb05efd517d194d485d8e92f5f728e86b021`|
|1363|夜天之书之主|`dc99f13ad1fe18d53c3bce96084c7ac4853ddd82dd236464a84c50898bf627ef`|
|1364|迅如雷光|`8be4c10e976252da1909f1c0d25dcc998e95be024068e360a5b32fbaaf5b1ddc`|
|1365|祝福之风再次|`f261a035c094775252c25a995f4b876afde643bba19a325261d6292fe6dc118e`|
