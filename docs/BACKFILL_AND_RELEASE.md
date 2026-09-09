# 翻译回填与发布

## 一键流程

```powershell
python tools/backfill_and_publish.py --review magica/i18n_audit/review.tsv --root . --check
python tools/backfill_and_publish.py --review magica/i18n_audit/review.tsv --root . --publish
```

`--check` 只检查稳定路径、原文唯一性和可回填行；正式回填会在 `.backfill-backups/<UTC时间>/` 保存原文件，并生成 `backfill-report.json`。脚本只接受 `decision` 为 `accept/accepted/fill/replace/approved/use` 的行，原文出现次数必须为 1，路径必须位于仓库根目录内。发布参数会触发 `publish-final.yml`，该工作流从 `latest` Release 取最终包，逐个上传并用对象存储 HEAD 大小核验，再刷新 EdgeOne/ESA。

## 手工复核后回填

TSV 至少包含 `path`、`original`、`replacement`、`decision` 四列；可用 `key`/`stable_key` 记录字段。先运行 `--check`，再运行正式命令。任何原文重复、缺失或路径越界都会停止且不写入。回填报告中的 `backup` 可直接复制回滚：把备份文件覆盖回报告中的 `changed` 路径即可。

## GitHub 修改触发

把人工审查 TSV 提交到 main 后，在 Actions 中运行“Publish exact final localization assets”；脚本也支持 `--publish` 一键触发。发布证据会作为 `final-mirror-publish-evidence` artifact 保存，包含四个文件的字节数与 SHA-256。线上验收必须同时检查 EdgeOne/ESA 的 `version_*.json` 与包 Content-Length/MD5；只看到 GitHub Release 不算线上完成。
