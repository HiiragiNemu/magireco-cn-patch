#!/usr/bin/env python3
"""Static ownership and publication contracts for the real hot-update producer."""

from __future__ import annotations

from pathlib import Path
import re
import textwrap
import unittest


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "sync-and-upload.yml"
PROMOTION = ROOT / "scripts" / "hotupdate_promotion.py"
DOGE_SYNC = ROOT / "scripts" / "sync-dogecloud.py"
PAN123_SYNC = ROOT / "scripts" / "sync-pan123-webdav.py"
MIRROR_TRANSACTION = ROOT / "scripts" / "release_asset_transaction.py"
RELEASE_BASELINE = ROOT / "scripts" / "hotupdate_release_baseline.py"


class HotUpdateWorkflowContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.promotion_text = PROMOTION.read_text(encoding="utf-8")
        cls.mirror_transaction_text = MIRROR_TRANSACTION.read_text(encoding="utf-8")
        cls.release_baseline_text = RELEASE_BASELINE.read_text(encoding="utf-8")
        cls.doge_text = DOGE_SYNC.read_text(encoding="utf-8")
        cls.pan123_text = PAN123_SYNC.read_text(encoding="utf-8")

    @classmethod
    def workflow_jobs(cls) -> dict[str, str]:
        """Return top-level job bodies without depending on a YAML library."""
        jobs_text = cls.text.split("\njobs:\n", 1)[1]
        starts = list(
            re.finditer(r"^  ([A-Za-z0-9_-]+):\s*$", jobs_text, flags=re.M)
        )
        jobs: dict[str, str] = {}
        for index, match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(jobs_text)
            jobs[match.group(1)] = jobs_text[match.end() : end]
        return jobs

    def test_change_detection_uses_the_tested_classifier(self):
        self.assertIn("scripts/classify_hotupdate_changes.py", self.text)
        self.assertIn('CHANGED=$(git diff --name-only', self.text)
        self.assertIn('|| echo "ALL"', self.text)

    def test_cross_job_context_references_are_declared(self):
        """Every steps/needs reference must be legal in its containing job."""
        jobs = self.workflow_jobs()
        self.assertEqual(
            list(jobs),
            [
                "setup",
                "pack-js",
                "pack-scenario",
                "publish",
                "r2-sync",
                "doge-sync",
                "pan123-upload",
                "mirror-release",
                "commit-configs",
                "bump-gate",
                "update-cursor",
                "summary",
            ],
        )
        for job_name, block in jobs.items():
            with self.subTest(job=job_name, context="steps"):
                declared_steps = set(
                    re.findall(
                        r"^\s+-?\s*id:\s*([A-Za-z0-9_-]+)\s*$",
                        block,
                        flags=re.M,
                    )
                )
                referenced_steps = set(
                    re.findall(r"\bsteps\.([A-Za-z0-9_-]+)\b", block)
                )
                self.assertEqual(referenced_steps - declared_steps, set())

            with self.subTest(job=job_name, context="needs"):
                declaration = re.search(
                    r"^    needs:\s*\[([^]]*)\]\s*$", block, flags=re.M
                )
                declared_needs = (
                    {item.strip() for item in declaration.group(1).split(",")}
                    if declaration
                    else set()
                )
                referenced_needs = set(
                    re.findall(r"\bneeds\.([A-Za-z0-9_-]+)\b", block)
                )
                self.assertEqual(referenced_needs - declared_needs, set())

    def test_setup_exports_classifier_flags_for_pack_jobs(self):
        setup = self.workflow_jobs()["setup"]
        self.assertIn("has_js:          ${{ steps.detect.outputs.has_js }}", setup)
        self.assertIn(
            "has_scenario:    ${{ steps.detect.outputs.has_scenario }}", setup
        )
        self.assertIn("if: steps.check_upstream.outputs.should_sync == 'true'", setup)
        self.assertNotIn("needs.setup", setup)

        pack_js = self.workflow_jobs()["pack-js"]
        pack_scenario = self.workflow_jobs()["pack-scenario"]
        self.assertIn("if: needs.setup.outputs.has_js == '1'", pack_js)
        self.assertIn("if: needs.setup.outputs.has_scenario == '1'", pack_scenario)
        self.assertNotIn("steps.detect", pack_js)
        self.assertNotIn("steps.check_upstream", pack_js)
        self.assertNotIn("steps.check_upstream", pack_scenario)

    def test_js_uses_deterministic_builder_and_final_product_verifier(self):
        self.assertIn(
            "python3 tools/build-v26-package.py --out cn_js_update_new.zip",
            self.text,
        )
        self.assertIn(
            "python3 tools/verify-v26-product.py --zip cn_js_update_new.zip",
            self.text,
        )
        self.assertNotIn("zip -r cn_js_update_new.zip", self.text)
        self.assertIn("runs-on: ubuntu-24.04", self.text)
        self.assertIn("python-version: '3.10.18'", self.text)
        self.assertIn(
            "python3 tools/build-v26-package.py --out cn_js_update_reprocheck.zip",
            self.text,
        )
        self.assertIn("cmp cn_js_update_reprocheck.zip cn_js_update_new.zip", self.text)
        self.assertIn("full_product_double_build_identical", self.text)

    def test_high_authority_gate_runs_before_product_packaging(self):
        pass20 = self.text.index(
            "python3 tools/pass20_official_static.py verify --state applied"
        )
        rebuild = self.text.index("python3 tools/build-v26-machine-review.py")
        freshness = self.text.index("git diff --exit-code --", rebuild)
        review_path = self.text.index(
            "magica/i18n_audit/release_v26_authority/machine_translation_review",
            freshness,
        )
        unit_tests = self.text.index("python3 tools/test-v26-authority-protection.py -v")
        verify = self.text.index("python3 tools/verify-v26-authority-protection.py --json")
        package = self.text.index(
            "python3 tools/build-v26-package.py --out cn_js_update_reprocheck.zip"
        )
        self.assertLess(pass20, rebuild)
        self.assertLess(rebuild, freshness)
        self.assertLess(freshness, review_path)
        self.assertLess(review_path, unit_tests)
        self.assertLess(unit_tests, verify)
        self.assertLess(verify, package)
        self.assertNotIn("tools/build-v26-authority-protection.py", self.text)

    def test_stable_publish_requires_closed_full_human_final_value_gate(self):
        validator = "python3 tools/validate-dsv4-human-review.py"
        self.assertIn(validator, self.text)
        self.assertIn("--require-release-open", self.text)
        self.assertIn(
            'if [ "${{ needs.setup.outputs.publish_hotfix }}" = "true" ]; then',
            self.text,
        )
        self.assertIn(
            "--final-values magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv",
            self.text,
        )
        self.assertIn(
            "--authority-resolutions magica/i18n_audit/release_v26_authority/pass20_authority_resolutions.tsv",
            self.text,
        )
        self.assertIn("--report _artifacts/dsv4_human_release_gate.json", self.text)
        self.assertLess(
            self.text.index(validator),
            self.text.index("python3 tools/build-v26-package.py --out cn_js_update_reprocheck.zip"),
        )

    def test_stable_publish_requires_materialized_pass20_review(self):
        verifier = "python3 tools/verify-pass20-human-materialization.py"
        package = "python3 tools/build-v26-package.py --out cn_js_update_reprocheck.zip"
        self.assertIn(verifier, self.text)
        self.assertIn("--report _artifacts/pass20_human_materialization_verification.json", self.text)
        self.assertIn("--require-release-open", self.text)
        self.assertLess(self.text.index(verifier), self.text.index(package))
        for test in (
            "python3 tools/test-import-pass20-human-review-xlsx.py -v",
            "python3 tools/test-stage-pass20-human-review-product.py -v",
            "python3 tools/test-promote-pass20-product-stage.py -v",
            "python3 tools/test-rollback-pass20-product-stage.py -v",
            "python3 tools/test-verify-pass20-human-materialization.py -v",
        ):
            self.assertIn(test, self.text)
            self.assertLess(self.text.index(test), self.text.index(verifier))

    def test_pass20_review_asset_uses_only_the_full_1564_workbook(self):
        current = (
            "test -f magica/i18n_audit/release_v26_authority/"
            "magireco_v26_translation_review_1564.xlsx"
        )
        retired = (
            "test ! -e magica/i18n_audit/release_v26_authority/"
            "pass20_human_review.xlsx"
        )
        self.assertIn(current, self.text)
        self.assertIn(retired, self.text)
        self.assertLess(self.text.index(current), self.text.index("python3 tools/i18n-authority-guard.py"))

    def test_engine_table_belongs_only_to_js_package(self):
        self.assertIn('engine = "madomagi/engine_i18n.tsv"', self.text)
        self.assertIn('assert names.count(engine) == 1', self.text)
        self.assertIn('assert "madomagi/engine_i18n.tsv" not in names', self.text)
        scenario_pack = re.search(
            r'name: "\[SCENARIO\] 打包.*?name: "\[SCENARIO\] 生成文件清单',
            self.text,
            flags=re.S,
        )
        self.assertIsNotNone(scenario_pack)
        self.assertNotIn("cp madomagi/engine_i18n.tsv", scenario_pack.group(0))

    def test_upstream_publish_targets_exact_latest_tag(self):
        self.assertIn("/releases/tags/latest", self.text)
        self.assertNotIn(
            'f"repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/releases/latest"',
            self.text,
        )
        self.assertIn('if rel.get("tag_name") != "latest"', self.text)

    def test_uploaded_assets_are_verified_and_fail_closed(self):
        self.assertIn("def verify_uploaded_asset(name, local_path):", self.text)
        self.assertIn('expected_digest = "sha256:" + digest.hexdigest()', self.text)
        self.assertIn('if asset.get("digest") != expected_digest:', self.text)
        self.assertIn("if not verify_uploaded_asset(fname, fpath):", self.text)
        self.assertIn("return verify_uploaded_asset(name, str(local_path))", self.text)

    def test_promotion_is_queued_rollback_capable_and_version_last(self):
        self.assertIn("cancel-in-progress: false", self.text)
        self.assertIn(
            "group: ${{ github.workflow }}-${{ github.ref }}-${{ github.event_name }}",
            self.text,
        )
        self.assertIn("def rename_asset(asset_id, old_name, new_name):", self.text)
        self.assertIn("promote_available_assets(", self.text)
        self.assertIn('backup_name = f"{final_name}.rollback-{run_id}"', self.promotion_text)
        self.assertIn(
            'VERSION_LAST = {"version_js.json", "version_scenario.json", "manifest.json",\n'
            '                              APK_SIDECAR}',
            self.text,
        )
        self.assertIn("to_process.sort(key=lambda name:", self.text)
        js_zip = self.promotion_text.index('(\"js\", \"cn_js_update_new.zip\"')
        js_manifest = self.promotion_text.index('(\"js\", \"cn_js_update_manifest_new.json\"')
        shared_manifest = self.promotion_text.index(
            '(\"shared\", \"manifest_new.json\", \"manifest.json\")'
        )
        js_version = self.promotion_text.index('(\"js\", \"version_js_new.json\"')
        self.assertLess(js_zip, js_manifest)
        self.assertLess(js_manifest, js_version)
        self.assertLess(js_manifest, shared_manifest)
        self.assertLess(shared_manifest, js_version)

    def test_candidate_triplet_is_cross_checked_before_promotion(self):
        self.assertIn("def validate_candidate_triplets(", self.promotion_text)
        self.assertIn("validate_candidate_triplets(root)", self.promotion_text)
        self.assertIn('int(manifest["version"]) == int(version["version"])', self.promotion_text)

    def test_preview_manifest_cannot_replace_formal_manifest(self):
        self.assertIn(
            "--manifest-name cn_js_update_manifest_new.json",
            self.text,
        )
        self.assertIn('"cn_js_update_manifest_new.json", "cn_js_update_manifest.json"', self.promotion_text)
        self.assertIn(
            "--manifest-name cn_scenario_update_manifest_new.json",
            self.text,
        )
        self.assertIn('"cn_scenario_update_manifest_new.json",', self.promotion_text)
        self.assertIn('"cn_scenario_update_manifest.json",', self.promotion_text)
        self.assertIn("_artifacts/cn_js_update_manifest_new.json", self.text)
        self.assertIn("_artifacts/cn_scenario_update_manifest_new.json", self.text)
        self.assertIn(
            '("shared", "manifest_new.json", "manifest.json")',
            self.promotion_text,
        )
        self.assertNotIn('if fname.endswith("_manifest.json")', self.text)
        self.assertNotIn("上传分块校验清单 manifest.json", self.text)
        self.assertEqual(
            self.text.count("python3 scripts/build_chunk_manifest.py --update"),
            2,
        )
        self.assertIn(
            'if final_name in (\n                  "version_js.json",\n'
            '                  "version_scenario.json",\n'
            '                  "manifest.json",',
            self.text,
        )

    def test_preview_asset_set_is_preflighted_before_remote_mutation(self):
        preflight = self.text.index("validate_candidate_triplets(ARTIFACTS_DIR)")
        fetch = self.text.index("release, existing_assets = fetch_assets()", preflight)
        upload = self.text.index('["gh", "release", "upload"', fetch)
        self.assertLess(preflight, fetch)
        self.assertLess(fetch, upload)
        for name in (
            "cn_js_update_new.zip",
            "cn_js_update_manifest_new.json",
            "version_js_new.json",
            "cn_scenario_update_new.zip",
            "cn_scenario_update_manifest_new.json",
            "version_scenario_new.json",
            "manifest_new.json",
        ):
            self.assertIn(f'"{name}"', self.text)

    def test_preview_build_cannot_advance_published_path_ledgers(self):
        self.assertEqual(self.text.count("LEDGER_MODE=check"), 2)
        self.assertEqual(self.text.count("LEDGER_MODE=update"), 2)
        self.assertEqual(self.text.count('--ledger-mode "$LEDGER_MODE"'), 2)
        self.assertIn(
            'if [ "${{ needs.setup.outputs.publish_hotfix }}" = "true" ]; then',
            self.text,
        )

    def test_cursor_waits_for_all_external_distribution_jobs(self):
        jobs = self.workflow_jobs()
        cursor = jobs["update-cursor"]
        summary = jobs["summary"]

        self.assertIn(
            "needs: [setup, commit-configs, r2-sync, doge-sync, pan123-upload, mirror-release]",
            cursor,
        )
        for job in ("r2-sync", "mirror-release"):
            self.assertIn(f"needs.{job}.result == 'success'", cursor)
        for job in ("doge-sync", "pan123-upload"):
            self.assertIn(f"needs.{job}.result != 'failure'", cursor)

        self.assertIn("fromJSON(vars.ENABLE_DOGE_SYNC || 'true')", jobs["doge-sync"])
        self.assertIn("fromJSON(vars.ENABLE_PAN123_SYNC || 'true')", jobs["pan123-upload"])

        self.assertIn(
            "needs: [setup, pack-js, pack-scenario, publish, r2-sync, bump-gate, "
            "doge-sync, pan123-upload, mirror-release, commit-configs, update-cursor]",
            summary,
        )
        self.assertIn("needs.pan123-upload.result", summary)
        self.assertIn("123云盘同步", summary)
        self.assertIn("🚫 已停用", summary)

    def test_publish_self_heals_interrupted_release_promotion(self):
        publish = self.workflow_jobs()["publish"]
        heal = publish.index("恢复上次未完成的转正")
        guard = publish.index("兜底护栏（打包失败即停链）")
        self.assertLess(heal, guard)
        self.assertIn(r'\.rollback-\d+$', publish)
        self.assertIn('rename(promoted["id"], final_name, preview_name)', publish)
        self.assertIn('rename(backup_asset["id"], backup_name, final_name)', publish)
        block = re.search(
            r"恢复上次未完成的转正.*?python3 <<'SCRIPT_END'\n(.*?)\n\s+SCRIPT_END",
            publish,
            flags=re.S,
        )
        self.assertIsNotNone(block)
        compile(textwrap.dedent(block.group(1)), "release_promotion_recovery.py", "exec")

    def test_two_stage_build_reuses_candidate_version(self):
        self.assertEqual(
            self.text.count(
                "from scripts.hotupdate_version import decide_candidate_version"
            ),
            2,
        )
        self.assertEqual(self.text.count("decision = decide_candidate_version("), 2)
        self.assertEqual(self.text.count("candidate_version = decision.version"), 2)
        self.assertIn("version_js_decision.json", self.text)
        self.assertIn("version_scenario_decision.json", self.text)
        self.assertNotIn('"version": base + 1', self.text)
        self.assertIn("if: success()", self.text)
        self.assertIn("只有产品字节真正变化时才递增", self.text)

    def test_pack_jobs_use_verified_upstream_latest_release_baselines(self):
        jobs = self.workflow_jobs()
        cases = (
            (
                "pack-js",
                "js",
                "version_js",
                "cn_js_update",
            ),
            (
                "pack-scenario",
                "scenario",
                "version_scenario",
                "cn_scenario_update",
            ),
        )
        for job_name, scope, version_name, zip_name in cases:
            with self.subTest(job=job_name):
                block = jobs[job_name]
                self.assertIn('UPSTREAM_OWNER: "HiiragiNemu"', block)
                self.assertIn('UPSTREAM_REPO: "magireco-cn-patch"', block)
                self.assertIn(
                    'gh api "repos/${UPSTREAM_OWNER}/${UPSTREAM_REPO}/releases/tags/latest"',
                    block,
                )
                self.assertIn("gh release download latest", block)
                self.assertIn(f"--pattern '{version_name}.json'", block)
                self.assertIn(f"--pattern '{version_name}_new.json'", block)
                self.assertIn(f"--pattern '{zip_name}.zip'", block)
                self.assertIn(f"--pattern '{zip_name}_new.zip'", block)
                self.assertIn("python3 scripts/hotupdate_release_baseline.py", block)
                self.assertIn(f"--scope {scope}", block)
                self.assertIn(
                    f'release_baseline_dir = os.path.join("_release_baseline", "{scope}")',
                    block,
                )
                self.assertIn("[release_candidate_path]", block)
                self.assertNotIn(
                    'official_path = os.path.join(CFG_DIR, f"{NAME}.json")',
                    block,
                )
                self.assertIn(f"{version_name}_release_baseline.json", block)

        self.assertIn("Release snapshot is not the exact latest tag", self.release_baseline_text)
        self.assertIn("Release version metadata and zip bytes disagree", self.release_baseline_text)
        self.assertIn('"repository_configures_trusted": False', self.release_baseline_text)
        self.assertIn("python3 scripts/test_hotupdate_release_baseline.py -v", self.text)

    def test_promotion_reconciles_lost_rename_and_delete_responses(self):
        self.assertIn("def _rename_and_confirm(", self.promotion_text)
        self.assertIn("def _delete_and_confirm(", self.promotion_text)
        self.assertGreaterEqual(self.promotion_text.count("_rename_and_confirm("), 5)
        self.assertGreaterEqual(self.promotion_text.count("_delete_and_confirm("), 3)

    def test_hotfix_publish_embedded_python_compiles(self):
        block = re.search(
            r"id: hotfix_publish.*?python3 <<'SCRIPT_END'\n(.*?)\n\s+SCRIPT_END",
            self.text,
            flags=re.S,
        )
        self.assertIsNotNone(block)
        compile(textwrap.dedent(block.group(1)), "hotfix_publish_inline.py", "exec")

    def test_workflow_commits_use_required_repository_identity(self):
        self.assertIn('git config user.name "Hiiragi Nemu"', self.text)
        self.assertIn(
            'git config user.email "128921071+HiiragiNemu@users.noreply.github.com"',
            self.text,
        )
        self.assertNotIn("magiacn-autobot@users.noreply.github.com", self.text)
        self.assertNotIn("MagiaCN AutoBot", self.text)
        self.assertNotIn("bot@magiacn.com", self.text)

    def test_downstream_latest_mirror_is_incremental_then_complete_verified(self):
        mirror = self.workflow_jobs()["mirror-release"]
        checkout = mirror.index("name: 📦 检出镜像事务工具")
        transaction_import = mirror.index("from scripts.release_asset_transaction import")
        self.assertLess(checkout, transaction_import)
        self.assertIn("scripts/release_asset_transaction.py", mirror)
        self.assertIn("sparse-checkout-cone-mode: false", mirror)
        self.assertIn("replace_release_asset_set(", self.text)
        self.assertIn("class TransactionalMirrorBackend:", self.text)
        self.assertNotIn("def upload_to_release(", self.text)
        self.assertNotIn("for n in all_names:", self.text)
        self.assertIn("if actual_names != expected_names:", self.text)
        self.assertIn("latest 全集合核验通过", self.text)
        self.assertIn("if up_digest and up_digest != down_digest:", self.text)
        self.assertIn("if u_digest:\n                  return u_digest != d_digest", self.text)

    def test_downstream_latest_never_deletes_stable_before_replacement_upload(self):
        self.assertIn("python3 scripts/test_release_asset_transaction.py -v", self.text)
        self.assertIn("All changed bytes are uploaded and verified", self.mirror_transaction_text)
        stage = self.mirror_transaction_text.index(
            "# Stage and verify all replacement bytes before touching stable names."
        )
        backup = self.mirror_transaction_text.index(
            'f"stable asset cannot be backed up: {stable_name}"'
        )
        cleanup = self.mirror_transaction_text.index("# Commit point:")
        self.assertLess(stage, backup)
        self.assertLess(backup, cleanup)
        self.assertIn("rollback also failed", self.mirror_transaction_text)
        self.assertIn('"--method", "PATCH", "-f", f"name={new_name}"', self.text)

    def test_downstream_mirror_embedded_python_compiles(self):
        block = re.search(
            r"id: mirror_release.*?python3 <<'SCRIPT_END'\n(.*?)\n\s+SCRIPT_END",
            self.text,
            flags=re.S,
        )
        self.assertIsNotNone(block)
        compile(textwrap.dedent(block.group(1)), "mirror_release_inline.py", "exec")

    def test_r2_and_first_mirror_fail_without_advancing_state(self):
        self.assertIn("上传/核验失败，不保存指纹", self.text)
        self.assertIn("for fname in processed: final_map[fname] = current_map[fname]", self.text)
        self.assertIn("head_object(", self.text)
        self.assertIn("首次镜像未完成", self.text)
        self.assertIn("变更快照有", self.text)

    def test_apk_distribution_is_not_chained_to_hot_update_packaging(self):
        """r2-sync 必须带 always()：APK 的分发不能被热更打包链连坐。

        2026-08-20 的事故就是这条不成立：
          · run #236 —— pack-js 红 → publish 的停链护栏红 → r2-sync 被跳过；
          · run #239 —— 无内容变更 → pack-* 被 skip，skip 沿 needs 图向下
            传递，publish 靠 always() 仍然绿，r2-sync 照样被跳过（整个 run
            显示成功）。
        而「构建完 APK 再 dispatch 过来」时上游 git 内容一个字节没变，走的
        正是后一条。于是 APK 停在 Release 里上不了 CDN，闸门却由构建 CI 照抬
        —— 玩家装完还低于闸门，无限更新。这条守卫钉住那次修复。
        """
        r2 = self.workflow_jobs()["r2-sync"]
        self.assertIn("if: always() && needs.setup.result == 'success'", r2)
        self.assertIn("apk_version: ${{ steps.sync_script.outputs.apk_version }}", r2)

    def test_client_apk_is_owned_by_this_repository_everywhere(self):
        """APK 与版本旁注的归属判据四处同源，漏改一处就会拿旧包盖新包。

        构建 CI 直接把 APK 传进本仓库的 latest Release，上游那份是搬家前的
        历史遗留。r2-sync / mirror-release / Doge / 123 云盘四条路各有一份
        判据，任何一处退回「只认上游」，CDN 上就会被旧包盖回去。
        """
        pattern = re.compile(
            r"LOCAL_OWNED_PREFIXES = \(['\"]magireco-latest['\"],\)")
        self.assertEqual(len(pattern.findall(self.text)), 2)  # r2-sync + mirror
        self.assertEqual(len(pattern.findall(self.doge_text)), 1)
        self.assertEqual(len(pattern.findall(self.pan123_text)), 1)

        jobs = self.workflow_jobs()
        # r2-sync：上游全集去掉自有名，再并上本仓库自有名
        self.assertIn("not is_local_owned(a['name'])", jobs["r2-sync"])
        self.assertIn("assets_by_name.update(local_assets)", jobs["r2-sync"])
        # mirror-release：既不从上游镜像下来，也不因为上游没有而被删掉
        self.assertIn('if is_local_owned(a["name"]):', jobs["mirror-release"])
        self.assertIn(
            'actual_names = {n for n in final_assets if not is_local_owned(n)}',
            jobs["mirror-release"],
        )

    def test_gate_version_is_reported_only_for_a_landed_apk(self):
        """闸门的输入必须是「玩家真能装到的那一版」，否则宁可不报。"""
        r2 = self.workflow_jobs()["r2-sync"]
        # 旁注排在 APK 之后上传：中断时不会留下「版本已宣称、包还没上去」
        self.assertIn('APK_SIDECAR}', r2)
        # 三个前提缺一不报
        self.assertIn("未处于已同步状态，本次不报告客户端版本", r2)
        self.assertIn("与旁注 sha256 不符", r2)
        # 无新增/更新时也报，让上一次失败的闸门提升能自愈
        self.assertIn("emit_apk_version(assets_by_name, set(unchanged))", r2)
        self.assertIn(
            "emit_apk_version(assets_by_name, set(unchanged) | set(processed))", r2)

    def test_gate_is_bumped_only_after_the_apk_is_on_the_cdn(self):
        """闸门只能由同步链在 APK 真的落到 CDN 之后抬。

        搬家之前它长在构建 APK 的 CI 里，打完包当场抬到本次构建号——只证明
        「构建成功」，与玩家能不能下到毫无因果关系。2026-08-20 就是这么把
        闸门抬到了一个 CDN 上根本没有的版本。
        """
        gate = self.workflow_jobs()["bump-gate"]
        self.assertIn("needs: [r2-sync]", gate)
        self.assertIn("if: needs.r2-sync.outputs.apk_version != \'\'", gate)
        # 落地前核对 CDN 边缘真正吐出来的大小
        self.assertIn('tolower($1)=="content-length:"', gate)
        self.assertIn("拒绝提升闸门", gate)
        # 够不着 CDN（不抬、不红）与 CDN 上是旧包（红），处理方式相反
        self.assertIn("本次不提升闸门", gate)
        # 非递增一律不写，且绝不自动回落
        self.assertIn("本步骤不会自动回落闸门", gate)
        self.assertIn("闸门已经是", gate)
        # 写配置仓库要过白名单
        self.assertIn(
            'ALLOW_CONFIG = {"MagirecoCN-Revival-Project/magirecocn-online-configs"}',
            gate,
        )

    def test_manual_default_is_js_only(self):
        block = re.search(
            r"package_scope:.*?options:\s*\n\s*- js\s*\n\s*- scenario\s*\n\s*- all",
            self.text,
            flags=re.S,
        )
        self.assertIsNotNone(block)
        self.assertIn("default: 'js'", block.group(0))
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && inputs.package_scope "
            "|| '按变更自动判断'",
            self.text,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
