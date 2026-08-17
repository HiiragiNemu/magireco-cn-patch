#!/usr/bin/env python3
"""Regression tests for build-v26-final-allowlist.py."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/build-v26-final-allowlist.py"
EXPECTED_NAME = "Hiiragi Nemu"
EXPECTED_EMAIL = "128921071+HiiragiNemu@users.noreply.github.com"
SPEC = importlib.util.spec_from_file_location("build_v26_final_allowlist", TOOL)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def command(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, text=True, encoding="utf-8",
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def init_repo(base: Path) -> tuple[Path, Path]:
    repo = base / "repo"
    repo.mkdir()
    for args in (("git", "init"), ("git", "config", "user.name", EXPECTED_NAME), ("git", "config", "user.email", EXPECTED_EMAIL)):
        result = command(repo, *args)
        if result.returncode:
            raise AssertionError(result.stderr)
    write(repo / ".gitattributes", "* text=auto eol=lf\n*.zip -text\n")
    write(repo / "madomagi/engine_i18n.tsv", "source\ttarget\nold\t旧\n")
    write(repo / "magica/js/_common/base.js", "const value = 1;\n")
    stub = repo / "authority_stub.py"
    write(
        stub,
        """#!/usr/bin/env python3
import json
print(json.dumps({
  "schema": "test-authority/1", "status": "PASS",
  "machine_review_fresh": True, "protected_fields": 3,
  "protected_text_changes": 0
}))
""",
    )
    for args in (("git", "add", "."), ("git", "commit", "-m", "baseline")):
        result = command(repo, *args)
        if result.returncode:
            raise AssertionError(result.stderr)

    # Real runtime content, EOL-only noise, a known root temp, and one explicit path.
    write(repo / "madomagi/engine_i18n.tsv", "source\ttarget\nnew\t新\n")
    write(repo / "magica/js/_common/base.js", b"const value = 1;\r\n")
    write(repo / "candidate.zip", b"PK\x03\x04synthetic")
    write(repo / "notes/review.json", "{\"reviewed\":true}\n")

    machine = repo / "magica/i18n_audit/release_v26_authority/machine_translation_review"
    summary = b'{"counts":{"master":1}}\n'
    master = b"id\ttext\n1\tlow-tier\n"
    write(machine / "summary.json", summary)
    write(machine / "full_machine_translation_review.tsv", master)
    sum_lines = [
        f"{sha(master)}  full_machine_translation_review.tsv\n",
        f"{sha(summary)}  summary.json\n",
    ]
    write(machine / "SHA256SUMS.txt", "".join(sum_lines))
    protected = repo / "magica/i18n_audit/release_v26_authority/protected_authority"
    manifest = {
        "baseline": {
            "machine_review_master": "magica/i18n_audit/release_v26_authority/machine_translation_review/full_machine_translation_review.tsv",
            "machine_review_master_sha256": sha(master),
            "machine_review_summary": "magica/i18n_audit/release_v26_authority/machine_translation_review/summary.json",
            "machine_review_summary_sha256": sha(summary),
        }
    }
    write(protected / "protection_manifest.json", json.dumps(manifest, sort_keys=True) + "\n")
    write(protected / "protected_translation_fields.tsv", "id\tvalue\n1\t权威\n")
    return repo, stub


def file_record(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha(data)}


def write_json(path: Path, value: object) -> None:
    write(path, json.dumps(value, sort_keys=True) + "\n")


def canonical_json_sha(value: object) -> str:
    return sha((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))


def make_stage(base: Path, *, mode: str) -> Path:
    if mode not in {"full", "manual_handoff", "nonterminal"}:
        raise AssertionError(mode)
    stage = base / "stage"
    accepted = stage / "accepted"
    generated = stage / "generated"
    accepted.mkdir(parents=True)
    generated.mkdir(parents=True)
    (stage / "pending").mkdir()
    completed_batches = 96 if mode == "full" else 74 if mode == "manual_handoff" else 1
    completed_items = 1912 if mode == "full" else 1472 if mode == "manual_handoff" else 20
    accepted_map: dict[str, dict[str, object]] = {}
    for number in range(1, completed_batches + 1):
        path = accepted / f"batch_{number:03d}.json"
        write_json(path, {"batch_number": number, "verdict": "approved"})
        accepted_map[path.name] = file_record(path)

    state = "complete" if mode == "full" else "closed-manual-handoff" if mode == "manual_handoff" else "ready"
    next_batch = None if mode != "nonterminal" else 2
    summary = {
        "accepted_batches": completed_batches,
        "completed_items": completed_items,
        "total_batches": 96,
        "total_items": 1912,
        "next_batch": next_batch,
        "protected_text_changes": 0,
    }
    if mode == "manual_handoff":
        summary.update({
            "ds_phase": "closed_manual_handoff",
            "ds_retry_disabled": True,
            "manual_required_items": 440,
            "manual_review_rows": 82,
        })
    write_json(generated / "summary.json", summary)
    write(generated / "review_results.jsonl", '{"item_id":"LOW-MT-00001"}\n')
    if mode == "manual_handoff":
        review_stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            review_stream, fieldnames=("item_id", "parent_verdict"),
            delimiter="\t", lineterminator="\n",
        )
        writer.writeheader()
        for number in range(1, 83):
            writer.writerow({
                "item_id": f"REVIEWED-{number:03d}",
                "parent_verdict": "correction" if number <= 37 else "unresolved",
            })
        write(generated / "manual_review.tsv", review_stream.getvalue())

        manual_rows: list[dict[str, object]] = []
        for offset in range(440):
            manual_rows.append({
                "source_index": 1473 + offset,
                "batch_number": 75 + offset // 20,
                "item_id": f"MANUAL-{offset + 1:03d}",
                "ds_review_status": "not-reviewed-ds",
                "review_status": "manual-required",
                "product_write_allowed": False,
                "human_decision": "",
            })
        write(
            generated / "manual_required.jsonl",
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in manual_rows),
        )
        manual_stream = io.StringIO(newline="")
        manual_writer = csv.DictWriter(
            manual_stream, fieldnames=tuple(manual_rows[0]),
            delimiter="\t", lineterminator="\n",
        )
        manual_writer.writeheader()
        manual_writer.writerows(manual_rows)
        write(generated / "manual_required.tsv", manual_stream.getvalue())
        handoff_manifest = {
            "terminal_mode": "manual_handoff",
            "ds_phase": "closed_manual_handoff",
            "ds_retry_disabled": True,
            "accepted_batches": 74,
            "ds_reviewed_items": 1472,
            "manual_required_batches": 22,
            "manual_required_items": 440,
            "manual_required_unreviewed": 440,
            "reviewed_human_decision_required": 82,
            "human_decision_required": 522,
            "protected_text_changes": 0,
            "product_tree_writes": False,
            "network_configuration_writes": False,
            "files": {
                "manual_required.jsonl": file_record(generated / "manual_required.jsonl"),
                "manual_required.tsv": file_record(generated / "manual_required.tsv"),
            },
            "queue_coverage": {
                "manual_item_ids_sha256": canonical_json_sha([
                    row["item_id"] for row in manual_rows
                ]),
                "manual_required_unreviewed": 440,
                "accepted_manual_overlap": 0,
                "inventory_missing": 0,
                "manual_source_index_range": {"start": 1473, "end": 1912},
                "manual_batch_range": {"start": 75, "end": 96, "count": 22},
            },
            "decision_contract": {
                "validation": {
                    "rows": 440, "blank": 440, "decided": 0,
                    "unresolved_apply_allowed": False,
                }
            },
        }
        write_json(generated / "manual_handoff_manifest.json", handoff_manifest)
        handoff_sha = sha((generated / "manual_handoff_manifest.json").read_bytes())
        handoff_state = {
            "terminal_mode": "manual_handoff",
            "ds_phase": "closed_manual_handoff",
            "ds_retry_disabled": True,
            "accepted_batches": 74,
            "ds_reviewed_items": 1472,
            "manual_required_items": 440,
            "reviewed_human_decision_required": 82,
            "human_decision_required": 522,
            "manual_handoff_manifest_sha256": handoff_sha,
            "ledger_entry_sha256": "ledger-final",
            "protected_text_changes": 0,
            "product_tree_writes": False,
            "network_configuration_writes": False,
        }
        write_json(generated / "manual_handoff_state.json", handoff_state)

    aggregates = {}
    aggregate_names = ["review_results.jsonl", "summary.json"]
    if mode == "manual_handoff":
        aggregate_names.append("manual_review.tsv")
    for name in aggregate_names:
        aggregates[name] = file_record(generated / name)
    manifest = {
        "completed_batches": completed_batches,
        "completed_items": completed_items,
        "source_order_verified": True,
        "product_tree_writes": False,
        "network_configuration_writes": False,
        "protected_text_changes": 0,
        "append_only_ledger": {
            "valid": True, "entries": 1, "last_entry_sha256": "ledger-final",
        },
        "accepted_batches": accepted_map,
        "aggregates": aggregates,
    }
    if mode == "manual_handoff":
        manifest["manual_handoff"] = {
            "ds_phase": "closed_manual_handoff",
            "ds_retry_disabled": True,
            "manual_required_items": 440,
            "manual_handoff_manifest_sha256": sha(
                (generated / "manual_handoff_manifest.json").read_bytes()
            ),
        }
    manifest_bytes = (json.dumps(manifest, sort_keys=True) + "\n").encode("utf-8")
    write(generated / "review_manifest.json", manifest_bytes)
    checkpoint = {
        "state": state,
        "last_completed_batch": completed_batches,
        "completed_items": completed_items,
        "total_batches": 96,
        "total_items": 1912,
        "next_batch": next_batch,
        "review_manifest_sha256": sha(manifest_bytes),
    }
    heartbeat: dict[str, object] = {"status": state, "completed_items": completed_items, "next_batch": next_batch}
    if mode == "manual_handoff":
        handoff_sha = sha((generated / "manual_handoff_manifest.json").read_bytes())
        checkpoint.update({
            "ds_phase": "closed_manual_handoff", "ds_retry_disabled": True,
            "manual_required_items": 440, "human_decision_required": 522,
            "manual_required_batches": 22, "manual_required_unreviewed": 440,
            "reviewed_human_decision_required": 82,
            "manual_handoff_manifest_sha256": handoff_sha,
        })
        heartbeat.update({
            "ds_retry_disabled": True, "manual_required_items": 440,
            "human_decision_required": 522,
        })
    write_json(generated / "checkpoint.json", checkpoint)
    write_json(generated / "heartbeat.json", heartbeat)
    write(generated / "selected.json", '{"selected":true}\n')

    if mode != "nonterminal":
        terminal_mode = "full_ds_review" if mode == "full" else "manual_handoff"
        pipeline_files = {
            relative: file_record(stage / relative)
            for relative in (
                "generated/checkpoint.json",
                "generated/heartbeat.json",
                "generated/review_manifest.json",
                "generated/summary.json",
            )
        }
        if mode == "manual_handoff":
            for relative in (
                "generated/manual_handoff_state.json",
                "generated/manual_handoff_manifest.json",
                "generated/manual_required.jsonl",
                "generated/manual_required.tsv",
            ):
                pipeline_files[relative] = file_record(stage / relative)
        pipeline: dict[str, object] = {
            "result": "PASS", "terminal_seal": True, "terminal_mode": terminal_mode,
            "total_batches": 96, "total_items": 1912,
            "protected_text_changes": 0,
            "product_tree_writes": False,
            "network_configuration_writes": False,
            "pipeline_files": pipeline_files,
            "terminal_gate": {
                "accepted_batches": completed_batches,
                "accepted_items": completed_items,
                "next_batch": None,
            },
        }
        job: dict[str, object] = {
            "total_batches": 96, "total_items": 1912,
            "ds_phase": "complete" if mode == "full" else "closed_manual_handoff",
            "terminal_mode": terminal_mode,
            "terminal_seal": {
                "terminal": True, "result": "PASS",
                "completed_batches": completed_batches,
                "completed_items": completed_items,
                "protected_text_changes": 0,
                "product_tree_writes": False,
                "network_configuration_writes": False,
            },
            "review_progress": {
                "completed_items": completed_items,
                "completed_batches": completed_batches,
                "next_batch": None,
            },
            "pipeline_files": pipeline_files,
        }
        if mode == "manual_handoff":
            handoff = {
                "accepted_batches": 74, "ds_reviewed_items": 1472,
                "manual_required_items": 440, "manual_required_unreviewed": 440,
                "reviewed_human_decision_required": 82, "human_decision_required": 522,
                "protected_text_changes": 0, "product_tree_writes": False,
                "network_configuration_writes": False,
                "queue_coverage": handoff_manifest["queue_coverage"],
                "manifest": {"path": "generated/manual_handoff_manifest.json", **file_record(generated / "manual_handoff_manifest.json")},
                "manual_queue": {"path": "generated/manual_required.jsonl", **file_record(generated / "manual_required.jsonl")},
                "manual_table": {"path": "generated/manual_required.tsv", **file_record(generated / "manual_required.tsv")},
            }
            pipeline["manual_handoff"] = handoff
            pipeline["terminal_gate"]["manual_required_items"] = 440  # type: ignore[index]
            job["manual_handoff"] = handoff
            job["terminal_seal"].update({  # type: ignore[union-attr]
                "manual_required_items": 440,
                "manual_required_unreviewed": 440,
                "human_decision_required": 522,
            })
        write_json(stage / "pipeline_verification.json", pipeline)
        job["pipeline_verification"] = file_record(stage / "pipeline_verification.json")
        write_json(stage / "job_manifest_v3.json", job)
    return stage


def run_builder(repo: Path, stage: Path, output: Path, stub: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return command(
        repo,
        sys.executable,
        str(TOOL),
        "--repo", str(repo),
        "--ds-stage", str(stage),
        "--output-dir", str(output),
        "--authority-verifier", str(stub),
        "--extra-allow", "notes/review.json",
        *extra,
    )


class FinalAllowlistTests(unittest.TestCase):
    def test_selective_product_contract_rejects_unlisted_runtime_paths(self) -> None:
        self.assertEqual(len(MOD.TOTENTANZ_SELECTIVE_RUNTIME), 44)
        self.assertTrue(MOD.TOTENTANZ_SELECTIVE_RUNTIME.isdisjoint(MOD.PRODUCT_RUNTIME))

        for path in (
            "magica/template/card/CardSort.html",
            "magica/template/user/APPopup.html",
            "magica/css/arena/ArenaResult.css",
            "magica/css/regularEvent/groupBattle/RegularEventGroupBattleTop.css",
            "magica/css/_common/common.css",
            "magica/template/collection/StoryCollection.html",
        ):
            with self.subTest(path=path):
                decision, category, _reason = MOD.classify_known(
                    path, eol_only=False, extra_repo=set()
                )
                self.assertEqual(
                    (decision, category), ("allow", "totentanz_selective_runtime")
                )

        for path in (
            "magica/research/totentanz-selective-localization-20260817/README.md",
            "magica/research/totentanz-selective-localization-20260817/engine_i18n_selected_additions.tsv",
            "magica/research/totentanz-selective-localization-20260817/native_battle_popup_audit.md",
        ):
            with self.subTest(path=path):
                decision, category, _reason = MOD.classify_known(
                    path, eol_only=False, extra_repo=set()
                )
                self.assertEqual(
                    (decision, category), ("allow", "totentanz_selective_audit")
                )

        for path in (
            "magica/js/new-unlisted.js",
            "magica/template/new-unlisted.html",
            "magica/css/new-unlisted.css",
            "magica/js/libs/new-unlisted.json",
            "magica/research/new-reviewed.html",
            "magica/i18n_audit/new-reviewed.json",
            "magica/image/new-reviewed.png",
            "magica/font/new-reviewed.ttf",
        ):
            with self.subTest(path=path):
                decision, category, _reason = MOD.classify_known(
                    path, eol_only=False, extra_repo=set()
                )
                self.assertEqual((decision, category), ("exclude", "unclassified_change"))

        selected_png = (
            "magica/resource/image_web/regularEvent/groupBattle/common/result/"
            "result_title_header.png"
        )
        decision, category, _reason = MOD.classify_known(
            selected_png, eol_only=False, extra_repo=set()
        )
        self.assertEqual(
            (decision, category), ("allow", "totentanz_selective_runtime")
        )

    def test_live_main_import_is_commit_bound_and_fails_on_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v26-allow-live-main-") as td:
            base = Path(td)
            repo, stub = init_repo(base)
            stage = make_stage(base, mode="full")
            imported = repo / "configures/manifest.json"
            expected = '{"source":"live-main"}\n'
            write(imported, expected)
            for args in (("git", "add", "configures/manifest.json"), ("git", "commit", "-m", "live main fixture")):
                result = command(repo, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
            live_main_commit = command(repo, "git", "rev-parse", "HEAD").stdout.strip()
            result = command(repo, "git", "reset", "--hard", "HEAD^")
            self.assertEqual(result.returncode, 0, result.stderr)

            write(imported, expected)
            good = base / "good"
            result = run_builder(
                repo, stage, good, stub,
                "--live-main-commit", live_main_commit,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            verification = json.loads((good / "live_main_import_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(verification["resolved_commit"], live_main_commit)
            self.assertEqual(verification["selected_paths"], ["configures/manifest.json"])
            self.assertTrue(verification["rows"][0]["match"])

            write(imported, '{"source":"drift"}\n')
            bad = base / "bad"
            result = run_builder(
                repo, stage, bad, stub,
                "--live-main-commit", live_main_commit,
            )
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            record = json.loads((bad / "verification_record.json").read_text(encoding="utf-8"))
            self.assertFalse(record["checks"]["live_main_imports_exact"])

    def test_terminal_build_is_deterministic_and_exact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v26-allow-terminal-") as td:
            base = Path(td)
            repo, stub = init_repo(base)
            stage = make_stage(base, mode="full")
            out_a = base / "audit-a"
            out_b = base / "audit-b"
            first = run_builder(repo, stage, out_a, stub, "--extra-ds-artifact", "generated/selected.json")
            second = run_builder(repo, stage, out_b, stub, "--extra-ds-artifact", "generated/selected.json")
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            names_a = sorted(p.relative_to(out_a).as_posix() for p in out_a.rglob("*") if p.is_file())
            names_b = sorted(p.relative_to(out_b).as_posix() for p in out_b.rglob("*") if p.is_file())
            self.assertEqual(names_a, names_b)
            for name in names_a:
                self.assertEqual((out_a / name).read_bytes(), (out_b / name).read_bytes(), name)
            verification = json.loads((out_a / "verification_record.json").read_text(encoding="utf-8"))
            self.assertTrue(verification["finalizable"])
            self.assertTrue(verification["checks"]["partition_exact"])
            self.assertTrue(verification["checks"]["dsv4_terminal_marker"])
            allow = (out_a / "final_allowlist_paths.txt").read_text(encoding="utf-8").splitlines()
            exclude = (out_a / "exclude_paths.txt").read_text(encoding="utf-8").splitlines()
            status = command(repo, "git", "status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines()
            self.assertEqual(len(allow) + len(exclude), len(status))
            self.assertIn("notes/review.json", allow)
            self.assertIn("magica/js/_common/base.js", exclude)
            self.assertIn("candidate.zip", exclude)

    def test_nonterminal_is_fail_closed_but_writes_audit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v26-allow-nonterminal-") as td:
            base = Path(td)
            repo, stub = init_repo(base)
            stage = make_stage(base, mode="nonterminal")
            output = base / "audit"
            result = run_builder(repo, stage, output, stub)
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            verification = json.loads((output / "verification_record.json").read_text(encoding="utf-8"))
            self.assertFalse(verification["finalizable"])
            self.assertFalse(verification["checks"]["dsv4_terminal_marker"])
            ds = json.loads((output / "dsv4_terminal_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(ds["status"], "NONTERMINAL")
            self.assertTrue(verification["checks"]["partition_exact"])

    def test_explicit_manual_handoff_is_terminal_without_claiming_ds_complete(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v26-allow-manual-handoff-") as td:
            base = Path(td)
            repo, stub = init_repo(base)
            stage = make_stage(base, mode="manual_handoff")
            output = base / "audit"
            result = run_builder(repo, stage, output, stub)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            verification = json.loads((output / "verification_record.json").read_text(encoding="utf-8"))
            self.assertTrue(verification["checks"]["dsv4_terminal_marker"])
            ds = json.loads((output / "dsv4_terminal_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(ds["status"], "PASS")
            self.assertEqual(ds["terminal_mode"], "manual_handoff")
            self.assertTrue(ds["manual_handoff_terminal"])
            self.assertFalse(ds["ds_review_complete"])
            self.assertEqual(ds["checkpoint"]["last_completed_batch"], 74)
            self.assertEqual(ds["checkpoint"]["completed_items"], 1472)
            self.assertEqual(ds["manual_required_jsonl"]["rows"], 440)
            self.assertEqual(ds["reviewed_manual_rows"], 82)
            self.assertEqual(ds["human_decision_required"], 522)
            self.assertIsNone(ds["checkpoint"]["next_batch"])
            self.assertTrue(ds["checkpoint"]["ds_retry_disabled"])
            self.assertEqual(set(ds["top_level_seal_hashes"]), {
                "job_manifest_v3.json", "pipeline_verification.json",
            })
            self.assertTrue(all(ds["terminal_checks"].values()))

    def test_manual_handoff_artifact_hash_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v26-allow-manual-drift-") as td:
            base = Path(td)
            repo, stub = init_repo(base)
            stage = make_stage(base, mode="manual_handoff")
            with (stage / "generated/manual_required.jsonl").open("ab") as stream:
                stream.write(b'{"item_id":"UNBOUND"}\n')
            output = base / "audit"
            result = run_builder(repo, stage, output, stub)
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            ds = json.loads((output / "dsv4_terminal_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(ds["status"], "NONTERMINAL")
            self.assertFalse(ds["terminal_checks"]["manual_jsonl_bound"])
            self.assertFalse(ds["terminal_checks"]["manual_rows_440"])
            self.assertFalse(ds["terminal_checks"]["top_level_manual_files_bound"])

    def test_manual_handoff_retry_flag_and_top_level_seal_are_mandatory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v26-allow-manual-seal-") as td:
            base = Path(td)
            repo, stub = init_repo(base)
            stage = make_stage(base, mode="manual_handoff")
            state_path = stage / "generated/manual_handoff_state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["ds_retry_disabled"] = False
            write_json(state_path, state)
            pipeline_path = stage / "pipeline_verification.json"
            pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
            pipeline["result"] = "DRIFT"
            write_json(pipeline_path, pipeline)
            output = base / "audit"
            result = run_builder(repo, stage, output, stub)
            self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
            ds = json.loads((output / "dsv4_terminal_verification.json").read_text(encoding="utf-8"))
            self.assertFalse(ds["terminal_checks"]["manual_state_exact"])
            self.assertFalse(ds["terminal_checks"]["job_binds_pipeline_verification"])
            self.assertFalse(ds["terminal_checks"]["top_level_terminal_seal_true"])

    def test_existing_output_and_unknown_extra_fail_before_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="v26-allow-negative-") as td:
            base = Path(td)
            repo, stub = init_repo(base)
            stage = make_stage(base, mode="full")
            existing = base / "existing"
            existing.mkdir()
            result = run_builder(repo, stage, existing, stub)
            self.assertEqual(result.returncode, 1)
            output = base / "new-output"
            result = command(
                repo, sys.executable, str(TOOL), "--repo", str(repo),
                "--ds-stage", str(stage), "--output-dir", str(output),
                "--authority-verifier", str(stub), "--extra-allow", "missing.json",
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())

    def test_current_worktree_snapshot_is_read_only_when_available(self) -> None:
        stage = ROOT.parent / "deepseek_jobs/magireco_v26_explicit_lowtier_review_20260811_001/staging_v3"
        if not (stage / "generated/checkpoint.json").is_file():
            self.skipTest("current external DSV4 stage is absent")
        before = command(ROOT, "git", "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
        with tempfile.TemporaryDirectory(prefix="v26-current-audit-") as td:
            output = Path(td) / "audit"
            result = command(
                ROOT, sys.executable, str(TOOL), "--repo", str(ROOT),
                "--ds-stage", str(stage), "--output-dir", str(output),
            )
            self.assertIn(result.returncode, (0, 2), result.stderr + result.stdout)
            verification = json.loads((output / "verification_record.json").read_text(encoding="utf-8"))
            self.assertTrue(verification["checks"]["partition_exact"])
            marker = json.loads((stage / "generated/checkpoint.json").read_text(encoding="utf-8"))
            ds = json.loads((output / "dsv4_terminal_verification.json").read_text(encoding="utf-8"))
            if marker.get("state") == "closed-manual-handoff":
                self.assertTrue(ds["terminal"])
                self.assertEqual(ds["terminal_mode"], "manual_handoff")
                self.assertFalse(ds["ds_review_complete"])
            elif marker.get("state") == "complete":
                self.assertTrue(ds["terminal"])
                self.assertTrue(ds["ds_review_complete"])
            else:
                self.assertFalse(ds["terminal"])
        after = command(ROOT, "git", "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
