#!/usr/bin/env python3
"""tools/story-import 的自检。

    python3 tools/story-import/test_ir_to_adv.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ir_to_adv                              # noqa: E402
from story_ir import IRError, validate        # noqa: E402


def line(i, cast, name, text, kind='dialogue', expression=None):
    return {'id': str(i), 'kind': kind, 'text': text, 'voice': '', 'cues': [],
            'expression': expression,
            'speaker': {'cast': cast, 'name': name, 'sourceId': 0, 'code': ''}}


def doc(lines):
    return {'irVersion': 1, 'title': 't', 'lines': lines,
            'source': {'game': 'madoka_portable', 'unit': 'u', 'textLang': 'zh-Hans'}}


CAST = ir_to_adv.load_cast()


class TestIRValidation(unittest.TestCase):
    def test_rejects_duplicate_ids(self):
        d = doc([line(1, 'madoka', '圆', 'a'), line(1, 'sayaka', '沙', 'b')])
        with self.assertRaises(IRError):
            validate(d)

    def test_rejects_bad_kind(self):
        d = doc([line(1, 'madoka', '圆', 'a', kind='sing')])
        with self.assertRaises(IRError):
            validate(d)

    def test_warns_on_empty_text(self):
        d = doc([line(1, 'madoka', '圆', '   ')])
        self.assertTrue(any('text 为空' in w for w in validate(d)))


class TestStage(unittest.TestCase):
    def test_first_speaker_centered(self):
        st = ir_to_adv.Stage()
        self.assertEqual(st.place('a')[0], 1)

    def test_second_speaker_splits_left_right(self):
        st = ir_to_adv.Stage()
        st.place('a')
        pos, entering, moved = st.place('b')
        self.assertEqual((pos, entering), (2, True))
        self.assertEqual(moved, [('a', 0)])

    def test_third_speaker_takes_center(self):
        st = ir_to_adv.Stage()
        st.place('a')
        st.place('b')
        pos, _, moved = st.place('c')
        self.assertEqual(pos, 1)
        self.assertEqual(moved, [])

    def test_fourth_speaker_evicts_least_recent(self):
        st = ir_to_adv.Stage()
        st.place('a')          # a 中 → 后被挪到左
        st.place('b')          # b 右
        st.place('c')          # c 中
        pos, _, moved = st.place('d')
        self.assertEqual(moved, [('a', None)])   # a 最久没说话
        self.assertEqual(pos, 0)

    def test_returning_speaker_does_not_re_enter(self):
        st = ir_to_adv.Stage()
        st.place('a')
        st.place('b')
        pos, entering, moved = st.place('a')
        self.assertEqual((pos, entering, moved), (0, False, []))


class TestConvert(unittest.TestCase):
    def test_basic_shape(self):
        d = doc([line(1, 'madoka', '鹿目圆', '第一行\n第二行'),
                 line(2, 'homura', '晓美焰', '回答')])
        adv, warns = ir_to_adv.convert(d, CAST, bg='bg_adv_20361.jpg',
                                       bgm='bgm03_story06')
        self.assertEqual(adv['version'], 3)
        steps = adv['story']['group_1']
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]['bg'], 'bg_adv_20361.jpg')
        self.assertEqual(steps[0]['turnChangeIn'], 'fadeIn')
        self.assertEqual(steps[-1]['turnChangeOut'], 'fadeOut')
        self.assertEqual(steps[0]['textCenter'], '第一行@第二行')
        self.assertEqual(steps[0]['nameCenter'], '鹿目圆')

    def test_newline_becomes_at_sign(self):
        d = doc([line(1, 'madoka', '圆', 'a\nb\nc')])
        adv, _ = ir_to_adv.convert(d, CAST)
        self.assertEqual(adv['story']['group_1'][0]['textCenter'], 'a@b@c')

    def test_warns_when_box_overflows(self):
        d = doc([line(1, 'madoka', '圆', 'a\nb\nc\nd')])
        _, warns = ir_to_adv.convert(d, CAST)
        self.assertTrue(any('放不下' in w for w in warns))

    def test_monologue_gets_thinking_effect(self):
        d = doc([line(1, 'homura', '晓美焰', '（怎么回事）', kind='monologue')])
        adv, _ = ir_to_adv.convert(d, CAST)
        self.assertEqual(adv['story']['group_1'][0]['turnEffect'], 'thinking')

    def test_castless_speaker_becomes_narration(self):
        d = doc([line(1, None, '路人', '喂'), line(2, 'madoka', '圆', '嗯')])
        adv, _ = ir_to_adv.convert(d, CAST)
        steps = adv['story']['group_1']
        self.assertEqual(steps[0]['narration'], '喂')
        self.assertEqual(steps[0]['nameNarration'], '路人')
        self.assertEqual(steps[0]['narrationEffect'], 'in')
        self.assertEqual(steps[1]['narrationEffect'], 'out')

    def test_no_voice_is_emitted(self):
        """源语音格式与魔纪 fullvoice 不兼容，写进去只会加载失败。"""
        d = doc([line(1, 'madoka', '圆', 'a')])
        d['lines'][0]['voice'] = '01_0_00010_md'
        adv, _ = ir_to_adv.convert(d, CAST)
        step = adv['story']['group_1'][0]
        self.assertNotIn('voice', step)
        self.assertNotIn('voiceFull', step)


class TestExpression(unittest.TestCase):
    def _faces(self, cast):
        return CAST[cast]['models'][0]['faces']

    def test_ladder_picks_first_available(self):
        f = self._faces('madoka')
        self.assertEqual(ir_to_adv.pick_face(f, 'smile'), 'mtn_ex_011.exp3.json')
        self.assertEqual(ir_to_adv.pick_face(f, 'puzzled'), 'mtn_ex_040.exp3.json')

    def test_ladder_falls_back_when_preferred_absent(self):
        """晓美焰 200200 没有 mtn_ex_010，neutral 必须退到梯子里下一个。"""
        f = self._faces('homura')
        self.assertNotIn('mtn_ex_010.exp3.json', f)
        self.assertEqual(ir_to_adv.pick_face(f, 'neutral'), 'mtn_ex_000.exp3.json')

    def test_unknown_expression_falls_back_to_neutral_ladder(self):
        f = self._faces('madoka')
        self.assertEqual(ir_to_adv.pick_face(f, None),
                         ir_to_adv.pick_face(f, 'neutral'))
        self.assertEqual(ir_to_adv.pick_face(f, '没这个类别'),
                         ir_to_adv.pick_face(f, 'neutral'))

    def test_faceless_model_returns_none(self):
        """丘比 810000 一个 exp3 都没有——必须返回 None 而不是编一个。"""
        self.assertIsNone(ir_to_adv.pick_face(self._faces('kyubey'), 'smile'))

    def test_every_ladder_resolves_for_every_cast(self):
        """阶梯必须对每个角色的每个类别都能落到一个真实存在的文件。"""
        for key, entry in CAST.items():
            faces = (entry['models'][0].get('faces') or [])
            if not faces:
                continue
            for cls in ir_to_adv.EXPRESSION_LADDER:
                got = ir_to_adv.pick_face(faces, cls)
                self.assertIn(got, faces, '%s / %s' % (key, cls))

    def test_face_written_only_on_change(self):
        d = doc([line(1, 'madoka', '圆', 'a', expression='smile'),
                 line(2, 'madoka', '圆', 'b', expression='smile'),
                 line(3, 'madoka', '圆', 'c', expression='puzzled')])
        steps = ir_to_adv.convert(d, CAST)[0]['story']['group_1']
        self.assertEqual(steps[0]['chara'][0]['face'], 'mtn_ex_011.exp3.json')
        self.assertNotIn('face', steps[1]['chara'][0])      # 没变就不写
        self.assertEqual(steps[2]['chara'][0]['face'], 'mtn_ex_040.exp3.json')


class TestAssetGuard(unittest.TestCase):
    def test_generated_faces_all_exist(self):
        d = doc([line(i, c, 'x', 'y', expression='smile') for i, c in
                 enumerate(['madoka', 'sayaka', 'mami', 'kyoko', 'homura',
                            'kyubey', 'hitomi', 'kyousuke', 'saotome', 'junko'])])
        adv, _ = ir_to_adv.convert(d, CAST)
        self.assertEqual(ir_to_adv.check_assets(adv, CAST), [])

    def test_guard_catches_a_bogus_face(self):
        adv = {'story': {'group_1': [
            {'chara': [{'id': 200101, 'face': 'mtn_ex_999.exp3.json'}]}]}}
        self.assertTrue(ir_to_adv.check_assets(adv, CAST))

    def test_kyubey_has_no_face_key(self):
        """810000 没有任何 exp3 文件，写 face 就是加载失败。"""
        d = doc([line(1, 'kyubey', '丘比', '要不要签契约')])
        adv, _ = ir_to_adv.convert(d, CAST)
        self.assertNotIn('face', adv['story']['group_1'][0]['chara'][0])

    def test_override_must_be_a_known_model(self):
        d = doc([line(1, 'madoka', '圆', 'a')])
        with self.assertRaises(IRError):
            ir_to_adv.convert(d, CAST, overrides={'madoka': 999999})
        adv, _ = ir_to_adv.convert(d, CAST, overrides={'madoka': 210500})
        self.assertEqual(adv['story']['group_1'][0]['chara'][0]['id'], 210500)


if __name__ == '__main__':
    unittest.main(verbosity=2)
