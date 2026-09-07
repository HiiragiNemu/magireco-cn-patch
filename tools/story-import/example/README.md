# 样例

**这些文件不参与打包**（剧情包只收 `madomagi/resource/scenario/json/` 那棵树），
放在这里只为让人一眼看清输入输出长什么样。

| 文件 | 是什么 |
|---|---|
| `ir-madoka_portable-Chapter01-01-00_00.json` | 携带版第一章第一场的 IR（56 条，简中） |
| `ir-battle_pentagram-ext_pro_000.json` | 五芒星主线序章的 IR（76 条，日文原文） |
| `adv-881011-1.sample.json` | 上面第一个转出来的魔纪剧情 |
| `adv-882001-1.sample.json` | 上面第二个转出来的魔纪剧情 |

复现：

```bash
python3 tools/story-import/ir_to_adv.py \
    tools/story-import/example/ir-madoka_portable-Chapter01-01-00_00.json \
    --bg bg_adv_20361.jpg --bgm bgm03_story06 \
    --out tools/story-import/example/adv-881011-1.sample.json
```

真要发布时 `--out` 指向
`madomagi/resource/scenario/json/adv/scenario_8/881011-1.json`，
并先读一遍上级 README 的「🔴 进了包的文件拿不出来」。
