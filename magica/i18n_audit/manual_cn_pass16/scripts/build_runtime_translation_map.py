#!/usr/bin/env python3
"""Build the reviewed Pass16 runtime translation map from the frozen audit input."""

from __future__ import annotations

import csv
from pathlib import Path


AUDIT = Path(__file__).resolve().parents[1]
SOURCE = AUDIT / "source_evidence" / "runtime_candidates_classified.tsv"
AUTHORITY = AUDIT / "source_evidence" / "runtime_authority_lookup_148.tsv"
OUTPUT = AUDIT / "runtime_translation_map.tsv"


EXACT = {
    "七色夏模様": "七色夏日景象",
    "主页背景「七色夏模様」。": "主页背景「七色夏日景象」。",
    "背景「七色夏模様」": "背景「七色夏日景象」",
    "仏罰！": "佛罚！",
    "喫茶店": "咖啡店",
    "安寧―Peace―": "安宁―Peace―",
    "我慢我慢我慢…追跡": "忍耐忍耐忍耐…追踪",
    "水場": "水边",
    "水鉄砲": "水枪",
    "永遠的刻": "永远之刻",
    "準備完了": "准备完毕",
    "私服(日本語)": "便服（日语）",
    "魔法少女(日本語)": "魔法少女（日语）",
    "魔法少女(葉月)": "魔法少女（叶月）",
    "窮地級": "绝境级",
    "困難級": "困难级",
    "绝望級": "绝望级",
    "銀幕衣装": "银幕服装",
    "調整屋": "调整屋",
    "調整屋硬币": "调整屋硬币",
    "好評配信中": "好评发布中",
    "好評配信中！": "好评发布中！",
    "引縄批根": "引绳批根",
    "桜前線急上昇": "樱花前线急速上升",
    "究極VS至高": "究极VS至高",
    "裏方独演会": "后台个人演出",
    "粛清天使": "肃清天使",
    "路地裏": "小巷",
    "橋": "桥",
    "霧峰村": "雾峰村",
    "霧峰村、神滨市": "雾峰村、神滨市",
    "現代神滨篇": "现代神滨篇",
    "現代神滨編": "现代神滨篇",
    "神滨大運動会": "神滨大运动会",
    "时女拾遺物語": "时女拾遗物语",
    "主页背景「时女拾遺物語」。": "主页背景「时女拾遗物语」。",
    "主页背景「神滨大運動会」。": "主页背景「神滨大运动会」。",
    "背景「时女拾遺物語」": "背景「时女拾遗物语」",
    "背景「神滨大運動会」": "背景「神滨大运动会」",
    "神滨市営霊园": "神滨市营陵园",
    "汤国市駅": "汤国市站",
    "緑地公园": "绿地公园",
    "海香的觉醒書": "海香的觉醒书",
    "可兑换専用在商店泳装衣装的券": "可在商店兑换泳装服装的专用券",
}

CHAR_REPLACEMENTS = (
    ("特別", "特别"),
    ("宮", "宫"),
    ("涼", "凉"),
    ("飾", "饰"),
    ("潤", "润"),
    ("恵", "惠"),
    ("世紀", "世纪"),
    ("紀", "纪"),
    ("馬", "马"),
    ("銀", "银"),
    ("銅", "铜"),
    ("異常", "异常"),
    ("瀕死", "濒死"),
    ("上昇", "提升"),
    ("敵単", "敌单"),
    ("敌単", "敌单"),
    ("交換", "兑换"),
    ("運動会", "运动会"),
    ("拾遺物語", "拾遗物语"),
    ("慟哭", "恸哭"),
    ("撫", "抚"),
    ("優", "优"),
    ("難", "难"),
    ("鈴", "铃"),
    ("寧", "宁"),
    ("塚", "冢"),
    ("縄", "绳"),
    ("遠", "远"),
    ("現代", "现代"),
    ("神浜", "神滨"),
    ("駿", "骏"),
    ("純", "纯"),
    ("綾", "绫"),
    ("詩", "诗"),
    ("謹賀", "谨贺"),
    ("遊佐", "游佐"),
    ("遊", "游"),
    ("葉", "叶"),
    ("涼", "凉"),
    ("第2部登場", "第2部登场"),
    ("専用", "专用"),
    ("連扭蛋", "连扭蛋"),
    ("第5話", "第5话"),
    ("日本語", "日语"),
)


