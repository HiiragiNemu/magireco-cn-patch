# Totentanz 中文化统计（2026-09-09）

## 统一基线

- 产品 JS：201；HTML：225；CSS：44；JSON：39；运行时字典：32。
- 产品/发布清单：1955 条；修复清单：91 条；可见未翻译 backlog：0。
- 审查总行数：15,982；其中运行时或已打包：13,358。
- 运行时字典字段：12,399；前端字段输入：1,685；静态 JS/HTML：303；引擎原生 i18n：621；可见术语闭合：3,136。
- 对话/剧情增量包：版本 3289（这是包版本号，不是独立剧情场景数）。

## 来源归属

| 来源 | 行数 |
|---|---:|
| 国服官方（official） | 2,122 |
| 本项目根目录人工审校（new-root-human） | 2,692 |
| 圆环记录 Wiki（wiki） | 1,096 |
| 历史 AI/旧批次（legacy-ai） | 1,640 |
| 未能逐行归属（unknown） | 8,432 |

“水银”没有在当前逐行导出中留下可核验的独立来源字段，保持 `typed-unavailable`，没有把历史 AI 批次冒充水银。unknown 也不强行分配给任何人。

## 实机自动分发

- 设备：`emulator-5554`。
- `config.json` 成功加载 4 条线路；客户端版本 `1.0.171` 与云端一致。
- `cn_js_update.zip`：112,257,149 bytes，8 段下载并提交，版本 87。
- `cn_scenario_update.zip`：193,930,737 bytes，8 段下载并提交，版本 3289。
- 日志最终结果：`热更检查完毕：已应用全部需要的更新`。

证据：`REAL_DEVICE_AUTO_DOWNLOAD_VERIFICATION.json`、`UPDATE_SIGNATURE_DIAGNOSIS.json`。
