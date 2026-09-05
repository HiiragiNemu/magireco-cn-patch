#!/usr/bin/env python3
# check.py — 单一 policy engine。Claude hooks 与 Git hooks 都只调用它。
#   check.py content [file] [--net]        (无 file 读 stdin)
#   check.py commit  [msgfile] [--net]
#   check.py push    [remote-name] [--net] (refs 从 stdin)
# 输出: pass | violation | error (+ 命中明细到 stderr)。三态，绝不在异常时静默放行。
# --net: 允许走网络(缓存过期时懒刷新；对缓存里没有的 xxx-xxx 裸名调用 resolve-private.py)。
#        git 钩子 / scan-repo 传 --net；Claude hooks **不传**——hook 被 Claude Code 超时掐掉 = 放行，
#        所以 Claude hook 路径永不走网络：缓存过期直接 ERROR 并让 Agent 手动跑 refresh。
#
# rev4 变更:
#   * R1 私有仓名只来自 private-repos.json(动态缓存)，policy.json 里不再有私有仓名；
#     content / commit / push 三个模式统一做 R1，缓存不可用一律 ERROR(fail closed)。
#   * 命中回显脱敏: 凭据形态的命中只回显前 8 字符，守卫自己不再把 token 打进会话。
#   * R6 指纹比较统一去掉 "SHA256:" 前缀(git %GK 带前缀，旧版永远比不中)。
#   * push 模式接收 remote 名，只审 "远端还没有的提交"(--not --remotes=<remote>)，
#     新分支/远端 SHA 本地不可见 时不再全历史重审。
#   * R4 业务标识正则也不在 policy.json 里了：来自缓存的 patterns(本机种子提供)。
#   * R5 = 禁止推送到任何 Agent 分支(claude/ codex/ chatgpt/ … 见 policy.agent_branch_prefixes，大小写不敏感)。
#     不做 main 保护/强推保护——那是 GitHub ruleset 的活。
#   * R6 签名验证不再依赖 gpg.ssh.allowedSignersFile：直接取提交对象里的 gpgsig，用
#     `ssh-keygen -Y check-novalidate` 做密码学验签并取出签名密钥指纹(git 的 %G?/%GK 没有 allowedSigners 时全是空)。
#   * push 模式也扫新提交的**内容**(新增行)：cherry-pick/rebase/am/合并/--no-verify 进来的内容在这里兜底。
#   * R1 补充(--net)：缓存里没有的 xxx-xxx 裸名交给 resolve-private.py 单名查询；未知名过多时改为整体 refresh 一次再比。
import sys, os, json, re, subprocess, time, tempfile

POLICY_PATH = '/root/.claude/policy/policy.json'
POLICY = json.load(open(POLICY_PATH, encoding='utf-8'))


def norm_fp(s):
    s = (s or '').strip()
    return s.split(':', 1)[1] if s.upper().startswith('SHA256:') else s


FORBIDDEN = re.compile('|'.join(POLICY['forbidden_patterns']), re.I)
SECRETS = [re.compile(p) for p in POLICY['secret_regexes']]
FINGER = norm_fp(POLICY['agent_signing_fingerprint'])
BRANCH_PREFIXES = [p.casefold() for p in POLICY['agent_branch_prefixes']]
SIGN_HELP = POLICY.get('signing_instructions', '请生成独立的 ed25519 SSH Signing Key 并把公钥发给维护者。')
PROVIDER_EMAILS = [e.casefold() for e in POLICY['agent_provider_emails']]
CACHE = POLICY['private_cache']
REFRESH = POLICY.get('refresh_script', '/root/.claude/hooks/refresh-private.py')
RESOLVE = POLICY.get('resolve_script', os.path.join(os.path.dirname(REFRESH), 'resolve-private.py'))
RESOLVE_BUDGET = int(POLICY.get('resolve_budget', 30))
NET = False                                               # 由 main 按 --net 设置
ZERO = '0' * 40
# xxx-xxx 裸名候选: 由 - 连接的 ≥2 段，段内字母数字(可含 .)，前后不是路径/单词字符(排除 --flag、a/b-c 路径段)
RX_SLUG = re.compile(r'(?<![A-Za-z0-9_./\\-])([A-Za-z0-9.]+(?:-[A-Za-z0-9.]+)+)(?![A-Za-z0-9_/:-])')   # 后跟 ':' 的是 trailer 键/HTTP 头，不是仓名
RESOLVE_IGNORE = {x.casefold() for x in POLICY.get('resolve_ignore', [])} | {
    'co-authored-by', 'signed-off-by', 'reviewed-by', 'acked-by', 'tested-by', 'reported-by', 'suggested-by', 'helped-by',
    'pre-commit', 'pre-push', 'commit-msg', 'pre-merge-commit', 'post-commit', 'utf-8', 'x86-64', 'read-only', 'no-verify'}

