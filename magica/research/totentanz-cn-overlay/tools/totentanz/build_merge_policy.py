from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> None:
    inv = json.loads((HERE / "inventory.json").read_text(encoding="utf-8"))
    entries = inv["entries"]
    translations = json.loads((HERE / "translation_candidates.json").read_text(encoding="utf-8"))
    policy = {
        "schema_version": 1,
        "base_direction": "start_from_current_totentanz_then_apply_localization_deltas",
        "rules": [
            {
                "priority": 10,
                "match": "css/**",
                "action": "keep_current_file",
                "reason": "current CSS contains new layouts/selectors; only patch CSS content literals by selector",
            },
            {
                "priority": 20,
                "match": "current_only files",
                "action": "keep_current_file",
                "reason": "legacy CN has no counterpart",
            },
            {
                "priority": 30,
                "match": "shared JS/HTML",
                "action": "apply_guarded_literal_edits_to_current",
                "candidate_file": "translation_candidates.json",
            },
            {
                "priority": 40,
                "match": "shared PNG",
                "action": "copy_only_if_listed_and_hashes_match",
                "candidate_file": "safe_copy_map.json",
                "verification": "python verify_safe_copy.py",
            },
            {
                "priority": 50,
                "match": "old_only files",
                "action": "exclude_by_default",
                "reason": "many are retired routes or APK-resident core files from an incompatible version",
            },
        ],
        "protect_current_paths": sorted(e["path"] for e in entries if e["status"] == "current_only"),
        "protect_current_css_paths": sorted(
            e["path"] for e in entries if e["extension"] == ".css" and e["status"] != "old_only"
        ),
        "guarded_translation_paths_high": sorted(
            {r["path"] for r in translations if r["confidence"] == "high"}
        ),
        "apk_layer_dependencies_do_not_fill_from_legacy": [
            "css/_common/sanitize.css",
            "css/_common/common.css",
            "css/_common/base.css",
            "css/_common/fonts.css",
            "js/system/replacement.js",
            "js/libs/jquery-3.7.1.min.js",
            "js/libs/require.js",
            "js/_common/base.js",
        ],
        "current_main_common_css_cleanup": {
            "remove_behavior_changing_tail_selectors": [
                "#sideMenu #menuBtns .unit",
                "#sideMenu #menuBtns .innocent",
                "#sideMenu #menuBtns .team",
                "#sideMenu #menuBtns .gacha",
                "#sideMenu #menuBtns .mission",
                "#sideMenu #menuBtns .shop",
                "#sideMenu #menuBtns .shop2",
            ],
            "remove_redundant_tail_selectors": [
                "#sideMenu #sideBigBtns .globalBigBtn.globalQuestBtn",
                "#sideMenu #sideBigBtns .globalBigBtn.globalBattleBtn",
                "#globalMenu #globalBackBtn",
            ],
            "reason": "the first group redirects update2 to legacy root art; the second repeats the base URL",
        },
        "test_routes": [
            "#/TopPage",
            "#/MyPage",
            "#/CampaignQuizTop",
            "#/CampaignSumoTop",
            "#/NewYearLogin",
            "#/CampaignSummerMissionTop/TEST_MISSION_ID",
            "#/RegularEventArenaRankMatchTop",
            "#/EventPuellaRaidTop",
            "#/PuellaHistoriaGroupRaidQuestResultMainBoss",
            "#/PuellaHistoriaGroupRaidQuestResultSubBoss",
        ],
    }
    (HERE / "merge_policy.json").write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "protect_current_paths": len(policy["protect_current_paths"]),
        "protect_current_css_paths": len(policy["protect_current_css_paths"]),
        "guarded_translation_paths_high": len(policy["guarded_translation_paths_high"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
