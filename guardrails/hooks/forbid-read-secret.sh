#!/usr/bin/env bash
# forbid-read-secret.sh — PreToolUse hook for Bash。禁止 Agent 主动去读 Token / 把 Token 打到会话里。
# 这是提醒级护栏(Agent 是 root，任何正则都能绕)，目标是拦"犯蠢"，不是拦恶意。
# rev4: 去掉裸词 token / 裸 .env 的超宽匹配(grep -rn access_token src/ 之类日常命令全被拦);
#       补 printf、${VAR:0:n} 截取、env|…、/proc/*/environ、os.environ/process.env、gh auth status -t。
set -uo pipefail
. "$(dirname "$0")/_lib.sh"
cmd=$(get_cmd)
[ "$cmd" = "__PARSE_ERROR__" ] && deny "[policy] 无法解析 hook 输入，按拦截处理"
[ -z "$cmd" ] && pass
# 1) 读取会暴露凭据的文件/环境
if printf '%s' "$cmd" | grep -qiE \
  '(^|[ ;|&(])(cat|sed|head|tail|grep|awk|view|less|more|bat|nl|tac|xxd|od|strings|base64|jq|yq|python3?|node|perl|ruby)( [^;|&]*)?(settings\.json|\.git-credentials|hosts\.yml|tokens?\.(env|json|txt|ya?ml)|credentials(\.json)?([ ;|&]|$)|(^|[ /"'"'"'])\.env([ "'"'"';|&]|$)|/proc/[^ ]*/environ)|(^|[ ;|&(/])env([ ;|&)]|$)|(^|[ ;|&(])printenv([ ;|&)]|$)|(declare|export) -p|os\.environ|process\.env|(^|[ ;|&(])token-helper( |$)|gh auth token|gh auth status[^;|&]*( -t| --show-token)|git config[^;|&]*credential|git credential(-[a-z]+)? (fill|get)'; then
  deny "禁止主动读取/暴露凭据(token/PAT/settings env)：命令可能把 Token 打到会话里。如需用 token，由护栏内部通过 token-helper 获取。"
fi
# 2) echo/printf 环境里的凭据变量(含 ${VAR:0:n} 截取)
if printf '%s' "$cmd" | grep -qiE '(echo|printf)[^|;&]*(\$\{[A-Z_]*(TOKEN|KEY|SECRET|PASS)[A-Z_]*[:}]|\$[A-Z_]*(TOKEN|SECRET)[A-Z_]*|\$[A-Z_]*_KEY([^A-Z_]|$))'; then
  deny "禁止 echo/printf 环境变量里的 Token/密钥（会被读到会话）。凭据由护栏内部处理。"
fi
pass