def translate(text: str) -> str:
    if text in EXACT:
        return EXACT[text]
    out = text
    for old, new in CHAR_REPLACEMENTS:
        out = out.replace(old, new)
    if out.startswith("全体編 "):
        out = out.replace("全体編 ", "全体篇 第", 1).replace("話", "话")
    if out.startswith("时女一族編 "):
        out = out.replace("时女一族編 ", "时女一族篇 第", 1).replace("話", "话")
    out = out.replace("状態异常耐性", "状态异常耐性")
    out = out.replace("状态異常耐性", "状态异常耐性")
    out = out.replace("防御力上昇", "防御力提升")
    out = out.replace("攻撃", "攻击")
    out = out.replace("調整屋", "调整屋")
    out = out.replace("神滨时空運動会", "神滨时空运动会")
    out = out.replace("第2節", "第2节")
    out = out.replace("史乃 沙優希", "史乃 沙优希").replace("史乃沙優希", "史乃沙优希")
    out = out.replace("南津 涼子", "南津 凉子").replace("南津涼子", "南津凉子")
    out = out.replace("恵 萌花", "惠 萌花").replace("恵萌花", "惠萌花")
    out = out.replace("飾利 潤", "饰利 润").replace("飾利潤", "饰利润")
    out = out.replace("宮尾时雨", "宫尾时雨")
    out = out.replace("篠目约鹤", "篠目夜鹤")
    out = out.replace("神原 駿河", "神原 骏河")
    out = out.replace("純 美雨", "纯 美雨")
    out = out.replace("綾野 梨花", "绫野 梨花")
    out = out.replace("遊佐 葉月", "游佐 叶月")
    out = out.replace("詩音 千里", "诗音 千里")
    out = out.replace("天乃鈴音", "天乃铃音")
    out = out.replace("水鉄砲", "水枪")
    out = out.replace("銀幕衣装", "银幕服装")
    out = out.replace("3世紀日本 邪馬台国", "3世纪日本 邪马台国")
    # National-server punctuation convention for parenthetical item/costume labels.
    if "DX福袋(" in out:
        out = out.rstrip("\t").replace("(", "（").replace(")", "）")
    return out


OFFICIAL_TERMS = {
    "南津 涼子", "南津涼子", "128,南津涼子", "恵 萌花", "恵萌花", "139,恵萌花",
    "天乃鈴音", "史乃 沙優希", "史乃沙優希", "史乃沙優希的服装【泳装】",
    "海香的觉醒書", "攻击力提升[Ⅲ] & 瀕死时攻击力提升[Ⅰ]",
}
WIKI_TERMS = {
    "千石 撫子", "神原 駿河", "純 美雨", "綾野 梨花", "遊佐 葉月", "詩音 千里",
    "飾利 潤", "飾利潤", "136,飾利潤", "宮尾时雨", "114,宮尾时雨",
    "宝崎市立光塚中等教育学校", "宝崎市立光塚中等教育学校校服",
    "引縄批根", "记忆结晶「引縄批根」（等级已满/已达最大界限突破）",
    "桜前線急上昇", "究極VS至高", "裏方独演会",
    "現代神滨篇", "現代神滨編", "神滨大運動会", "时女拾遺物語",
    "篠目约鹤的“记忆”",
}
WIKI_PRESERVED = {
    "“你们要悔改”（译注：《圣经·马太福音》3章第2節）＠背对十字的光线，稳静地陈述着＠班里活跃的开心果＠站在有烦恼的人面前，也会露出这样的一面",
    "一次又一次地想起来＠垂死的少女们的慟哭，和令人窒息的血腥味＠握住手掌上残留着鲜血感觉，直面无法赦免的罪＠也许是因为想受到制裁，亦或是...",
}


