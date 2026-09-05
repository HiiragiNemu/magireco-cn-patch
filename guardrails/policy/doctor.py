#!/usr/bin/env python3
# doctor.py — 一键自检：护栏是否装好/可用。输出 [PASS]/[FAIL]/[WARN] 各项 + Overall。
# rev4: 路径从本文件位置推导(bootstrap 搬家后仍可用); 检查 token-helper / 私有种子 / read-secret & tamper hooks /
#       gpg.ssh.allowedSignersFile(没有它 git 把 SSH 签名当成未签名) / 仓库级 core.hooksPath 覆盖 / 缓存来源。
import json, os, sys, subprocess, time
P = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(P)
H = os.path.join(BASE, 'hooks'); G = os.path.join(H, 'git')
fails, warns = [], []
def ok(name, cond, why=''):
    print(('[PASS] ' if cond else '[FAIL] ') + name + ('' if cond or not why else ' — ' + why))
    if not cond: fails.append(name)
def warn(name, cond, why=''):
    if not cond: print('[WARN] ' + name + (' — ' + why if why else '')); warns.append(name)
def exe(p): return os.path.isfile(p) and os.access(p, os.X_OK)
def sh(*a):
    try: return subprocess.run(list(a), capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception: return ''

pol = {}
try:
    pol = json.load(open(os.path.join(P, 'policy.json'), encoding='utf-8'))
    ok('policy.json 可读', len(pol.get('forbidden_patterns', [])) > 0, '规则数=%d' % len(pol.get('forbidden_patterns', [])))
except Exception as e:
    ok('policy.json 可读', False, str(e))

# 1) Claude hooks(本机 CLI 部署)
SET = os.path.expanduser('~/.claude/settings.json')
try:
    s = json.load(open(SET, encoding='utf-8'))
    cmds = ' '.join(h.get('command', '') for grp in s.get('hooks', {}).get('PreToolUse', []) for h in grp.get('hooks', []))
    for n in ('forbid-content.sh', 'forbid-commit.sh', 'forbid-push.sh', 'forbid-read-secret.sh'):
        ok('Claude PreToolUse hook %s' % n, n in cmds)
    warn('Claude PreToolUse hook forbid-tamper.sh(可选)', 'forbid-tamper.sh' in cmds)
    ok('Claude SessionStart refresh', 'refresh-private.py' in ' '.join(h.get('command', '') for grp in s.get('hooks', {}).get('SessionStart', []) for h in grp.get('hooks', [])))
    ok('attribution.sessionUrl 关闭', s.get('attribution', {}).get('sessionUrl') is False)
    ok('未输出 permissionDecision=allow(旧版会跳过全部权限确认)', 'permissionDecision":"allow' not in open(os.path.join(H, 'forbid-content.sh')).read())
    if os.environ.get('CLAUDE_CODE_REMOTE') == 'true':
        print('[WARN] 当前是 claude.ai 云会话: 官方文档称云端不读 ~/.claude/settings.json，以上 Claude hooks 可能根本没生效，请用仓库 .claude/settings.json'); warns.append('cloud')
except Exception as e:
    ok('~/.claude/settings.json 可读', False, str(e))
# 2) Git hooks
hp = sh('git', 'config', '--global', '--get', 'core.hooksPath')
ok('git core.hooksPath(global)', hp == G, '应为 %s，当前 %r' % (G, hp))
local_hp = sh('git', 'config', '--local', '--get', 'core.hooksPath') if sh('git', 'rev-parse', '--is-inside-work-tree') == 'true' else ''
ok('当前仓库未用 core.hooksPath 覆盖全局', not local_hp or local_hp == G, '本仓库 core.hooksPath=%r 会绕开全局钩子' % local_hp)
for hk in ('pre-commit', 'pre-merge-commit', 'commit-msg', 'pre-push'):
    ok('git hook %s 可执行' % hk, exe(os.path.join(G, hk)))
ok('policy/check.py 可执行', exe(os.path.join(P, 'check.py')))
ok('hooks/resolve-private.py 可执行', exe(os.path.join(H, 'resolve-private.py')))
def _code(path):
    return '\n'.join(l for l in open(path, encoding='utf-8', errors='replace').read().splitlines() if not l.lstrip().startswith('#'))
ok('git 钩子带 --net(懒刷新/即时查询只在 git 层)', all('--net' in _code(os.path.join(G, hk)) for hk in ('pre-commit', 'commit-msg', 'pre-push')))
ok('Claude hooks 不带 --net(不在 hook 内联网)', not any('--net' in _code(os.path.join(H, f)) for f in os.listdir(H) if f.endswith('.sh')))
# 3) R1 动态名单
cache = pol.get('private_cache', os.path.join(H, 'private-repos.json'))
if os.path.isfile(cache):
    try:
        d = json.load(open(cache, encoding='utf-8')); exp = d.get('expires_at', 0)
        ok('私有仓缓存存在', True)
        ok('缓存新鲜', time.time() <= exp, '过期于 %s —— git 钩子会就地刷新，Claude hooks 会直接拦并要求手动 refresh' % time.strftime('%Y-%m-%d %H:%M', time.localtime(exp)))
        ok('缓存非空', len(d.get('private', [])) > 0)
        pats = ' '.join(pol.get('forbidden_patterns', [])).casefold()
        leak = [n for n in d.get('private', []) if '/' not in str(n) and str(n).casefold() in pats]
        ok('policy.json(随包分发)不含缓存里的私有仓名', not leak, '泄露到静态词表: %s' % ', '.join(leak[:5]))
        leak2 = [x for x in d.get('patterns', []) if str(x) in ' '.join(pol.get('forbidden_patterns', []))]
        ok('policy.json 不含缓存里的 R4 业务标识正则', not leak2, '泄露: %s' % ', '.join(map(str, leak2[:5])))
        warn('缓存含 R4 业务标识 patterns(来自种子)', len(d.get('patterns', [])) > 0, '为空 = R4 未生效(本机需要种子里的 patterns)')
        src = d.get('sources', [])
        warn('缓存来源含 GitHub 实时数据(gh/token)', any(x != 'seed' for x in src), '当前来源=%s，仅种子 = 名单不会随新建私有仓更新' % '+'.join(src))
    except Exception as e:
        ok('私有仓缓存解析', False, str(e))
else:
    ok('私有仓缓存存在', False, '缺失，请运行 refresh-private.py')
seed = pol.get('private_seed', '')
warn('私有种子存在(本机)', os.path.isfile(seed), '%s 不存在: 名单完全依赖 gh/token' % seed)
ntok = len([k for k in os.environ if k.startswith('GH_TOKEN_')])
warn('环境里有 GH_TOKEN_n(各 Owner 的 Metadata:Read PAT)', ntok > 0, '当前进程环境里没有 GH_TOKEN_1..N —— token-helper 未把 PAT 写进环境？名单只能靠 种子/gh')
# 4) 签名
gs = sh('git', 'config', '--get', 'commit.gpgsign'); ff = sh('git', 'config', '--get', 'gpg.format')
ok('SSH 签名配置(commit.gpgsign=true,gpg.format=ssh)', gs == 'true' and ff == 'ssh', 'gpgsign=%s format=%s' % (gs, ff))
hp2 = sh('git', 'config', '--get', 'gpg.ssh.allowedSignersFile')
if not hp2:
    print('[INFO] 未配置 gpg.ssh.allowedSignersFile：不影响护栏(rev4 用 ssh-keygen check-novalidate 直接验签)，只是 git log --show-signature 会显示 N')
warn('ssh-keygen 可用(pre-commit 指纹比对需要)', bool(sh('which', 'ssh-keygen')))
print('Overall: ' + ('PASS' if not fails else 'DEGRADED') + (' (warnings: %d)' % len(warns) if warns else ''))
sys.exit(0 if not fails else 1)