PASS, VIOLATION, ERROR = 'pass', 'violation', 'error'
CRED_PREFIX = re.compile(r'(?i)^(ghp|gho|ghs|ghu|ghr)_|^github_pat_')


def read_stdin():
    return sys.stdin.buffer.read().decode('utf-8', 'replace')


def mask(s):
    """命中若是凭据形态，只回显前缀——deny 理由会进入 Agent 会话/transcript。"""
    if CRED_PREFIX.search(s) or any(r.search(s) for r in SECRETS):
        return s[:8] + '…(凭据已脱敏,%d字符)' % len(s)
    return s


def scan(text):
    """R2/R4/R7: 静态正则(不含私有仓名)。"""
    hits = set()
    for m in FORBIDDEN.finditer(text):
        hits.add(mask(m.group(0)))
    for r in SECRETS:
        for m in r.finditer(text):
            hits.add('SECRET:' + mask(m.group(0)))
    return sorted(hits)


# ---------- private repo cache (canonical) ----------
def ck(v):
    v = v.strip()
    if '/' in v:
        o, _, r = v.partition('/')
        return o.strip().casefold() + '/' + r.strip().casefold()
    return v.casefold()


def load_cache():
    try:
        d = json.load(open(CACHE, encoding='utf-8'))
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return None


def cache_status(d):
    if not isinstance(d, dict):
        return 'error'
    if d.get('status') == 'error':
        return 'error'
    exp = d.get('expires_at'); gen = d.get('generated_at')
    if isinstance(exp, (int, float)) and time.time() <= exp:
        return 'fresh'
    if isinstance(gen, (int, float)):
        return 'stale'
    return 'unknown'


def refresh_inplace():
    """懒刷新一次(只在 --net 下调用)；成功返回新 dict，失败返回 None。git 钩子没有超时问题。"""
    try:
        subprocess.run([sys.executable, REFRESH], capture_output=True, timeout=60)
        return load_cache()
    except Exception:
        return None


def cache_private(d):
    priv = set()
    if isinstance(d, dict):
        for n in d.get('private', []):
            n = str(n)
            priv.add(n.casefold()); priv.add(ck(n))
    return priv


def cache_patterns(d):
    """R4: 业务标识正则(来自本机种子 -> 缓存)。坏正则按 ERROR 处理，不静默跳过。"""
    pats = [str(x) for x in (d.get('patterns', []) if isinstance(d, dict) else [])]
    return re.compile('|'.join(pats), re.I) if pats else None


def private_check(text):
    """R1: 私有仓名(owner/repo 与 裸名 两种形态)。缓存缺失/损坏/过期且刷新失败 => ERROR。"""
    d = load_cache(); st = cache_status(d)
    if st != 'fresh' and NET:                             # 缺失/损坏/过期: 只有 --net 才就地刷新
        d = refresh_inplace() or d
        st = cache_status(d)
    if st != 'fresh':
        if not NET:
            return ERROR, ['私有仓缓存%s，本层不联网刷新。请先运行: python3 %s  然后重试' % ('缺失/损坏' if st == 'error' else '已过期', REFRESH)]
        if st == 'error':
            return ERROR, ['私有仓缓存缺失/损坏且刷新失败——请检查 私有种子/GH_TOKEN_n/网络 后运行 refresh-private.py']
        return ERROR, ['私有仓缓存刷新失败(%s)，为防泄露按拦截处理——请修复网络/token 后重试' % st]
    try:
        rx = cache_patterns(d)
    except re.error as e:
        return ERROR, ['缓存 patterns 含非法正则(%s)，请修本机种子' % e]
    if rx:
        hits = sorted({m.group(0) for m in rx.finditer(text)})
        if hits:
            return VIOLATION, ['业务标识: ' + ' '.join(hits[:5])]
    priv = cache_private(d)
    low = text.casefold()
    for m in re.finditer(r'[\w.-]+/[\w.-]+', text):
        if ck(m.group(0)) in priv:
            return VIOLATION, ['私有仓名: ' + m.group(0)]
    for p in priv:
        if p and p in low:
            return VIOLATION, ['私有仓名: ' + p]
    if NET:
        return resolve_unknown(text, d, priv)
    return PASS, []