def source_for(old: str, new: str) -> tuple[str, str, str]:
    if old in OFFICIAL_TERMS or any(term in old for term in OFFICIAL_TERMS if len(term) > 6):
        return (
            "1_official_cn_dump_normalized",
            r"A:\magireco_cn_dump_20221010_decrypted_json (normalized exact evidence)",
            "国服 dump 同一名称/文本的简体规范值",
        )
    if old in WIKI_TERMS or "篠目约鹤" in old:
        return (
            "2_designated_wiki",
            "wiki-data/data/{characters,memoria,pages_index}.json",
            "指定 Wiki 的角色、记忆结晶或篇章定名",
        )
    if old in {
        "七色夏模様", "主页背景「七色夏模様」。", "背景「七色夏模様」",
        "永遠的刻", "我慢我慢我慢…追跡",
    }:
        return (
            "3_manual_translation",
            "人工语义翻译；指定 dump/Wiki 未提供中文定名",
            "无权威中文命中，列入高优先级人工复核",
        )
    if old == "粛清天使":
        return (
            "3_manual_crosschecked",
            "https://www.wiki-source/wiki/入名库什",
            "指定 dump/Wiki 无中文对；人工翻译并由中文资料页交叉核对",
        )
    return (
        "3_manual_verified",
        "人工逐项字形、语义与同族字段核对",
        "保留 ID、数字、范围、回合、等级和字段结构",
    )


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open("r", encoding="utf-8", newline=""), delimiter="\t"))
    authority_rows = list(csv.DictReader(AUTHORITY.open("r", encoding="utf-8", newline=""), delimiter="\t"))
    def authority_key(value: str) -> str:
        # The read-only lookup serializes embedded newlines and strips trailing TABs.
        return value.replace("\\n", "\n").rstrip("\t")

    authority = {authority_key(row["text"]): row for row in authority_rows}
    assert len(rows) == 148, f"expected 148 unique candidates, got {len(rows)}"
    assert len(authority) == 148, f"expected 148 authority lookup rows, got {len(authority)}"
    out_rows = []
    for row in rows:
        old = row["text"]
        evidence = authority[authority_key(old)]
        authority_cn = evidence["authoritative_cn"]
        # The evidence TSV serializes multiline cells with literal ``\n``.
        # Restore only when the source candidate itself is multiline so a
        # backslash-n that is genuinely part of a label remains untouched.
        if "\n" in old and "\\n" in authority_cn:
            authority_cn = authority_cn.replace("\\n", "\n")
        new = authority_cn or (old if old in WIKI_PRESERVED else translate(old))
        # The Wiki evidence for DX lucky bags establishes the name component
        # (for example, 銀 -> 银).  Keep the national-server punctuation house
        # style already used by the client rather than importing ASCII brackets.
        if "DX福袋(" in new:
            new = new.replace("(", "（").replace(")", "）")
        assert new != old or old in WIKI_PRESERVED, f"untranslated mapping: {old!r}"
        if evidence["authoritative_cn"]:
            tier = evidence["tier"]
            source = evidence["exact_source_path"] + "#" + evidence["source_pointer"]
            note = evidence["notes"]
        elif old in WIKI_PRESERVED:
            tier = evidence["tier"] or "2_wiki_exact_equivalent"
            source = evidence["exact_source_path"] + "#" + evidence["source_pointer"]
            note = evidence["notes"]
        else:
            tier, source, note = source_for(old, new)
        out_rows.append({
            "review_index": row["review_index"],
            "original_text": old,
            "final_cn": new,
            "expected_occurrences": row["occurrences"],
            "classification": row["classification"],
            "risk": row["risk"],
            "source_tier": tier,
            "source_path": source,
            "translation_note": note,
        })
    fields = list(out_rows[0])
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"wrote {len(out_rows)} mappings to {OUTPUT}")


if __name__ == "__main__":
    main()
