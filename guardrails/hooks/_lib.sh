#!/usr/bin/env bash
# _lib.sh — 四个 PreToolUse hook 共用的小函数。被 source，不单独执行。
# 语义(对齐 Claude Code hooks 文档):
#   * 放行 = "不表态": exit 0 且不输出。旧版输出 permissionDecision=allow，等于给 Bash/Write/Edit 全部跳过权限确认。
#   * 拦截 = 输出 permissionDecision=deny 的 JSON **并且** exit 2 (exit 2 单独也能拦，双保险；
#     hook 被 Claude Code 超时掐掉 = 无决策 = 放行，所以 hook 内不能做慢操作: 这里调用 check.py 一律**不带 --net**)。
POLICY=/root/.claude/policy/policy.json
CHECK=/root/.claude/policy/check.py
pass(){ exit 0; }
deny(){
  python3 -c 'import json,sys;print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":sys.argv[1]}},ensure_ascii=False))' "$1" 2>/dev/null \
    || printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[policy] blocked"}}\n'
  printf '%s\n' "$1" >&2
  exit 2
}
# 从 hook 输入 JSON 取 tool_input.command；解析失败输出哨兵(调用方按保守处理)
get_cmd(){ python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); sys.stdout.write((d.get("tool_input") or {}).get("command") or "")
except Exception: sys.stdout.write("__PARSE_ERROR__")' 2>/dev/null || printf '__PARSE_ERROR__'; }
# 用引擎扫一段文本: 返回 pass / 其他(明细在 $2 文件)
engine_content(){ printf '%s' "$1" | python3 "$CHECK" content 2>"$2"; }
