#!/usr/bin/env bash
# forbid-tamper.sh — PreToolUse hook for Bash（rev4 新增，可选）。拦 Agent "顺手修掉护栏" 的典型犯蠢动作:
# 改 core.hooksPath / disableAllHooks、删改护栏目录、给 settings.json 动手脚。仍是提醒级(Agent 为 root)。
set -uo pipefail
. "$(dirname "$0")/_lib.sh"
cmd=$(get_cmd)
[ "$cmd" = "__PARSE_ERROR__" ] && deny "[policy] 无法解析 hook 输入，按拦截处理"
[ -z "$cmd" ] && pass
BASE=$(dirname "$(dirname "$POLICY")")            # /root/.claude 或 bootstrap 的 $GUARD
EB=$(printf '%s' "$BASE" | sed 's/[.[\*^$]/\\&/g')  # 正则转义
HOMEDIRS='(~|\$HOME|/root)/\.claude'
if printf '%s' "$cmd" | grep -qiE "core\.hooksPath|disableAllHooks|(rm|mv|chmod|chown|truncate|shred|sed -i|tee)[^;|&]*($EB/(hooks|policy|token-helper|private-seed)|$HOMEDIRS/settings\.json)|>[ ]*($EB/(hooks|policy)|$HOMEDIRS/settings\.json)|[ /]\.git/hooks/(pre-commit|pre-merge-commit|commit-msg|pre-push)"; then
  deny "禁止改动护栏自身(core.hooksPath / disableAllHooks / 护栏目录 / settings.json)。护栏由人工通过发布包升级。"
fi
pass
