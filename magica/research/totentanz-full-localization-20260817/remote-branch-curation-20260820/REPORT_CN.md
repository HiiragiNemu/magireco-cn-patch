# 远端分支权威取舍（2026-08-20）

## 结论

- 已核对当前远端 `main@ad4f4daf494b10793d23e045fe8ff24d01835afd` 与全部 5 个非 `main` 远端分支。
- 三个 `audit/*` 分支相对 `main` **没有独有产品文件**；独有内容是临时工作流、触发器、生成器或审计分块。
- `audit/full-current-localization-20260820` 的分块只有 `00/01/02/04`，缺少 `03`，不作为产品来源。
- `audit/libs-display-names-20260820` 的 268 条扫描已逐项与当前产品比对：
  - **106** 条已在当前产品中文化；
  - **109** 条按旧国服精确字面值保留；
  - **34** 条按 Wiki 正式名称保留；
  - **19** 条为 `Scene0` 的 `film*` 正式结构标签保留；
  - **0** 条未决。
- `Magia`、`Nine Phases`、`Last Magia`、`Whereabouts of the feather`、`Vs.The World` 等在国服或 Wiki 中本就保留原字面值，不按普通 UI 漏译处理。
- 当前本地 CSS、HTML、JSON、engine 与图像层比这些审计分支更完整；没有用远端较旧整树覆盖。

逐项标题见 `LIBS_DISPLAY_NAME_CURATION.tsv`，分支取舍见 `REMOTE_BRANCH_DECISIONS.tsv`。
