#!/usr/bin/env python3
"""Deterministic tests for the closed frontend empty-candidate partition."""

from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "tools" / "build-v26-machine-review.py"
SPEC = importlib.util.spec_from_file_location("build_v26_machine_review", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FrontendEmptyClassificationTests(unittest.TestCase):
    def test_product_file_hash_normalizes_utf8_crlf_but_not_binary(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lf = root / "lf.txt"
            crlf = root / "crlf.txt"
            binary_lf = root / "binary-lf.bin"
            binary_crlf = root / "binary-crlf.bin"
            lf.write_bytes("第一行\n第二行\n".encode("utf-8"))
            crlf.write_bytes("第一行\r\n第二行\r\n".encode("utf-8"))
            binary_lf.write_bytes(b"\x00first\nsecond\n")
            binary_crlf.write_bytes(b"\x00first\r\nsecond\r\n")
            self.assertEqual(
                MODULE.canonical_product_file_sha256(lf),
                MODULE.canonical_product_file_sha256(crlf),
            )
            self.assertNotEqual(
                MODULE.canonical_product_file_sha256(binary_lf),
                MODULE.canonical_product_file_sha256(binary_crlf),
            )

    def test_ap_recovery_engine_evidence_partition(self) -> None:
        evidence = MODULE.read_json(MODULE.AP_RECOVERY_ENGINE)
        self.assertTrue(evidence["ok"])
        self.assertEqual(evidence["active_rules"], 308)
        rules = evidence["records"]
        self.assertEqual(len(rules), 308)
        self.assertEqual(
            Counter(row["source_tier"] for row in rules),
            Counter({"official-cn": 7, "confirmed-human": 301}),
        )
        self.assertTrue({
            "50 AP Potion", "AP Potion", "Magia Stones", "Use ", "Stock: ",
            "Cost: ", "Restore",
        }.issubset({row["source"] for row in rules}))
        self.assertEqual(evidence["timer_coverage"]["value_count"], 301)
        self.assertTrue(evidence["timer_coverage"]["all_values_present"])
        self.assertEqual(len(evidence["removed_unsupported_records"]), 2)

    def test_product_snapshot_excludes_self_referential_maintenance_files(self) -> None:
        before = MODULE.product_content_snapshot()
        probes = [
            ROOT / "tools" / ".machine-review-snapshot-probe.txt",
            ROOT / "scripts" / ".machine-review-snapshot-probe.txt",
            ROOT / ".github" / ".machine-review-snapshot-probe.txt",
        ]
        self.assertTrue(all(not probe.exists() for probe in probes))
        try:
            for probe in probes:
                probe.parent.mkdir(parents=True, exist_ok=True)
                probe.write_text("maintenance-only\n", encoding="utf-8", newline="\n")
            self.assertEqual(before, MODULE.product_content_snapshot())
        finally:
            for probe in probes:
                probe.unlink(missing_ok=True)

    def test_product_snapshot_includes_runtime_product_file(self) -> None:
        before = MODULE.product_content_snapshot()
        probe = ROOT / "magica" / "js" / ".machine-review-product-probe.txt"
        self.assertFalse(probe.exists())
        try:
            probe.write_text("runtime-product\n", encoding="utf-8", newline="\n")
            self.assertNotEqual(before, MODULE.product_content_snapshot())
        finally:
            probe.unlink(missing_ok=True)

    def test_engine_621_provenance_partition(self) -> None:
        master: list[dict[str, str]] = []
        MODULE.append_migrated_i18n_and_engine(master)
        engine = [row for row in master if row["scope"] == "native_engine_i18n"]
        native_expected = MODULE.read_json(MODULE.ENGINE_OFFICIAL_CN_NATIVE)["expected_post_application"]
        self.assertEqual(len(engine), 621)
        self.assertEqual(
            Counter(row["component"] for row in engine),
            Counter(native_expected["engine_component_partition"]),
        )
        self.assertFalse(any(row["component"] == "engine_runtime_i18n_unverified" for row in engine))
        final_root_rows = [row for row in engine if row["source_stage"] == "final-root-review-20260819"]
        self.assertEqual(len(final_root_rows), 88)
        sidecar_by_id = {
            row["row_id"]: row
            for row in MODULE.read_json(MODULE.ENGINE_FINAL_ROOT_REVIEW)["rows"]
        }
        self.assertEqual(
            Counter(sidecar_by_id[row["source_batch"]]["semantic_verdict"] for row in final_root_rows),
            Counter({"approved-current": 78, "correction-proposed": 10}),
        )
        self.assertEqual(
            Counter(row["highest_authority_tier"] for row in final_root_rows),
            Counter({
                "official-cn-native-sequence-exact-both-abis": 6,
                "manual-semantic-reviewed": 82,
            }),
        )
        self.assertEqual(Counter(row["is_machine_translation"] for row in final_root_rows), Counter({"false": 88}))
        self.assertTrue(all("origin_machine_translated=unknown" in row["evidence"] for row in final_root_rows))
        no = next(row for row in engine if row["japanese_or_source_original"] == "いいえ")
        self.assertEqual(no["current_cn"], "否")
        self.assertEqual(no["component"], "engine_runtime_i18n_root_reviewed")
        self.assertEqual(no["review_status"], "root-reviewed-approved")
        single_rare = next(row for row in engine if row["japanese_or_source_original"] == "単発 - レアカード")
        self.assertEqual(single_rare["current_cn"], "单抽 - 稀有卡牌")
        self.assertEqual(single_rare["component"], "engine_runtime_i18n_official")
        self.assertEqual(single_rare["highest_authority_tier"], "official-cn-native-exact")
        ap_rows = {
            row["japanese_or_source_original"]: row
            for row in engine
            if row["source_stage"] == "ap-recovery-gap-verification"
        }
        self.assertEqual(len(ap_rows), 308)
        self.assertEqual(ap_rows["^Use "]["current_cn"], "消费 ")
        timer = ap_rows["^1 AP will recover in 2:34 / AP will be fully recovered in "]
        self.assertEqual(timer["current_cn"], "距回复1 AP还有 2:34 / 距AP全部回复还有 ")
        self.assertEqual(timer["component"], "engine_runtime_i18n_confirmed_human")
        self.assertEqual(timer["review_status"], "confirmed-human-verified")
        self.assertNotIn("~ AP will recover in ", ap_rows)
        self.assertNotIn("~ / AP will be fully recovered in ", ap_rows)
        connect = next(row for row in engine if row["japanese_or_source_original"] == "コネクト")
        self.assertEqual(connect["current_cn"], "连携")
        self.assertEqual(connect["source_stage"], "connect-context-authority")
        self.assertEqual(connect["review_status"], "official-cn-terminology-verified")
        self.assertEqual(connect["component"], "engine_runtime_i18n_official")
        connect_ascii = next(row for row in engine if row["japanese_or_source_original"] == "Connect")
        self.assertEqual(connect_ascii["current_cn"], "连携")
        self.assertEqual(connect_ascii["source_stage"], "connect-context-authority")
        self.assertEqual(connect_ascii["component"], "engine_runtime_i18n_official")
        barrier_prefix = next(row for row in engine if row["japanese_or_source_original"] == "敵からのダメージを ")
        self.assertEqual(barrier_prefix["current_cn"], "使来自敌方的伤害无效化")
        barrier_suffix = next(row for row in engine if row["japanese_or_source_original"] == "だけ無効化する")
        self.assertEqual(barrier_suffix["current_cn"], "点")
        magia_drain = next(row for row in engine if row["japanese_or_source_original"] == "Magia Drain [VI]")
        self.assertEqual(magia_drain["current_cn"], "Magia汲取[Ⅵ]")
        self.assertEqual(magia_drain["component"], "engine_runtime_i18n_root_reviewed")
        self.assertEqual(magia_drain["review_status"], "resolved")
        magia_effect = next(
            row for row in engine
            if row["japanese_or_source_original"]
            == "Magia Damage DOWN [VI] (Target/1 Turn) / Magia Damage UP [VI] (Self/1 Turn)"
        )
        self.assertEqual(
            magia_effect["current_cn"],
            "Magia伤害下降[Ⅵ](敌单/1T) & Magia伤害提升[Ⅵ](自/1T)",
        )
        self.assertEqual(magia_effect["component"], "engine_runtime_i18n_wiki")
        mp_boost = next(row for row in engine if row["japanese_or_source_original"] == "MPブーストUp")
        self.assertEqual(mp_boost["current_cn"], "MP获取量提升")
        self.assertEqual(mp_boost["component"], "engine_runtime_i18n_official")
        burn = next(row for row in engine if row["japanese_or_source_original"] == "やけど")
        self.assertEqual(burn["current_cn"], "灼伤")
        self.assertEqual(burn["component"], "engine_runtime_i18n_official")
        survive = next(row for row in engine if row["japanese_or_source_original"] == "サヴァイヴ")
        self.assertEqual(survive["current_cn"], "幸存")
        self.assertEqual(survive["component"], "engine_runtime_i18n_official")
        self.assertEqual(survive["review_status"], "official-source-verified")
        variable = next(row for row in engine if row["japanese_or_source_original"] == "ヴァリアブル")
        self.assertEqual(variable["current_cn"], "Variable")
        self.assertEqual(variable["component"], "engine_runtime_i18n_wiki")
        self.assertEqual(variable["review_status"], "authority-retained-formal-mechanic")

    def test_final_root_engine_sidecar_exact_binding(self) -> None:
        payload = MODULE.read_json(MODULE.ENGINE_FINAL_ROOT_REVIEW)
        self.assertEqual(payload["schema"], 2)
        self.assertEqual(payload["binding"], "current-engine-physical-line-exact")
        rows = payload["rows"]
        self.assertEqual(len(rows), 212)
        self.assertEqual(len({row["row_id"] for row in rows}), 212)
        self.assertEqual(len({row["physical_line"] for row in rows}), 212)
        self.assertEqual(len({row["source_key"] for row in rows}), 212)
        self.assertTrue(all(row["origin_machine_translated"] == "unknown" for row in rows))
        self.assertEqual(
            Counter(row["semantic_verdict"] for row in rows),
            Counter({"approved-current": 172, "correction-proposed": 40}),
        )
        self.assertEqual(
            Counter(row["source_tier"] for row in rows),
            Counter({
                "official-cn-native-sequence-exact-both-abis": 35,
                "manual-semantic-reviewed": 177,
            }),
        )
        engine_lines = MODULE.PRODUCT / "madomagi" / "engine_i18n.tsv"
        current = engine_lines.read_text(encoding="utf-8-sig").splitlines()
        native = {
            row["source"]: row
            for row in MODULE.read_json(MODULE.ENGINE_OFFICIAL_CN_NATIVE)["records"]
            if row.get("product_write_allowed")
        }
        for row in rows:
            source, target = current[row["physical_line"] - 1].split("\t")
            expected = (
                native[source]["selected_cn"]
                if source in native
                else row["proposed_cn"] if row["semantic_verdict"] == "correction-proposed" else row["before_cn"]
            )
            self.assertEqual(source, row["source_key"])
            self.assertEqual(target, expected)

    def test_final_root_engine_sidecar_drift_fails_closed(self) -> None:
        original = MODULE.read_json(MODULE.ENGINE_FINAL_ROOT_REVIEW)
        mutations = {
            "unknown-tier": lambda data: data["rows"][0].__setitem__("source_tier", "unknown-tier"),
            "unknown-verdict": lambda data: data["rows"][0].__setitem__("semantic_verdict", "unknown-verdict"),
            "wrong-line": lambda data: data["rows"][0].__setitem__("physical_line", 9999),
            "wrong-source": lambda data: data["rows"][0].__setitem__("source_key", data["rows"][0]["source_key"] + "X"),
            "wrong-current": lambda data: next(
                row for row in data["rows"] if row["source_key"] == "【データサイズ："
            ).__setitem__(
                "proposed_cn",
                next(row for row in data["rows"] if row["source_key"] == "【データサイズ：")["proposed_cn"] + "X",
            ),
        }
        with tempfile.TemporaryDirectory() as folder:
            for label, mutate in mutations.items():
                with self.subTest(label=label):
                    data = json.loads(json.dumps(original, ensure_ascii=False))
                    mutate(data)
                    path = Path(folder) / f"{label}.json"
                    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    with mock.patch.object(MODULE, "ENGINE_FINAL_ROOT_REVIEW", path):
                        with self.assertRaises((AssertionError, KeyError)):
                            MODULE.append_migrated_i18n_and_engine([])

    def test_visible_term_closure_and_pass18_exact_inheritance(self) -> None:
        dicts = MODULE.Dictionaries(MODULE.LIBS)
        closure_rows, closure_index = MODULE.load_visible_term_closure(dicts)
        self.assertEqual(len(closure_rows), 3136)
        self.assertEqual(len(closure_index), 3136)
        self.assertEqual(
            Counter((row["source_tier"], row["review_status"]) for row in closure_rows),
            Counter({
                ("official-cn", "official-source-verified"): 762,
                ("root-reviewed-official-cn-terminology", "root-reviewed-approved"): 2372,
                ("wiki-exact-stable-id-plus-official-cn-terminology", "root-reviewed-approved"): 2,
            }),
        )

        pass18_master: list[dict[str, str]] = []
        applied = MODULE.apply_pass18_inventory(pass18_master, dicts, closure_index)
        runtime = [row for row in applied if row["file"].startswith("magica/js/libs/")]
        static = [row for row in applied if not row["file"].startswith("magica/js/libs/")]
        self.assertEqual(len(runtime), 938)
        self.assertEqual(len(static), 1)
        self.assertEqual(
            Counter(row["pass18_current_status"] for row in runtime),
            Counter({
                "direct-current-after-image": 536,
                "visible-term-closure-exact-supersession": 402,
            }),
        )
        self.assertEqual(
            Counter(row["strict_lookup_method"] for row in applied),
            Counter({"stable-key": 912, "json-pointer": 26, "static-literal": 1}),
        )
        p18_00018 = next(row for row in applied if row["change_id"] == "P18-00018")
        self.assertEqual(p18_00018["superseding_closure_id"], "DICT-00252")
        self.assertEqual(
            p18_00018["pass18_current_status"],
            "visible-term-closure-exact-supersession",
        )

        closure_master = list(pass18_master)
        closure_applied = MODULE.apply_visible_term_closure(closure_master, closure_rows)
        self.assertEqual(len(closure_applied), 3136)
        closure_current = next(
            row for row in closure_master
            if Path(row["file"]).name == "cardMagiaMap.json"
            and row["stable_key_or_line"] == "26018"
            and row["field"] == "shortDescription"
        )
        MODULE.finalize_review_columns(closure_current)
        self.assertEqual(closure_current["current_cn"], p18_00018["current_product_cn"])
        self.assertEqual(closure_current["source_bucket"], "new-root-human")
        self.assertIn("P18-00018", closure_current["evidence"])

    def test_pass18_unexplained_drift_and_missing_target_fail_closed(self) -> None:
        dicts = MODULE.Dictionaries(MODULE.LIBS)
        _, closure_index = MODULE.load_visible_term_closure(dicts)
        p18_00018 = next(row for row in MODULE.read_tsv(MODULE.PASS18) if row["change_id"] == "P18-00018")
        target = (
            Path(p18_00018["file"]).name,
            p18_00018["stable_key"],
            p18_00018["field"],
        )
        without_explanation = dict(closure_index)
        without_explanation.pop(target)
        with self.assertRaisesRegex(AssertionError, "no exact visible-term closure chain"):
            MODULE.apply_pass18_inventory([], dicts, without_explanation)

        with self.assertRaisesRegex(AssertionError, "strict dictionary target missing"):
            dicts.strict_value("cardList.json", "missing-stable-key", "cardName")
        value, method = dicts.strict_value(
            "charaMessageList.json",
            "8263",
            "message",
            json_pointer="/8263/message",
        )
        self.assertEqual(method, "json-pointer")
        self.assertTrue(value.startswith("我是PROMISED BLOOD的一员"))

    def audited_sources(self) -> list[dict[str, str]]:
        path = ROOT / "i18n" / "generated" / "input-provenance.tsv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            frontend = [
                row
                for row in csv.DictReader(handle, delimiter="\t")
                if row["source_file"] == "i18n/frontend-strings.tsv"
            ]
        unknown_empty = [
            row
            for row in frontend
            if (row["status"] != "present" or not row["candidate_cn"])
            and row["key"] not in MODULE.FRONTEND_EMPTY_53_DECISIONS
        ]
        self.assertEqual(unknown_empty, [])
        return [row for row in frontend if row["key"] in MODULE.FRONTEND_EMPTY_53_DECISIONS]

    def test_partition_is_exact_and_complete(self) -> None:
        rows = self.audited_sources()
        decisions = {
            row["source_text"]: MODULE.classify_frontend_empty_candidate(row)
            for row in rows
        }
        self.assertEqual(len(rows), 53)
        self.assertEqual(set(MODULE.FRONTEND_EMPTY_53_DECISIONS), {r["key"] for r in rows})
        self.assertEqual(
            Counter(d["closure_status"] for d in decisions.values()),
            Counter(
                {
                    "runtime-absent/not-backlog": 18,
                    "visible-cn-compatible-identity": 33,
                    "identity-punctuation": 1,
                    "official-cn-exact-path-dom-match": 1,
                }
            ),
        )

        for source, decision in decisions.items():
            if decision["closure_status"] == "runtime-absent/not-backlog":
                self.assertEqual(decision["suggested_cn"], "")
            elif decision["closure_status"] in {
                "visible-cn-compatible-identity",
                "identity-punctuation",
            }:
                self.assertEqual(decision["suggested_cn"], source)

        self.assertEqual(decisions["・"]["closure_status"], "identity-punctuation")
        self.assertEqual(
            decisions["属性相性"]["closure_status"],
            "official-cn-exact-path-dom-match",
        )
        self.assertEqual(
            decisions["属性相性"]["suggested_cn"],
            "属性克制",
        )
        self.assertEqual(decisions["属性相性"]["is_machine_translation"].split(";", 1)[0], "false")
        self.assertEqual(decisions["属性相性"]["manual_review_status"], "official-source-verified")
        official_source = next(row for row in rows if row["source_text"] == "属性相性")
        populated_official = {
            **official_source,
            "candidate_id": "candidate-id-changes-when-target-changes",
            "candidate_cn": "属性克制",
            "status": "present",
        }
        populated_decision = MODULE.classify_frontend_empty_candidate(populated_official)
        self.assertEqual(populated_decision["current_cn"], "属性克制")
        self.assertEqual(populated_decision["suggested_cn"], "属性克制")
        self.assertEqual(populated_decision["authority_status"], "official-source-verified")
        self.assertNotEqual(
            {d["manual_review_status"] for d in decisions.values()},
            {"needs-review/root-translation-required"},
        )

    def test_generated_backlog_rows_preserve_partition(self) -> None:
        _, rows = MODULE.build_glossary_support_and_frontend_backlog()
        self.assertEqual(len(rows), 53)
        self.assertEqual(
            Counter(row["manual_review_status"] for row in rows),
            Counter(
                {
                    "runtime-absent/not-backlog": 18,
                    "visible-cn-compatible-identity": 33,
                    "identity-punctuation": 1,
                    "official-source-verified": 1,
                }
            ),
        )
        self.assertEqual(
            [row["japanese_or_source_original"] for row in rows if row["manual_review_status"] == "official-source-verified"],
            ["属性相性"],
        )

        master: list[dict[str, str]] = []
        MODULE.append_support_universe(master, [], rows)
        for row in master:
            MODULE.finalize_review_columns(row)
        self.assertEqual(
            Counter(row["review_status"] for row in master),
            Counter(
                {
                    "runtime-absent/not-backlog": 18,
                    "visible-cn-compatible-identity": 33,
                    "identity-punctuation": 1,
                    "official-source-verified": 1,
                }
            ),
        )
        self.assertFalse(
            any(
                row["review_status"] == "needs-review/root-translation-required"
                or row["suggested_cn"] == "needs-review/root-translation-required"
                for row in master
            )
        )
        official = next(row for row in master if row["original_text"] == "属性相性")
        self.assertEqual(official["suggested_cn"], "属性克制")
        self.assertEqual(official["source_bucket"], "official")
        self.assertEqual(official["machine_translated"], "false")
        self.assertEqual(official["authority_status"], "official-source-verified")

    def test_unknown_candidate_fails_closed(self) -> None:
        with self.assertRaisesRegex(AssertionError, "unclassified empty frontend candidate"):
            MODULE.classify_frontend_empty_candidate(
                {"key": "global:unknown", "source_text": "UNKNOWN", "candidate_cn": ""}
            )


if __name__ == "__main__":
    unittest.main()
