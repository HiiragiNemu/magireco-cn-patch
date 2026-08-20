#!/usr/bin/env python3
"""Independent regression tests for the terminal evidence composer."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/build-final-source-exhaustion-report.py"
EVIDENCE = ROOT.parent / "next_round_execution_20260819"


def module():
    spec = importlib.util.spec_from_file_location("source_exhaustion", SCRIPT)
    assert spec and spec.loader
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def fixture(mod, temp: Path) -> tuple[Path, Path]:
    repo, evidence = temp / "repo", temp / "evidence"
    for rel in mod.REPO_INPUTS.values():
        copy(ROOT / rel, repo / rel)
    for rel in mod.EXTERNAL_INPUTS.values():
        copy(EVIDENCE / rel, evidence / rel)
    deps = mod.load_tsv(EVIDENCE / mod.EXTERNAL_INPUTS["dependencies"])
    for row in deps:
        source = ROOT / "magica" / Path(row["path"])
        if row["path"].endswith(".html") and source.is_file():
            copy(source, repo / "magica" / Path(row["path"]))
    round6 = mod.load_json(ROOT / mod.REPO_INPUTS["round6_verification"])
    for entry in round6["entries"]:
        copy(ROOT / entry["product_path"], repo / entry["product_path"])
    return repo, evidence


def fails(mod, repo: Path, evidence: Path, text: str) -> None:
    try:
        mod.build_summary(repo, evidence)
    except mod.EvidenceError as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError("fail-closed mutation was accepted")


def main() -> int:
    mod = module()
    result = mod.build_summary(ROOT, EVIDENCE)
    assert result["status"] == "PASS"
    assert result["text"]["old_only_paths"]["remaining"] == 0
    assert result["text"]["missing_dependencies"]["html"]["materialized"] == 11
    assert result["text"]["missing_dependencies"]["html"]["terminal_excluded_or_no_fixed_text"] == 37
    assert result["images"]["same_path"]["actionable_closed"] == 160
    assert result["images"]["dynamic_official_cn"]["product_present"] == 681
    assert result["images"]["native_quest_atlas"]["verified_frames"] == 9
    assert result["engine_i18n"]["logical_rules"] == 615
    assert result["engine_i18n"]["physical_lines"] == 616
    assert result["engine_i18n"]["final_semantic_review"] == {
        "reviewed": 212,
        "total": 212,
        "acceptable_no_change": 172,
        "corrections_required": 40,
        "corrections_applied": 40,
        "official_cn_dual_abi_exact_corrections": 35,
        "root_semantic_corrections": 5,
        "historical_origin_machine_translated": "unknown-preserved-in-evidence",
        "rollback_reapply_roundtrip": "pass",
    }
    assert result["engine_i18n"]["authority_partition"] == {
        "official": 58,
        "confirmed_human_dynamic_timer": 301,
        "root_reviewed": 252,
        "wiki": 3,
        "intentional": 1,
    }
    assert result["engine_i18n"]["unverified"] == 0
    assert result["engine_i18n"]["consumer_boundaries"] == []
    assert len(result["engine_i18n"]["resolved_consumer_boundaries"]) == 2
    assert result["engine_i18n"]["dynamic_timer_prefix_closure"]["status"] == "closed"
    assert mod.output_bytes(result) == mod.output_bytes(mod.build_summary(ROOT, EVIDENCE))

    with tempfile.TemporaryDirectory(prefix="source-exhaustion-test-") as raw:
        repo, evidence = fixture(mod, Path(raw))
        clean = mod.build_summary(repo, evidence)
        old_path = evidence / mod.EXTERNAL_INPUTS["old_only"]
        old_bytes = old_path.read_bytes()
        old = json.loads(old_bytes.decode("utf-8"))
        old["remaining"]["actionable_rows"] = 1
        old_path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        fails(mod, repo, evidence, "remainder")
        old_path.write_bytes(old_bytes)

        engine = repo / mod.REPO_INPUTS["engine_table"]
        engine_bytes = engine.read_bytes()
        engine.write_bytes(engine_bytes + b"EXTRA\tEXTRA\n")
        fails(mod, repo, evidence, "615/616")
        engine.write_bytes(engine_bytes)

        application_path = repo / mod.REPO_INPUTS["engine_final_application"]
        application_bytes = application_path.read_bytes()
        application = json.loads(application_bytes.decode("utf-8"))
        application["correction_rows"] = 39
        application_path.write_text(json.dumps(application, ensure_ascii=False), encoding="utf-8")
        fails(mod, repo, evidence, "40-correction")
        application_path.write_bytes(application_bytes)

        machine_path = repo / mod.REPO_INPUTS["machine_review_summary"]
        machine_bytes = machine_path.read_bytes()
        machine = json.loads(machine_bytes.decode("utf-8"))
        machine["counts"]["engine_unverified"] = 1
        machine_path.write_text(json.dumps(machine, ensure_ascii=False), encoding="utf-8")
        fails(mod, repo, evidence, "unverified")
        machine_path.write_bytes(machine_bytes)

        out = Path(raw) / "out"
        outputs = mod.output_bytes(clean)
        mod.write_or_check(outputs, out, False)
        mod.write_or_check(outputs, out, True)
        (out / "REPORT_CN.md").write_text("stale", encoding="utf-8")
        try:
            mod.write_or_check(outputs, out, True)
        except mod.EvidenceError:
            pass
        else:
            raise AssertionError("stale output was accepted")

    check = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=ROOT, text=True, capture_output=True)
    assert check.returncode == 0, (check.stdout, check.stderr)
    print("PASS: 8/8 final source-exhaustion tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
