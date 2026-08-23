"""story IR —— 外部作品剧情导入魔纪的中间格式。

两个解包仓库（PuellaMagia-Pocket / theBattlePentagram）各自把游戏解成这个
格式，本目录的 ir_to_adv.py 再把它转成魔纪的 adv 剧情 json。加一部新作品
只需要再写一个「→ IR」的抽取器，转换与入库这一段不用动。

    {
      "irVersion": 1,
      "source": {"game": "madoka_portable", "unit": "Chapter01/01/00_00",
                 "textLang": "zh-Hans"},
      "title": "……",
      "lines": [
        {
          "id": "1000010",                  源内唯一，用于回溯
          "kind": "dialogue"|"monologue"|"narration",
          "speaker": {"cast": "sayaka",     magireco_cast.json 的键；null = 魔纪没有立绘
                      "name": "美树沙耶香",
                      "sourceId": 1,        源作品里的角色号（排错用）
                      "code": "sa"},
          "text": "第一行\\n第二行",          换行用 \\n，转换器负责换成魔纪的 @
          "voice": "01_0_00010_sa",         源语音名；魔纪没有对应音源时忽略
          "cues": [{"type": "bg", "value": "..."}]   可选演出提示
        }
      ]
    }

`kind` 的落地：
  dialogue   立绘 + 姓名条（textLeft / textCenter / textRight）
  monologue  同上，外加 turnEffect: "thinking"
  narration  无立绘的旁白（narration + nameNarration）
             speaker.cast 为 null 的行会被自动降级成 narration
"""
IR_VERSION = 1
KINDS = ('dialogue', 'monologue', 'narration')


class IRError(ValueError):
    pass


def validate(doc):
    """结构校验。返回警告列表；结构性错误直接抛 IRError。"""
    if not isinstance(doc, dict):
        raise IRError('IR 必须是对象')
    if doc.get('irVersion') != IR_VERSION:
        raise IRError('irVersion 期望 %r，实际 %r' % (IR_VERSION, doc.get('irVersion')))
    src = doc.get('source')
    if not isinstance(src, dict) or not src.get('game') or not src.get('unit'):
        raise IRError('source.game / source.unit 必填')
    lines = doc.get('lines')
    if not isinstance(lines, list) or not lines:
        raise IRError('lines 不能为空')

    warnings = []
    seen = set()
    for i, ln in enumerate(lines):
        where = '%s[%d]' % (src['unit'], i)
        if not isinstance(ln, dict):
            raise IRError('%s 不是对象' % where)
        lid = ln.get('id')
        if not lid:
            raise IRError('%s 缺 id' % where)
        if lid in seen:
            raise IRError('%s id 重复：%s' % (where, lid))
        seen.add(lid)
        if ln.get('kind') not in KINDS:
            raise IRError('%s kind 非法：%r' % (where, ln.get('kind')))
        if not isinstance(ln.get('text'), str):
            raise IRError('%s text 必须是字符串' % where)
        if not ln['text'].strip():
            warnings.append('%s text 为空' % where)
        sp = ln.get('speaker') or {}
        if not isinstance(sp, dict):
            raise IRError('%s speaker 必须是对象' % where)
        if ln['kind'] != 'narration' and not sp.get('cast') and not sp.get('name'):
            warnings.append('%s 既没有 cast 也没有 name，会退化成无名旁白' % where)
    return warnings
