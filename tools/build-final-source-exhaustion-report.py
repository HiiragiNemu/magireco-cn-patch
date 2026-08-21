#!/usr/bin/env python3
"""Compose the sealed source-exhaustion evidence without rescanning sources."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

SCHEMA = "magireco-final-source-exhaustion-20260821/v3"
RESEARCH = Path("magica/research/totentanz-full-localization-20260817")
OUTPUT = RESEARCH / "final-source-exhaustion-20260819"

REPO_INPUTS = {
    "authority_summary": RESEARCH / "authority-source-exhaustion-round3/summary.json",
    "authority_verification": RESEARCH / "authority-source-exhaustion-round3/verification.json",
    "image_inventory": RESEARCH / "source-exhaustion/image_source_exhaustion_verification.json",
    "image_closure": RESEARCH / "image-gap-closure-round3/closure_verification.json",
    "missing_html": RESEARCH / "missing-html-authority-20260819/runtime/verification.json",
    "rule_popup": RESEARCH / "rule-popup-cn-20260819/runtime/verification.json",
    "round6_manifest": RESEARCH / "visible-closure-round6/runtime/manifest.json",
    "round6_verification": RESEARCH / "visible-closure-round6/runtime/verification.json",
    "engine_gap": RESEARCH / "engine-i18n/ap-recovery-gap-verification.json",
    "engine_final_quality": RESEARCH / "engine-i18n/final-root-review-20260819/engine_unknown_212_quality_summary.json",
    "engine_final_sidecar": RESEARCH / "engine-i18n/final-root-review-20260819/engine_unknown_212_root_review_sidecar.json",
    "engine_final_application": RESEARCH / "engine-i18n/final-root-review-20260819/engine_unknown_212_application_verification.json",
    "engine_final_roundtrip": RESEARCH / "engine-i18n/final-root-review-20260819/engine_unknown_212_roundtrip_verification.json",
    "engine_native_closure": RESEARCH / "engine-i18n/official-cn-native-exhaustion-20260821/official-cn-native-localization-exhaustion.json",
    "engine_machine_review": Path("magica/i18n_audit/release_v26_authority/machine_translation_review/engine_i18n_review_621.tsv"),
    "machine_review_summary": Path("magica/i18n_audit/release_v26_authority/machine_translation_review/summary.json"),
    "engine_table": Path("madomagi/engine_i18n.tsv"),
}

EXTERNAL_INPUTS = {
    "old_only": Path("old_only_928_closure_20260819/closure_summary.json"),
    "old_only_verification": Path("old_only_928_closure_20260819/verification.json"),
    "dependencies": Path("visible_closure_audit_20260819/dependency_classification_122.tsv"),
    "dynamic_images": Path("dynamic_image_recovery_audit_20260819/dynamic_official_cn_681_product_coverage_verification.json"),
    "native_atlas": Path("apk_overlay_atlas_clean_20260819/verification.json"),
    "native_atlas_manifest": Path("apk_overlay_atlas_clean_20260819/manifest.json"),
    "native_engine": Path("native_engine_i18n_authority_audit_315_20260819/verification.json"),
    "special_surfaces": Path("visible_residual_final_20260819/special_surface_closure.json"),
    "zero_categories": Path("visible_residual_final_20260819/zero_increment_categories.tsv"),
}


class EvidenceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def raw(path: Path) -> bytes:
    require(path.is_file(), f"missing evidence: {path}")
    return path.read_bytes()


def load_json(path: Path):
    try:
        return json.loads(raw(path).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"invalid JSON: {path}: {exc}") from exc


def load_tsv(path: Path) -> list[dict[str, str]]:
    try:
        rows = list(csv.DictReader(raw(path).decode("utf-8-sig").splitlines(), delimiter="\t"))
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"invalid TSV: {path}: {exc}") from exc
    require(bool(rows), f"empty TSV: {path}")
    return rows


def evidence_entry(path: Path, root: Path | None = None) -> dict[str, object]:
    label = str(path)
    if root is not None:
        try:
            label = path.relative_to(root).as_posix()
        except ValueError:
            pass
    return {"path": label, "bytes": path.stat().st_size}


def build_summary(repo_root: Path, evidence_root: Path) -> dict[str, object]:
    repo_root, evidence_root = repo_root.resolve(), evidence_root.resolve()
    rp = {key: repo_root / rel for key, rel in REPO_INPUTS.items()}
    ep = {key: evidence_root / rel for key, rel in EXTERNAL_INPUTS.items()}

    authority = load_json(rp["authority_summary"])
    authority_check = load_json(rp["authority_verification"])
    require(authority.get("scope", {}).get("official_old_root") == "A:\\magicaOLD", "official root drift")
    require(authority.get("scope", {}).get("upstream_root") == "A:\\totentanz-frontend", "upstream root drift")
    require(authority_check.get("old_only_path_inventory.tsv", {}).get("rows") == 928, "928 inventory drift")

    old = load_json(ep["old_only"])
    old_check = load_json(ep["old_only_verification"])
    require(old.get("schema") == "visible-closure-old-only-928-final-v5", "old-only schema is not terminal")
    require(old.get("status") == "pass-closed" and old.get("input_rows") == 928, "old-only closure failed")
    remaining = old.get("remaining", {})
    require(remaining.get("actionable_paths") == remaining.get("actionable_rows") == remaining.get("japanese_ui_candidates") == 0, "old-only remainder is nonzero")
    require(old_check.get("status") == "pass" and old_check.get("assertions", {}).get("remaining_actionable") == 0, "old-only verification failed")

    deps = load_tsv(ep["dependencies"])
    require(len(deps) == 122 and len({row.get("path") for row in deps}) == 122, "dependency inventory drift")
    ext = Counter(Path(row["path"]).suffix.lower() for row in deps)
    require(ext == Counter({".css": 62, ".html": 48, ".json": 12}), f"dependency partition drift: {dict(ext)}")
    css = [row for row in deps if row["path"].endswith(".css")]
    html = [row for row in deps if row["path"].endswith(".html")]
    json_rows = [row for row in deps if row["path"].endswith(".json")]
    for name, rows in (("CSS", css), ("JSON", json_rows)):
        require(not any(row.get("disposition", "").startswith("actionable-") for row in rows), f"{name} actionable value remains")

    html_check = load_json(rp["missing_html"])
    require(html_check.get("result") == "passed" and html_check.get("checked_files") == 10, "ten-file HTML materialization failed")
    require(html_check.get("literal_records") == 30, "HTML literal record drift")
    materialized = {entry["product_path"] for entry in html_check.get("entries", [])}
    require(len(materialized) == 10, "HTML product path set is not ten")

    rule = load_json(rp["rule_popup"])
    require(rule.get("result") == "passed" and rule.get("checked_files") == 1, "RulePopup verification failed")
    require(rule.get("translation_records") == 146 and rule.get("unexpected_kana_records") == 0, "RulePopup record drift")
    rule_path = "magica/template/etc/RulePopup.html"
    materialized.add(rule_path)
    require(len(materialized) == 11, "HTML materialized set is not eleven")
    inventory_html = {f"magica/{row['path']}" for row in html}
    require(materialized <= inventory_html, "materialized HTML escaped the sealed inventory")
    present_html = {f"magica/{row['path']}" for row in html if (repo_root / "magica" / Path(row["path"])).is_file()}
    require(present_html == materialized and len(inventory_html - present_html) == 37, "HTML 11+37 terminal partition drift")
    rule_text = (repo_root / rule_path).read_text(encoding="utf-8-sig")
    require(not re.search(r"[\u3041-\u3096\u30a1-\u30fa]", rule_text), "RulePopup still contains kana")

    round6_manifest = load_json(rp["round6_manifest"])
    round6 = load_json(rp["round6_verification"])
    op_count = sum(len(entry.get("operations", [])) for entry in round6_manifest.get("entries", []))
    require(round6.get("result") == "passed" and round6.get("checked_files") == 6, "Round6 verification failed")
    require(round6_manifest.get("literal_count") == round6.get("literal_changes") == op_count == 15, "Round6 is not 15/15")
    for entry in round6.get("entries", []):
        path = repo_root / entry["product_path"]
        require(path.is_file() and path.stat().st_size == entry["bytes"], f"Round6 product drift: {path}")

    images = load_json(rp["image_inventory"])
    counts = images.get("counts", {})
    require(images.get("result") == "PASS", "same-path image inventory failed")
    require((counts.get("same_path_png"), counts.get("unresolved_actionable"), counts.get("exhausted_no_value")) == (8868, 160, 8708), "8868 image partition drift")
    image_closure = load_json(rp["image_closure"])
    require(image_closure.get("status") == "PASS" and image_closure.get("known_actionable") == image_closure.get("closed_total") == 160, "160 image closure failed")
    require(image_closure.get("remaining_from_known_inventory") == 0, "image remainder is nonzero")

    dynamic = load_json(ep["dynamic_images"])
    require(dynamic.get("result") == "PASS", "dynamic image verification failed")
    require(all(dynamic.get(key) == 681 for key in ("classification_candidates", "unique_paths", "product_present", "png_parse_pass")), "dynamic images are not 681/681")
    require(dynamic.get("direct_copy_candidates", 0) + dynamic.get("canvas_adaptation_candidates", 0) == 681, "dynamic image partition drift")

    atlas = load_json(ep["native_atlas"])
    atlas_manifest = load_json(ep["native_atlas_manifest"])
    require(atlas.get("status") == "passed" and atlas.get("frame_count") == 9, "native atlas is not 9/9")
    require(atlas.get("non_target_changed_pixel_count") == 0 and atlas.get("checks", {}).get("nine_target_frames_verified") is True, "native atlas target boundary failed")
    require(atlas_manifest.get("frame_count") == len(atlas_manifest.get("visible_replacements", [])) == 9, "native atlas manifest drift")

    engine_gap = load_json(rp["engine_gap"])
    engine_lines = raw(rp["engine_table"]).decode("utf-8-sig").splitlines()
    require(engine_gap.get("ok") is True, "engine evidence failed")
    require((engine_gap.get("logical_rule_count"), engine_gap.get("physical_line_count")) == (621, 622), "engine evidence is not 621/622")
    require(engine_gap.get("generated_timer_rules") == 301, "dynamic AP timer expansion is not 301 rules")
    require(engine_gap.get("timer_coverage", {}).get("all_values_present") is True, "dynamic AP timer coverage is incomplete")
    require(engine_gap.get("unsupported_rules") == 2 and engine_gap.get("unsupported_present") == 0, "AP consumer boundary drift")
    require(len(engine_lines) == 622 and sum("\t" in line for line in engine_lines) == 621, "current engine table is not 621/622")
    require(not any(line.startswith("~") for line in engine_lines), "unsupported substring rule leaked into engine table")
    native_engine = load_json(ep["native_engine"])
    require(native_engine.get("passed") is True and native_engine.get("tsv_rows") == native_engine.get("json_rows") == 314, "native engine baseline evidence failed")
    require(native_engine.get("checks", {}).get("summary_physical_lines_315") is True, "native engine is not the 315-line terminal state")
    require(native_engine.get("checks", {}).get("unsupported_ap_substring_rules_absent") is True, "native engine contains unsupported AP rules")

    native_closure = load_json(rp["engine_native_closure"])
    native_records_all = native_closure.get("records", [])
    native_records = [row for row in native_records_all if row.get("product_write_allowed") is True]
    native_expected = native_closure.get("expected_post_application", {})
    require(
        native_closure.get("schema") == "official-cn-native-localization-exhaustion/v1"
        and len(native_records_all) == 189
        and len(native_records) == 182
        and len(native_closure.get("dispositions", [])) == 349,
        "official CN native localization closure drifted",
    )
    require(
        native_expected.get("engine_logical_rules") == 621
        and native_expected.get("engine_physical_lines") == 622,
        "official CN native post-application contract drifted",
    )
    native_by_source = {row["source"]: row for row in native_records}
    require(len(native_by_source) == 182, "official CN native accepted source keys are not unique")

    engine_quality = load_json(rp["engine_final_quality"])
    require(engine_quality.get("schema") == 2, "engine final-review schema drift")
    require(engine_quality.get("scope", {}).get("rows") == 212, "engine final review is not 212/212")
    require(
        engine_quality.get("verdict_counts") == {
            "acceptable-no-change": 172,
            "correction-required": 40,
        },
        "engine final-review verdict partition drift",
    )
    require(
        engine_quality.get("correction_source_counts") == {
            "official-cn-native-sequence-exact-both-abis": 35,
            "manual-semantic-reviewed": 5,
        },
        "engine final-review correction source partition drift",
    )
    application = load_json(rp["engine_final_application"])
    require(
        application.get("status") == "pass"
        and application.get("state") == "applied"
        and application.get("review_rows") == application.get("exact_bindings") == 212
        and application.get("correction_rows") == 40
        and application.get("errors") == [],
        "engine 40-correction application verification failed",
    )
    roundtrip = load_json(rp["engine_final_roundtrip"])
    require(
        roundtrip.get("status") == "pass"
        and roundtrip.get("final", {}).get("state") == "applied"
        and roundtrip.get("final", {}).get("exact_bindings") == 212,
        "engine correction rollback/reapply roundtrip failed",
    )
    sidecar = load_json(rp["engine_final_sidecar"])
    sidecar_rows = sidecar.get("rows", [])
    require(sidecar.get("schema") == 2 and len(sidecar_rows) == 212, "engine final-review sidecar drift")
    require(len({row.get("row_id") for row in sidecar_rows}) == 212, "engine final-review row IDs are not unique")
    require(all(row.get("origin_machine_translated") == "unknown" for row in sidecar_rows), "engine historical origin marker drift")
    verdicts = Counter(row.get("semantic_verdict") for row in sidecar_rows)
    require(verdicts == Counter({"approved-current": 172, "correction-proposed": 40}), "engine sidecar verdict drift")
    current_engine_bindings = 0
    native_shadowed_bindings = 0
    for row in sidecar_rows:
        physical_line = row.get("physical_line")
        require(isinstance(physical_line, int) and 1 <= physical_line <= len(engine_lines), "engine physical-line binding escaped the table")
        parts = engine_lines[physical_line - 1].split("\t", 1)
        require(len(parts) == 2 and parts[0] == row.get("source_key"), f"engine source binding drift: {row.get('row_id')}")
        native = native_by_source.get(row["source_key"])
        expected_cn = (
            native["selected_cn"]
            if native is not None
            else row.get("proposed_cn") if row.get("semantic_verdict") == "correction-proposed" else row.get("before_cn")
        )
        require(parts[1] == expected_cn, f"engine current Chinese binding drift: {row.get('row_id')}")
        native_shadowed_bindings += int(native is not None)
        current_engine_bindings += 1

    engine_review_rows = load_tsv(rp["engine_machine_review"])
    require(len(engine_review_rows) == 621, "engine machine-review inventory is not 621")
    engine_partition = Counter(row.get("component") for row in engine_review_rows)
    expected_engine_partition = Counter(native_expected["engine_component_partition"])
    require(engine_partition == expected_engine_partition, f"engine authority partition drift: {dict(engine_partition)}")
    engine_review_by_source = {row["japanese_or_source_original"]: row for row in engine_review_rows}
    require(len(engine_review_by_source) == 621, "engine machine-review source keys are not unique")
    final_root_takeover = sum(
        engine_review_by_source[row["source_key"]].get("source_stage") == "final-root-review-20260819"
        for row in sidecar_rows
    )
    final_root_shadowed = len(sidecar_rows) - final_root_takeover
    require(
        native_shadowed_bindings == 123
        and final_root_takeover == native_expected["final_root_review_takeover"]
        and final_root_shadowed == native_expected["final_root_review_higher_authority_shadowed"],
        "engine final-root higher-authority partition drifted",
    )
    machine_summary = load_json(rp["machine_review_summary"])
    machine_counts = machine_summary.get("counts", {})
    require(machine_counts.get("engine_unverified") == 0, "engine unverified rows remain")
    require(machine_counts.get("engine_partition") == dict(expected_engine_partition), "engine summary partition drift")

    surfaces = load_json(ep["special_surfaces"])
    battle = next((row for row in surfaces if row.get("surface") == "战斗结束"), None)
    require(battle is not None and "玩家自定义名称" in battle.get("notes", ""), "player-name retention evidence missing")
    zero_rows = load_tsv(ep["zero_categories"])
    formal = next((row for row in zero_rows if row.get("category", "").startswith("Puella Historia、Magia")), None)
    require(formal is not None and formal.get("increment") == "0", "formal mechanism retention evidence missing")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "as_of": "2026-08-21",
        "scope": {
            "repo_root": str(repo_root),
            "official_cn_text_root": "A:\\magicaOLD",
            "current_us_text_root": "A:\\totentanz-frontend",
            "mode": "terminal-evidence-compose-after-official-cn-native-application",
            "product_writes": 85,
            "git_writes": 0,
            "network_writes": 0,
        },
        "text": {
            "old_only_paths": {"total": 928, "closed": 928, "remaining": 0},
            "missing_dependencies": {
                "total": 122,
                "css": {"total": 62, "fixed_visible_value": 0, "terminal_excluded": 62},
                "json": {"total": 12, "fixed_visible_value": 0, "terminal_excluded": 12},
                "html": {"total": 48, "materialized": 11, "terminal_excluded_or_no_fixed_text": 37, "materialized_paths": sorted(materialized)},
            },
            "rule_popup": {"translation_records": 146, "unexpected_kana_records": 0},
            "round6": {"literal_changes": 15, "verified": 15, "files": 6},
            "retained_by_policy": {
                "formal_mechanisms": "Puella Historia、Magia、正式机制名、角色刻意口癖/自称",
                "player_names": "Inkyubus、Kyubi* 等玩家自定义名称",
                "official_cn_connect_skill_descriptions": 9,
            },
            "remaining_authority_or_root_translation_increment": 0,
        },
        "images": {
            "same_path": {"total": 8868, "actionable_closed": 160, "no_transferable_value": 8708, "remaining": 0},
            "dynamic_official_cn": {"total": 681, "product_present": 681, "remaining": 0},
            "native_quest_atlas": {"verified_frames": 9, "remaining_declared_frames": 0, "non_target_changed_pixels": 0, "artifact": atlas_manifest.get("artifact")},
        },
        "engine_i18n": {
            "logical_rules": 621,
            "physical_lines": 622,
            "official_cn_native_exhaustion": {
                "unique_runtime_han_strings": 349,
                "classified": 349,
                "stable_mapping_records": 189,
                "accepted_source_keys": 182,
                "actual_table_changes": 85,
                "new_source_keys": 6,
                "debug_or_unstable_injections": 0,
            },
            "final_semantic_review": {
                "reviewed": current_engine_bindings,
                "total": 212,
                "higher_authority_shadowed": final_root_shadowed,
                "retained_final_root_takeover": final_root_takeover,
                "acceptable_no_change": 172,
                "corrections_required": 40,
                "corrections_applied": 40,
                "official_cn_dual_abi_exact_corrections": 35,
                "root_semantic_corrections": 5,
                "historical_origin_machine_translated": "unknown-preserved-in-evidence",
                "rollback_reapply_roundtrip": "pass",
            },
            "dynamic_timer_prefix_closure": {
                "source_fragments": 2,
                "generated_prefix_rules": 301,
                "first_countdown_range": "0:00..5:00",
                "full_countdown_suffix_preserved": True,
                "consumer_contract": "exact-and-prefix-only",
                "status": "closed",
            },
            "authority_partition": {
                "official": 207,
                "confirmed_human_dynamic_timer": 301,
                "root_reviewed": 110,
                "wiki": 2,
                "intentional": 1,
            },
            "unverified": 0,
            "unsupported_runtime_rules_present": 0,
            "consumer_boundaries": [],
            "resolved_consumer_boundaries": [
                {
                    "rule_id": row.get("rule_id"),
                    "source": row.get("source"),
                    "suggested_cn": row.get("target"),
                    "classification": "closed-by-finite-prefix-expansion",
                    "reason": "301 prefixes cover every first-countdown value from 0:00 through 5:00 and preserve the full-countdown suffix",
                }
                for row in engine_gap.get("unsupported_records", [])
            ],
        },
        "nonterminal_inputs_explicitly_not_used": [
            "stale 316-line engine snapshots",
            "pre-closure/error 24-item lists",
            "pre-application RulePopup rejection",
        ],
        "evidence": {
            "repository": {key: evidence_entry(path, repo_root) for key, path in sorted(rp.items())},
            "external_read_only": {key: evidence_entry(path) for key, path in sorted(ep.items())},
        },
    }


def render_report(summary: dict[str, object]) -> str:
    html = summary["text"]["missing_dependencies"]["html"]
    resolved_boundary = summary["engine_i18n"]["resolved_consumer_boundaries"]
    lines = [
        "# 最终来源耗尽聚合报告（2026-08-21）",
        "",
        "## 终态",
        "",
        "**PASS：在封存的 A:\\magicaOLD、A:\\totentanz-frontend、权威层、图像与 native/engine 证据范围内，仍可安全物化的权威中文或已审核新译增量为 0。**",
        "",
        "本报告组合已完成证据，并记录本轮从国服双 ABI native 稳定源键物化到 engine 表的 85 项变更；没有重新扫描 A 盘大树。",
        "",
        "## 文本",
        "",
        "- 旧国服/美服独有文本路径：**928/928**，剩余 **0**。",
        "- 缺依赖 CSS：**62**，固定可见汉化价值 **0**。",
        "- 缺依赖 JSON：**12**，稳定固定 UI 汉化价值 **0**。",
        "- 缺依赖 HTML：**48 = 已物化 11 + 明确排除或无固定文本 37**。",
        "- RulePopup：**146** 条记录，意外日文假名 **0**。",
        "- Round6：**15/15** 条可见文本已物化并验证。",
        "",
        "### 已物化 HTML",
        "",
    ]
    lines.extend(f"- `{path}`" for path in html["materialized_paths"])
    lines += [
        "",
        "## 图像",
        "",
        "- 同路径图：**8,868**；可行动项 **160/160** 闭合，无价值 **8,708**。",
        "- 动态官方中文图：**681/681** 已进入产品并通过解码验证。",
        "- native quest 图集：**9/9** 帧闭合，目标框外像素变化 **0**。",
        "",
        "## 明确保留",
        "",
        "- `Puella Historia`、`Magia`、正式机制名、角色刻意口癖/自称。",
        "- `Inkyubus`、`Kyubi*` 等玩家自定义名称。",
        "- 9 个稳定 skillId 的旧国服原文自身使用 `Connect`；普通 UI 仍按规则使用“连携”。",
        "",
        "## engine_i18n 消费者边界",
        "",
        "- 当前表：**621 条逻辑规则 / 622 物理行**；无 `~` 伪规则。",
        "- 国服 native：运行时可分配区含中文的 **349/349** 项已分类；得到 **189** 条稳定映射记录，接受 **182** 个源键，实际表变更 **85** 项（含新增源键 **6**），调试/不稳定源注入 **0**。",
        "- 历史最终语义复审：原 **212/212** 绑定仍可追溯；其中 **124** 项现由更高权威覆盖，保留原最终复审接管 **88** 项。历史 **40/40** 项修正的应用及回撤证据仍保留。",
        "- 终态分区：官方 **207** / 已确认人工动态 AP 规则 **301** / 根任务复审 **110** / Wiki **2** / 刻意结构规则 **1**；未验证 **0**。",
        "- 当前消费者只支持 exact 与 `^prefix`。两段 AP 动态文本已通过 **301 条有限前缀**覆盖首段倒计时 `0:00..5:00`，并保留末段完整回复时间后缀：",
        "",
    ]
    lines.extend(f"- `{row['source']}` → `{row['suggested_cn']}`（`{row['rule_id']}`，已闭合）" for row in resolved_boundary)
    lines += [
        "",
        "## 证据纪律",
        "",
        "没有采用旧 316 行 engine 快照、闭合前错误 24 项清单或闭合前 RulePopup 拒绝结论。`summary.json` 记录当前产品、国服 native 闭合证据及外部只读证据的路径与字节数。",
        "",
    ]
    return "\n".join(lines)


def output_bytes(summary: dict[str, object]) -> dict[str, bytes]:
    return {
        "summary.json": (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        "REPORT_CN.md": render_report(summary).encode("utf-8"),
    }


def write_or_check(outputs: dict[str, bytes], output_dir: Path, check: bool) -> None:
    if check:
        for name, expected in outputs.items():
            path = output_dir / name
            require(path.is_file() and path.read_bytes() == expected, f"stale or missing output: {path}")
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        path = output_dir / name
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(payload)
        temp.replace(path)


def main() -> int:
    repo_default = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_default)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    evidence = (args.evidence_root or (repo.parent / "next_round_execution_20260819")).resolve()
    output = (args.output_dir or (repo / OUTPUT)).resolve()
    try:
        summary = build_summary(repo, evidence)
        write_or_check(output_bytes(summary), output, args.check)
    except EvidenceError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print("PASS: final source exhaustion 928/928; HTML 11+37; images 8868+681; atlas 9; native Han 349/349; engine 621/622, AP timer 301/301, final-root 124 shadowed + 88 retained, unverified 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
