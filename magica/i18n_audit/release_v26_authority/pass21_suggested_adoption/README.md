# Pass21 建议中文直接采用记录

本目录记录用户明确要求直接采用的 29 条建议中文。它们全部保留
`legacy_unverified_ai_assisted`／机器来源，不提升为官方、Wiki 或确认人工。

- canonical 采用：29 条；
- 运行时物化：24 项、30 处、23 个文件；
- 当前产品未引用、仅维护层保存：5 条；
- 官方／Wiki／确认人工保护变化：0。

文件说明：

- `product_patch.json`：稳定 ID 到精确产品目标的机器补丁；
- `product.diff`：运行时可读差异；
- `stage_verification.json`：暂存、结构、语法和保护门；
- `promotion_verification.json`：原子提升结果；
- `rollback_manifest.json`：逐文件 before／after 合同；
- `rollback_verification.json`：真实回撤事务结果；
- `final_verification.json`：回撤后 30/30 before、重新提升后 30/30 after、
  权威保护、人工门和最终 JS ZIP 合同。

Draft Release 的 `pass21_suggested_adoption_audit_bundle.zip` 另含
`rollback/before/` 与 `rollback/after/` 快照及执行工具。解压后在仓库根目录运行：

```powershell
python tools/apply-pass20-suggested-adoptions.py `
  --repo-root . `
  --stage-root <解压目录>\stage `
  --allow-repository-write `
  --rollback
```

该命令只在当前文件逐字等于登记 after 时回撤；任何漂移均在写入前停止。
