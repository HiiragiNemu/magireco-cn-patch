#!/usr/bin/env python3
"""Synthetic M/A/D, bad-hash, roundtrip, and compensated-rollback tests."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
import warnings
import zipfile


SCRIPT = Path(__file__).with_name("v26_final_delivery.py")
SPEC = importlib.util.spec_from_file_location("v26_final_delivery", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def run(command: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {command}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def write_product_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=MODULE.EXPECTED_DOS_TIME)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.comment = b""
            info.extra = b""
            archive.writestr(
                info,
                members[name],
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


class FinalDeliveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="v26-final-delivery-test-")
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        run(["git", "init", "-b", "main"], self.repo)
        run(["git", "config", "user.name", "Hiiragi Nemu"], self.repo)
        run(
            [
                "git",
                "config",
                "user.email",
                "128921071+HiiragiNemu@users.noreply.github.com",
            ],
            self.repo,
        )
        self.artifact_members = {
            MODULE.ENGINE_MEMBER: "戻る\t返回\n".encode("utf-8"),
            "magica/css/a.css": b"body{}\n",
            "magica/js/a.js": b"define(function(){return true;});\n",
            "magica/template/a.html": b"<p>ok</p>\n",
        }
        (self.repo / "mod.txt").write_bytes(b"before\n")
        (self.repo / "binary.dat").write_bytes(bytes(range(256)) * 8)
        (self.repo / "delete.txt").write_bytes(b"delete me\n")
        (self.repo / "keep.txt").write_bytes(b"unchanged\n")
        for rel, data in self.artifact_members.items():
            product_path = self.repo / rel
            product_path.parent.mkdir(parents=True, exist_ok=True)
            product_path.write_bytes(data)
        run(["git", "add", "."], self.repo)
        run(["git", "commit", "-m", "baseline"], self.repo)
        self.baseline = run(["git", "rev-parse", "HEAD"], self.repo).stdout.strip()
        (self.repo / "mod.txt").write_bytes(b"after\n")
        binary = bytearray((self.repo / "binary.dat").read_bytes())
        for index in range(256, 1024):
            binary[index] ^= 0xFF
        (self.repo / "binary.dat").write_bytes(bytes(binary))
        (self.repo / "delete.txt").unlink()
        (self.repo / "added name.txt").write_bytes("新增\n".encode("utf-8"))
        self.allowlist = self.root / "allowlist.txt"
        self.allowlist.write_text(
            "added name.txt\nbinary.dat\ndelete.txt\nmod.txt\n",
            encoding="utf-8",
            newline="\n",
        )
        self.artifact = self.root / MODULE.ARTIFACT_NAME
        write_product_zip(self.artifact, self.artifact_members)
        self.artifact_contract = {
            "file_entries": 4,
            "magica_entries": 3,
            "engine_entries": 1,
            "scenario_entries": 0,
            "audit_research_entries": 0,
        }
        self.bundle = self.root / "bundle"
        self.report = MODULE.generate_bundle(
            repo=self.repo,
            baseline=self.baseline,
            allowlist_path=self.allowlist,
            artifact_path=self.artifact,
            output_dir=self.bundle,
            artifact_contract=self.artifact_contract,
            from_worktree=True,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _manifest(self) -> dict:
        return json.loads((self.bundle / MODULE.MANIFEST_NAME).read_text(encoding="utf-8"))

    def _checkout_final_commit(self) -> str:
        manifest = self._manifest()
        final_tree = manifest["final"]["tree"]
        final_commit = run(
            ["git", "commit-tree", final_tree, "-p", self.baseline, "-m", "synthetic final"],
            self.repo,
        ).stdout.strip()
        run(["git", "reset", "--hard", final_commit], self.repo)
        return final_tree

    def _powershell(self) -> str:
        executable = shutil.which("pwsh") or shutil.which("powershell")
        if not executable:
            self.skipTest("PowerShell is unavailable")
        return executable

    def test_manifest_covers_modified_added_deleted_and_binary_patch(self) -> None:
        manifest = self._manifest()
        self.assertEqual(
            {
                MODULE.ARTIFACT_NAME,
                MODULE.PATCH_NAME,
                MODULE.MANIFEST_NAME,
                MODULE.ROLLBACK_NAME,
                MODULE.VERIFICATION_NAME,
            },
            {item.name for item in self.bundle.iterdir()},
        )
        self.assertEqual({"A": 1, "M": 2, "D": 1}, manifest["change_counts"])
        self.assertEqual(self.artifact_contract, manifest["modified_artifact"]["expected"])
        zip_actual = manifest["modified_artifact"]["actual"]
        self.assertEqual(4, zip_actual["file_entries"])
        self.assertEqual(3, zip_actual["magica_entries"])
        self.assertEqual(1, zip_actual["engine_entries"])
        self.assertEqual(0, zip_actual["scenario_entries"])
        self.assertEqual(0, zip_actual["audit_research_entries"])
        self.assertEqual(0, zip_actual["duplicate_paths"])
        self.assertEqual(0, zip_actual["crc_errors"])
        tree_binding = manifest["modified_artifact"]["final_tree_binding"]
        self.assertEqual("PASS", tree_binding["status"])
        self.assertEqual(manifest["final"]["tree"], tree_binding["final_tree"])
        self.assertEqual(4, tree_binding["matched_entry_count"])
        self.assertEqual(0, tree_binding["byte_mismatch_count"])
        self.assertEqual(
            self.artifact.read_bytes(),
            (self.bundle / MODULE.ARTIFACT_NAME).read_bytes(),
        )
        self.assertEqual(
            ["added name.txt", "binary.dat", "delete.txt", "mod.txt"],
            [row["path"] for row in manifest["paths"]],
        )
        patch = (self.bundle / MODULE.PATCH_NAME).read_bytes()
        self.assertIn(b"GIT binary patch", patch)
        verified = MODULE.verify_bundle(repo=self.repo, bundle_dir=self.bundle)
        self.assertEqual("PASS", verified["status"])
        self.assertEqual(
            manifest["final"]["tree"],
            verified["cached_patch_roundtrip"]["forward"]["actual_tree"],
        )
        self.assertEqual(
            manifest["baseline"]["tree"],
            verified["cached_patch_roundtrip"]["reverse"]["actual_tree"],
        )

    def test_shared_clone_can_verify_cached_roundtrip(self) -> None:
        shared = self.root / "shared-clone"
        run(["git", "clone", "--shared", str(self.repo), str(shared)], self.root)
        verified = MODULE.verify_bundle(repo=shared, bundle_dir=self.bundle)
        manifest = self._manifest()
        self.assertEqual(manifest["final"]["tree"], verified["final_tree"])
        self.assertTrue(
            verified["cached_patch_roundtrip"]["forward"]["tree_equal"]
        )
        self.assertTrue(
            verified["cached_patch_roundtrip"]["reverse"]["tree_equal"]
        )

    def test_tampered_but_structurally_valid_product_zip_is_rejected(self) -> None:
        changed = dict(self.artifact_members)
        changed["magica/js/a.js"] = b"define(function(){return false;});\n"
        write_product_zip(self.bundle / MODULE.ARTIFACT_NAME, changed)
        with self.assertRaisesRegex(
            MODULE.DeliveryError, "product ZIP does not match final tree"
        ):
            MODULE.verify_bundle(repo=self.repo, bundle_dir=self.bundle)

    def test_structurally_valid_stale_product_zip_is_rejected_before_output(self) -> None:
        stale_members = dict(self.artifact_members)
        stale_members["magica/js/a.js"] = b"define(function(){return false;});\n"
        stale = self.root / "stale-cn-js-update.zip"
        write_product_zip(stale, stale_members)
        target = self.root / "stale-bundle"
        with self.assertRaisesRegex(
            MODULE.DeliveryError, "product ZIP does not match final tree"
        ):
            MODULE.generate_bundle(
                repo=self.repo,
                baseline=self.baseline,
                allowlist_path=self.allowlist,
                artifact_path=stale,
                output_dir=target,
                artifact_contract=self.artifact_contract,
                from_worktree=True,
            )
        self.assertFalse(target.exists())

    def test_wrong_product_zip_contract_fails_before_output(self) -> None:
        wrong_contract = dict(self.artifact_contract)
        wrong_contract["file_entries"] = 3
        wrong_contract["magica_entries"] = 2
        target = self.root / "wrong-contract"
        with self.assertRaisesRegex(MODULE.DeliveryError, "product ZIP contract mismatch"):
            MODULE.generate_bundle(
                repo=self.repo,
                baseline=self.baseline,
                allowlist_path=self.allowlist,
                artifact_path=self.artifact,
                output_dir=target,
                artifact_contract=wrong_contract,
                from_worktree=True,
            )
        self.assertFalse(target.exists())

    def test_duplicate_product_zip_member_is_rejected(self) -> None:
        duplicate = self.root / "duplicate.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(
                duplicate,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                for name, data in (
                    (MODULE.ENGINE_MEMBER, b"engine\n"),
                    ("magica/js/a.js", b"one\n"),
                    ("magica/js/a.js", b"two\n"),
                    ("magica/template/a.html", b"<p/>\n"),
                ):
                    info = zipfile.ZipInfo(name, date_time=MODULE.EXPECTED_DOS_TIME)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
        with self.assertRaisesRegex(MODULE.DeliveryError, "duplicate_paths"):
            MODULE.inspect_product_artifact(
                duplicate,
                {
                    "file_entries": 4,
                    "magica_entries": 3,
                    "engine_entries": 1,
                    "scenario_entries": 0,
                    "audit_research_entries": 0,
                },
            )

    def test_output_inside_repo_and_unlisted_change_fail_closed(self) -> None:
        inside = self.repo / "forbidden-output"
        with self.assertRaisesRegex(MODULE.DeliveryError, "outside"):
            MODULE.generate_bundle(
                repo=self.repo,
                baseline=self.baseline,
                allowlist_path=self.allowlist,
                artifact_path=self.artifact,
                output_dir=inside,
                artifact_contract=self.artifact_contract,
                from_worktree=True,
            )
        short_allowlist = self.root / "short.txt"
        short_allowlist.write_text("mod.txt\n", encoding="utf-8", newline="\n")
        # Worktree mode intentionally stages only listed paths, so its virtual tree
        # is safe and contains only mod.txt.  Supplying a real final tree proves the
        # exact-diff gate rejects every unlisted path.
        final_tree = self._manifest()["final"]["tree"]
        with self.assertRaisesRegex(MODULE.DeliveryError, "does not exactly equal"):
            MODULE.generate_bundle(
                repo=self.repo,
                baseline=self.baseline,
                allowlist_path=short_allowlist,
                artifact_path=self.artifact,
                output_dir=self.root / "should-not-exist",
                artifact_contract=self.artifact_contract,
                final_treeish=final_tree,
            )
        self.assertFalse((self.root / "should-not-exist").exists())

    def test_wrong_submission_identity_fails_before_output(self) -> None:
        run(["git", "config", "user.name", "CyberNova"], self.repo)
        target = self.root / "wrong-identity"
        with self.assertRaisesRegex(MODULE.DeliveryError, "repo-local user.name"):
            MODULE.generate_bundle(
                repo=self.repo,
                baseline=self.baseline,
                allowlist_path=self.allowlist,
                artifact_path=self.artifact,
                output_dir=target,
                artifact_contract=self.artifact_contract,
                from_worktree=True,
            )
        self.assertFalse(target.exists())

    def test_bad_manifest_sha_stops_before_mutation(self) -> None:
        final_tree = self._checkout_final_commit()
        manifest_path = self.bundle / MODULE.MANIFEST_NAME
        original = manifest_path.read_bytes()
        manifest_path.write_bytes(original + b" ")
        script = self.bundle / MODULE.ROLLBACK_NAME
        result = run(
            [
                self._powershell(),
                "-NoProfile",
                "-File",
                str(script),
                "-RepoRoot",
                str(self.repo),
            ],
            self.repo,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest SHA-256 mismatch", result.stderr + result.stdout)
        self.assertEqual(final_tree, run(["git", "write-tree"], self.repo).stdout.strip())

    def test_wrong_worktree_blob_sha_stops_before_mutation(self) -> None:
        final_tree = self._checkout_final_commit()
        (self.repo / "mod.txt").write_bytes(b"tampered after image\n")
        script = self.bundle / MODULE.ROLLBACK_NAME
        result = run(
            [
                self._powershell(),
                "-NoProfile",
                "-File",
                str(script),
                "-RepoRoot",
                str(self.repo),
            ],
            self.repo,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("worktree Git blob SHA mismatch", result.stderr + result.stdout)
        self.assertEqual(final_tree, run(["git", "write-tree"], self.repo).stdout.strip())
        self.assertEqual(b"tampered after image\n", (self.repo / "mod.txt").read_bytes())

    def test_rollback_restores_exact_baseline_tree(self) -> None:
        self._checkout_final_commit()
        script = self.bundle / MODULE.ROLLBACK_NAME
        result = run(
            [
                self._powershell(),
                "-NoProfile",
                "-File",
                str(script),
                "-RepoRoot",
                str(self.repo),
            ],
            self.repo,
        )
        report = json.loads(result.stdout)
        baseline_tree = run(
            ["git", "rev-parse", f"{self.baseline}^{{tree}}"], self.repo
        ).stdout.strip()
        self.assertEqual(baseline_tree, run(["git", "write-tree"], self.repo).stdout.strip())
        self.assertEqual("PASS", report["status"])
        # Compare the indexed Git blob: checkout EOL policy may legitimately
        # render the Windows worktree as CRLF while the restored tree stays exact.
        self.assertEqual("before\n", run(["git", "show", ":mod.txt"], self.repo).stdout)
        self.assertTrue((self.repo / "delete.txt").exists())
        self.assertFalse((self.repo / "added name.txt").exists())

    def test_post_apply_failure_compensates_to_exact_final_tree(self) -> None:
        final_tree = self._checkout_final_commit()
        final_bytes = (self.repo / "mod.txt").read_bytes()
        script = self.bundle / MODULE.ROLLBACK_NAME
        result = run(
            [
                self._powershell(),
                "-NoProfile",
                "-File",
                str(script),
                "-RepoRoot",
                str(self.repo),
                "-SimulatePostApplyFailure",
            ],
            self.repo,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("original final tree was restored transactionally", result.stderr + result.stdout)
        self.assertEqual(final_tree, run(["git", "write-tree"], self.repo).stdout.strip())
        self.assertEqual(final_bytes, (self.repo / "mod.txt").read_bytes())
        self.assertFalse((self.repo / "delete.txt").exists())
        self.assertTrue((self.repo / "added name.txt").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
