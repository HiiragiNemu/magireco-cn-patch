from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY = Path(
    r"D:\magia\MyProducts\MAGIA RECORD CN\totentanz-publish-20260822"
    r"\magirecocn-legacy-client-main"
)
PRODUCT = Path(os.environ.get(
    "TOTENTANZ_PRODUCT_ROOT",
    r"D:\magia\MyProducts\MAGIA RECORD CN\totentanz-localization-work-20260822",
))
OFFICIAL_MAIN = Path(
    r"D:\magia\MyProducts\MAGIA RECORD CN\Full_Raw_Dump_V2"
    r"\magica\api\page\MainQuest_001.json"
)
OFFICIAL_SHOP = Path(
    r"D:\magia\MyProducts\MAGIA RECORD CN\Full_Raw_Dump_V2"
    r"\magica\api\page\ShopTop_001.json"
)
STATIC_PAGES = Path(
    r"D:\magia\MyProducts\MAGIA RECORD CN\静态数据"
    r"\static\magica\json\page"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def engine_pairs(path: Path) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        assert "\t" in line, (path, line_no, line)
        source, target = line.split("\t", 1)
        # Empty targets are an existing exact/prefix contract used to suppress
        # one redundant suffix (for example 上昇する); only the source is required.
        assert source, (path, line_no)
        assert source not in pairs, (path, "duplicate source", source)
        pairs[source] = target
    return pairs


def find_record(rows, nested_key: str, stable_field: str, stable_value):
    matches = [row[nested_key] for row in rows if row.get(nested_key, {}).get(stable_field) == stable_value]
    assert len(matches) == 1, (nested_key, stable_field, stable_value, len(matches))
    return matches[0]


def mission_denominator(mission: dict[str, dict]) -> tuple[int, int, int]:
    observed: dict[str, set[str | None]] = {}
    occurrences = 0

    def walk(value) -> None:
        nonlocal occurrences
        if isinstance(value, dict):
            for index in (1, 2, 3):
                code = value.get(f"mission{index}")
                master = value.get(f"missionMaster{index}")
                if isinstance(code, str) and code:
                    description = master.get("description") if isinstance(master, dict) else None
                    observed.setdefault(code, set()).add(description)
                    occurrences += 1
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    pages = sorted(STATIC_PAGES.glob("*.json"))
    assert len(pages) == 135
    for path in pages:
        walk(json.loads(path.read_text(encoding="utf-8-sig")))

    live_only_codes = {"ACTION_25"}
    assert set(observed) | live_only_codes == set(mission), (
        "missing", sorted(set(observed) - set(mission)),
        "extra", sorted(set(mission) - set(observed)),
    )
    for code, descriptions in observed.items():
        rule = mission[code]
        allowed = {rule.get("source"), rule.get("target"), *(rule.get("sourceAliases") or [])}
        unknown = sorted(
            description for description in descriptions
            if description is not None and description not in allowed
        )
        assert not unknown, (code, unknown)
    return len(pages), occurrences, len(observed)


def main() -> None:
    libs = ROOT / "magica/js/libs"
    engine = engine_pairs(ROOT / "madomagi/engine_i18n.tsv")
    product_engine = engine_pairs(PRODUCT / "madomagi/engine_i18n.tsv")
    assert engine == product_engine
    assert len(engine) == 702

    # Group 1: chapter field authority and render-wrapper fixture.
    official = load(OFFICIAL_MAIN)
    chapter = find_record(official["userChapterList"], "chapter", "chapterId", 20)
    section = find_record(official["userSectionList"], "section", "sectionId", 102004)
    assert chapter["chapterNoForView"] == "第10章"
    assert [f"U+{ord(c):04X}" for c in chapter["chapterNoForView"]] == [
        "U+7B2C", "U+0031", "U+0030", "U+7AE0"
    ]
    assert section["genericId"] == 20
    assert section["genericIndex"] == 4
    assert section["title"] == "默示天灾"
    chapter_map = {row["chapterId"]: row for row in load(libs / "chapterList.json")}
    assert chapter_map[20]["chapterNoForView"] == "第10章"
    assert chapter_map[60]["chapterNoForView"] == "第10章"
    node = subprocess.run(
        ["node", str(ROOT / "tools/test-pass51-chapter-render.js")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert node.returncode == 0, node.stdout + node.stderr
    assert "PASS51_CHAPTER_VM=PASS" in node.stdout

    # Group 2: exact Mission composite keys and field-level official wording.
    mission = load(libs / "questMissionDescriptionMap.json")
    assert len(mission) == 123
    expected_missions = {
        "NOT_DEAD": ("一人も倒れずにクリア", "无人退场下通关", "Clear without losing any Magical Girls"),
        "ACTION_15": ("15ターン以内クリア", "15回合内通关", "Clear within 15 Turn(s)"),
        "COUNT_CONNECT_1": ("コネクトを1回発動", "发动1次Connect", "Connect 1 time(s)"),
    }
    for code, (source, target, alias) in expected_missions.items():
        rule = mission[code]
        assert rule["source"] == source
        assert rule["target"] == target
        assert rule["sourceAliases"] == [alias]
        assert rule["sourceTier"] == "official-cn-exact-mission-code"
        assert rule["reviewStatus"] == "official-exact-stable-key"
    official_battle = find_record(
        official["userQuestBattleList"], "questBattle", "questBattleId", 10180151
    )
    assert official_battle["mission1"] == "NOT_DEAD"
    assert official_battle["mission2"] == "ACTION_15"
    assert official_battle["mission3"] == "COUNT_CONNECT_1"
    assert official_battle["missionMaster1"]["description"] == "无人退场下通关"
    assert official_battle["missionMaster2"]["description"] == "15回合内通关"
    assert official_battle["missionMaster3"]["description"] == "发动1次Connect"
    assert mission["COUNT_CONNECT_1"]["target"] not in {
        "发动1次连携", "发动1次连接", "发动1次链接"
    }
    assert engine["Connect"] == "连携"
    assert engine["Connect 1 time(s)"] == "发动1次Connect"
    event_witch_missions = {
        "HP_30": ("Clear with 30% or more Total HP", "总计剩余HP在30 ％以上通关"),
        "HP_20": ("Clear with 20% or more Total HP", "总计剩余HP在20 ％以上通关"),
        "HP_10": ("Clear with 10% or more Total HP", "总计剩余HP在10 ％以上通关"),
        "ACTION_10": ("Clear within 10 Turn(s)", "10回合内通关"),
        "ACTION_25": ("Clear within 25 Turn(s)", "25回合内通关"),
        "NOT_CONTINUE": ("Clear without using a Continue", "不使用续关下通关"),
        "CLEAR": ("Clear", "通关"),
    }
    for code, (alias, target) in event_witch_missions.items():
        assert mission[code]["sourceAliases"] == [alias]
        assert mission[code]["target"] == target
    mission_pages, mission_occurrences, mission_codes = mission_denominator(mission)
    quest_result = subprocess.run(
        ["node", str(ROOT / "tools/test-pass51-quest-result-model.js")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert quest_result.returncode == 0, quest_result.stdout + quest_result.stderr
    assert "PASS51_QUEST_RESULT_FULL_MODEL_VM=PASS" in quest_result.stdout

    # Group 3: battle initial floating labels reach both createWithTTF constructors.
    assert engine["ヴァリアブル"] == "全属性克制"
    assert engine["ダメージUP!"] == "伤害提升!"
    cpp = (LEGACY / "magia-native/src/MagiaLegacy.cpp").read_text(encoding="utf-8")
    assert cpp.count("static bool translateTtfInitialText(") == 1
    assert "engineLookup(t, text, translated)" in cpp
    assert "enginePrefixLookup(t, v.data, v.size, translated)" in cpp
    assert cpp.count("translateTtfInitialText(text,") == 2
    assert cpp.count("(void*)createWithTtfCfgNew") == 1
    assert cpp.count("(void*)createWithTtfStrNew") == 1
    assert "g_dbgNoI18nSetString || !text" in cpp

    # Group 4: NPC display names use translated CARD/CHARA stable fields before aliases.
    card = {row["cardId"]: row for row in load(libs / "cardList.json")}
    chara = {row["id"]: row for row in load(libs / "charaList.json")}
    assert card[10414]["cardName"] == "莉薇娅·梅黛洛斯"
    assert chara[1041]["name"] == "莉薇娅·梅黛洛斯"
    assert card[10133]["cardName"] == "龙城明日香"
    assert chara[1013]["name"] == "龙城明日香"
    support_js = (ROOT / "magica/js/quest/SupportSelect.js").read_text(encoding="utf-8")
    npc_expr = (
        'p.questBattle.npcHelpNameHidden?"？？？":'
        "e.card&&e.card.cardName?e.card.cardName:"
        "e.chara&&e.chara.name?e.chara.name:a.userName"
    )
    assert support_js.count(npc_expr) == 1
    assert support_js.count('f.userName=p.questBattle.npcHelpNameHidden?"？？？":a.userName') == 0
    official_shop_text = OFFICIAL_SHOP.read_text(encoding="utf-8")
    official_main_text = OFFICIAL_MAIN.read_text(encoding="utf-8")
    assert '"cardName": "莉薇娅·梅黛洛斯"' in official_shop_text
    assert '"charaName": "龙城明日香"' in official_main_text

    # Group 5: visible formation controls are already Chinese at the template layer.
    formation = (ROOT / "magica/template/formation/DeckFormation.html").read_text(encoding="utf-8")
    for text in ["切换队伍", "解散队伍", "自动编成", "复制编队确认", "请选择魔法阵形。"]:
        if text == "复制编队确认":
            js = (ROOT / "magica/js/formation/DeckFormation.js").read_text(encoding="utf-8")
            assert text in js
        else:
            assert text in formation
    visible_without_template_comments = re.sub(r"<%.*?%>", "", formation, flags=re.S)
    assert not re.search(r"[ぁ-ゖァ-ヺ]", visible_without_template_comments)

    # Group 6: original asset-domain replacement. The rejected CSS label overlay
    # stays absent; DeckFormation continues to load its original background path.
    css = (ROOT / "magica/css/formation/DeckFormation.css").read_text(encoding="utf-8")
    selector = "#DeckFormation #deckFooter .attBox.enemyDetail:before"
    assert css.count(selector) == 0
    assert 'content:"敌人的属性"' not in css
    asset_url = "/magica/resource/image_web/page/formation_2/bg_element_enemy_b.png"
    assert css.count(asset_url) == 1
    asset = ROOT / asset_url.removeprefix("/")
    png = asset.read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(png[16:20], "big") == 162
    assert int.from_bytes(png[20:24], "big") == 110

    json_paths = sorted(libs.glob("*.json"))
    assert len(json_paths) == 32
    for path in json_paths:
        load(path)

    print("PASS51_VISIBLE_LOCALIZATION=PASS")
    print("GROUPS=6")
    print("CHAPTER_STABLE_ID=CHAPTER|20")
    print("CHAPTER_FIELD=chapterNoForView")
    print("CHAPTER_EXACT_OFFICIAL=第10章")
    print(node.stdout.strip())
    print("MISSION_RULES=123")
    print(f"MISSION_STATIC_PAGES={mission_pages}")
    print(f"MISSION_OCCURRENCES={mission_occurrences}")
    print(f"MISSION_OBSERVED_CODES={mission_codes}")
    print("MISSION_MISSING_CODES=0")
    print("MISSION_SOURCE_VARIANT_MISMATCH=0")
    print("MISSION_KEYS=NOT_DEAD,ACTION_15,COUNT_CONNECT_1")
    print("EVENTWITCH_MISSION_KEYS=HP_30,HP_20,HP_10,ACTION_10,ACTION_25,NOT_CONTINUE,CLEAR")
    print("MISSION_CONNECT_TARGET=发动1次Connect")
    print("CONNECT_STANDALONE_TARGET=连携")
    print(quest_result.stdout.strip())
    print("ENGINE_RULES=702")
    print("BATTLE_INITIAL=ヴァリアブル->全属性克制,ダメージUP!->伤害提升!")
    print("NPC_STABLE_IDS=CARD|10414,CHARA|1041,CARD|10133,CHARA|1013")
    print("FORMATION_VISIBLE_LABELS=5")
    print("ENEMY_ATTRIBUTE_SELECTOR=0")
    print("ENEMY_ATTRIBUTE_ORIGINAL_ASSET=formation_2/bg_element_enemy_b.png")
    print("JSON_DICTIONARIES=32")


if __name__ == "__main__":
    main()
