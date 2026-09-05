#!/usr/bin/env python3
# scan-repo.py <repo-path> [--scan-current] [--scan-history]
#   默认/--scan-current: HEAD 当前树文本文件 + 全历史提交消息。
#   --scan-history: 每个历史提交的所有树文本文件(重量级,仅在确需查"历史上曾出现违规"时显式用)。
# rev4 修复:
#   * 无 origin 远端时 selfname='' 曾使 `'' not in h` 永远为假 => 任何命中都被丢掉 => 永远报"干净"(fail open)。
#   * 私有仓名改为读 private-repos.json 动态缓存(与 check.py 同源)，缓存不可用 => 退出 2 并明说。
#   * 不再按扩展名白名单挑文件(漏 .gitmodules/Dockerfile/无扩展名文件)，改为二进制嗅探(前 8KB 含 NUL 即跳过)。
#   * 命中里的凭据脱敏，不把 token 打进终端/会话。
import sys, os, re, json, subprocess, time
P_PATH = '/root/.claude/policy/policy.json'
P = json.load(open(P_PATH, encoding='utf-8'))
RX = re.compile('|'.join(P['forbidden_patterns']), re.I)
SECRETS = [re.compile(x) for x in P['secret_regexes']]
CRED = re.compile(r'(?i)^(ghp|gho|ghs|ghu|ghr)_|^github_pat_')

repo = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '.'
mode = 'history' if '--scan-history' in sys.argv[1:] else 'current'


def git(*args, timeout=300, binary=False):
    try:
        r = subprocess.run(['git', '-C', repo, *args], capture_output=True, timeout=timeout)
        return r.stdout if binary else r.stdout.decode('utf-8', 'replace')
    except Exception:
        return b'' if binary else ''


def mask(s):
    if CRED.search(s) or any(r.search(s) for r in SECRETS):
        return s[:8] + '…(凭据已脱敏)'
    return s


# 私有仓名: 与 check.py 同源
try:
    cache = json.load(open(P['private_cache'], encoding='utf-8'))
    exp = cache.get('expires_at', 0)
    if cache.get('status') == 'error' or not isinstance(exp, (int, float)):
        raise ValueError('cache status')
    PRIV = sorted({str(n).casefold() for n in cache.get('private', [])}, key=len, reverse=True)
    _pats = [str(x) for x in cache.get('patterns', [])]
    RX4 = re.compile('|'.join(_pats), re.I) if _pats else None
    if time.time() > exp:
        print('# 警告: 私有仓缓存已过期，名单可能不全(先运行 refresh-private.py)', file=sys.stderr)
except Exception as e:
    print('# 私有仓缓存不可用(%s): 无法做 R1 审计，退出' % type(e).__name__, file=sys.stderr); sys.exit(2)


def scanbytes(s, tag):
    hits = [tag + ': ' + mask(m.group(0)) for m in RX.finditer(s)]
    hits += [tag + ' SECRET: ' + mask(m.group(0)) for r in SECRETS for m in r.finditer(s)]
    low = s.casefold()
    hits += [tag + ' 私有仓名: ' + p for p in PRIV if p in low]
    if RX4:
        hits += [tag + ' 业务标识: ' + m.group(0) for m in RX4.finditer(s)]
    return hits


def is_text(b):
    return b'\0' not in b[:8192]


url = git('remote', 'get-url', 'origin').strip()
selfname = url.rstrip('/').rsplit('/', 1)[-1]
selfname = selfname[:-4] if selfname.endswith('.git') else selfname
selfname = selfname.casefold()


def keep(h):
    return not (selfname and selfname in h.casefold())      # 豁免本仓库自身名(只在真的拿到了仓名时)


hits = []; corpus = []
msgs = git('log', '--all', '--format=%B'); corpus.append(msgs)
hits += [h for h in scanbytes(msgs, 'MSG') if keep(h)]
if mode == 'history':
    for c in git('rev-list', '--all').splitlines():
        if not c.strip():
            continue
        for n in git('ls-tree', '-r', '--name-only', c).splitlines():
            b = git('show', '%s:%s' % (c, n), binary=True)
            if is_text(b):
                t = b.decode('utf-8', 'replace'); corpus.append(n); corpus.append(t)
                hits += [h for h in scanbytes(t, 'FILE(%s@%s)' % (n, c[:9])) if keep(h)]
else:
    for n in git('ls-tree', '-r', '--name-only', 'HEAD').splitlines():
        b = git('show', 'HEAD:' + n, binary=True)
        if is_text(b):
            t = b.decode('utf-8', 'replace'); corpus.append(n); corpus.append(t)
            hits += [h for h in scanbytes(t, 'FILE(%s)' % n) if keep(h)]
# R1 补充: 缓存里没有的 xxx-xxx 裸名 / 已知 owner 下的 owner/repo，交给引擎 --net 即时查(预算超出则整体刷新一次)
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location('guardcheck', os.path.join(os.path.dirname(os.path.abspath(P_PATH)), 'check.py'))
    gc = importlib.util.module_from_spec(spec); spec.loader.exec_module(gc); gc.NET = True
    alltext = '\n'.join(corpus)
    st, note = gc.resolve_unknown(alltext, cache, gc.cache_private(cache))
    if st == gc.VIOLATION:
        hits += ['RESOLVE ' + n for n in note]
    elif st == gc.ERROR:
        print('# 即时查询未完成: ' + ' '.join(note), file=sys.stderr)
except Exception as e:
    print('# 即时查询失败(%s)，只报告静态/缓存命中' % type(e).__name__, file=sys.stderr)
seen = sorted(set(hits))
if seen:
    sys.stdout.write('\n'.join(seen[:60]) + '\n'); print('# 命中数:', len(seen), file=sys.stderr); sys.exit(1)
print('# 干净：%s 模式无命中(自身仓名豁免: %s)' % (mode, selfname or '无'), file=sys.stderr); sys.exit(0)
