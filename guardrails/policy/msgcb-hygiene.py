# 消息卫生: 会话链接/型号档位/私有仓名/TOKEN/域名 -> 中性化。用法: git filter-repo --message-callback "$(cat msgcb-hygiene.py)"
# rev4: 私有仓名→中性名 的映射不再内嵌在本文件(本文件随包分发)，改读本机 sanitize-map.json(与私有种子放一起，不分发):
#   {"magireco\\.moe": "wiki-source", "<私有仓名>": "<中性名>", ...}   # key 是正则(re.I)，按文件顺序依次替换
# 注意: 映射表里若有 前缀键→'xxx-'(带尾横线) 的条目，裸名命中时会留下悬空横线("<名> is down" -> "xxx- is down")，请自查顺序与尾横线。
import re, json, os
_MAP = os.environ.get('SANITIZE_MAP', '/root/.claude/sanitize-map.json')
_model = re.compile(r'Claude[ -]?[A-Za-z]{1,8}[ -]?[0-9]+(?:\.[0-9]+)?|claude-[0-9]+(?:\.[0-9]+)?', re.I)
_sess_url = re.compile(r'https?://claude\.ai[/A-Za-z0-9_-]*session_[A-Za-z0-9]+')
_sessline = re.compile(r'Claude-Session:[^\n]*', re.I)
_claudeai = re.compile(r'claude\.ai', re.I)
try:
    _priv = json.load(open(_MAP, encoding='utf-8'))
except Exception as _e:
    raise SystemExit('sanitize-map.json 不可用(%s): %s —— 拒绝在没有映射表的情况下改写历史' % (_MAP, _e))
m = message.decode('utf-8', 'replace')
m = _sess_url.sub('', m); m = _sessline.sub('', m); m = _claudeai.sub('', m)
m = _model.sub('Claude', m)
for k, v in _priv.items():
    m = re.sub(k, v, m, flags=re.I)
return m.encode('utf-8')