def slug_candidates(text, priv, owners=()):
    out = set()
    owners_cf = {o.casefold() for o in owners}
    for m in re.finditer(r'(?<![\w.-])([\w.-]+)/([\w.-]+)', text):     # 已知 owner 下的 owner/repo 也即时查
        if m.group(1).casefold() in owners_cf and ck(m.group(0)) not in priv and 1 <= len(m.group(2)) <= 100:
            out.add(m.group(0))
    for m in RX_SLUG.finditer(text):
        t = m.group(1)
        if not (6 <= len(t) <= 100) or t.casefold() in priv or t.casefold() in RESOLVE_IGNORE:
            continue
        if not any(re.search(r'[A-Za-z]{2}', part) for part in t.split('-')):
            continue                                      # 2026-09-04 / 1-2-3 之类
        out.add(t)
    return out


def resolve_unknown(text, d, priv):
    """缓存里没有的 xxx-xxx 裸名 -> resolve-private.py 单名查询(负缓存 24h)。
    候选超过 resolve_budget 时不逐个查，改为整体 refresh 一次(O(owners) 个请求)再按新名单比。"""
    cands = sorted(slug_candidates(text, priv, d.get('owners', []) if isinstance(d, dict) else ()))
    if not cands:
        return PASS, []
    if len(cands) > RESOLVE_BUDGET:
        d2 = refresh_inplace()
        if cache_status(d2) != 'fresh':
            return ERROR, ['未知裸名 %d 个超出单查预算且整体刷新失败——请修复 GH_TOKEN_n/网络 后重试' % len(cands)]
        priv2 = cache_private(d2); low = text.casefold()
        hits = [p for p in priv2 - priv if p and p in low]
        return (VIOLATION, ['私有仓名(刷新后新增): ' + hits[0]]) if hits else (PASS, [])
    try:
        r = subprocess.run([sys.executable, RESOLVE, *cands], capture_output=True, text=True, timeout=120)
        res = json.loads(r.stdout.strip() or '{}')
    except Exception as e:
        return ERROR, ['resolve-private 调用失败(%s)' % type(e).__name__]
    priv_hits = [n for n, v in res.items() if isinstance(v, dict) and v.get('status') == 'private']
    if priv_hits:
        return VIOLATION, ['私有仓名(即时查询): ' + ' '.join(priv_hits[:5])]
    errs = [n for n in cands if not isinstance(res.get(n), dict) or res[n].get('status') == 'error']
    if errs:
        return ERROR, ['无法确认 %d 个裸名是否私有仓(GH_TOKEN_n/网络/gh 均不可用): %s' % (len(errs), ' '.join(errs[:5]))]
    return PASS, []


def full_check(text):
    """静态规则 + R1 动态规则。三模式共用。"""
    hits = scan(text)
    if hits:
        return VIOLATION, hits
    return private_check(text)


