#!/usr/bin/env bash
# forbid-push.sh — PreToolUse hook for Bash，命中 `git … push`（快速预防层）。权威 refs/签名检查在 git pre-push。
# rev4: 放行不输出 allow; 拦 --no-verify; 补上 Claude Code 实际使用的形态 `git push -u origin claude/xxx`(rev3 只认 HEAD:claude/ 形态)。
# R5 = 禁推一切 Agent 分支(前缀表来自 policy.agent_branch_prefixes)。不做 main/强推保护——那是 GitHub ruleset 的活。
set -uo pipefail
. "$(dirname "$0")/_lib.sh"
cmd=$(get_cmd)
[ "$cmd" = "__PARSE_ERROR__" ] && deny "[policy] 无法解析 hook 输入，按拦截处理"
printf '%s' "$cmd" | grep -qE '(^|[;&| ])git([ ]+-[^ ]+([ ]+[^ -][^ ]*)?)*[ ]+push([ ]|$)' || pass
printf '%s' "$cmd" | grep -qiE -- '--no-verify|hooksPath' && deny "禁止绕过护栏: git push 不得使用 --no-verify / 改 core.hooksPath。"
PFX="($(python3 -c 'import json,sys;print("|".join(p.rstrip("/") for p in json.load(open(sys.argv[1]))["agent_branch_prefixes"]))' "$POLICY" 2>/dev/null || echo 'claude|codex|chatgpt|gpt|agent|deepseek|kimi'))"
# 形态: refs/heads/claude/x | HEAD:claude/x | push [opts] <remote> [+]claude/x
if printf '%s' "$cmd" | grep -qiE "refs/heads/$PFX[/_-]|:$PFX/|push([ ]+-[^ ]+)*[ ]+[A-Za-z0-9._-]+[ ]+\+?$PFX/"; then
  deny "R5: 禁止向 claude/ codex/ chatgpt/ 这类 Agent 分支推送。请先 git switch -c <中性分支名>（或按约定直推 main）。"
fi
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
[ "$(engine_content "$cmd" "$tmp")" = "pass" ] && pass
deny "[policy] $(tr '\n' ' ' <"$tmp")"
