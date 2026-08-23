#!/usr/bin/env python3
"""story IR → 魔纪 adv 剧情 json。

    python3 tools/story-import/ir_to_adv.py IR.json \
        --story-id 980101-1 --bg bg_adv_20361.jpg --bgm bgm03_story06 \
        --out madomagi/resource/scenario/json/adv/scenario_9/980101-1.json

产出的文件放进 `madomagi/resource/scenario/json/adv/scenario_<首位数字>/<storyId>.json`，
随 `cn_scenario_update.zip` 下发，由 JS 侧 `nativeCommand.startStory("<storyId>")`
播放。整条链路见同目录 README.md。

## 演出策略（v1，刻意保守）

* 全部塞进 `group_1`，不做分支。IR 也还没有分支。
* 站位：一人居中（pos 1），两人分左右（pos 0 / 2），第三人挤掉最久没说话的那位。
* 表情固定用该模型**确实存在**的一个中性表情（见 magireco_cast.json 的 faces）。
  源作品的表情轨还没解出来，宁可全程一个表情，也不要写一个不存在的 exp3
  文件名——那会让原生播放器加载失败。
* `speaker.cast` 为 null（路人、旁白、合唱）→ 降级成 `narration`。
* 语音一律不写：源语音是 PSP 的 .ahx / Vita 的 .at9，与魔纪 fullvoice 的
  编码和命名都不同，没转码前写了就是加载失败。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from story_ir import IRError, validate          # noqa: E402

CAST_TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'magireco_cast.json')

# 魔纪 ADV 的三个站位 → 文本/姓名字段
POS = {0: ('textLeft', 'nameLeft'), 1: ('textCenter', 'nameCenter'),
       2: ('textRight', 'nameRight')}
SINGLE_POS = 1
PAIR_POS = (0, 2)

# ── 表情阶梯 ────────────────────────────────────────────────────────
#
# 键是 story IR 的表情类别（两个解包仓库产出，语义由文本特征统计得到）；
# 值是魔纪表情编号的**优先顺序**，取该立绘第一个真实存在的。
#
# 魔纪这边每个编号是什么意思，同样是量出来的不是猜的：adv json 里
# tear / cheek / eyeClose / mouthOpen 是独立字段，拿它们与 face 的共现率
# 反推语义（全库 10469 个剧情文件）：
#
#   000/001 各项最低 → 无表情      010 笑 1.7×      → 普通/淡笑
#   011 笑 4.8×      → 笑          013/014 脸红+笑  → 害羞的笑
#   020/021/022 ！35~54% 无笑无泪  → 强调/喊
#   030 …… 37.3% 泪 2.3× 闭眼 1.9× → 困扰/落寞
#   031 泪 21× 脸红 38.5%          → 哭
#   040/042 ？+…… 高、！低         → 疑惑/沉思
#   050/051 ？2.5× 惊 3.8×         → 惊讶
#   060 泪·脸红·闭眼·张嘴·！·悲 六项全显著 → 痛苦
#
# ⚠ 「怒」未解：全库七项特征里怒的信号最高只有 1.2%，找不到对应编号。
#   源侧也没有单独的怒档，所以暂时不需要——真需要时别硬凑一个。
#
# **阶梯必须以 000/001 之类的保底收尾**：写一个该模型没有的 exp3 文件名，
# 原生 ADV 播放器会加载失败，而这种错在 json 里看不出来。
EXPRESSION_LADDER = {
    'neutral':  ('010', '000', '001', '020', '030'),
    'smile':    ('011', '014', '013', '012', '010', '001', '000'),
    'excited':  ('020', '050', '021', '022', '051', '010', '000'),
    'pensive':  ('030', '042', '040', '032', '001', '000'),
    'puzzled':  ('040', '042', '050', '030', '010', '000'),
    'emphasis': ('020', '021', '022', '011', '010', '000'),
}
NEUTRAL_LADDER = EXPRESSION_LADDER['neutral']

MAX_LINES_PER_BOX = 3


def load_cast(path=CAST_TABLE):
    with open(path, encoding='utf-8') as f:
        return json.load(f)['cast']


def pick_face(faces, expression):
    """按阶梯挑一个该立绘**确实存在**的表情文件名；挑不到返回 None。"""
    if not faces:
        return None
    ladder = EXPRESSION_LADDER.get(expression) or NEUTRAL_LADDER
    for code in ladder:
        for f in faces:
            if f.startswith('mtn_ex_%s.' % code):
                return f
    return faces[0]


def pick_model(entry, override=None):
    """选一个立绘 id 与一个确实存在的中性表情。"""
    models = entry.get('models') or []
    if override:
        for m in models + (entry.get('sceneZeroModels') or []):
            if m['id'] == override:
                models = [m]
                break
        else:
            raise IRError('立绘 %s 不在 %s 的可用列表里' % (override, entry.get('nameZh')))
    if not models:
        return None, None
    m = models[0]
    return m['id'], (m.get('faces') or [])


class Stage:
    """维护「台上有谁、站哪」。

    魔纪的 ADV 只有三个站位：0 左 / 1 中 / 2 右。策略：
      第一个人        居中
      第二个人        把居中那位挪到左边，自己站右边
      第三个人        补中间
      第四个人起      挤掉最久没说话的那位（原位淡出，新人接管）
    """

    CENTER = 1
    LEFT, RIGHT = 0, 2

    def __init__(self):
        self.slots = {}          # pos -> cast
        self.order = []          # cast，最近说话的排在最后

    def place(self, cast):
        """返回 (pos, 是否新登场, [(别的角色, 新 pos 或 None 表示淡出)])。"""
        for pos, who in self.slots.items():
            if who == cast:
                self._touch(cast)
                return pos, False, []

        moved = []
        if not self.slots:
            pos = self.CENTER
        elif len(self.slots) == 1:
            (held_pos, held), = self.slots.items()
            if held_pos == self.CENTER:
                self.slots.pop(self.CENTER)
                self.slots[self.LEFT] = held
                moved.append((held, self.LEFT))
                pos = self.RIGHT
            else:
                pos = self.RIGHT if held_pos == self.LEFT else self.LEFT
        elif len(self.slots) == 2:
            pos = next(p for p in (self.CENTER, self.LEFT, self.RIGHT)
                       if p not in self.slots)
        else:
            stale = next(c for c in self.order if c in self.slots.values())
            pos = next(p for p, w in self.slots.items() if w == stale)
            moved.append((stale, None))
            self.order.remove(stale)

        self.slots[pos] = cast
        self._touch(cast)
        return pos, True, moved

    def _touch(self, cast):
        if cast in self.order:
            self.order.remove(cast)
        self.order.append(cast)


def convert(doc, cast_table, bg=None, bgm=None, overrides=None):
    """IR → adv 剧情 json（dict）。返回 (json, warnings)。"""
    warnings = list(validate(doc))
    overrides = overrides or {}
    steps = []
    stage = Stage()
    ids = {}          # cast -> live2d id
    faces = {}        # cast -> 该立绘真实存在的表情清单
    cur_face = {}     # cast -> 当前挂着的表情文件名
    in_narration = False

    for ln in doc['lines']:
        sp = ln.get('speaker') or {}
        cast = sp.get('cast')
        entry = cast_table.get(cast) if cast else None
        text = ln['text'].replace('\r\n', '\n').replace('\r', '\n')
        if text.count('\n') + 1 > MAX_LINES_PER_BOX:
            warnings.append('%s 有 %d 行，魔纪对话框放不下 3 行以上'
                            % (ln['id'], text.count('\n') + 1))
        body = text.replace('\n', '@')
        name = sp.get('name') or ''

        if entry is None or ln['kind'] == 'narration':
            step = {'narration': body}
            if name:
                step['nameNarration'] = name
            if not in_narration:
                step['narrationEffect'] = 'in'
                if bg:
                    step['narrationBg'] = bg
                in_narration = True
            steps.append(step)
            continue

        if cast not in ids:
            ids[cast], faces[cast] = pick_model(entry, overrides.get(cast))
            if ids[cast] is None:
                warnings.append('%s 没有可用立绘，降级成旁白' % cast)
                step = {'narration': body}
                if name:
                    step['nameNarration'] = name
                if not in_narration:
                    step['narrationEffect'] = 'in'
                    in_narration = True
                steps.append(step)
                continue

        want = pick_face(faces[cast], ln.get('expression'))
        pos, entering, moved = stage.place(cast)
        chara = []
        for other, newpos in moved:
            if newpos is None:
                chara.append({'id': ids[other], 'effect': 'fadeout'})
            else:
                chara.append({'id': ids[other], 'pos': newpos})
        me = {'id': ids[cast]}
        if entering:
            me.update({'cheek': 0, 'motion': 0, 'pos': pos})
        # 表情只在**变化时**写，跟真实剧情文件的写法一致（没变就只留 id）
        if want and (entering or cur_face.get(cast) != want):
            me['face'] = want
            cur_face[cast] = want
        chara.append(me)

        tkey, nkey = POS[pos]
        step = {'chara': chara, nkey: name, tkey: body}
        if in_narration:
            step['narrationEffect'] = 'out'
            in_narration = False
        if ln['kind'] == 'monologue':
            step['turnEffect'] = 'thinking'
        steps.append(step)

    if not steps:
        raise IRError('转换后没有任何一步')

    first = steps[0]
    first['turnChangeIn'] = 'fadeIn'
    if bg and 'narrationBg' not in first:
        first['bg'] = bg
    if bgm:
        first['bgm'] = bgm
    steps[-1]['turnChangeOut'] = 'fadeOut'
    if bgm:
        steps[-1]['bgmFadeOut'] = 1

    return {'story': {'group_1': steps}, 'version': 3}, warnings


def check_assets(adv, cast_table):
    """回头检查：写进去的每个 id / face 都得在 magireco_cast.json 里存在。"""
    known = {}
    for entry in cast_table.values():
        for m in (entry.get('models') or []) + (entry.get('sceneZeroModels') or []):
            known[m['id']] = set(m.get('faces') or [])
    problems = []
    for group, steps in adv['story'].items():
        for i, s in enumerate(steps):
            for c in s.get('chara', []):
                cid = c.get('id')
                if cid not in known:
                    problems.append('%s[%d] 立绘 %s 不在映射表里' % (group, i, cid))
                elif c.get('face') and c['face'] not in known[cid]:
                    problems.append('%s[%d] 立绘 %s 没有表情 %s'
                                    % (group, i, cid, c['face']))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ir')
    ap.add_argument('--out', required=True)
    ap.add_argument('--bg', default=None, help='如 bg_adv_20361.jpg')
    ap.add_argument('--bgm', default=None, help='如 bgm03_story06')
    ap.add_argument('--cast-override', action='append', default=[],
                    metavar='CAST=ID', help='换立绘，如 madoka=200100')
    ap.add_argument('--cast-table', default=CAST_TABLE)
    a = ap.parse_args()

    overrides = {}
    for item in a.cast_override:
        k, _, v = item.partition('=')
        overrides[k] = int(v)

    with open(a.ir, encoding='utf-8') as f:
        doc = json.load(f)
    cast = load_cast(a.cast_table)
    adv, warns = convert(doc, cast, a.bg, a.bgm, overrides)
    problems = check_assets(adv, cast)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(adv, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)

    print('写出 %s：%d 步' % (a.out, len(adv['story']['group_1'])))
    for w in warns:
        print('  警告：%s' % w)
    for p in problems:
        print('  ❌ %s' % p)
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
