#!/usr/bin/env python3
# resolve-private.py — R1 补充：对"缓存里没有、但长得像仓库名(xxx-xxx)"的裸名做单名可见性查询。
#   用法: resolve-private.py <name>...      name = 裸名(如 foo-bar) 或 owner/repo
#   输出: 一行 JSON {name: {"status": private|public|absent|error, "owner": "..."}}；总是 exit 0，结果看 status。
# 由 check.py --net 调用(git 钩子 / scan-repo)。Claude hook 路径不走网络，不会调用它。
# 语义(与 refresh 一致，只读环境变量 GH_TOKEN_n):
#   * 裸名对缓存/种子里的每个 owner 逐个查 GET /repos/{owner}/{name}；优先用 refresh 记录的"该 owner 对应的 token"。
#   * 200 -> private/public；404/403 -> 该 token 看不到，换下一把；网络/5xx/超时 -> 重试 1 次后算 error。
#   * 所有 token 都 404 -> absent(不是任何已知 owner 的私有仓 => 放行)。没有任何 token 且 gh 也失败 -> error(拦)。
#   * 结果写入 <private_cache>.resolve.json 负缓存: public/absent 24h，private 也 24h(下一次 refresh 会把它并进正式名单)。
import sys, os, re, json, time, subprocess, urllib.request, urllib.error

POLICY = json.load(open('/root/.claude/policy/policy.json', encoding='utf-8'))
CACHE = POLICY['private_cache']; NEG = CACHE + '.resolve.json'
SEED = POLICY.get('private_seed', '')
NEG_TTL = int(POLICY.get('resolve_cache_ttl', 86400))
PER_CALL_TIMEOUT = 3


def load(path):
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return {}


def tokens():
    out = {}
    for k in sorted((k for k in os.environ if re.fullmatch(r'GH_TOKEN_\d+', k)), key=lambda k: int(k.split('_')[-1])):
        v = os.environ.get(k, '').strip()
        if v:
            out[k] = v
    t = os.environ.get('GH_TOKEN', '').strip()
    if t and t != 'proxy-injected':
        out['GH_TOKEN'] = t
    return out


def api(owner, repo, tok):
    for attempt in range(2):
        try:
            req = urllib.request.Request('https://api.github.com/repos/%s/%s' % (owner, repo),
                                         headers={'Authorization': 'Bearer ' + tok, 'Accept': 'application/vnd.github+json',
                                                  'User-Agent': 'resolve-private'})
            with urllib.request.urlopen(req, timeout=PER_CALL_TIMEOUT) as resp:
                return 'private' if json.load(resp).get('private') else 'public'
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                if e.code == 403 and e.headers.get('X-RateLimit-Remaining') == '0':
                    return 'error'
                return 'skip'
            if attempt == 0:
                time.sleep(0.5); continue
            return 'error'
        except Exception:
            if attempt == 0:
                time.sleep(0.5); continue
            return 'error'
    return 'error'


def gh_api(owner, repo):
    try:
        r = subprocess.run(['gh', 'api', 'repos/%s/%s' % (owner, repo), '--jq', '.private'],
                           capture_output=True, text=True, timeout=8)
        if r.returncode == 0 and r.stdout.strip() in ('true', 'false'):
            return 'private' if r.stdout.strip() == 'true' else 'public'
        if r.returncode != 0 and ('404' in r.stderr or 'Not Found' in r.stderr):
            return 'skip'
    except Exception:
        pass
    return 'error'


def resolve_one(name, owners, toks, token_owners):
    if '/' in name:
        o, repo = name.split('/', 1); owners = [o]
    else:
        repo = name
    any_error = False; any_public = None
    for o in owners:
        mapped = [k for k in toks if o in token_owners.get(k, [])]
        order = mapped or list(toks)                     # 该 owner 有专属 PAT 时只问它: 它的 404 就是权威答案
        got = None
        for k in order:
            r = api(o, repo, toks[k])
            if r in ('private', 'public'):
                got = r; break
            if r == 'error':
                any_error = True
        if got is None and not toks:
            r = gh_api(o, repo)
            if r in ('private', 'public'):
                got = r
            elif r == 'error':
                any_error = True
        if got == 'private':
            return {'status': 'private', 'owner': o}
        if got == 'public':
            any_public = o
    if any_error:
        return {'status': 'error', 'owner': ''}
    return {'status': 'public', 'owner': any_public} if any_public else {'status': 'absent', 'owner': ''}


def main(names):
    cache = load(CACHE); seed = load(SEED) if SEED else {}
    owners = sorted(set(cache.get('owners', [])) | set(cache.get('covered_owners', [])) | set(seed.get('owners', [])))
    token_owners = cache.get('token_owners', {})
    toks = tokens()
    neg = load(NEG); now = time.time(); out = {}
    for n in names:
        key = n.casefold()
        e = neg.get(key)
        if isinstance(e, dict) and now - e.get('ts', 0) < NEG_TTL:
            out[n] = {'status': e['status'], 'owner': e.get('owner', ''), 'cached': True}; continue
        if not owners:
            out[n] = {'status': 'error', 'owner': '', 'note': 'no owners known'}; continue
        r = resolve_one(n, owners, toks, token_owners)
        out[n] = r
        if r['status'] != 'error':
            neg[key] = {'status': r['status'], 'owner': r.get('owner', ''), 'ts': now}
    try:
        neg = {k: v for k, v in neg.items() if now - v.get('ts', 0) < NEG_TTL}
        tmp = NEG + '.tmp'; json.dump(neg, open(tmp, 'w', encoding='utf-8')); os.replace(tmp, NEG)
    except Exception:
        pass
    print(json.dumps(out, ensure_ascii=False))


main([a for a in sys.argv[1:] if a and not a.startswith('--')])
