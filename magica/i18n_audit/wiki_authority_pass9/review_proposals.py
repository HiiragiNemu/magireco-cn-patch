from __future__ import annotations

import csv
import gzip
import hashlib
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REVIEW = Path(__file__).resolve().parent
PROPOSALS_PATH = ROOT / "work/main/wiki_patch_analysis/proposals.json"
PASS8_DIR = ROOT / "work/main/extract/pass8/magica/js/libs"
BASELINE_DIR = ROOT / "work/main/extract/baseline/magica/js/libs"
DUMP_AUTHORITY = ROOT / "work/main/extract/dump/authority/authority.json"
WIKI_REPO = ROOT / "work/wiki_authority/wiki-data"
WIKI = WIKI_REPO / "data"
SUPPLEMENT = ROOT / "work/wiki_authority/output/pass8_likely_llm_wiki_candidates.tsv"
PAIR_TSV = ROOT / "work/wiki_authority/output/wiki_authority_pairs.tsv"
DOPPEL_EXPECTED = ROOT / "work/wiki_authority/output/pass8_llm_doppel_replacements.json"

KEY_FIELDS = {
    "arenaClassList.json": ("arenaBattleFreeRankClass",),
    "cardList.json": ("cardId",),
    "chapterList.json": ("chapterId",),
    "charaList.json": ("id",),
    "charaMessageList.json": ("charaNo", "messageId"),
    "doppelList.json": ("id",),
    "enemyList.json": ("enemyId",),
    "eventList.json": ("eventId",),
    "eventStoryList.json": ("storyIds",),
    "formationSheetList.json": ("id",),
    "giftList.json": ("id",),
    "itemList.json": ("itemCode",),
    "live2dList.json": ("charaId", "live2dId"),
    "patrolAreaList.json": ("patrolAreaId",),
    "pieceList.json": ("pieceId",),
    "sectionList.json": ("sectionId",),
    "shopItemList.json": ("id",),
}
SEP = {"charaMessageList.json": "|", "live2dList.json": "|"}
EMOTION_METHODS = {
    "wiki_emotion_keyed",
    "wiki_emotion_typed_source",
    "wiki_emotion_typed_fuzzy_zh",
    "wiki_emotion_typed_bipartite",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def index_json(name: str, value):
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    fields = KEY_FIELDS[name]
    sep = SEP.get(name, "")
    return {sep.join(str(row[field]) for field in fields): row for row in value}


def norm(value) -> str:
    value = html.unescape(str(value or ""))
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("＠", "\n")
    value = unicodedata.normalize("NFKC", value).replace("・", "·")
    return re.sub(r"\s+", "", value).strip()


def para(value) -> str:
    value = html.unescape(str(value or "")).replace("\r\n", "\n").replace("\r", "\n").strip()
    value = re.sub(r"[ \t]*\n+[ \t]*", "＠", value)
    return re.sub("＠+", "＠", value)


def split_top(value: str, delim: str = "|"):
    out, start, curly, square, i = [], 0, 0, 0, 0
    while i < len(value):
        if value.startswith("{{", i):
            curly += 1
            i += 2
            continue
        if value.startswith("}}", i):
            curly = max(0, curly - 1)
            i += 2
            continue
        if value.startswith("[[", i):
            square += 1
            i += 2
            continue
        if value.startswith("]]", i):
            square = max(0, square - 1)
            i += 2
            continue
        if value[i] == delim and curly == 0 and square == 0:
            out.append(value[start:i])
            start = i + 1
        i += 1
    out.append(value[start:])
    return out


def extract_outer_params(wikitext: str, marker: str):
    pos = wikitext.find("{{" + marker)
    if pos < 0:
        return {}
    i, depth = pos + 2, 1
    while i < len(wikitext) and depth:
        if wikitext.startswith("{{", i):
            depth += 1
            i += 2
            continue
        if wikitext.startswith("}}", i):
            depth -= 1
            i += 2
            continue
        i += 1
    body = wikitext[pos + 2 : i - 2]
    params = {}
    for segment in split_top(body)[1:]:
        eq, curly, square, j = -1, 0, 0, 0
        while j < len(segment):
            if segment.startswith("{{", j):
                curly += 1
                j += 2
                continue
            if segment.startswith("}}", j):
                curly = max(0, curly - 1)
                j += 2
                continue
            if segment.startswith("[[", j):
                square += 1
                j += 2
                continue
            if segment.startswith("]]", j):
                square = max(0, square - 1)
                j += 2
                continue
            if segment[j] == "=" and curly == 0 and square == 0:
                eq = j
                break
            j += 1
        if eq >= 0:
            params[segment[:eq].strip()] = segment[eq + 1 :].strip()
    return params


def extract_calls(wikitext: str, name: str):
    needle, i = "{{" + name + "|", 0
    while True:
        pos = wikitext.find(needle, i)
        if pos < 0:
            return
        j, depth = pos + 2, 1
        while j < len(wikitext) and depth:
            if wikitext.startswith("{{", j):
                depth += 1
                j += 2
                continue
            if wikitext.startswith("}}", j):
                depth -= 1
                j += 2
                continue
            j += 1
        if depth == 0:
            yield split_top(wikitext[pos + 2 : j - 2])
            i = j
        else:
            return


def git_blob_texts(path: Path):
    out = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            out[row["title"]] = row["wikitext"]
    return out


TEMPLATES = git_blob_texts(WIKI / "archive/templates.jsonl.gz")
ARTICLES = git_blob_texts(WIKI / "archive/articles.jsonl.gz")


def named_call_params(call):
    params = {}
    for segment in call[1:]:
        if "=" in segment:
            key, value = segment.split("=", 1)
            params[key.strip()] = value.strip()
    return params


# Keep the sticker number and image filename in the join: the same Japanese
# location label is intentionally translated differently by sticker #008 and
# #195, so a text-only global match would be ambiguous.
STICKERS = {}
for block in re.findall(
    r"\{\{魔法少女贴纸\s*(.*?)\n\}\}", ARTICLES["魔法少女贴纸"], flags=re.S
):
    params = {}
    for line in block.splitlines():
        match = re.match(r"\s*\|\s*([^=]+?)\s*=\s*(.*?)\s*$", line)
        if match:
            params[match.group(1).strip()] = match.group(2).strip()
    if params.get("编号"):
        STICKERS[params["编号"].zfill(3)] = params

EFFECT = {}
for line in TEMPLATES["Template:效果中文"].splitlines():
    match = re.match(r"\s*\|\s*(.*?)\s*=\s*(.*?)\s*$", line)
    if match and not match.group(1).startswith("#"):
        EFFECT[match.group(1).strip()] = match.group(2).strip()


def render_markup(value, language: str = "zh") -> str:
    text = html.unescape(str(value or "")).strip()
    text = re.sub(r"</?noinclude>", "", text, flags=re.I)
    for _ in range(10):
        old = text
        text = re.sub(
            r"\{\{\s*(?:ruby|Ruby)\s*\|\s*([^|{}]+)(?:\|[^{}]*)?\}\}",
            lambda match: match.group(1).strip(),
            text,
        )

        def effect_replace(match):
            source = match.group(1).strip()
            return EFFECT.get(source, source) if language == "zh" else source

        text = re.sub(
            r"\{\{\s*(?:效果翻译|效果中文)\s*\|\s*([^{}]+?)\s*\}\}",
            effect_replace,
            text,
        )
        text = re.sub(
            r"\{\{\s*翻译\s*\|\s*([^|{}]+)(?:\|[^{}]*)?\}\}",
            lambda match: match.group(1).strip(),
            text,
        )
        if text == old:
            break
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("'''", "").replace("''", "").strip()


def number_signature(value: str):
    pattern = re.compile(r"\d+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+|X(?:V?I{0,3}|I[VX])|∞")
    return Counter(pattern.findall(unicodedata.normalize("NFKC", value)))


def scope_signature(value: str):
    value = unicodedata.normalize("NFKC", value)
    for old, new in [
        ("我方全体", "己全"),
        ("全体友方", "己全"),
        ("友方全体", "己全"),
        ("自身", "自"),
        ("自己", "自"),
        ("敌方单体", "敌单"),
        ("单个敌人", "敌单"),
        ("敌方全", "敌全"),
        ("全体敌人", "敌全"),
    ]:
        value = value.replace(old, new)
    tokens = []
    for group in re.findall(r"[（(]([^）)]*)[）)]", value):
        found = None
        for token in ("己全", "敌全", "敌单", "自", "同伴", "全"):
            if token in group:
                found = token
                break
        if found:
            tokens.append(found)
    # Wiki sometimes uses bare 全 as a shorthand for 己全.
    return Counter("己全" if token == "全" else token for token in tokens)


def structural_issues(value: str):
    issues = []
    if not value:
        issues.append("empty_after")
    if any(mark in value for mark in ("{{", "}}", "[[", "]]", "<!--", "-->", "<noinclude", "<br")):
        issues.append("raw_wiki_or_html_markup")
    if any(unicodedata.category(char).startswith("C") for char in value):
        issues.append("control_or_format_character")
    if value != value.strip():
        issues.append("leading_or_trailing_whitespace")
    if "  " in value:
        issues.append("double_ascii_space")
    # Only flag ordinary ASCII spacing.  U+3000 is deliberately used by a few
    # Wiki strings as a visual layout separator and is not source corruption.
    if re.search(r" +[，。！？；：、）】》」”]", value):
        issues.append("space_before_cjk_punctuation")
    if re.search(r"[，。！？；：、）】》」”] +", value):
        issues.append("space_after_cjk_punctuation")
    if value.startswith("＠") or value.endswith("＠") or "＠＠" in value:
        issues.append("broken_paragraph_marker")
    pairs = (("(", ")"), ("[", "]"), ("（", "）"), ("「", "」"), ("『", "』"), ("【", "】"), ("“", "”"), ("《", "》"))
    imbalance = [(left, right) for left, right in pairs if value.count(left) != value.count(right)]
    # `(ry` is a deliberate abbreviation of 以下略 in memoria 1749.
    if imbalance and "(ry" not in value:
        issues.append("unbalanced_bracket_or_quote")
    return issues


PROPOSALS = load(PROPOSALS_PATH)
PASS8 = {}
BASELINE = {}
PASS8_INDEX = {}
BASELINE_INDEX = {}
for path in sorted(PASS8_DIR.glob("*.json")):
    name = path.name
    PASS8[name] = load(path)
    BASELINE[name] = load(BASELINE_DIR / name)
    PASS8_INDEX[name] = index_json(name, PASS8[name])
    BASELINE_INDEX[name] = index_json(name, BASELINE[name])
DUMP = load(DUMP_AUTHORITY)

MEMORIA = load(WIKI / "memoria.json")
MEMORIA_BY_NUMBER = {}
for record in MEMORIA.values():
    if not isinstance(record, dict) or record.get("number") is None:
        continue
    number = str(record["number"])
    # Some simplified-Chinese redirect/generated pages share a number with the
    # original Japanese-keyed record. Prefer the non-generated, data-rich row.
    richness = sum(bool(record.get(field)) for field in ("name_ja", "desc_zh", "effect", "effect_max"))
    rank = (not record.get("_generated", False), richness)
    old = MEMORIA_BY_NUMBER.get(number)
    old_rank = (
        not old.get("_generated", False),
        sum(bool(old.get(field)) for field in ("name_ja", "desc_zh", "effect", "effect_max")),
    ) if old else (False, -1)
    if rank > old_rank:
        MEMORIA_BY_NUMBER[number] = record
CHARACTERS = load(WIKI / "characters.json")
CHAR_BY_ID = {
    str(record.get("charaId")): record
    for record in CHARACTERS.values()
    if isinstance(record, dict) and record.get("charaId") is not None
}
DOPPELS = load(WIKI / "doppel.json")
DOPPEL_BY_CID = {}
for doppel in DOPPELS.values():
    if not isinstance(doppel, dict):
        continue
    page = doppel.get("character_page") or doppel.get("_page")
    for cid, character in CHAR_BY_ID.items():
        if character.get("_page") == page or character.get("nameZh") == page:
            DOPPEL_BY_CID[cid] = doppel
            break

CHAR_TEMPLATES = {}
for title, wikitext in TEMPLATES.items():
    if title.startswith("Template:角色数据表/") and title.count("/") == 1:
        params = extract_outer_params(wikitext, "角色数据表")
        cid = params.get("编号", "").strip()
        if cid.isdigit():
            CHAR_TEMPLATES[cid] = params

SUPPLEMENT_INDEX = {}
with SUPPLEMENT.open("r", encoding="utf-8-sig", newline="") as handle:
    for row in csv.DictReader(handle, delimiter="\t"):
        SUPPLEMENT_INDEX[(row["target"], row["record_key"], row["field"])] = row

PAIR_INDEX = defaultdict(set)
with PAIR_TSV.open("r", encoding="utf-8-sig", newline="") as handle:
    for row in csv.DictReader(handle, delimiter="\t"):
        PAIR_INDEX[norm(row["ja"])].add(norm(row["zh"]))

EMOTION_PAGES = {}
EMOTION_BY_CID = {}
for title, wikitext in ARTICLES.items():
    if not title.startswith("精神强化/"):
        continue
    match = re.search(r"角色ID\s*=\s*(\d+)", wikitext)
    if not match:
        continue
    head = wikitext.split("{{精神强化技能表单元/表尾}}", 1)[0]
    rows = []
    for row_number, parts in enumerate(extract_calls(head, "精神强化技能表单元"), 1):
        if len(parts) < 4:
            continue
        rows.append(
            {
                "row": row_number,
                "type": "SKILL" if "技能型" in parts[1] else "ABILITY",
                "code": parts[2],
                "ja": render_markup(parts[3], "ja"),
                "zh": render_markup(parts[3], "zh"),
            }
        )
    if rows:
        cid = match.group(1)
        EMOTION_PAGES[title] = {"cid": cid, "rows": rows}
        EMOTION_BY_CID[cid] = {"title": title, "rows": rows}


def emotion_title(proposal):
    evidence = proposal["evidence"]
    return evidence.split(" one-to-one", 1)[0].split(" typed Chinese", 1)[0].split(" overview", 1)[0]


def expected_character_template(proposal):
    key = proposal["key"]
    file = proposal["file"]
    field = proposal["field"]
    cid = key[:4]
    params = CHAR_TEMPLATES.get(cid)
    if not params:
        return None
    suffix = key[4:]
    if file == "cardSkillMap.json" and len(suffix) == 1 and suffix in "12345":
        rank = int(suffix)
        raw = params.get("连携中文") if field == "name" else params.get(f"连携效果{rank}")
    elif file == "cardMagiaMap.json" and len(suffix) == 1 and suffix in "12345":
        rank = int(suffix)
        raw = params.get("magia中文") if field == "name" else params.get(f"magia效果{rank}")
    elif file in {"cardMagiaMap.json", "doppelCardMagiaMap.json"} and suffix == "8":
        raw = params.get("doppel中文") if field == "name" else params.get("doppel效果")
    elif file == "pieceSkillMap.json" and suffix in {"1", "2"}:
        if field == "name":
            raw = params.get("EX技能中文" if suffix == "1" else "EX技能最大中文")
        else:
            raw = params.get("EX技能效果" if suffix == "1" else "EX技能最大效果")
    else:
        return None
    return render_markup(raw, "zh")


KNOWN_HEALTH_EXPECTED = {
    ("pieceList.json", "1490", "description"): "没有任何预兆，大脑和身体里闪过了一丝电流＠这是知识、经验、思考、状况、和其他所有生存能力所带来的＠来自异次元的真理＠“原来如此……所有事情都……完全明白了……！”",
    ("pieceList.json", "1696", "description"): "那一天，偶然和闪耀着光芒的喜欢的情感相会了＠呼吸停止、心脏为了庆祝这次相遇剧烈跳动着＠一瞬间，世界被光与色填满，同时，视野变得一片黑暗＠在渐渐淡薄的意识中最后所见的，是刚刚改变人生的美…",
    ("pieceList.json", "1970", "description"): "“为什么树里大人要去捡垃圾啊……”＠“都怪被出席天数牵着鼻子走的你……”＠“结菜小姐！快看这个！这个铅笔盒好像还能用！”＠“小丽……你可真差劲……不要这么干啊……”",
    ("pieceList.json", "1721", "description"): "Blu-ray&DVD 第3卷 特别绘制封面插图＠（TV动画 2nd SEASON）",
    ("pieceSkillMap.json", "175700", "shortDescription"): "必定雾 & 防御力DOWN[Ⅳ](敌单/1T)",
    ("pieceSkillMap.json", "175701", "shortDescription"): "必定雾 & 防御力DOWN[Ⅴ](敌单/1T)",
}


def validate_source(proposal):
    method = proposal["method"]
    file, key, field = proposal["file"], proposal["key"], proposal["field"]
    after = proposal["after"]
    checks = []
    errors = []

    if method in EMOTION_METHODS:
        title = emotion_title(proposal)
        page = EMOTION_PAGES.get(title)
        if not page:
            errors.append("emotion_page_missing")
            return checks, errors
        if not key.startswith(page["cid"]):
            errors.append("emotion_character_prefix_mismatch")
        hits = [row for row in page["rows"] if norm(row["zh"]) == norm(after)]
        if not hits:
            errors.append("emotion_target_not_on_typed_wiki_page")
        else:
            checks.append("emotion_target_on_typed_wiki_page")
        if method in {"wiki_emotion_keyed", "wiki_emotion_typed_source"}:
            if not any(norm(row["ja"]) == norm(proposal["source_ja"]) for row in page["rows"]):
                errors.append("emotion_exact_source_not_on_page")
            else:
                checks.append("emotion_exact_source_on_page")
        if method == "wiki_emotion_typed_bipartite":
            row_match = re.search(r"row=(\d+)", proposal["evidence"])
            if not row_match:
                errors.append("bipartite_row_evidence_missing")
            else:
                row_number = int(row_match.group(1))
                if not any(row["row"] == row_number and norm(row["zh"]) == norm(after) for row in page["rows"]):
                    errors.append("bipartite_row_evidence_mismatch")
                else:
                    checks.append("bipartite_row_evidence_exact")
        if number_signature(proposal["before"]) != number_signature(after):
            errors.append("emotion_numeric_signature_changed")
        else:
            checks.append("emotion_numeric_signature_preserved")
        if proposal["before"].count("&") != after.count("&"):
            errors.append("emotion_conjunct_count_changed")
        else:
            checks.append("emotion_conjunct_count_preserved")
        if scope_signature(proposal["before"]) != scope_signature(after):
            errors.append("emotion_scope_signature_changed")
        else:
            checks.append("emotion_scope_signature_preserved")
        return checks, errors

    if method == "wiki_character_template_typed_id":
        expected = expected_character_template(proposal)
        if expected is None:
            errors.append("typed_character_template_target_missing")
        elif norm(expected) != norm(after):
            errors.append("typed_character_template_value_mismatch")
        else:
            checks.append("typed_character_id_and_slot_exact")
        return checks, errors

    if method == "wiki_memoria_keyed":
        record = MEMORIA_BY_NUMBER.get(key)
        if not record:
            errors.append("memoria_record_missing")
        else:
            expected = (
                record.get("name_sc") or record.get("name_zh") or record.get("name_tw")
                if field == "pieceName"
                else record.get("desc_zh")
            )
            if norm(expected) != norm(after):
                errors.append("memoria_keyed_value_mismatch")
            else:
                checks.append("memoria_number_and_field_exact")
        return checks, errors

    if method == "wiki_memoria_effect_keyed":
        try:
            number, suffix = str(int(key) // 100), int(key) % 100
        except ValueError:
            errors.append("memoria_effect_key_invalid")
            return checks, errors
        record = MEMORIA_BY_NUMBER.get(number)
        expected = record.get("effect" if suffix == 0 else "effect_max") if record and suffix in {0, 1} else None
        if expected is None:
            errors.append("memoria_effect_record_missing")
        elif norm(expected) != norm(after):
            errors.append("memoria_effect_value_mismatch")
        else:
            checks.append("memoria_effect_piece_id_and_level_exact")
        return checks, errors

    if method == "wiki_doppel_keyed":
        try:
            cid = str(int(key) // 100)
        except ValueError:
            errors.append("doppel_key_invalid")
            return checks, errors
        record = DOPPEL_BY_CID.get(cid)
        mapping = {
            "name": "name_zh",
            "title": "form_zh",
            "description": "description_zh",
        }
        expected = record.get(mapping[field]) if record and field in mapping else None
        if expected is None:
            errors.append("doppel_typed_record_missing")
        elif norm(expected) != norm(after):
            errors.append("doppel_typed_value_mismatch")
        else:
            checks.append("doppel_id_to_character_join_exact")
        return checks, errors

    if method == "doppel_name_consistency_propagation":
        if file not in {"cardMagiaMap.json", "doppelCardMagiaMap.json"} or not key.endswith("8"):
            errors.append("doppel_consistency_target_invalid")
            return checks, errors
        cid = key[:-1]
        record = DOPPEL_BY_CID.get(cid)
        template = CHAR_TEMPLATES.get(cid)
        # The dedicated Doppel page is the canonical keyed source where it
        # exists; the character template is a fallback for the one scene0 row
        # absent from doppel.json.
        expected = record.get("name_zh") if record else None
        if not expected:
            expected = render_markup(template.get("doppel中文"), "zh") if template else None
        expected_group = cid + "00"
        group_match = re.search(r"doppel group=(\d+)", proposal.get("evidence", ""))
        if expected is None:
            errors.append("doppel_consistency_wiki_record_missing")
        elif norm(after) != norm(expected):
            errors.append("doppel_consistency_wiki_name_mismatch")
        else:
            checks.append("doppel_consistency_wiki_name_exact")
        if not group_match or group_match.group(1) != expected_group:
            errors.append("doppel_consistency_group_evidence_mismatch")
        else:
            checks.append("doppel_consistency_group_join_exact")
        return checks, errors

    if method == "wiki_full_exact_review":
        row = SUPPLEMENT_INDEX.get((file, key, field))
        if not row:
            errors.append("full_exact_review_evidence_missing")
        elif row.get("recommended_unique_at_best_priority") != "true":
            errors.append("full_exact_review_not_unique_best_priority")
        elif row.get("official_dump_same_id_field_exact") == "true":
            errors.append("full_exact_review_hits_official_dump_lock")
        elif norm(row.get("recommended_wiki_zh")) != norm(after):
            errors.append("full_exact_review_value_mismatch")
        else:
            checks.append("full_exact_japanese_unique_best_priority")
        return checks, errors

    if method == "wiki_global_unique_exact":
        if norm(proposal["baseline"]) != norm(proposal["source_ja"]):
            errors.append("global_unique_baseline_source_mismatch")
        else:
            checks.append("global_unique_baseline_source_exact")
        pair_hit = norm(after) in PAIR_INDEX.get(norm(proposal["source_ja"]), set())
        # One remaining pair is sourced only from a raw emotion overview row.
        if not pair_hit:
            pair_hit = any(
                norm(row["ja"]) == norm(proposal["source_ja"]) and norm(row["zh"]) == norm(after)
                for page in EMOTION_PAGES.values()
                for row in page["rows"]
            )
        if not pair_hit:
            errors.append("global_unique_wiki_pair_not_reproduced")
        else:
            checks.append("global_unique_wiki_pair_reproduced")
        return checks, errors

    if method == "wiki_context_cross_id_fix":
        if (file, key, field, after) != (
            "itemList.json",
            "EVENT_DAILYTOWER_1160_EXCHANGE_1",
            "name",
            "珍藏的糖果",
        ):
            errors.append("cross_id_fix_unexpected_target")
        else:
            checks.append("cross_id_item_context_exact")
        return checks, errors

    if method == "wiki_context_keyed_sticker":
        sticker = STICKERS.get("195")
        expected_target = (
            "itemList.json",
            "EVENT_DAILYTOWER_1189_STICKER_130300",
            "shortDescription",
        )
        if (file, key, field) != expected_target:
            errors.append("sticker_context_target_mismatch")
        elif not sticker:
            errors.append("sticker_195_wiki_record_missing")
        else:
            image = sticker.get("图片名", "").lower()
            ja = render_markup(sticker.get("出没场所日文"), "ja")
            zh = render_markup(sticker.get("出没场所中文"), "zh")
            if image != "event_dailytower_1189_sticker_130300_l":
                errors.append("sticker_195_image_join_mismatch")
            if norm(proposal.get("source_ja")) != norm(ja):
                errors.append("sticker_195_japanese_value_mismatch")
            if norm(after) != norm(zh):
                errors.append("sticker_195_chinese_value_mismatch")
            if not errors:
                checks.append("sticker_number_image_and_location_exact")
        return checks, errors

    if "health_correction" in method:
        expected = KNOWN_HEALTH_EXPECTED.get((file, key, field))
        if expected is None or after != expected:
            errors.append("health_correction_unrecognized_or_changed")
        else:
            checks.append("source_health_correction_exact")
        return checks, errors

    errors.append("unknown_review_method")
    return checks, errors


def risk_level(proposal):
    method = proposal["method"]
    ratio = float(proposal.get("match_ratio", 1.0))
    if method == "wiki_emotion_typed_bipartite":
        return "medium" if ratio < 0.70 else "low"
    if method == "wiki_emotion_typed_fuzzy_zh":
        return "medium" if ratio < 0.90 else "low"
    if method == "wiki_global_unique_exact":
        return "medium"
    return "low"


proposal_keys = [(row["file"], row["key"], row["field"]) for row in PROPOSALS]
duplicate_targets = {key for key, count in Counter(proposal_keys).items() if count > 1}
reviewed = []
for proposal in PROPOSALS:
    file, key, field = proposal["file"], proposal["key"], proposal["field"]
    target = (file, key, field)
    checks, errors = [], []
    if target in duplicate_targets:
        errors.append("duplicate_proposal_target")
    pass_record = PASS8_INDEX.get(file, {}).get(key)
    baseline_record = BASELINE_INDEX.get(file, {}).get(key)
    if pass_record is None or field not in pass_record:
        errors.append("pass8_target_missing")
    elif pass_record[field] != proposal["before"]:
        errors.append("pass8_before_literal_mismatch")
    else:
        checks.append("pass8_before_literal_exact")
    if baseline_record is None or field not in baseline_record:
        errors.append("baseline_target_missing")
    elif str(baseline_record[field]) != str(proposal["baseline"]):
        errors.append("baseline_literal_mismatch")
    else:
        checks.append("baseline_literal_exact")
    authority_record = DUMP.get(file, {}).get(key, {}) if isinstance(DUMP.get(file, {}), dict) else {}
    if field in authority_record:
        errors.append("official_dump_lock_collision")
    else:
        checks.append("official_dump_lock_clear")
    issues = structural_issues(proposal["after"])
    if issues:
        errors.extend(issues)
    else:
        checks.append("text_structure_healthy")
    source_checks, source_errors = validate_source(proposal)
    checks.extend(source_checks)
    errors.extend(source_errors)
    # 1285 deliberately preserves 真宵's 日常自販機/日常茶飯事 pun.
    special_note = ""
    if file == "pieceList.json" and key == "1285" and field in {"pieceName", "description"}:
        special_note = "INTENTIONAL_PUN: 日常自販機 intentionally rendered 家常便贩; memoria.notes confirms the misreading joke"
        checks.append("intentional_pun_verified_from_memoria_notes")
    decision = "ACCEPT" if not errors else "REJECT"
    reviewed.append(
        {
            "file": file,
            "key": key,
            "field": field,
            "decision": decision,
            "risk_level": risk_level(proposal),
            "method": proposal["method"],
            "score": proposal["score"],
            "match_ratio": f'{float(proposal.get("match_ratio", 1.0)):.9f}',
            "before": proposal["before"],
            "after": proposal["after"],
            "baseline": proposal["baseline"],
            "checks": ";".join(checks),
            "errors": ";".join(errors),
            "evidence": proposal["evidence"],
            "source_ja": proposal["source_ja"],
            "corrected_value": "",
            "note": special_note,
        }
    )


def write_tsv(path: Path, rows):
    fields = [
        "file",
        "key",
        "field",
        "decision",
        "risk_level",
        "method",
        "score",
        "match_ratio",
        "before",
        "after",
        "baseline",
        "checks",
        "errors",
        "evidence",
        "source_ja",
        "corrected_value",
        "note",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


accepted = [row for row in reviewed if row["decision"] == "ACCEPT"]
rejected = [row for row in reviewed if row["decision"] == "REJECT"]
write_tsv(REVIEW / "accepted_review.tsv", accepted)
write_tsv(REVIEW / "rejected_review.tsv", rejected)

# Complete 114-record / 342-field Doppel equivalence check.
expected_bundle = load(DOPPEL_EXPECTED)
proposal_index = {(row["file"], row["key"], row["field"]): row for row in PROPOSALS}
doppel_rows = []
for record in expected_bundle["records"]:
    for field in ("name", "title", "description"):
        expected = record["fields"][field]
        target = ("doppelList.json", expected["doppel_id"], field)
        proposal = proposal_index.get(target)
        change_needed = expected["change_needed"] == "true"
        if change_needed and proposal and norm(proposal["after"]) == norm(expected["new_wiki_runtime"]):
            status = "PROPOSED_CORRECT"
        elif change_needed and proposal:
            status = "PROPOSED_WRONG"
        elif change_needed:
            status = "MISSING_PROPOSAL"
        elif norm(expected["old_pass8"]) == norm(expected["new_wiki_runtime"]):
            status = "ALREADY_EQUIVALENT"
        else:
            status = "UNEXPECTED_EQUIVALENCE_STATE"
        doppel_rows.append(
            {
                "doppel_id": expected["doppel_id"],
                "wiki_page": expected["wiki_page"],
                "field": field,
                "change_needed": str(change_needed).lower(),
                "status": status,
                "old_pass8": expected["old_pass8"],
                "expected_wiki": expected["new_wiki_runtime"],
                "proposal_present": str(proposal is not None).lower(),
                "proposal_method": proposal["method"] if proposal else "",
                "proposed_value": proposal["after"] if proposal else "",
                "japanese_match_method": expected["japanese_match_method"],
                "japanese_similarity": expected["japanese_similarity"],
                "baseline_japanese": expected["baseline_japanese"],
                "wiki_japanese": expected["wiki_japanese"],
                "wiki_source_ref": expected["wiki_source_ref"],
            }
        )

doppel_fields = [
    "doppel_id",
    "wiki_page",
    "field",
    "change_needed",
    "status",
    "old_pass8",
    "expected_wiki",
    "proposal_present",
    "proposal_method",
    "proposed_value",
    "japanese_match_method",
    "japanese_similarity",
    "baseline_japanese",
    "wiki_japanese",
    "wiki_source_ref",
]
with (REVIEW / "doppel_equivalence_report.tsv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=doppel_fields, delimiter="\t")
    writer.writeheader()
    writer.writerows(doppel_rows)

# Three-dictionary Doppel name consistency after applying every proposal.
modified = {(row["file"], row["key"], row["field"]): row["after"] for row in PROPOSALS}
doppel_name_groups = []
for doppel_id, doppel_record in sorted(PASS8_INDEX["doppelList.json"].items(), key=lambda item: int(item[0])):
    cid = str(int(doppel_id) // 100)
    skill_key = cid + "8"
    values = {
        "doppelList": modified.get(("doppelList.json", doppel_id, "name"), doppel_record.get("name")),
        "cardMagiaMap": modified.get(
            ("cardMagiaMap.json", skill_key, "name"),
            PASS8_INDEX["cardMagiaMap.json"].get(skill_key, {}).get("name"),
        ),
        "doppelCardMagiaMap": modified.get(
            ("doppelCardMagiaMap.json", skill_key, "name"),
            PASS8_INDEX["doppelCardMagiaMap.json"].get(skill_key, {}).get("name"),
        ),
    }
    present = {name: value for name, value in values.items() if value is not None}
    doppel_name_groups.append(
        {
            "doppel_id": doppel_id,
            "skill_key": skill_key,
            **values,
            "present_count": len(present),
            "distinct_count": len(set(present.values())),
            "status": "CONSISTENT" if len(present) == 3 and len(set(present.values())) == 1 else "SPLIT_OR_MISSING",
        }
    )
with (REVIEW / "doppel_three_dictionary_consistency.tsv").open("w", encoding="utf-8-sig", newline="") as handle:
    fields = [
        "doppel_id",
        "skill_key",
        "doppelList",
        "cardMagiaMap",
        "doppelCardMagiaMap",
        "present_count",
        "distinct_count",
        "status",
    ]
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
    writer.writeheader()
    writer.writerows(doppel_name_groups)

emotion = [row for row in reviewed if row["method"] in EMOTION_METHODS]
bipartite = [row for row in emotion if row["method"] == "wiki_emotion_typed_bipartite"]
fuzzy = [row for row in emotion if row["method"] == "wiki_emotion_typed_fuzzy_zh"]
global_unique = [row for row in reviewed if row["method"] == "wiki_global_unique_exact"]

summary = {
    "schema": 1,
    "proposal_file": str(PROPOSALS_PATH),
    "proposal_sha256": hashlib.sha256(PROPOSALS_PATH.read_bytes()).hexdigest(),
    "proposal_count": len(PROPOSALS),
    "accepted": len(accepted),
    "rejected": len(rejected),
    "duplicate_targets": len(duplicate_targets),
    "official_dump_lock_collisions": sum("official_dump_lock_collision" in row["errors"] for row in reviewed),
    "by_method": dict(Counter(row["method"] for row in reviewed)),
    "by_risk": dict(Counter(row["risk_level"] for row in reviewed)),
    "emotion": {
        "total": len(emotion),
        "accepted": sum(row["decision"] == "ACCEPT" for row in emotion),
        "fuzzy": len(fuzzy),
        "fuzzy_ratio_min": min((float(row["match_ratio"]) for row in fuzzy), default=None),
        "fuzzy_ratio_below_0_90": sum(float(row["match_ratio"]) < 0.90 for row in fuzzy),
        "bipartite": len(bipartite),
        "bipartite_ratio_min": min((float(row["match_ratio"]) for row in bipartite), default=None),
        "bipartite_ratio_below_0_70": sum(float(row["match_ratio"]) < 0.70 for row in bipartite),
        "numeric_signature_failures": sum("emotion_numeric_signature_changed" in row["errors"] for row in emotion),
        "conjunct_count_failures": sum("emotion_conjunct_count_changed" in row["errors"] for row in emotion),
        "scope_signature_failures": sum("emotion_scope_signature_changed" in row["errors"] for row in emotion),
        "typed_page_membership_failures": sum("emotion_target_not_on_typed_wiki_page" in row["errors"] for row in emotion),
    },
    "global_unique": {
        "total": len(global_unique),
        "accepted": sum(row["decision"] == "ACCEPT" for row in global_unique),
        "baseline_source_failures": sum("global_unique_baseline_source_mismatch" in row["errors"] for row in global_unique),
        "wiki_pair_failures": sum("global_unique_wiki_pair_not_reproduced" in row["errors"] for row in global_unique),
    },
    "llm_doppel_114": {
        "records": len(expected_bundle["records"]),
        "fields": len(doppel_rows),
        "status_counts": dict(Counter(row["status"] for row in doppel_rows)),
        "japanese_match_method_counts": dict(
            Counter(record["match_method"] for record in expected_bundle["records"])
        ),
    },
    "doppel_three_dictionary": {
        "groups": len(doppel_name_groups),
        "all_three_present": sum(row["present_count"] == 3 for row in doppel_name_groups),
        "split_or_missing": sum(row["status"] != "CONSISTENT" for row in doppel_name_groups),
    },
    "intentional_content": {
        "pieceList.json/1285": "INTENTIONAL_PUN: 日常自販機 intentionally rendered 家常便贩; verified by memoria.notes"
    },
    "wiki_commits": {
        "working_head": "42641f87818b37262032fd4dc5d5c756a48fed7a",
        "i18n_reference": "186326575607a98c1f1810fa09ada67016420145",
        "shared_data_tree": "9495350e70fbdbf03970b008c05aa006a823c11d",
    },
}
(REVIEW / "review_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

risks = [
    "# Independent proposal review",
    "",
    f"- Proposal SHA-256: `{summary['proposal_sha256']}`",
    f"- Reviewed: {summary['proposal_count']}",
    f"- Accepted: {summary['accepted']}",
    f"- Rejected: {summary['rejected']}",
    f"- Official dump lock collisions: {summary['official_dump_lock_collisions']}",
    "",
    "## Emotion mapping",
    "",
    f"- Total reviewed: {summary['emotion']['total']}",
    f"- Fuzzy: {summary['emotion']['fuzzy']} (minimum ratio {summary['emotion']['fuzzy_ratio_min']}; below 0.90: {summary['emotion']['fuzzy_ratio_below_0_90']})",
    f"- Bipartite: {summary['emotion']['bipartite']} (minimum ratio {summary['emotion']['bipartite_ratio_min']}; below 0.70: {summary['emotion']['bipartite_ratio_below_0_70']})",
    f"- Numeric signature failures: {summary['emotion']['numeric_signature_failures']}",
    f"- Conjunct-count failures: {summary['emotion']['conjunct_count_failures']}",
    f"- Scope signature failures: {summary['emotion']['scope_signature_failures']}",
    f"- Typed Wiki-page membership failures: {summary['emotion']['typed_page_membership_failures']}",
    "",
    "## Global unique exact",
    "",
    f"- Total reviewed: {summary['global_unique']['total']}",
    f"- Baseline/source exact failures: {summary['global_unique']['baseline_source_failures']}",
    f"- Reproduced Wiki-pair failures: {summary['global_unique']['wiki_pair_failures']}",
    "",
    "## Doppel",
    "",
    f"- LLM set: {summary['llm_doppel_114']['records']} records / {summary['llm_doppel_114']['fields']} fields",
    f"- Equivalence states: `{json.dumps(summary['llm_doppel_114']['status_counts'], ensure_ascii=False)}`",
    f"- Three-dictionary name groups: {summary['doppel_three_dictionary']['groups']}; split or missing: {summary['doppel_three_dictionary']['split_or_missing']}",
    "",
    "## Residual interpretation risks",
    "",
    "- `wiki_emotion_typed_bipartite` remains an inferred one-to-one assignment, but every accepted row is constrained to the same character page and preserves all numeric, conjunction, and scope signatures.",
    "- `wiki_global_unique_exact` is exact on normalized Japanese but has weaker typed context than keyed methods; every accepted row reproduces a unique Wiki pair and passes the target-field checks.",
    "- Wiki community wording is treated as the requested authority even when less polished than the LLM text; this review tests provenance, identity, structure, and alignment rather than stylistic rewriting.",
    "- `pieceList.json/1285` uses `家常便贩` intentionally: `memoria.notes` documents the `日常自販機` / `日常茶飯事` pun.",
    "- Memoria 1749 deliberately retains `(ry`, mirroring the source's internet-slang truncation rather than an unmatched-parenthesis defect.",
    "",
    "## Source identity",
    "",
    "- Working repository HEAD: `42641f87818b37262032fd4dc5d5c756a48fed7a`",
    "- i18n reference branch: `186326575607a98c1f1810fa09ada67016420145`",
    "- Both commits resolve `data/` to tree `9495350e70fbdbf03970b008c05aa006a823c11d`.",
]
(REVIEW / "RISKS.md").write_text("\n".join(risks) + "\n", encoding="utf-8")

artifacts = [
    "accepted_review.tsv",
    "rejected_review.tsv",
    "doppel_equivalence_report.tsv",
    "doppel_three_dictionary_consistency.tsv",
    "review_summary.json",
    "RISKS.md",
    "review_proposals.py",
]
with (REVIEW / "SHA256SUMS.txt").open("w", encoding="ascii", newline="\n") as handle:
    for name in artifacts:
        digest = hashlib.sha256((REVIEW / name).read_bytes()).hexdigest()
        handle.write(f"{digest}  {name}\n")

print(json.dumps(summary, ensure_ascii=False, indent=2))
if rejected:
    raise SystemExit(2)
