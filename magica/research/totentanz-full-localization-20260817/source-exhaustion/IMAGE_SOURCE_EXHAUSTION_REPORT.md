# 旧国服 / 当前美服可见文本图片源耗尽审计

## 结论

**图片源尚未耗尽。** 在 `resource/image_web` 的 8,868 个同路径 PNG 中，仍有 **160 个 `unresolved-actionable`**：旧国服图片含可回收的官方中文可见文本，而当前美服资源仍为英文、日文或未简体化，且未被现有 159 张官方覆盖清单或 58 张重制图片清单覆盖。

- 可按同路径同尺寸复用：**152**
- 尺寸／画布已漂移，必须在当前画布重制：**8**
- 本报告实际写入产品文件：**0**
- `exhausted-no-value`：**8,708**

## 排除项的闭合分解

| 原因 | 数量 | 结论 |
|---|---:|---|
| `source-byte-identical` | 2,235 | 旧国服与当前美服同路径PNG字节完全一致，没有新增中文价值。 |
| `rendered-pixels-identical` | 3,619 | 文件编码/元数据不同，但解码后的像素完全一致，没有可见中文差异。 |
| `invalid-non-image-placeholders` | 4 | 扩展名为PNG但内容不是可解码图片，属于异常占位资源，不能提供可见中文。 |
| `no-current-literal-reference` | 2,354 | 像素确有差异，但当前美服/产品JS、HTML、CSS、JSON中没有静态字面引用；按本轮排除规则视为过时或未引用资源。 |
| `already-covered-by-current-manifests` | 171 | 已由159张官方国服覆盖清单或58张当前画布中文重制清单覆盖；无需重复加入。 |
| `already-localized-in-product-unclaimed-by-image-manifests` | 9 | 旧图像清单未声明，但当前产品文件已实际显示中文；逐图确认不是遗漏。 |
| `manual-visual-review-no-transferable-official-cn-text` | 316 | 仍被引用且像素不同，但逐图对照没有可转移的官方中文可见文本。 |

合计：160 + 8,708 = 8,868，与同路径 PNG 总数一致。

## 代表性遗漏

仍可回收的官方中文图片覆盖：相机按钮、角色／记忆结晶菜单、扭蛋标签、镜界／排名／演习、活动任务、战斗与返回入口、剧情入口、魔法少女入口、Box Gacha 状态等。完整 160 条路径、引用证据、尺寸和 SHA-256 见 `image_unresolved_actionable.tsv`。

## 安全边界

1. 同尺寸条目也必须在正式应用前核对当前路径语义；不得按文件名全局猜测。
2. 8 个尺寸漂移条目只回收中文文字，不直接拿旧图覆盖新画布。
3. 无静态字面引用的 2,354 张图片按本轮规则排除；若以后发现动态路径运行时证据，应重新进入候选。
4. 本轮为报告态，没有复制任何 A 盘大文件，也没有修改 `magica/` 产品资源。

## 工件

- 机器总表：`image_source_exhaustion.json`
- 人工/后续执行清单：`image_unresolved_actionable.tsv`
- 本报告：`IMAGE_SOURCE_EXHAUSTION_REPORT.md`
