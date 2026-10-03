# 校订与生产交付状态（接续中）

2026-10-03T04:26:53.949055+00:00

已核实线上Reader仍旧稿，361目标/240TXT隔离生产输入已重构；正在执行与现有部署一致的数据生成链，不发包。

确认历史范围1079项已逐项核算：694发布记录、361已备稿、23人译豁免、1旧全审，已知首次/残余待校订0。不得将此结论扩大为全库无错。当前361目标中的359份实际修订均未进入运行源；2份无需改字节。

正式Reader源码15d2ee951514ea13e67d68a6864707a7f926fa98、部署f271c901。五个实际正文接口匹配旧源而非最终候选；新稿并非线上读取失败，而是尚未整合。所有361目标已在目录中，单看目录有条目不能证明文字已更新。

本轮隔离生产目录：`D:\magia\deliveries\reader-production-20260930-1226\production-readiness-20261003`。生产脚本produce_reader.py只在reader-build与build-only.git构造候选快照、运行既有数据生成器；本地候选提交不创建远端分支、不推送运行源、不部署，正式整合后必须绑定真实main重新生成。不能将这个本地快照发布成正式Reader来源。

客户端唯一接入仍为`docs/story-quality/client-integration/READY.json`，manifest `f4db42783439dc15e2cb94cdcc10857c5e40c8d2e020b4004891bf9e5cc258a1`；当前无CLIENT_RECEIPT。完整新稿/累计只在CN patch。
