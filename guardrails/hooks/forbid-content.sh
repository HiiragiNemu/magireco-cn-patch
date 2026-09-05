#!/usr/bin/env bash
# forbid-content.sh — PreToolUse hook for Write|Edit|NotebookEdit。委托单一 policy engine。
# rev4: 放行不再输出 allow(不跳过权限确认); 拦截 exit 2; 覆盖 NotebookEdit(new_source); 输入解析失败按拦截;
#       取消 rev3 对护栏目录/settings.json/审查目录的写入豁免：护栏文件和普通文件一样扫(含规则词的 README 也会被拦，按决定)。
set -uo pipefail
. "$(dirname "$0")/_lib.sh"
input=$(cat)
tmpc=$(mktemp); tmp=$(mktemp); trap 'rm -f "$tmpc" "$tmp"' EXIT
fp=$(printf '%s' "$input" | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin); ti=d.get("tool_input") or {}
    c=ti.get("content") or ti.get("new_string") or ti.get("new_source") or ""
    open(sys.argv[1],"w",encoding="utf-8").write(c if isinstance(c,str) else json.dumps(c,ensure_ascii=False))
    print(ti.get("file_path") or ti.get("notebook_path") or "?")
except Exception:
    print("__PARSE_ERROR__")' "$tmpc" 2>/dev/null || echo "__PARSE_ERROR__")
[ "$fp" = "__PARSE_ERROR__" ] && deny "[policy] 无法解析 hook 输入，按拦截处理(fail closed)"
[ -s "$tmpc" ] || pass
res=$(python3 "$CHECK" content "$tmpc" 2>"$tmp")
[ "$res" = "pass" ] && pass
reason=$(tr '\n' ' ' <"$tmp")
deny "[policy] ${reason:-内容命中禁止词表，请改用功能性/中性表述} 路径: $fp"