# ---------- git helpers ----------
def git(args, cwd=None, timeout=60):
    """返回 (ok, stdout)。任何异常都算失败，交给调用方保守处理。"""
    try:
        r = subprocess.run(['git', *args], capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.returncode == 0, r.stdout
    except Exception:
        return False, ''


def commit_signature(sha, cwd=None):
    """读提交对象，剥出 gpgsig 头 => (kind, fp)。kind: none|ssh|pgp|bad|error。ssh 时 fp='SHA256:…'。
    等价于 git 内部 parse_signed_commit + ssh-keygen -Y check-novalidate，但不需要 allowedSignersFile。"""
    try:
        r = subprocess.run(['git', 'cat-file', 'commit', sha], capture_output=True, timeout=30, cwd=cwd)
    except Exception:
        return 'error', ''
    if r.returncode != 0:
        return 'error', ''
    head, _, msg = r.stdout.partition(b'\n\n')
    sig, payload, in_sig = [], [], False
    for line in head.split(b'\n'):
        if line.startswith(b'gpgsig ') or line.startswith(b'gpgsig-sha256 '):
            in_sig = True; sig.append(line.split(b' ', 1)[1]); continue
        if in_sig and line.startswith(b' '):
            sig.append(line[1:]); continue
        in_sig = False; payload.append(line)
    if not sig:
        return 'none', ''
    sigblob = b'\n'.join(sig) + b'\n'
    if sigblob.startswith(b'-----BEGIN PGP'):
        return 'pgp', ''
    if not sigblob.startswith(b'-----BEGIN SSH SIGNATURE-----'):
        return 'bad', ''
    data = b'\n'.join(payload) + b'\n\n' + msg
    try:
        with tempfile.NamedTemporaryFile('wb', suffix='.sig', delete=False) as f:
            f.write(sigblob); sigpath = f.name
        v = subprocess.run(['ssh-keygen', '-Y', 'check-novalidate', '-n', 'git', '-s', sigpath],
                           input=data, capture_output=True, timeout=30)
    except Exception:
        return 'error', ''
    finally:
        try: os.unlink(sigpath)
        except Exception: pass
    if v.returncode != 0:
        return 'bad', ''
    m = re.search(rb'key (SHA256:[A-Za-z0-9+/=]+)', v.stdout + v.stderr)
    return 'ssh', (m.group(1).decode() if m else '')


def is_provider(email):
    e = (email or '').casefold()
    return any(p in e for p in PROVIDER_EMAILS)


# ---------- modes ----------
def cmd_content(text):
    return full_check(text)


def cmd_commit(msgfile=None, cwd=None):
    if msgfile and os.path.exists(msgfile):
        msg = open(msgfile, encoding='utf-8', errors='replace').read()
    else:
        msg = read_stdin()
    # git 会在 commit-msg 之后才剥掉注释行；这里先剥，避免状态注释里的文件名误伤
    ok, cc = git(['config', '--get', 'core.commentChar'], cwd)
    cc = cc.strip() if ok else ''
    if len(cc) != 1:
        cc = '#'                                          # 未设置 / "auto" / 多字符 => 按默认 '#'
    body = '\n'.join(l for l in msg.splitlines() if not l.startswith(cc))
    res, note = full_check(body)
    if res != PASS:
        return res, note
    ok, out = git(['var', 'GIT_AUTHOR_IDENT'], cwd, 10)
    if not ok:
        return ERROR, ['无法读取 git 作者身份']
    m = re.search(r'<([^>]*)>', out); email = m.group(1) if m else ''
    if is_provider(email):
        return VIOLATION, ['作者是 Agent 提供商 noreply: ' + email]
    if not re.search(r'(?im)^\s*Co-authored-by:', body):
        ok, cnt = git(['rev-list', '--count', 'HEAD'], cwd, 10)
        if ok and int(cnt.strip() or '0') > 0:
            return VIOLATION, ['缺少 Co-authored-by: <Agent>']
    return PASS, []


def new_commits(lsha, rsha, remote, cwd):
    """要审的提交 = 本地要推的 tip 减去远端已有的。优先用远端跟踪分支排除(覆盖新分支/远端 SHA 本地不可见)。"""
    if remote:
        ok, out = git(['rev-list', lsha, '--not', '--remotes=' + remote], cwd, 300)
        if ok:
            return out.splitlines()
    if rsha != ZERO:
        ok, out = git(['rev-list', lsha, '--not', rsha], cwd, 300)
        if ok:
            return out.splitlines()
    ok, out = git(['rev-list', lsha], cwd, 300)          # 兜底: 全量(保守)
    return out.splitlines() if ok else None


def cmd_push(remote=None, cwd=None):
    data = read_stdin()
    for line in data.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        lref, lsha, rref, rsha = parts[:4]
        for pre in BRANCH_PREFIXES:
            if rref.casefold().startswith('refs/heads/' + pre):
                return VIOLATION, ['R5: 禁止推送到 Agent 分支 %s。请用中性分支名(或按约定直推 main)。' % rref]
        if lsha == ZERO:
            continue                                      # 删除远端分支
        commits = new_commits(lsha, rsha, remote, cwd)
        if commits is None:
            return ERROR, ['无法枚举待推送提交(git rev-list 失败)']
        for c in commits:
            c = c.strip()
            if not c:
                continue
            ok, info = git(['show', '-s', '--format=%ae|%ce|%B', c], cwd, 30)
            if not ok or '|' not in info:
                return ERROR, ['无法读取提交 ' + c[:9]]
            ae, ce, body = info.split('|', 2)
            kind, fp = commit_signature(c, cwd)
            if kind == 'error':
                return ERROR, ['无法验证提交 %s 的签名(git cat-file / ssh-keygen 不可用)' % c[:9]]
            if kind == 'none':
                return VIOLATION, ['未签名提交 %s。%s' % (c[:9], SIGN_HELP)]
            if kind == 'pgp':
                return VIOLATION, ['提交 %s 用的是 OpenPGP 签名，规则6 要求 SSH 签名。%s' % (c[:9], SIGN_HELP)]
            if kind == 'bad':
                return VIOLATION, ['提交 %s 的 SSH 签名验签失败(损坏/篡改)。' % c[:9]]
            if not fp or norm_fp(fp) == FINGER:
                return VIOLATION, ['提交 %s 使用了 Agent 通用签名密钥(或无法读出密钥指纹)。%s' % (c[:9], SIGN_HELP)]
            res, note = full_check(body)
            if res != PASS:
                return res, ['提交 %s: %s' % (c[:9], ' '.join(note[:4]))]
            if is_provider(ae) or is_provider(ce):
                return VIOLATION, ['提交作者/提交者是 Agent noreply: ' + c[:9]]
            ok, added = added_lines(c, cwd)
            if not ok:
                return ERROR, ['无法读取提交 %s 的内容差异' % c[:9]]
            if added.strip():
                res, note = full_check(added)
                if res != PASS:
                    return res, ['提交 %s 内容: %s' % (c[:9], ' '.join(note[:4]))]
    return PASS, []


def added_lines(sha, cwd):
    """该提交相对其父提交新增的行 + 涉及路径(合并提交对每个父分别比)。"""
    ok, out = git(['diff-tree', '-r', '-m', '--no-color', '--unified=0', '--diff-filter=ACMR', '-p', sha], cwd, 300)
    if not ok:
        return False, ''
    lines = []
    for l in out.splitlines():
        if l.startswith('+++ b/'):
            lines.append(l[6:])
        elif l.startswith('+') and not l.startswith('+++'):
            lines.append(l[1:])
    return True, '\n'.join(lines)


# ---------- main ----------
def main(argv):
    global NET
    args = [a for a in argv if not a.startswith('--')]
    NET = '--net' in argv
    mode = args[0] if args else 'content'
    extra = args[1] if len(args) > 1 else ''
    try:
        if mode == 'content':
            text = open(extra, encoding='utf-8', errors='replace').read() if extra and os.path.exists(extra) else read_stdin()
            res, note = cmd_content(text)
        elif mode == 'commit':
            res, note = cmd_commit(extra or None)
        elif mode == 'push':
            res, note = cmd_push(extra or None)
        else:
            res, note = ERROR, ['未知模式 ' + mode]
    except Exception as e:                                # 引擎自身异常也不放行
        res, note = ERROR, ['check.py 内部异常: %s' % type(e).__name__]
    print(res)
    if note:
        sys.stderr.write('\n'.join(note) + '\n')
    sys.exit(0 if res == PASS else 1)


if __name__ == '__main__':
    main(sys.argv[1:])
