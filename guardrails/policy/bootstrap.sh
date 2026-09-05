#!/usr/bin/env bash
# bootstrap.sh —— 护栏铺设脚本(rev4)。两种用法：
#   A) claude.ai/code → Environment → Setup Script：把本文件整段粘进去，改好下面的 PKG_URL_DEFAULT。
#      (Setup Script 以 root、在仓库根目录运行；每个环境缓存只跑一次；环境变量不一定进得来，所以 URL 直接写死)
#   B) 本机(Droidspaces)：HOOK_PACKAGE_URL=file:///sdcard/guardrails-rev4-package.zip bash bootstrap.sh
#      再运行一次 = 升级(幂等；私有种子/映射表/缓存会保留)。
#
# 做的事(全部幂等，"不漏装、不重装")：
#   1. 下载并解包(zip 或 tgz)到 $GUARD，把脚本里写死的 /root/.claude/... 路径改写到 $GUARD
#   2. git 层：git config --global core.hooksPath -> $GUARD/hooks/git (所有仓库、含新 clone 的，自动生效；云端随快照保留)
#   3. Claude 层(仓库级)：向当前仓库(及 GUARD_REPOS 里列出的仓库)的 .claude/settings.json 合并 5 个 PreToolUse + SessionStart +
#      attribution.sessionUrl=false。按脚本文件名去重——仓库里已经提交过护栏 settings 的不会装第二遍；新写出的文件若未被 git 跟踪
#      则写进 .git/info/exclude，不污染 git status。云端只读仓库级 settings，这一步就是云端 Claude 层的全部。
#   4. Claude 层(用户级)：~/.claude/settings.json 同样合并一份(本机 CLI 用；云端会忽略，无害)
#   5. 依赖：ssh-keygen(R6 验签硬依赖)缺失时尽力 apt-get；python3/git/curl 缺失直接失败
#   6. 私有仓并集刷新(best-effort)：来源 = 种子文件 / GUARD_SEED_B64 / GH_TOKEN_n(环境变量) / gh。Setup Script 里拿不到环境变量
#      时这里会失败——没关系，仓库级 SessionStart hook 会在会话开始时(环境变量已就位)再刷；刷成功前守卫按 ERROR 拦一切写入/提交。
#   7. 跑 doctor 打印自检
#
# 云端环境还需要在 Environment 设置里配：
#   环境变量  GH_TOKEN_1..N = 各 Owner 的 Metadata:Read PAT； GUARD_SEED_B64 = `base64 -w0 private-seed.json`(owners/private/patterns)
#   网络白名单  CDN 域名 + api.github.com (refresh/resolve 直连 GitHub API)
set -u
# >>>>>>>>>>>>>>>>>>>>>>>>  改这一行：CDN 上的包地址(.zip 或 .tgz)  <<<<<<<<<<<<<<<<<<<<<<<<
PKG_URL_DEFAULT="https://YOUR-CDN.example/guardrails-rev4-package.zip"
URL="${HOOK_PACKAGE_URL:-$PKG_URL_DEFAULT}"
GUARD="${GUARD_DIR:-$HOME/.claude/guardrails}"
SETUP_VERSION="v4"
log(){ printf '[guardrails] %s\n' "$*"; }
die(){ log "失败: $*"; log "没有护栏就不该让 Agent 跑——请修好后重跑本脚本"; exit 1; }

# ---- 1. 依赖 ----
for b in python3 git curl; do command -v "$b" >/dev/null 2>&1 || die "缺少 $b"; done
if ! command -v ssh-keygen >/dev/null 2>&1; then
  log "缺少 ssh-keygen(R6 验签需要)，尝试安装 openssh-client…"
  (apt-get install -y openssh-client >/dev/null 2>&1 || (apt-get update >/dev/null 2>&1 && apt-get install -y openssh-client >/dev/null 2>&1)) \
    && log "openssh-client 已安装" || log "警告: 无法安装 openssh-client——签名相关检查会按保守拦截，请手动安装"
fi

