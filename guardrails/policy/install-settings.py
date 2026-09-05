#!/usr/bin/env python3
# install-settings.py [target-settings.json] [--exclude-untracked]
#   幂等地把护栏 hooks + attribution.sessionUrl=false 合并进一个 settings.json：
#   * 不给路径 => ~/.claude/settings.json(本机 CLI 用户级)
#   * 给 <repo>/.claude/settings.json => 仓库级(云端唯一会读的 Claude hooks 来源)。--exclude-untracked: 文件若未被 git 跟踪，
#     写进 .git/info/exclude，不污染 git status(仓库里已经提交了护栏 settings 的，按脚本名去重，不会装第二遍)。
# 保留已有 env/permissions/model 等，只增量加 hooks；去重按脚本**文件名**(路径不同也算已装)。
# rev4: 补上旧版漏掉的 forbid-read-secret.sh(旧版只装了 3 个，shipped settings.json 有 4 个)；新增 forbid-tamper.sh；
#       Write|Edit 扩到 NotebookEdit；`if` 放宽为 Bash(git *)(if 是 best-effort 过滤，脚本内部再精确判断)；
#       hook timeout 120s(Claude hook 路径已不联网，120s 只是给大文件正则扫描留余量；hook 超时 = 无决策 = 放行，timeout 必须大于内部最慢路径)。
# 注意: Anthropic 托管的 claude.ai 云会话**不读** ~/.claude/settings.json(只读仓库 .claude/settings.json 与组织托管设置)，
#       本脚本只对本机 CLI 部署有效。云部署见 README「需你决定」#1。
import json, os, sys, subprocess
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
SET = os.path.abspath(ARGS[0]) if ARGS else os.path.expanduser('~/.claude/settings.json')
EXCLUDE_UNTRACKED = '--exclude-untracked' in sys.argv
H = '/root/.claude/hooks'

def cmd(name, timeout=120):
    return {"type": "command", "command": "bash %s/%s" % (H, name), "timeout": timeout}

HOOKS = {
  "PreToolUse": [
    {"matcher": "Write|Edit|NotebookEdit", "hooks": [cmd("forbid-content.sh")]},
    {"matcher": "Bash", "hooks": [dict(cmd("forbid-commit.sh"), **{"if": "Bash(git *)"})]},
    {"matcher": "Bash", "hooks": [dict(cmd("forbid-push.sh"), **{"if": "Bash(git *)"})]},
    {"matcher": "Bash", "hooks": [cmd("forbid-read-secret.sh", 30)]},
    {"matcher": "Bash", "hooks": [cmd("forbid-tamper.sh", 30)]},
  ],
  "SessionStart": [
    {"hooks": [{"type": "command", "command": "python3 %s/refresh-private.py" % H, "timeout": 120,
                "statusMessage": "刷新全所有者私有仓并集"}]},
  ],
}
ATTRIB = {"sessionUrl": False}

def load():
    try:
        return json.load(open(SET, encoding='utf-8'))
    except Exception:
        return {}

def has_cmd(d, event, c):
    want = os.path.basename(c.split()[-1])
    for grp in d.get('hooks', {}).get(event, []):
        for h in grp.get('hooks', []):
            toks = h.get('command', '').split()
            if toks and os.path.basename(toks[-1]) == want:
                return True
    return False


def git_exclude_if_untracked(path):
    """仓库级文件未被跟踪时写进 .git/info/exclude(本地忽略，不进提交)。"""
    d = os.path.dirname(path)
    try:
        top = subprocess.run(['git', '-C', d, 'rev-parse', '--show-toplevel'], capture_output=True, text=True, timeout=10)
        if top.returncode != 0:
            return
        top = top.stdout.strip()
        tracked = subprocess.run(['git', '-C', top, 'ls-files', '--error-unmatch', os.path.relpath(path, top)],
                                 capture_output=True, timeout=10).returncode == 0
        if tracked:
            return
        gitdir = subprocess.run(['git', '-C', top, 'rev-parse', '--git-path', 'info/exclude'], capture_output=True, text=True, timeout=10).stdout.strip()
        excl = os.path.join(top, gitdir) if not os.path.isabs(gitdir) else gitdir
        rel = '/' + os.path.relpath(path, top).replace(os.sep, '/')
        os.makedirs(os.path.dirname(excl), exist_ok=True)
        cur = open(excl, encoding='utf-8').read() if os.path.isfile(excl) else ''
        if rel not in cur.splitlines():
            open(excl, 'a', encoding='utf-8').write(('' if cur.endswith('\n') or not cur else '\n') + rel + '\n')
    except Exception:
        pass

def main():
    d = load()
    hv = d.setdefault('hooks', {})
    for event, groups in HOOKS.items():
        hv.setdefault(event, [])
        for grp in groups:
            if not has_cmd(d, event, grp['hooks'][0]['command']):
                hv[event].append(grp)
    a = d.setdefault('attribution', {})
    for k, v in ATTRIB.items():
        if a.get(k) != v:
            a[k] = v
    before = json.dumps(load(), sort_keys=True)
    if json.dumps(d, sort_keys=True) == before:
        print('%s 已含护栏 hooks，未改动' % SET)
    else:
        os.makedirs(os.path.dirname(SET), exist_ok=True)
        tmp = SET + '.tmp'
        json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        open(tmp, 'a', encoding='utf-8').write('\n')
        os.replace(tmp, SET)
        if SET.startswith(os.path.expanduser('~/.claude/')):
            try:
                os.chmod(SET, 0o600)
            except Exception:
                pass
        print('%s 已注入护栏 hooks（幂等）; PreToolUse=%d SessionStart=%d' %
              (SET, len(hv.get('PreToolUse', [])), len(hv.get('SessionStart', []))))
    if EXCLUDE_UNTRACKED:
        git_exclude_if_untracked(SET)

main()
