#!/usr/bin/env python3
"""Apply the reviewed Pass16 runtime and static-UI Chinese corrections."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AUDIT = Path(__file__).resolve().parents[1]
REPO = AUDIT.parents[2]
PEER_RULES = AUDIT / "source_evidence" / "static_ui_peer_rules.tsv"
RUNTIME_MAP = AUDIT / "runtime_translation_map.tsv"
LIBS = REPO / "magica" / "js" / "libs"
UI_LOG = AUDIT / "ui_change_log.tsv"
RUNTIME_LOG = AUDIT / "runtime_change_log.tsv"
SUMMARY = AUDIT / "application_summary.json"


changes: list[dict[str, str]] = []


def read_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if raw.count(b"\r\n") else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), newline


def write_text(path: Path, text: str, newline: str) -> None:
    data = text if newline == "\n" else text.replace("\n", "\r\n")
    path.write_bytes(data.encode("utf-8"))


def line_of(text: str, token: str) -> int:
    pos = text.find(token)
    return text.count("\n", 0, max(0, pos)) + 1


def log_change(path: str, line: int, old: str, new: str, category: str, source: str, risk: str = "medium") -> None:
    changes.append({
        "file": path,
        "line": str(line),
        "original_text": old,
        "final_cn": new,
        "category": category,
        "source": source,
        "risk": risk,
    })


def replace_in_file(
    relative: str,
    old: str,
    new: str,
    *,
    category: str,
    source: str,
    risk: str = "medium",
    required: bool = True,
) -> int:
    path = REPO / relative
    text, newline = read_text(path)
    if old == new:
        return 0
    count = text.count(old)
    if count:
        scan = text
        for _ in range(count):
            line = line_of(scan, old)
            log_change(relative, line, old, new, category, source, risk)
            scan = scan.replace(old, new, 1)
        text = text.replace(old, new)
        write_text(path, text, newline)
        return count
    if required and new not in text:
        raise RuntimeError(f"required UI replacement not found: {relative}: {old!r}")
    return 0


def apply_peer_rules() -> dict[str, int]:
    rows = list(csv.DictReader(PEER_RULES.open("r", encoding="utf-8", newline=""), delimiter="\t"))
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["path"] == "magica/js/test/SoundTest.js":
            continue  # Replaced below as a complete, internally consistent 75-label set.
        groups[(row["path"], row["main_value"], row["proposed_new"])].append(row)
    allowed_missing = {
        "peer_static_102", "peer_static_196", "peer_static_197", "peer_static_198",
        "peer_static_199", "peer_static_200", "peer_static_203", "peer_static_204",
        "peer_static_250", "peer_static_251",
    }
    stats = Counter()
    # Longer tokens first so a short orthographic rule cannot destroy the anchor
    # of a later phrase-level rule in the same minified line.
    ordered_groups = sorted(
        groups.items(),
        key=lambda item: (item[0][0], -max(len(item[0][1]), len(item[1][0]["old"]))),
    )
    for (relative, main_value, proposed), group in ordered_groups:
        path = REPO / relative
        text, newline = read_text(path)
        if main_value == proposed or proposed in text and main_value not in text:
            stats["already_final"] += len(group)
            continue
        token = main_value if main_value and main_value in text else ""
        if not token:
            old = group[0]["old"]
            if old and old in text:
                token = old
        if not token:
            ids = {row["peer_rule_id"] for row in group}
            if ids <= allowed_missing:
                stats["handled_by_manual_override"] += len(group)
                continue
            if proposed in text:
                stats["already_final"] += len(group)
                continue
            raise RuntimeError(f"peer rule target missing: {relative}: {main_value!r} -> {proposed!r}")
        count = text.count(token)
        positions = [m.start() for m in re.finditer(re.escape(token), text)]
        text = text.replace(token, proposed)
        write_text(path, text, newline)
        for pos in positions:
            log_change(
                relative,
                text[:pos].count("\n") + 1,
                token,
                proposed,
                "static_ui_manual_review",
                "Pass16 peer rules, personally re-reviewed",
                group[0]["risk"].split(":", 1)[0],
            )
        stats["changed_occurrences"] += count
        stats["changed_rule_rows"] += len(group)
    stats["input_rule_rows"] = len(rows)
    return dict(stats)


SOUND_LABELS = {
    "01": "卡牌详情中的自我介绍", "02": "扭蛋获取时",
    "03": "剧情第1话通关时", "04": "剧情第2话通关时", "05": "剧情第3话通关时",
    "06": "自我介绍演出用①", "07": "自我介绍演出用②", "08": "自我介绍演出用③",
    "09": "自我介绍演出用④", "10": "自我介绍演出用⑤", "11": "自我介绍演出用⑥",
    "12": "自我介绍演出用⑦", "13": "强化完成", "14": "强化（等级已满时）",
    "15": "剧情等级提升", "16": "魔力解放第1次", "17": "魔力解放第2次",
    "18": "魔力解放第3次", "19": "Magia等级提升",
    "20": "觉醒（稀有度提升）②", "21": "觉醒（稀有度提升）③",
    "22": "觉醒（稀有度提升）④", "23": "觉醒（稀有度提升）⑤",
    "24": "每日首次登录时", "25": "时间变化①（6～9时）", "26": "时间变化②（11～13时）",
    "27": "时间变化③（17～19时）", "28": "时间变化④（22～24时）",
    "29": "时间变化⑤（上述时段以外）", "30": "关卡", "31": "镜界", "32": "GvG",
    "33": "点击时台词（默认①）", "34": "点击时台词（默认②）", "35": "点击时台词（默认③）",
    "36": "点击时台词（默认④）", "37": "点击时台词（剧情等级2）",
    "38": "点击时台词（剧情等级3）", "39": "点击时台词（剧情等级4）",
    "40": "点击时台词（剧情等级5）", "41": "点击时台词（多次点击）",
    "42": "战斗开始时", "43": "胜利①（★1、2、3）", "44": "胜利②（★4）",
    "45": "胜利③（★5）", "46": "胜利④（★6）", "47": "行动盘选择①",
    "48": "行动盘选择②", "49": "行动盘选择③", "50": "行动盘选择④",
    "51": "行动盘选择（发起连携）", "52": "行动盘选择（接受连携）",
    "53": "第1次攻击时①（长台词）", "54": "第1次攻击时②（长台词）",
    "55": "第1次攻击时③（长台词）", "56": "第2、3次攻击时①",
    "57": "第2、3次攻击时②", "58": "第2、3次攻击时③",
    "59": "第2次攻击时①（同一角色）", "60": "第2次攻击时②（同一角色）",
    "61": "第3次攻击时①（同一角色）", "62": "第3次攻击时②（同一角色）",
    "63": "发动Magia时①（★1、2、3）", "64": "发动Magia时②（Magia★4）",
    "65": "发动Magia时③（Magia★5）", "66": "发动Magia时④（Magia★6）",
    "67": "发动魔女化身时", "68": "攻击时（发起连携）", "69": "攻击时（接受连携）",
    "70": "技能（目标：自身）", "71": "技能（目标：我方）", "72": "技能（目标：敌方）",
    "73": "受伤时（通常）", "74": "受伤时（濒死）", "75": "战斗不能",
}


LIVE2D_LABELS = {
    "01": "自我介绍", "02": "自我介绍（扭蛋获取时）",
    "03": "魔法少女剧情第1话通关", "04": "魔法少女剧情第2话通关", "05": "魔法少女剧情第3话通关",
    "13": "强化完成", "14": "强化（等级已满时）", "15": "剧情等级提升",
    "16": "魔力解放①", "17": "魔力解放②", "18": "魔力解放③", "19": "Magia等级提升",
    "20": "魔法少女觉醒①", "21": "魔法少女觉醒②", "22": "魔法少女觉醒③", "23": "魔法少女觉醒④",
    "24": "登录①（首次登录时）", "25": "登录②（早晨）", "26": "登录③（白天）",
    "27": "登录④（夜晚）", "28": "登录⑤（深夜）", "29": "登录⑥（其他）",
    "30": "登录⑦（AP满时）", "31": "登录⑧（BP满时）", "32": "登录⑨（GvG）",
    "33": "点击魔法少女①", "34": "点击魔法少女②", "35": "点击魔法少女③",
    "36": "点击魔法少女④", "37": "点击魔法少女⑤", "38": "点击魔法少女⑥",
    "39": "点击魔法少女⑦", "40": "点击魔法少女⑧", "41": "点击魔法少女⑨",
    "42": "关卡开始", "43": "关卡胜利①", "44": "关卡胜利②", "45": "关卡胜利③", "46": "关卡胜利④",
    "63": "发动Magia①", "64": "发动Magia②", "65": "发动Magia③", "66": "发动Magia④",
}


def replace_code_labels(relative: str, labels: dict[str, str], mode: str) -> int:
    path = REPO / relative
    text, newline = read_text(path)
    count = 0
    for code, label in labels.items():
        if mode == "js":
            pattern = re.compile(r'(\["' + re.escape(code) + r'",\s*")[^"]*("\])')
        else:
            pattern = re.compile(r'(data-voice="' + re.escape(code) + r'">)' + re.escape(code) + r'[:：][^<]*(</div>)')
        match = pattern.search(text)
        if not match:
            raise RuntimeError(f"missing {mode} label {code} in {relative}")
        old = match.group(0)
        if mode == "js":
            new = match.group(1) + label + match.group(2)
        else:
            new = match.group(1) + code + ":" + label + match.group(2)
        if old != new:
            log_change(relative, text[:match.start()].count("\n") + 1, old, new, "static_ui_manual_translation", "Pass16 complete label-set review", "medium")
            text = text[:match.start()] + new + text[match.end():]
            count += 1
    write_text(path, text, newline)
    return count


def apply_static_overrides() -> dict[str, int]:
    stats = Counter()
    # Complete label sets prevent partially translated, internally inconsistent test UIs.
    stats["sound_labels"] += replace_code_labels("magica/js/test/SoundTest.js", SOUND_LABELS, "js")
    stats["live2d_labels"] += replace_code_labels("magica/template/test/BackdoorLive2d.html", LIVE2D_LABELS, "html")

    rules = [
        # Production-facing pages.
        ("magica/template/event/raid/EventRaidCloseTop.html", 'data-mission-name="個人撃破報酬"', 'data-mission-name="个人击破报酬"', "visible_html_attribute", "manual", "high"),
        ("magica/template/event/raid/EventRaidCloseTop.html", 'data-mission-name="全体撃破報酬"', 'data-mission-name="全体击破报酬"', "visible_html_attribute", "manual", "high"),
        ("magica/template/event/raid/EventRaidTop.html", 'data-mission-name="個人撃破報酬"', 'data-mission-name="个人击破报酬"', "visible_html_attribute", "manual", "high"),
        ("magica/template/event/raid/EventRaidTop.html", 'data-mission-name="全体撃破報酬"', 'data-mission-name="全体击破报酬"', "visible_html_attribute", "manual", "high"),
        ("magica/template/regularEvent/groupBattle/RegularEventGroupBattleLog.html", 'data-mission-name="個人"', 'data-mission-name="个人"', "visible_html_attribute", "manual", "high"),
        ("magica/template/top/TopPage.html", "利用規約", "使用条款", "production_ui", "manual", "high"),
        ("magica/template/purchase/PurchaseTemps.html", "未成年の方は保護者の同意を得て下さい。", "未成年人请先征得监护人同意。", "production_ui", "manual", "high"),
        ("magica/js/view/mission/MissionTopView.js", '+"时间"', '+"小时"', "production_ui_semantic_fix", "manual", "high"),
        # Piece archive wording and structure.
        ("magica/js/view/memoria/PieceArchiveView.js", '"仓库":"持有格"', '"保管库":"持有格"', "production_ui", "manual", "high"),
        ("magica/js/view/memoria/PieceArchiveView.js", '"将所选记忆结晶"+d+"移至', '"将所选记忆结晶从"+d+"移至', "production_ui_grammar", "manual", "high"),
        ("magica/js/view/memoria/PieceArchiveView.js", '"将所选记忆结晶"+e+"已移至', '"已将所选记忆结晶从"+e+"移至', "production_ui_grammar", "manual", "high"),
        ("magica/js/view/memoria/PieceArchiveView.js", '"将所选记忆结晶"+d.name+"已移至', '"已将所选记忆结晶从"+d.name+"移至', "production_ui_grammar", "manual", "high"),
        ("magica/js/view/memoria/PieceArchiveView.js", '"可移至保管库:"', '"可移入保管库:"', "debug_ui", "manual", "low"),
        ("magica/js/view/memoria/PieceArchiveView.js", '"持有栏可移动:"', '"可移入持有格:"', "debug_ui", "manual", "low"),
        # Backdoor/test residuals and terminology.
        ("magica/js/test/BackdoorList.js", 'title: "完了"', 'title: "完成"', "test_ui", "manual", "medium"),
        ("magica/js/test/BackdoorList.js", 'title: "回复 战斗博物馆重置"', 'title: "重置战斗博物馆回复功能"', "test_ui", "manual", "medium"),
        ("magica/js/test/BackdoorList.js", 'c = "1 份散装 通关"', 'c = "第一部一键通关"', "test_ui", "manual", "medium"),
        ("magica/js/test/BackdoorList.js", 'title: "突破活动调试模式"', 'title: "踏破活动调试模式"', "test_ui", "manual", "medium"),
        ("magica/js/test/BackdoorList.js", 'title: "Magia 石材购买状态确认"', 'title: "魔法石购买状态"', "test_ui", "manual", "medium"),
        ("magica/js/test/BackdoorQuestList.js", "現代神浜編", "现代神滨篇", "test_ui", "designated Wiki", "high"),
        ("magica/js/test/BackdoorQuestList.js", '"話 Battle"', '"话 战斗"', "test_ui", "manual", "medium"),
        ("magica/template/test/Backdoor.html", "活动<%= model.eventId %>的设置", "活动<%= model.eventId %>套装", "test_ui", "manual", "medium"),
        ("magica/template/test/Backdoor.html", "最下部", "最下方", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", "最上部", "最上方", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", ">検索<", ">搜索<", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", ">全表示<", ">全部显示<", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", "全素材 × 100", "全部素材 × 100", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", ">１字削除<", ">删除1个字符<", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", ">1字削除<", ">删除1个字符<", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", ">報酬付与<", ">发放奖励<", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", "（所持数：", "（持有数：", "test_ui", "manual", "low"),
        ("magica/template/test/Backdoor.html", ">個数指定<", ">指定数量<", "test_ui", "manual", "low"),
        ("magica/template/test/backdoorList.html", "相撲TOP", "相扑首页", "test_ui", "manual", "medium"),
        ("magica/template/test/backdoorList.html", "章节Lv 上升", "剧情等级提升", "test_ui", "manual", "medium"),
        ("magica/template/test/backdoorList.html", "1 份散装 通关", "第一部一键通关", "test_ui", "manual", "medium"),
        ("magica/template/test/backdoorList.html", "无理 战斗 再试一次", "重试理违战", "test_ui", "manual", "medium"),
        ("magica/template/test/backdoorList.html", "完了（TU999）", "完成（TU999）", "test_ui", "manual", "low"),
        ("magica/template/test/backdoorList.html", "エラーコードを入力。", "输入错误代码。", "test_ui", "manual", "low"),
        ("magica/template/test/backdoorList.html", "ツイートリンクを入力。", "输入推文链接。", "test_ui", "manual", "low"),
        ("magica/template/test/BackdoorLive2d.html", ">角色列表显示<", ">显示角色列表<", "test_ui", "manual", "low"),
        ("magica/template/test/BackdoorLive2d.html", ">育成<", ">养成<", "test_ui", "manual", "low"),
        ("magica/template/test/BackdoorQuestBattle.html", ">貼付<", ">粘贴<", "test_ui", "manual", "low"),
        ("magica/template/test/BackdoorQuestBattle.html", ">履歴<", ">历史记录<", "test_ui", "manual", "low"),
        ("magica/template/test/BackdoorQuestBattle.html", ">1字削除<", ">删除1个字符<", "test_ui", "manual", "low"),
        ("magica/template/test/BackdoorQuestBattle.html", ">入力<", ">输入<", "test_ui", "manual", "low"),
        ("magica/template/test/EffectTest.html", ">表示<", ">显示<", "test_ui", "manual", "low"),
        ("magica/template/test/EffectTest.html", ">削除<", ">删除<", "test_ui", "manual", "low"),
        ("magica/template/test/FriendSearch.html", ">検索<", ">搜索<", "test_ui", "manual", "low"),
        ("magica/template/test/FriendSearch.html", '<span class="btn follow">关注</p>', '<span class="btn follow">关注</span>', "html_structure_repair", "manual", "high"),
        ("magica/template/test/PresentListTest.html", "×<%= model.quantity %\\>枚", "×<%= model.quantity %\\>张", "test_ui", "manual", "low"),
        ("magica/template/test/QuestStub.html", "戦闘不能回数", "战斗不能次数", "test_ui", "manual", "low"),
        ("magica/template/test/SelectStoryTest.html", ">貼付<", ">粘贴<", "test_ui", "manual", "low"),
        ("magica/template/test/SelectStoryTest.html", ">履歴<", ">历史记录<", "test_ui", "manual", "low"),
        ("magica/template/test/SelectStoryTest.html", ">1字削除<", ">删除1个字符<", "test_ui", "manual", "low"),
        ("magica/template/test/SelectStoryTest.html", ">入力<", ">输入<", "test_ui", "manual", "low"),
        ("magica/template/test/SelectStoryTest.html", ">履歴削除<", ">删除历史记录<", "test_ui", "manual", "low"),
        ("magica/template/test/SdCharaTest.html", ">迷你角色显示<", ">显示迷你角色<", "test_ui", "manual", "low"),
        ("magica/template/test/SdCharaTest.html", 'placeholder="输入index"', 'placeholder="请输入index"', "test_ui", "manual", "low"),
        ("magica/template/test/SdCharaTest.html", 'placeholder="输入charaId"', 'placeholder="请输入charaId"', "test_ui", "manual", "low"),
        ("magica/template/test/SdCharaTest.html", 'placeholder="输入Scale"', 'placeholder="请输入Scale"', "test_ui", "manual", "low"),
        ("magica/template/test/SdCharaTest.html", 'placeholder="输入Fade"', 'placeholder="请输入Fade"', "test_ui", "manual", "low"),
        ("magica/template/test/SdCharaTest.html", ">显示暂存<", ">显示暂存角色<", "test_ui", "manual", "low"),
        ("magica/template/test/SdCharaTest.html", ">隐藏暂存<", ">隐藏暂存角色<", "test_ui", "manual", "low"),
    ]
    for relative, old, new, category, source, risk in rules:
        stats[category] += replace_in_file(relative, old, new, category=category, source=source, risk=risk)

    # The legal popup is reviewed as a whole because the prior file mixed Japanese labels,
    # machine-like Chinese, invisible characters, and one malformed opening tag.
    relative = "magica/template/etc/LawPopup.html"
    path = REPO / relative
    old_text, newline = read_text(path)
    new_text, _ = read_text(AUDIT / "final_templates" / "LawPopup.html")
    if old_text != new_text:
        log_change(relative, 1, "旧版中日混合且含<<span结构错误的法律文本", "全中文法律信息与已修复span结构", "production_legal_ui", "Pass16 full manual rewrite", "high")
        write_text(path, new_text, newline)
        stats["law_popup_full_rewrite"] += 1
    return dict(stats)


def json_pointer_token(value: Any) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def apply_runtime() -> dict[str, Any]:
    rows = list(csv.DictReader(RUNTIME_MAP.open("r", encoding="utf-8", newline=""), delimiter="\t"))
    mapping = {row["original_text"]: row for row in rows}
    counts = Counter()
    runtime_log: list[dict[str, str]] = []

    def walk(value: Any, dictionary: str, pointer: str) -> Any:
        if isinstance(value, dict):
            return {key: walk(child, dictionary, pointer + "/" + json_pointer_token(key)) for key, child in value.items()}
        if isinstance(value, list):
            return [walk(child, dictionary, pointer + f"/{index}") for index, child in enumerate(value)]
        if isinstance(value, str) and value in mapping:
            row = mapping[value]
            new = row["final_cn"]
            action = "authority_preserved" if new == value else "replaced"
            counts[(value, action)] += 1
            runtime_log.append({
                "dictionary": dictionary,
                "pointer": pointer or "/",
                "original_text": value,
                "final_cn": new,
                "action": action,
                "source_tier": row["source_tier"],
                "source_path": row["source_path"],
                "risk": row["risk"],
            })
            return new
        return value

    json_paths = sorted(LIBS.glob("*.json"), key=lambda p: p.name)
    if len(json_paths) != 23:
        raise RuntimeError(f"expected 23 runtime dictionaries, got {len(json_paths)}")
    for path in json_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        data = walk(data, path.name, "")
        # Official same-record alignment for every adjustment-expert coin record.
        if path.name == "itemList.json":
            aligned = 0
            for index, record in enumerate(data):
                if not isinstance(record, dict):
                    continue
                code = str(record.get("itemCode", ""))
                if code.startswith("GACHA_FREEBIE") and "MEDAL" in code and record.get("shortDescription") == "调整专家币":
                    aligned += 1
                    for field, final in (("name", "调整专家币"), ("description", "在「调整专家币」中用于兑换的道具")):
                        old = record.get(field)
                        if old != final:
                            runtime_log.append({
                                "dictionary": path.name,
                                "pointer": f"/{index}/{field}",
                                "original_text": str(old),
                                "final_cn": final,
                                "action": "official_same_record_alignment",
                                "source_tier": "1_official_cn_dump_same_record",
                                "source_path": r"A:\magireco_cn_dump_20221010_decrypted_json\authority\authority.json#/itemList.json/GACHA_FREEBIE_343_MEDAL",
                                "risk": "high",
                            })
                            record[field] = final
            if aligned != 225:
                raise RuntimeError(f"expected 225 adjustment-expert coin records, got {aligned}")
        # The gold member was already Chinese in Pass15 and therefore was not
        # one of the 148 untranslated candidates.  Keep the whole DX lucky-bag
        # family on the same national-server full-width punctuation rule.
        if path.name == "shopItemList.json":
            harmonized = 0
            for index, record in enumerate(data):
                if isinstance(record, dict) and record.get("name") == "3周年DX福袋(金)":
                    runtime_log.append({
                        "dictionary": path.name, "pointer": f"/{index}/name",
                        "original_text": "3周年DX福袋(金)", "final_cn": "3周年DX福袋（金）",
                        "action": "punctuation_harmonization", "source_tier": "3_manual_verified",
                        "source_path": "国服中文标点规则与同族商品名", "risk": "low",
                    })
                    record["name"] = "3周年DX福袋（金）"
                    harmonized += 1
            if harmonized != 1:
                raise RuntimeError(f"expected one gold DX lucky-bag punctuation alignment, got {harmonized}")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    for row in rows:
        old = row["original_text"]
        actual = counts[(old, "replaced")] + counts[(old, "authority_preserved")]
        expected = int(row["expected_occurrences"])
        if actual != expected:
            raise RuntimeError(f"runtime occurrence mismatch for {old!r}: {actual} != {expected}")

    fields = ["dictionary", "pointer", "original_text", "final_cn", "action", "source_tier", "source_path", "risk"]
    with RUNTIME_LOG.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(runtime_log)
    return {
        "unique_map_rows": len(rows),
        "candidate_occurrences": sum(int(row["expected_occurrences"]) for row in rows),
        "candidate_replaced": sum(v for (old, action), v in counts.items() if action == "replaced"),
        "authority_preserved": sum(v for (old, action), v in counts.items() if action == "authority_preserved"),
        "runtime_log_rows": len(runtime_log),
        "official_adjustment_coin_records": 225,
        "punctuation_harmonized_records": 1,
    }


def write_ui_log() -> None:
    fields = ["file", "line", "original_text", "final_cn", "category", "source", "risk"]
    with UI_LOG.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(changes)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    peer = apply_peer_rules()
    static = apply_static_overrides()
    runtime = apply_runtime()
    write_ui_log()
    # Rebuild the embedded runtime layer only after all 23 external dictionaries are final.
    subprocess.run([sys.executable, "Build_JS_Injector.py"], cwd=REPO, check=True)
    authority_summary = json.loads((AUDIT / "source_evidence" / "runtime_authority_lookup_148_summary.json").read_text(encoding="utf-8"))
    summary = {
        "base_commit": "4db6698623311ee5ab1dce9ebce940e0eb2748f0",
        "peer_rules": peer,
        "static_overrides": static,
        "ui_change_log_rows": len(changes),
        "runtime": runtime,
        "authority_lookup": {
            "matches": authority_summary["authoritative_matches"],
            "unmatched": authority_summary["unmatched"],
            "tier_counts": authority_summary["tier_counts"],
        },
        "jquery_sha256": sha256(LIBS / "jquery-3.7.1.min.js"),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
