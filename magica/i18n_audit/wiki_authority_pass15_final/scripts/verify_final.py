#!/usr/bin/env python3
"""Read-only verification of the pass15 final audit and runtime payload."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


EXPECTED_DICTS = (
    "arenaClassList", "cardList", "cardMagiaMap", "cardSkillMap", "chapterList",
    "charaList", "charaMessageList", "doppelCardMagiaMap", "doppelList",
    "emotionSkillMap", "enemyList", "eventList", "eventStoryList",
    "formationSheetList", "giftList", "itemList", "live2dList", "patrolAreaList",
    "pieceList", "pieceSkillMap", "placeSkillMap", "sectionList", "shopItemList",
)
BASE = "2a5eedeef0d58b5e43f367eb420e011d27529497"
GACHA = (
    "magica/js/campaign/box_gacha/CampaignBoxGachaTop.js",
    "magica/template/campaign/box_gacha/CampaignBoxGachaTop.html",
    "magica/template/gacha/GachaTop.html",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_builder(path: Path):
    spec = importlib.util.spec_from_file_location("pass15_final_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    audit = Path(__file__).resolve().parents[1]
    tree = (args.tree or audit.parents[2]).resolve()
    libs = tree / "magica/js/libs"
    summary = json.loads((audit / "authority_layer_summary.json").read_text(encoding="utf-8"))
    ledger = read_tsv(audit / "authority_layer_ledger_892.tsv")
    residual = read_tsv(audit / "remaining_residual_8959.tsv")
    coverage = json.loads((audit / "sources/field_source_coverage.json").read_text(encoding="utf-8"))
    structure = json.loads((audit / "runtime_structure_audit.json").read_text(encoding="utf-8"))

    errors: list[str] = []
    checksum_rows = 0
    checksum_file = audit / "SHA256SUMS.txt"
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        checksum_rows += 1
        expected, rel = line.split("  ", 1)
        candidate = audit / rel
        if not candidate.is_file() or sha(candidate.read_bytes()) != expected:
            errors.append(f"SHA256SUMS mismatch: {rel}")
    if summary.get("verified_remaining_residual") != 8959 or len(residual) != 8959:
        errors.append("residual count mismatch")
    if len(ledger) != 892:
        errors.append("ledger row count mismatch")
    if coverage.get("field_source_coverage_status") != "PASS":
        errors.append("field source coverage is not PASS")
    counts = coverage.get("counts", {})
    if counts.get("changed_standalone_json_fields") != 382 or counts.get("covered_changed_fields") != 382:
        errors.append("382/382 field coverage mismatch")
    if structure.get("status") != "PASS" or structure.get("errors"):
        errors.append("runtime structure audit is not PASS")
    baseline_comparison = structure.get("baseline_comparison", {})
    if baseline_comparison.get("changed_string_field_count") != 382:
        errors.append("runtime structure changed-field count mismatch")

    for name, expected in summary.get("output_sha256", {}).items():
        path = audit / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            errors.append(f"summary hash mismatch: {name}")

    protected: list[dict[str, object]] = []
    css = run(["git", "-C", str(tree), "ls-tree", "-r", "--name-only", BASE, "--", "magica/css"])
    if css.returncode:
        errors.append("cannot list protected CSS from baseline")
        css_paths: list[str] = []
    else:
        css_paths = [line for line in css.stdout.splitlines() if line]
    for rel in sorted(set(css_paths + list(GACHA))):
        current = tree / rel
        # git show in text mode is unsuitable for arbitrary bytes; hash the blob
        # through Git and compare with hash-object of the current file.
        base_blob = run(["git", "-C", str(tree), "rev-parse", f"{BASE}:{rel}"])
        current_blob = run(["git", "-C", str(tree), "hash-object", f"--path={rel}", str(current)])
        same = base_blob.returncode == current_blob.returncode == 0 and base_blob.stdout.strip() == current_blob.stdout.strip()
        protected.append({"path": rel, "byte_identical": same})
        if not same:
            errors.append(f"protected path drift: {rel}")

    with tempfile.TemporaryDirectory(prefix="pass15_verify_") as temp_name:
        temp = Path(temp_name)
        shutil.copy2(tree / "Build_JS_Injector.py", temp / "Build_JS_Injector.py")
        shutil.copytree(tree / "original_source", temp / "original_source")
        shutil.copytree(libs, temp / "magica/js/libs")
        jquery = temp / "magica/js/libs/jquery-3.7.1.min.js"
        builds = []
        for _ in range(2):
            cp = run(["python", "Build_JS_Injector.py"], cwd=temp)
            digest = sha(jquery.read_bytes()) if jquery.is_file() else None
            builds.append({
                "exit_code": cp.returncode,
                "stdout": cp.stdout.strip(),
                "stderr": cp.stderr.strip(),
                "jquery_sha256": digest,
            })
            if cp.returncode:
                errors.append("isolated builder failed")
        current_sha = sha((libs / "jquery-3.7.1.min.js").read_bytes())
        if not (builds[0]["jquery_sha256"] == builds[1]["jquery_sha256"] == current_sha):
            errors.append("isolated builds are not deterministic")
        node = run(["node", "--check", str(jquery)])
        if node.returncode:
            errors.append("node syntax check failed")

        builder = load_builder(temp / "Build_JS_Injector.py")
        text = jquery.read_text(encoding="utf-8")
        pos = text.rfind("var cn = ")
        if pos < 0:
            errors.append("embedded dictionary marker missing")
            embedded = {}
        else:
            embedded, _ = json.JSONDecoder().raw_decode(text[pos + len("var cn = "):])
        standalone = {}
        for name in EXPECTED_DICTS:
            raw = json.loads((temp / f"magica/js/libs/{name}.json").read_text(encoding="utf-8-sig"))
            standalone[name] = builder.map_dictionary(name, raw)
        embedded_match = embedded == standalone and len(standalone) == len(EXPECTED_DICTS)
        if not embedded_match:
            errors.append("standalone/embedded dictionary mismatch")

    result = {
        "schema": "magireco-cn-pass15-final-portable-verification/v1",
        "status": "PASS" if not errors else "FAIL",
        "tree": str(tree),
        "base": BASE,
        "ledger_rows": len(ledger),
        "remaining_residual": len(residual),
        "sha256sums": {"entries": checksum_rows, "match": not any(e.startswith("SHA256SUMS mismatch:") for e in errors)},
        "field_source_coverage": counts,
        "runtime_structure_audit": {
            "status": structure.get("status"),
            "changed_string_fields": baseline_comparison.get("changed_string_field_count"),
            "numeric_signature_drift": baseline_comparison.get("numeric_signature_drift_count"),
            "warnings": structure.get("warnings", []),
        },
        "protected_paths": {
            "count": len(protected),
            "identical": sum(bool(row["byte_identical"]) for row in protected),
            "files": protected,
        },
        "deterministic_builds": builds,
        "jquery_sha256": current_sha,
        "node_check": {"exit_code": node.returncode, "stdout": node.stdout.strip(), "stderr": node.stderr.strip()},
        "standalone_embedded": {"count": len(standalone), "match": embedded_match},
        "errors": errors,
    }
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
