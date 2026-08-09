# Totentanz 当前独有 UI 中文化报告

## 结果

- 生产 UI：**57/57 条已定稿并验证**。
- 测试页面：**50/50 条已定稿并验证**。
- 合计：107 条唯一文本，覆盖 183 个实际字符串/content 槽位；其中 174 个槽位发生中文替换。
- 文件：20/20 个文件生成 overlay；源文件保持原哈希，未写入 `work/patch-front/magica`。
- 共享汉字可直接沿用的 7 条（如“第 ”、“分”、“秒”、“大吉”）以 `already_cn_compatible` 记录，未做无意义字节改写。

## 替换边界

1. JS 只替换完整引号字面量。
2. CSS 只替换 `content: "..."`/`content: '...'` 的完整值。
3. HTML 只替换提取器同口径的完整文本节点，以及 `title`、`placeholder`、`alt`、`value` 属性值。
4. 数字、`<br>` 标签、HTML 实体、`%0a`、GP/Lv/DP/Pt/UI/index/charaId/Scale/Fade 等受保护记号逐条比对。
5. overlay 逐文件由原始 Totentanz 文件重建；修改后的文件与该重建结果逐字节相同，因此 JS/HTML/CSS 结构、换行和 BOM 均保持。

## 术语口径

| 日文/概念 | 中文口径 |
|---|---|
| マギレコ / マギアレコード | 魔纪 / 魔法纪录 |
| 八雲みたま | 八云御魂 |
| ミラーズ / ミラーズランクマッチ | 镜界 / 镜界排位赛 |
| キモチ戦 | 心魔战 |
| マギアストーン | 魔法石 |
| サポートPt | 支援Pt |
| グループレイド | 小组讨伐 |

同时核对现有 `magica` 权威用语：魔法少女、记忆结晶、镜层、巡逻、心魔战、歼灭战、战斗博物馆。本批新增文本未出现的术语没有强行植入。

## 静态验证

### 基线

```text
C:\Users\proje\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verify_static.py --phase baseline
BASELINE_OK files=20 records=107 production=57 test=50 occurrences=183 sha256_match=20/20
exit_status: 0
```

### 中文 overlay

```text
C:\Users\proje\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verify_static.py --phase modified
MODIFIED_OK files=20 records=107 occurrences=183 removed_source_slots=174/174 structural_exact=20/20 numeric_markup_guards=107/107
exit_status: 0
```

### JS 语法与 UI 假名残留

```text
C:\Users\proje\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verify_static.py --phase syntax
SYNTAX_UI_OK js=5/5 kana_ui_slot_residuals=0 checked_files=20
exit_status: 0
```

### 隔离目录应用与回滚

```text
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\apply_overlay.ps1 -TargetMagica C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verification_stage\magica -BackupRoot C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verification_stage\backup
APPLY_OK files=20 target=C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verification_stage\magica backup=C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verification_stage\backup record=C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verification_stage\backup\application_record.json
exit_status: 0

powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\rollback_overlay.ps1 -RecordPath C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verification_stage\backup\application_record.json
ROLLBACK_OK files=20 target=C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verification_stage\magica
exit_status: 0
```

### 补丁正反向应用

```text
C:\Users\proje\AppData\Local\Python\pythoncore-3.14-64\python.exe C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-magirecocn-revival-project\work\new_ui_localization\verify_patch_roundtrip.py
PATCH_ROUNDTRIP_OK files=20 apply_match=20/20 rollback_match=20/20
exit_status: 0
```

## 产物

- `overlay/`：相对 `magica/` 的 20 个覆盖文件。
- `translations.tsv`：107 条定稿、作用域、实际命中次数和状态。
- `new_ui_localization.patch`：以 `a/magica/...` → `b/magica/...` 为路径的补丁。
- `manifest.json`：逐文件基线/overlay SHA-256、大小和 BOM 状态。
- `verification_record.json` / `verification.log`：命令、输入、原样输出和退出状态。
- `apply_overlay.ps1` / `rollback_overlay.ps1`：带备份记录的应用与回滚；已在 `verification_stage/` 往返验证。
