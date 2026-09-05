#!/usr/bin/env python3
# refresh-private.py — 重建 private-repos.json：对**所有所有者**做一次私有仓并集。
#
# 来源(并集):
#   1) 私有种子 policy.private_seed (默认 /root/.claude/private-seed.json)。**只放本机，不随包分发**。
#      云端没有这个文件时，可从环境变量 GUARD_SEED_B64(种子 JSON 的 base64) 或 GUARD_SEED_JSON 读取——
#      与 GH_TOKEN_n 同一暴露面(环境使用者/Agent 可读)，比 PAT 本身更不敏感。
#      格式: {"owners": ["Org1", ...], "private": ["Org1/repo", "repo", ...], "patterns": ["业务域名/标识 正则", ...]}
#      patterns = R4 业务标识(域名/内部流水线名)正则，原样进缓存，由 check.py/scan-repo 应用。
#   2) gh CLI(best-effort，失败不 fail-all)
#   3) 环境变量 GH_TOKEN_1..N(各 Owner 的 Metadata:Read PAT；token-helper ELF 的唯一职责就是把它们写进环境)，
#      以及 GH_TOKEN(云端占位符 'proxy-injected' 忽略)。每次调用失败重试≤3；任一把重试后仍失败 => 整体失败(不回写，退出 1)。
#      403/404 = 该 token 看不到 => 正常跳过；403 且是 rate limit => 算失败(否则会静默漏掉整个 owner)。
#
# 完整性:
#   * 至少一个来源成功(种子/gh 取到数据/任一 token 成功)，否则不回写、退出 1 => 缓存保持缺失/陈旧 => check.py ERROR。
#   * policy.expected_owners 里的每个 owner 必须被"种子覆盖"或"gh/token 看到了它至少 1 个私有仓"，否则视为不完整、
#     不回写。(HTTP 200 不算覆盖: 无权限时 orgs/{o}/repos 返回 200+仅公开仓；云环境 GitHub 代理也只放挂载仓。)
#     某 owner 确实 0 个私有仓 => 把它写进种子的 owners 即可。
#
# rev4 修复: 去掉写死的私有仓名种子; gh --jq 输出裸字符串(非 JSON)导致 me 永远取不到; user/repos 只翻第 1 页;
#            user/repos 返回的组织仓被错记到 username 下; 路径全部来自 policy.json(bootstrap 只需改写 policy.json)。
import json, subprocess, os, sys, re, urllib.request, urllib.error, time

POLICY = json.load(open('/root/.claude/policy/policy.json', encoding='utf-8'))
CACHE = POLICY['private_cache']
SEED = POLICY.get('private_seed', '/root/.claude/private-seed.json')
EXPECTED = set(POLICY.get('expected_owners', []))
TTL = int(POLICY.get('private_cache_ttl', 300))


def fail(msg):
    print('FAIL: ' + msg, file=sys.stderr); print('FAIL'); sys.exit(1)


# ---------- tokens (环境变量) ----------
def all_tokens():
    """返回 [(环境变量名, token)]。"""
    toks = []
    for k in sorted((k for k in os.environ if re.fullmatch(r'GH_TOKEN_\d+', k)), key=lambda k: int(k.split('_')[-1])):
        v = os.environ.get(k, '').strip()
        if v and v not in [t for _, t in toks]:
            toks.append((k, v))
    t = os.environ.get('GH_TOKEN', '').strip()
    if t and t != 'proxy-injected' and t not in [x for _, x in toks]:   # claude.ai 云环境的占位符不是可用 token
        toks.append(('GH_TOKEN', t))
    return toks


# ---------- GitHub REST via token ----------
def api_once(url, tok):
    try:
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok,
                                                   'Accept': 'application/vnd.github+json',
                                                   'User-Agent': 'refresh-private'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            return 'resolved', json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            try:
                body = e.read().decode('utf-8', 'replace').lower()
            except Exception:
                body = ''
            if e.code == 403 and ('rate limit' in body or e.headers.get('X-RateLimit-Remaining') == '0'):
                return 'error', None                   # 限流不是"看不到"，是失败
            return 'skipped', None
        return 'error', None
    except Exception:
        return 'error', None


def api_retry(url, tok):
    for _ in range(3):
        kind, val = api_once(url, tok)
        if kind != 'error':
            return kind, val
        time.sleep(1)
    return 'error', None


def api_pages(path, tok):
    """翻页拉全部；返回 (kind, list)。任一页 error => error。"""
    out = []
    for page in range(1, 11):                          # ≤1000 仓/owner
        kind, r = api_retry('https://api.github.com/%s%sper_page=100&page=%d' % (path, '&' if '?' in path else '?', page), tok)
        if kind != 'resolved':
            return kind, out
        if not isinstance(r, list):
            return 'error', out
        out.extend(r)
        if len(r) < 100:
            break
    return 'resolved', out


