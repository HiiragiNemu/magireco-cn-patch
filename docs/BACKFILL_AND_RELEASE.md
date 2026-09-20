# 翻译回填与发布

## 回填流程

```powershell
python tools/backfill_and_publish.py --review magica/i18n_audit/review.tsv --root . --check
python tools/backfill_and_publish.py --review magica/i18n_audit/review.tsv --root .
```

`--check` 只检查稳定路径、原文唯一性和可回填行；正式回填会在
`.backfill-backups/<UTC时间>/` 保存原文件，并生成 `backfill-report.json`。
脚本只接受 `decision` 为 `accept/accepted/fill/replace/approved/use` 的行；
原文出现次数必须为 1，路径必须位于仓库根目录内。

## 发布

旧的 `publish-final.yml` 已退役并删除，因为它钉死了过时的 JS/Scenario
大小与摘要。回填脚本不再隐式触发发布。

当前发布入口是 `.github/workflows/sync-and-upload.yml`（“个人仓库游戏更新发布”）；
正式发布前先审查 `backfill-report.json`，再通过现役发布链生成、核验并提升
`version_*.json` / Release 资产。客户端 APK 使用独立的
`build-personal-client.yml` 做显式构建与验证，不能与内容热更发布混为一条腿。
