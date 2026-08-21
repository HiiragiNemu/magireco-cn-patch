#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_tool():
    path = ROOT / "tools/apply-pass20-suggested-adoptions.py"
    spec = importlib.util.spec_from_file_location("pass21_adoptions_tested", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()
HELPER = TOOL.load_module(
    "pass21_adoptions_stage_helper_tested",
    ROOT / "tools/stage-pass20-human-review-product.py",
)


class Pass21SuggestedAdoptionTests(unittest.TestCase):
    def test_real_manifest_is_exact_low_authority_29_item_subset(self):
        # Pass21 is already promoted in the product tree.  The frozen queue keeps
        # the pre-adoption Chinese for provenance, while the target manifest now
        # correctly records the promoted value.  Verify that sealed state instead
        # of trying to rebuild a pre-promotion selection from post-promotion data.
        _, queue_rows = TOOL.read_tsv(ROOT / TOOL.QUEUE_REL)
        queue = TOOL.unique(queue_rows, "Pass20 queue")
        adoptions = TOOL.read_adoption_manifest(ROOT / TOOL.ADOPTION_REL)
        target_payload = json.loads((ROOT / TOOL.TARGETS_REL).read_text(encoding="utf-8"))
        targets = TOOL.unique(target_payload["items"], "Pass20 target manifest")

        self.assertEqual(len(adoptions), 29)
        self.assertEqual(sum(row["runtime_strategy"] == "target-manifest-exact" for row in adoptions.values()), 22)
        self.assertEqual(sum(row["runtime_strategy"] == "explicit-safe-paths" for row in adoptions.values()), 2)
        self.assertEqual(sum(row["runtime_strategy"] == "canonical-only" for row in adoptions.values()), 5)
        self.assertEqual(set(adoptions), {row["item_id"] for row in queue_rows if row.get("suggested_cn", "")})
        for item_id, adoption in adoptions.items():
            source = queue[item_id]
            target = targets[item_id]
            self.assertEqual(source["highest_authority_tier"], "legacy_unverified_ai_assisted")
            self.assertEqual(source["product_write_forbidden"], "false")
            self.assertEqual(adoption["current_cn"], source["current_cn"])
            self.assertEqual(adoption["ds_suggested_cn"], source["suggested_cn"])
            self.assertEqual(target["current_cn"], HELPER.decode_cell(adoption["adopted_cn"]))

    def test_frontend_update_preserves_machine_authority_and_adds_lineage(self):
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp)
            frontend = candidate / TOOL.FRONTEND_REL
            frontend.parent.mkdir(parents=True)
            selected = []
            existing_lineage = {}
            lines = ["# 原文\t译文\t风险\t出现次数\t出现于"]
            for index in range(29):
                source = f"source-{index}"
                before = f"before-{index}"
                after = before if index < 2 else f"after-{index}"
                lines.append(f"{source}\t{before}\tlow\t1\tmagica/js/{index}.js")
                if index < 2:
                    existing_lineage[TOOL.digest((source + "\0" + before).encode("utf-8"))] = {
                        "batch": "legacy-kimi-ai-assisted", "commit": "old",
                    }
                selected.append({
                    "item_id": f"LOW-MT-{index:05d}",
                    "source": {"japanese_or_source_original": source, "current_cn": before},
                    "final_cn": after,
                })
            frontend.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            migration = candidate / TOOL.MIGRATION_REL
            migration.write_text(json.dumps({
                "source_tables": {"frontend-strings.tsv": {
                    "translated_candidate_lineage": existing_lineage,
                    "normalized_lf_sha256": "old",
                }},
            }), encoding="utf-8")

            TOOL.update_frontend_and_lineage(candidate, selected)

            updated = frontend.read_text(encoding="utf-8")
            self.assertIn("source-2\tafter-2\t", updated)
            self.assertNotIn("source-2\tbefore-2\t", updated)
            payload = json.loads(migration.read_text(encoding="utf-8"))
            lineage = payload["source_tables"]["frontend-strings.tsv"]["translated_candidate_lineage"]
            self.assertEqual(len(lineage), 29)
            self.assertEqual(sum(row == {
                "batch": "pass21-user-directed-machine-suggestion", "commit": "",
            } for row in lineage.values()), 27)
            self.assertEqual(sum(row == {
                "batch": "legacy-kimi-ai-assisted", "commit": "old",
            } for row in lineage.values()), 2)
            adoption = payload["post_migration_adoptions"]["pass21_user_directed_suggested_adoptions"]
            self.assertTrue(adoption["machine_origin"])
            self.assertEqual(adoption["adoption_status"], "user-directed-suggestion-adopted")
            self.assertEqual(adoption["new_lineage_fingerprints"], 27)
            self.assertEqual(adoption["preserved_existing_lineage_fingerprints"], 2)

    def test_real_two_unchanged_adoptions_preserve_historical_lineage(self):
        adoptions = TOOL.read_adoption_manifest(ROOT / TOOL.ADOPTION_REL)
        unchanged = [
            row for row in adoptions.values()
            if row["adopted_cn"] == row["current_cn"]
        ]
        self.assertEqual({row["item_id"] for row in unchanged}, {"LOW-MT-00852", "LOW-MT-01200"})
        current = json.loads((ROOT / TOOL.MIGRATION_REL).read_text(encoding="utf-8"))
        lineage = current["source_tables"]["frontend-strings.tsv"]["translated_candidate_lineage"]
        for row in unchanged:
            fp = TOOL.digest(
                (row["source_text"] + "\0" + row["adopted_cn"]).encode("utf-8")
            )
            self.assertIn(fp, lineage)
            self.assertNotEqual(lineage[fp]["batch"], "pass21-user-directed-machine-suggestion")

    def test_runtime_exact_explicit_and_canonical_only_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp)
            exact = candidate / "magica/js/exact.js"
            explicit = candidate / "magica/template/explicit.html"
            canonical = candidate / "magica/js/canonical.js"
            exact.parent.mkdir(parents=True)
            explicit.parent.mkdir(parents=True)
            exact.write_text('const value="旧值";\n', encoding="utf-8", newline="\n")
            explicit.write_text('<div title="仓库"></div>\n', encoding="utf-8", newline="\n")
            canonical.write_text('const value="保持";\n', encoding="utf-8", newline="\n")
            selected = [
                {
                    "item_id": "EXACT", "before_literal": "旧值", "after_literal": "新值",
                    "strategy": "target-manifest-exact", "runtime_rewrites": [],
                    "target": {"application_allowed": True, "occurrences": [{"path": "js/exact.js"}]},
                },
                {
                    "item_id": "EXPLICIT", "before_literal": "仓库", "after_literal": "保管库",
                    "strategy": "explicit-safe-paths",
                    "runtime_rewrites": [{
                        "path": "template/explicit.html", "before": "仓库", "after": "保管库", "expected_count": 1,
                    }],
                    "target": {
                        "application_allowed": False, "occurrences": [],
                        "product_target_paths": ["template/explicit.html"],
                    },
                },
                {
                    "item_id": "CANONICAL", "before_literal": "保持", "after_literal": "仅维护层",
                    "strategy": "canonical-only", "runtime_rewrites": [],
                    "target": {"application_allowed": False, "occurrences": [], "product_target_paths": []},
                },
            ]

            changed, records, _ = TOOL.apply_runtime_changes(
                candidate, selected, HELPER, enforce_release_contract=False,
            )

            self.assertEqual(changed, ["magica/js/exact.js", "magica/template/explicit.html"])
            self.assertEqual({row["item_id"] for row in records}, {"EXACT", "EXPLICIT"})
            self.assertIn('"新值"', exact.read_text(encoding="utf-8"))
            self.assertIn('title="保管库"', explicit.read_text(encoding="utf-8"))
            self.assertEqual(canonical.read_text(encoding="utf-8"), 'const value="保持";\n')

    def _transaction_fixture(self, base: Path) -> tuple[Path, Path, dict[str, bytes]]:
        repo = base / "repo"
        stage = base / "stage"
        rollback = stage / "rollback"
        repo.mkdir()
        stage.mkdir()
        source_bytes = {
            TOOL.QUEUE_REL: b"queue\n",
            TOOL.TARGETS_REL: b"targets\n",
            TOOL.ADOPTION_REL: b"adoptions\n",
        }
        for rel, data in source_bytes.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        runtime_files = [f"magica/js/runtime-{index:02d}.js" for index in range(23)]
        canonical_files = [
            TOOL.FRONTEND_REL.as_posix(), TOOL.MIGRATION_REL.as_posix(), TOOL.CONTRACT_REL.as_posix(),
            *(rel.as_posix() for rel in TOOL.GENERATED_RELS),
        ]
        originals: dict[str, bytes] = {}
        records = []
        for index, rel in enumerate(runtime_files + canonical_files):
            before = f"before-{index}\n".encode()
            after = f"after-{index}\n".encode()
            target = repo.joinpath(*Path(rel).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(before)
            originals[rel] = before
            before_snapshot = rollback / "before" / rel
            after_snapshot = rollback / "after" / rel
            before_snapshot.parent.mkdir(parents=True, exist_ok=True)
            after_snapshot.parent.mkdir(parents=True, exist_ok=True)
            before_snapshot.write_bytes(before)
            after_snapshot.write_bytes(after)
            records.append({
                "path": rel, "before_exists": True,
                "before_snapshot": f"rollback/before/{rel}",
                "after_snapshot": f"rollback/after/{rel}",
                "before_sha256": TOOL.digest(before), "after_sha256": TOOL.digest(after),
                "before_size": len(before), "after_size": len(after),
            })
        report = {
            "schema": "magireco-cn-pass20-suggested-adoption-stage/1", "status": "PASS",
            "repository_writes": 0, "selected_items": 29,
            "target_manifest_exact_items": 22, "explicit_safe_path_items": 2,
            "canonical_only_items": 5, "runtime_materialized_items": 24,
            "runtime_occurrences": 30, "runtime_patch_records": 28,
            "runtime_files": runtime_files,
            "promotion_files": sorted(runtime_files + canonical_files),
            "protected_text_changes": 0,
            "adoption_manifest": TOOL.ADOPTION_REL.as_posix(),
            "queue_sha256": TOOL.digest(source_bytes[TOOL.QUEUE_REL]),
            "targets_sha256": TOOL.digest(source_bytes[TOOL.TARGETS_REL]),
            "adoption_manifest_sha256": TOOL.digest(source_bytes[TOOL.ADOPTION_REL]),
        }
        (stage / "verification.json").write_text(json.dumps(report), encoding="utf-8")
        (rollback / "manifest.json").write_text(json.dumps({
            "schema": "magireco-cn-pass20-suggested-adoption-rollback/1",
            "selection": {
                "items": 29, "target_manifest_exact_items": 22,
                "explicit_safe_path_items": 2, "canonical_only_items": 5,
                "runtime_materialized_items": 24, "runtime_occurrences": 30,
            },
            "files": records,
        }), encoding="utf-8")
        return repo, stage, originals

    def test_transaction_promotes_and_exactly_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, stage, originals = self._transaction_fixture(Path(temp))
            result = TOOL.promote(stage, repo)
            self.assertEqual(result["mode"], "promote")
            for rel, before in originals.items():
                self.assertNotEqual(repo.joinpath(*Path(rel).parts).read_bytes(), before)
            result = TOOL.rollback(stage, repo)
            self.assertEqual(result["mode"], "rollback")
            for rel, before in originals.items():
                self.assertEqual(repo.joinpath(*Path(rel).parts).read_bytes(), before)

    def test_mid_write_failure_restores_every_file(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, stage, originals = self._transaction_fixture(Path(temp))
            calls = 0

            def fail_on_third(source: Path, target: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError("synthetic mid-write failure")
                TOOL.atomic_replace(source, target)

            with self.assertRaisesRegex(TOOL.AdoptionError, "all changed files restored"):
                TOOL.promote(stage, repo, replace=fail_on_third)
            for rel, before in originals.items():
                self.assertEqual(repo.joinpath(*Path(rel).parts).read_bytes(), before)
            self.assertFalse((stage / "promotion_verification.json").exists())

    def test_report_write_failure_restores_every_file(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, stage, originals = self._transaction_fixture(Path(temp))

            def fail_report(_path: Path, _data: bytes) -> None:
                raise OSError("synthetic report failure")

            with self.assertRaisesRegex(TOOL.AdoptionError, "all changed files restored"):
                TOOL.promote(stage, repo, report_writer=fail_report)
            for rel, before in originals.items():
                self.assertEqual(repo.joinpath(*Path(rel).parts).read_bytes(), before)
            self.assertFalse((stage / "promotion_verification.json").exists())

    def test_source_hash_drift_rejects_promotion_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, stage, originals = self._transaction_fixture(Path(temp))
            (repo / TOOL.ADOPTION_REL).write_bytes(b"drift\n")
            with self.assertRaisesRegex(TOOL.AdoptionError, "source hash drifted"):
                TOOL.promote(stage, repo)
            for rel, before in originals.items():
                self.assertEqual(repo.joinpath(*Path(rel).parts).read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
