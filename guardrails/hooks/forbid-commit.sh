#!/usr/bin/env bash
# forbid-commit.sh — PreToolUse hook for Bash，命中 `git … commit`（快速预防层）。
# 权威的 msg/作者/签名检查在 git 钩子；这里: 作者邮箱 + 命令串扫描 + 拦绕过护栏的开关。
# rev4: 放行不输出 allow; 拦 --no-verify/-n/--no-gpg-sign/-c core.hooksPath=/-c commit.gpgsign=false/--author=…noreply。
set -uo pipefail
. "$(dirname "$0")/_lib.sh"
cmd=$(get_cmd)
[ "$cmd" = "__PARSE_ERROR__" ] && deny "[policy] 无法解析 hook 输入，按拦截处理"
printf '%s' "$cmd" | grep -qE '(^|[;&| ])git([ ]+-[^ ]+([ ]+[^ -][^ ]*)?)*[ ]+commit([ ]|$)' || pass
if printf '%s' "$cmd" | grep -qiE -- '--no-verify|(^|[ ])-n([ ]|$)|--no-gpg-sign|hooksPath|commit\.gpgsign=false|gpg\.format=(gpg|openpgp|x509)|--author=[^;|&]*noreply@(anthropic|openai|deepseek|moonshot)|user\.email=[^;|&]*noreply@'; then
  deny "禁止绕过护栏: 不得使用 --no-verify/-n/--no-gpg-sign、改 core.hooksPath/commit.gpgsign/gpg.format，或把作者设成 Agent noreply。"
fi
email=$(git config user.email 2>/dev/null || echo '')
case "$(printf '%s' "$email" | tr 'A-Z' 'a-z')" in *noreply@anthropic.com|*noreply@openai.com|*noreply@deepseek.com|*noreply@moonshot.cn) deny "作者邮箱是 Agent 提供的 noreply（$email）→ 禁止 Agent 自己署名，须人类贡献者 + Co-authored-by: <Agent>";; esac
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
[ "$(engine_content "$cmd" "$tmp")" = "pass" ] && pass
deny "[policy] $(tr '\n' ' ' <"$tmp")"
