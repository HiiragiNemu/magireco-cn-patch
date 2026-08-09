# Totentanz `magica` 中文覆盖研究

本目录记录将旧国服 `magica` 的可验证中文内容叠加到当前 Totentanz 前端时的输入、决策、候选清单、生成素材和验证方法。运行时目录仍以当前 Totentanz 为结构基线；旧国服内容只作为中文权威来源，不整树覆盖。

## 固定输入

| 输入 | SHA-256 |
|---|---|
| `A:\magicaOLD.7z` | `ee1f1cf622c245ac45f565f73e88473f4b8b45889941edf2b5646ee8155d1c94` |
| `A:\totentanz-frontend.tar` | `b8273e94bf832578f7fff89a43e0ff3b206e8d6d210f18c9f10433dce6bcc414` |
| `A:\magirecocn-image-callgraph-l2d-reuse-final.zip` | `02abe9993826b34b6007e8c1bdde278d0f644f86ed8e612ae5b72c69ae438a6c` |
| `A:\magirecocn-images-complete.zip` | `0b63f6b7854cf2c8a0c104cb8f021d206550edbba4d5ef1d6b375ee8d21bdd90` |
| 仓库基点 | `3c983a778429d5e56a2569aa28ea8c622d988c63` |

原始仓库基线另存为 `work/integration_baseline/magica-origin-main-3c983a7.tar.gz`，归档 SHA-256 为 `2e78566ec917abd13a7dc7ff7c775e554ee4a5eb453ae84582e4d7e76268ddd1`。

## 合并规则

1. **当前结构优先**：保留 Totentanz 的路由、模块依赖、HTML 骨架、全部新增 CSS/UI 和资源路径。
2. **中文来源分层**：同字段国服/权威数据 > 旧国服同路径字面量或同画布图片 > Wiki 类型化映射 > 经逐项复核的新 UI 翻译 > 生成式图片文字本地化。
3. **只改完整槽位**：JS 只改完整字符串字面量，HTML 只改完整文本节点或受控属性，CSS 只改 `content` 值；数字、标签、实体、占位符与标识符均受守卫。
4. **图片必须同路径、同几何并经语言复核**：相似或同尺寸并不自动代表中文；未确认的候选只保留在证据表，不进入运行时。
5. **研究与运行时分离**：`magica/research/` 和 `magica/i18n_audit/` 由 CI 明确排除，实际覆盖包只包含 `css/`、`fonts/`、`js/`、`resource/`、`template/`。

## 已进入运行时的覆盖

### 当前独有 UI 文本

- 20 个当前文件，107 条唯一 UI 文本；生产 57/57、测试 50/50。
- 183 个实际槽位中 174 个发生中文替换；7 个原本已兼容中文的共享汉字保持原样。
- 5 个 JS 全部通过 `node --check`；20 个文件按原始 Totentanz 文件确定性重建，结构、换行和 BOM 保持。
- 明细见 `evidence/new-ui/translations.tsv`、`evidence/new-ui/manifest.json` 和 `reports/new-ui-localization.md`。

### 当前 `update2` 菜单图片

- `魔法少女`、`记忆结晶`、`扭蛋`、`任务`：采用旧国服已确认中文画布，写入当前相同资源路径。
- `队伍`、`商店`：当前小尺寸 UI 在旧国服没有可直接采用的中文画布，使用当前画布参考进行文字本地化，透明度、尺寸和路径经人工复核。
- `common.css` 中将当前 `update2` 路径重定向到旧大图的历史尾段已移除；当前 CSS 本体恢复为 Totentanz 基线哈希，不再通过 CSS 回退旧 UI。
- 来源、基线哈希、输出哈希和尺寸见 `manifests/verified_menu_overlay.json`；对照图见 `previews/update2-menu-before-after.png`。

## 不进入运行时的旧文件

- 旧 `index.html`、`baseConfig.js`、`help.js`、`base.css`、`common.css`、`GlobalMenu.css`。
- 旧 jQuery/模块映射和任何会隐藏、错位或覆盖第二部、Puella Historia、Scene0、巡逻、常驻活动等新入口的文件。
- 旧 `update2` 中仍含日文的按钮画布。
- 仅凭感知哈希、同尺寸或文件名推断的图片候选。

## 两套 APK 图片包的关系

两份 ZIP 不是“纯 APK 本地控制”与“纯网络接收”两套互斥资源系统，而是同一 APK 图片集合的两种派生清单/裁切结果：

- 561/561 张直接图片同路径且字节相同。
- 997/997 个图集帧同路径；954 个字节相同，2 个像素相同但编码不同，39 个裁切/尺寸不同，2 个同尺寸但像素不同。
- 两包均含 87 个 `image_native` 路径、0 个 `image_web` 路径，也不含当前 11 张 `resource/image_web/common/global` 菜单图片。

实际运行是耦合分层：WebView 对 `/magica/*` 先读应用私有目录，缺失时回落网络；热更新包会写入该目录；页面还可经 `data-native*`/`DATA_GET_BASE64` 调用原生桥；原生层另负责端点、Label 翻译和字体重定向。完整证据见 `reports/apk-web-resource-architecture.md` 与 `evidence/apk-architecture/`。

## 研究文件索引

- `reports/legacy-overlay-analysis.md`：旧国服覆盖机制、结构差异和中文候选。
- `reports/totentanz-frontend-analysis.md`：当前前端新增文件、CSS/依赖边界和资源映射。
- `reports/apk-web-resource-architecture.md`：两套 APK 图片包及运行时资源分层。
- `reports/new-ui-localization.md`：当前独有 UI 的逐槽位翻译与回滚验证。
- `evidence/legacy/`：强中文字面量、PNG 候选、菜单图标人工审计。
- `evidence/totentanz/`：合并策略、CSS 差异、文本候选和安全/复核资源映射。
- `evidence/apk-architecture/`：ZIP 对应关系、桥接引用、manifest/APK 对应与哈希。
- `evidence/new-ui/`：107 条译文、20 文件 manifest、独立补丁及验证记录。
- `tools/`：分析、应用、验证、打包与回滚脚本。

## 复现入口

```text
python magica/research/totentanz-cn-overlay/tools/apply_verified_overlay.py \
  --repo-magica magica \
  --legacy-magica <解压后的旧国服 magica> \
  --totentanz-magica <解压后的当前 Totentanz magica>

python magica/research/totentanz-cn-overlay/tools/verify_overlay.py \
  --repo-magica magica \
  --totentanz-magica <解压后的当前 Totentanz magica>

python magica/research/totentanz-cn-overlay/tools/build_payload.py \
  --repo-magica magica \
  --output <输出 ZIP>
```

最终分支的补丁、完整命令输出、退出状态和已实跑回滚记录位于 `patches/`、`verification/`；发布 ZIP 不包含本研究目录。