# ---------- gh CLI (best-effort) ----------
def gh_raw(args, timeout=40):
    try:
        r = subprocess.run(['gh', 'api', *args], capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def gh_json(args):
    out = gh_raw(args)
    if out is None:
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


def gh_list(path):
    out = []
    for page in range(1, 11):
        r = gh_json(['%s%sper_page=100&page=%d' % (path, '&' if '?' in path else '?', page),
                     '--jq', '[.[]|{name,full_name,private,fork}]'])
        if not isinstance(r, list):
            return None if page == 1 else out
        out.extend(r)
        if len(r) < 100:
            break
    return out


# ---------- collect ----------
priv, owners, covered, sources, patterns, token_owners = set(), set(), set(), [], [], {}


def collect(items):
    """按 full_name 归属 owner(user/repos 会混着返回组织仓)。私有 fork 与上游同名，跳过以免误伤公开上游。
    返回本批看到私有仓的 owner 集合(用于记录 token -> owners，供 resolve-private 优先选 token)。
    只有"看到了该 owner 至少 1 个私有仓"才算覆盖了这个 owner: GitHub 对无权限的 orgs/{o}/repos 返回 200+仅公开仓，
    对被代理过滤的请求也可能返回 200+部分仓，200 本身不代表拿全了。"""
    seen = set()
    for it in items or []:
        if not isinstance(it, dict) or not it.get('private') or it.get('fork'):
            continue
        full = it.get('full_name') or ''
        if '/' not in full:
            continue
        o, nm = full.split('/', 1)
        priv.add(full); priv.add(nm); owners.add(o); covered.add(o); seen.add(o)
    return seen


# 1) 私有种子(本机文件；没有文件则看环境变量)
seed_text = None
if os.path.isfile(SEED):
    seed_text = open(SEED, encoding='utf-8').read()
elif os.environ.get('GUARD_SEED_B64', '').strip():
    import base64
    try:
        seed_text = base64.b64decode(os.environ['GUARD_SEED_B64'].strip()).decode('utf-8')
    except Exception as e:
        fail('GUARD_SEED_B64 解码失败: %s' % type(e).__name__)
elif os.environ.get('GUARD_SEED_JSON', '').strip():
    seed_text = os.environ['GUARD_SEED_JSON']
if seed_text is not None:
    try:
        s = json.loads(seed_text)
        so = set(map(str, s.get('owners', []))); sp = set(map(str, s.get('private', [])))
        owners |= so; covered |= so; priv |= sp
        patterns = [str(x) for x in s.get('patterns', [])]
        for x in patterns:
            re.compile(x)                                # 坏正则在这里就炸，不进缓存
        for p in sp:
            if '/' in p:
                o, nm = p.split('/', 1); owners.add(o); covered.add(o); priv.add(nm)
        sources.append('seed' if os.path.isfile(SEED) else 'seed-env')
    except Exception as e:
        fail('私有种子解析失败: %s' % type(e).__name__)

# 2) gh CLI
me = (gh_raw(['user', '--jq', '.login']) or '').strip() or None     # --jq 输出裸字符串，不是 JSON
if me:
    owners.add(me)
    orgs = gh_json(['user/memberships/orgs', '--jq', '[.[]|.organization.login]'])
    if isinstance(orgs, list):
        owners.update(o for o in orgs if isinstance(o, str))
    mine = gh_list('user/repos?affiliation=owner')
    if mine is not None:
        collect(mine); sources.append('gh')
for o in sorted(owners):
    if o == me:
        continue
    r = gh_list('orgs/%s/repos?type=all' % o)
    if r is not None:
        collect(r)
        if 'gh' not in sources:
            sources.append('gh')

# 3) tokens(每把都必须成功，任一失败 => 整体失败)
for idx, (envname, tok) in enumerate(all_tokens(), 1):
    seen_here = set()
    kind, u = api_retry('https://api.github.com/user', tok)
    if kind == 'error':
        fail('token #%d 调用 /user 失败(网络/限流/无效)' % idx)
    login = u.get('login') if kind == 'resolved' and isinstance(u, dict) else None
    if login:
        owners.add(login)
    kind, mine = api_pages('user/repos?affiliation=owner', tok)
    if kind == 'error':
        fail('token #%d 枚举 user/repos 失败' % idx)
    if kind == 'resolved':
        seen_here |= collect(mine)
    for o in sorted(owners):
        if o == login:
            continue
        kind, r = api_pages('orgs/%s/repos?type=all' % o, tok)
        if kind == 'error':
            fail('token #%d 枚举 orgs/%s/repos 失败' % (idx, o))
        if kind == 'resolved':
            seen_here |= collect(r)
    token_owners[envname] = sorted(seen_here)
    sources.append('token%d' % idx)

# ---------- 完整性 ----------
if not sources:
    fail('没有任何可用来源(无私有种子、gh 不可用、环境里没有 GH_TOKEN_n)。不回写，缓存保持缺失/陈旧 => 守卫按 ERROR 拦截')
missing = sorted(EXPECTED - covered)
if missing:
    fail('以下 owner 未被任何来源覆盖(种子未列出, gh/token 也没看到它的任何私有仓): %s => 名单不完整，不回写' % ', '.join(missing))

now = time.time()
os.makedirs(os.path.dirname(CACHE), exist_ok=True)
tmp = CACHE + '.tmp'
json.dump({'generated_at': now, 'expires_at': now + TTL, 'status': 'fresh',
           'sources': sources, 'covered_owners': sorted(covered),
           'private': sorted(priv), 'owners': sorted(owners), 'patterns': patterns, 'token_owners': token_owners},
          open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
os.replace(tmp, CACHE)                                   # 原子替换，check.py 不会读到半截文件
print('private=%d owners=%d patterns=%d sources=%s ttl=%ds' % (len(priv), len(owners), len(patterns), '+'.join(sources), TTL))
