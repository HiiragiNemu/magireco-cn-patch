# Round3 人工可显示文本清单格式

`manual_translation_round3.tsv` 使用 UTF-8 TSV，必需列：`item_id`、
`target_path`、`stable_key`、`field`、`source_text`、`final_cn`、
`upstream_source_path`。

工具不生成或修改译文。`item_id` 全表唯一，`target_path + stable_key` 唯一；
`final_cn` 不可为空。产品目标严格限制为 help、SecondPartLastInfo、Walpurgis
commentList、三个指定 CSS、announcements 和 event_banner。

prepare 会保存 TSV、源文件、应用前文件和预期文件的精确字节快照及独立检查点副本；
apply、verify、rollback 逐字节比较这些快照，任何漂移均关闭写入。JSON 仅按稳定键修改，CSS 仅修改
唯一的 `content:` 字符串；HTML 标签／属性、EJS／格式占位符、`＠` 分隔符、JSON
结构和 CSS 骨架均保持不变。