# ---- 2. 下载 + 解包(保留本机私有文件与缓存) ----
case "$URL" in *YOUR-CDN.example*) die "PKG_URL_DEFAULT 还是占位符，请填 CDN 地址(或设置 HOOK_PACKAGE_URL)";; esac
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
curl -fsSL "$URL" -o "$TMP/pkg" || die "包下载失败: $URL"
mkdir -p "$TMP/x"
if unzip -qo "$TMP/pkg" -d "$TMP/x" 2>/dev/null; then :; elif tar -xzf "$TMP/pkg" -C "$TMP/x" 2>/dev/null; then :; else die "包既不是 zip 也不是 tgz"; fi
SRC=$(dirname "$(find "$TMP/x" -path '*/policy/check.py' | head -1)")/..
[ -f "$SRC/policy/check.py" ] || die "包里没有 policy/check.py"
mkdir -p "$GUARD"
for keep in private-seed.json sanitize-map.json hooks/private-repos.json hooks/private-repos.json.resolve.json; do
  [ -f "$GUARD/$keep" ] && { mkdir -p "$TMP/keep/$(dirname "$keep")"; cp -a "$GUARD/$keep" "$TMP/keep/$keep"; }
done
rm -rf "$GUARD/hooks" "$GUARD/policy"
cp -a "$SRC/hooks" "$SRC/policy" "$GUARD/"; [ -f "$SRC/README.md" ] && cp -a "$SRC/README.md" "$GUARD/"
[ -d "$TMP/keep" ] && cp -a "$TMP/keep/." "$GUARD/"

# ---- 3. 路径改写 ----
for f in "$GUARD"/policy/* "$GUARD"/hooks/*.sh "$GUARD"/hooks/*.py "$GUARD"/hooks/git/*; do
  [ -f "$f" ] || continue
  sed -i "s#/root/.claude/hooks#$GUARD/hooks#g; s#/root/.claude/policy#$GUARD/policy#g; s#/root/.claude/private-seed.json#$GUARD/private-seed.json#g; s#/root/.claude/sanitize-map.json#$GUARD/sanitize-map.json#g; s#/root/.claude/settings.json#$HOME/.claude/settings.json#g" "$f" 2>/dev/null || true
done
chmod +x "$GUARD"/hooks/*.sh "$GUARD"/hooks/*.py "$GUARD"/hooks/git/* "$GUARD"/policy/*.py 2>/dev/null || true

# ---- 4. git 层 ----
git config --global core.hooksPath "$GUARD/hooks/git" || die "无法写 git 全局配置"
log "core.hooksPath -> $GUARD/hooks/git"

# ---- 5. Claude 层：仓库级(当前仓库 + GUARD_REPOS) + 用户级 ----
install_repo(){ # $1 = 仓库路径
  local top; top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || { log "跳过 $1(不是 git 仓库)"; return; }
  python3 "$GUARD/policy/install-settings.py" "$top/.claude/settings.json" --exclude-untracked || log "警告: $top 仓库级 settings 注入失败"
}
install_repo "$PWD"
IFS=':' read -r -a EXTRA <<< "${GUARD_REPOS:-}"; for r in "${EXTRA[@]:-}"; do [ -n "$r" ] && install_repo "$r"; done
python3 "$GUARD/policy/install-settings.py" || log "警告: 用户级 settings 注入失败(云端可忽略)"

# ---- 6. 私有仓并集(best-effort) ----
if python3 "$GUARD/hooks/refresh-private.py" >/dev/null 2>"$TMP/refresh.err"; then
  log "私有仓并集已刷新"
else
  log "私有仓并集暂未刷新($(head -c 120 "$TMP/refresh.err" | tr '\n' ' '))——会话开始时 SessionStart hook 会用环境变量再刷；刷成功前守卫按 ERROR 拦截写入/提交"
fi

# ---- 7. 自检 ----
echo "$SETUP_VERSION $(date -u +%FT%TZ) $URL" > "$GUARD/.setup-done"
python3 "$GUARD/policy/doctor.py" 2>/dev/null | grep -E 'FAIL|Overall' || true
log "铺设完成($SETUP_VERSION) -> $GUARD"
