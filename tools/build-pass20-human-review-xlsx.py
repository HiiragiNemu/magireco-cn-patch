#!/usr/bin/env python3
"""Reproducibly build and verify the 1,565-row human review workbook.

The workbook itself is authored by @oai/artifact-tool.  This wrapper prepares
the bound source/target records, discovers the bundled Node runtime without
changing host network settings, invokes the artifact-tool authoring script,
hardens worksheet protection, and validates the blank import contract.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
AUDIT = ROOT / "magica/i18n_audit/release_v26_authority"
CANONICAL = AUDIT / "magireco_v26_translation_review_1565.xlsx"
DELIVERY = ROOT / "outputs/019fd6ce-093f-7d63-ac45-ca01a7008cf8/magireco_v26_translation_review_1565.xlsx"
INPUT_JSON = ROOT / "_artifacts/spreadsheet_build/v26_translation_review_1565_input.json"
PREPARE = TOOLS / "prepare-pass20-human-review-xlsx.py"
AUTHOR = TOOLS / "build-pass20-human-review-xlsx.mjs"
FINALIZE = TOOLS / "finalize-pass20-human-review-xlsx.py"


class BuildError(RuntimeError):
    pass


def _first_file(paths) -> Path | None:
    for value in paths:
        if value:
            path = Path(value).expanduser().resolve()
            if path.is_file() and not path.is_symlink():
                return path
    return None


def find_node() -> Path:
    explicit = os.environ.get("CODEX_BUNDLED_NODE")
    path_node = shutil.which("node")
    cached = sorted(Path.home().glob(".cache/codex-runtimes/*/dependencies/node/bin/node.exe"))
    found = _first_file([explicit, path_node, *cached])
    if found is None:
        raise BuildError("Node runtime not found; load the Codex workspace dependencies first")
    return found


def find_artifact_tool() -> Path:
    explicit = os.environ.get("OAI_ARTIFACT_TOOL_ENTRY")
    local = ROOT / "node_modules/@oai/artifact-tool/dist/artifact_tool.mjs"
    cached = sorted(
        Path.home().glob(
            ".cache/codex-runtimes/*/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs"
        )
    )
    found = _first_file([explicit, local, *cached])
    if found is None:
        raise BuildError("@oai/artifact-tool not found; load the Codex workspace dependencies first")
    return found


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise BuildError(f"build step failed with exit {completed.returncode}: {Path(command[0]).name}")


def _load_importer():
    path = TOOLS / "import-pass20-human-review-xlsx.py"
    spec = importlib.util.spec_from_file_location("pass20_xlsx_import", path)
    if spec is None or spec.loader is None:
        raise BuildError("workbook importer could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_outputs(canonical: Path = CANONICAL, delivery: Path = DELIVERY) -> dict[str, object]:
    for path in (canonical, delivery):
        if not path.is_file() or path.is_symlink():
            raise BuildError(f"workbook missing or unsafe: {path}")
        with zipfile.ZipFile(path) as package:
            if package.testzip() is not None:
                raise BuildError(f"workbook CRC failure: {path}")
            names = package.namelist()
            if len(names) != len(set(names)):
                raise BuildError(f"duplicate workbook member: {path}")
    if canonical.read_bytes() != delivery.read_bytes():
        raise BuildError("canonical and delivery workbooks differ")

    importer = _load_importer()
    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp) / "blank-decisions.tsv"
        result = importer.import_workbook(
            canonical,
            AUDIT / "pass20_remaining_manual_review.tsv",
            AUDIT / "dsv4_terminal_handoff/full_review.tsv",
            AUDIT / "dsv4_human_decisions.tsv",
            AUDIT / "pass20_product_targets.json",
            output,
            priority_path=AUDIT / "pass20_priority_manual_review.tsv",
            inventory_path=AUDIT / "pass20_machine_source_inventory.tsv",
            shadow_path=AUDIT / "pass20_authority_shadowed_machine_items.tsv",
            resolutions_path=AUDIT / "pass20_authority_resolutions.tsv",
        )
        if output.read_bytes() != (AUDIT / "dsv4_human_decisions.tsv").read_bytes():
            raise BuildError("blank workbook import was not byte-preserving")
    expected = {
        "workbook_rows": 1565,
        "priority_rows": 199,
        "approved_machine_rows": 1366,
        "workbook_excluded_rows": 0,
        "external_authority_audit_rows": 347,
        "higher_authority_shadowed_rows": 24,
        "decisions_imported": 0,
        "protected_text_changes": 0,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise BuildError(f"blank workbook verification count drifted: {result}")
    return {
        "status": "PASS",
        "canonical": str(canonical),
        "delivery": str(delivery),
        "bytes": canonical.stat().st_size,
        "counts": expected,
        "target_contract_sha256": result["target_contract_sha256"],
    }


def build(*, prepare_only: bool = False) -> dict[str, object]:
    _run([sys.executable, str(PREPARE)])
    if not INPUT_JSON.is_file():
        raise BuildError("prepared workbook input was not created")
    if prepare_only:
        payload = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
        return {"status": "PASS", "prepared": str(INPUT_JSON), "counts": payload["counts"]}

    node = find_node()
    artifact_tool = find_artifact_tool()
    build_root = ROOT / "_artifacts/spreadsheet_build"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pass20-xlsx-", dir=build_root) as temp:
        temp_root = Path(temp)
        staged = temp_root / CANONICAL.name
        staged_delivery = temp_root / (CANONICAL.stem + ".delivery.xlsx")
        env = dict(os.environ)
        env["OAI_ARTIFACT_TOOL_ENTRY"] = str(artifact_tool)
        env["PASS20_XLSX_OUTPUT"] = str(staged)
        env["PASS20_XLSX_DELIVERY"] = str(staged_delivery)
        _run([str(node), str(AUTHOR)], env=env)
        _run([
            sys.executable, str(FINALIZE),
            "--xlsx", str(staged), "--delivery", str(staged_delivery),
        ])
        verify_outputs(staged, staged_delivery)
        CANONICAL.parent.mkdir(parents=True, exist_ok=True)
        DELIVERY.parent.mkdir(parents=True, exist_ok=True)
        staged.replace(CANONICAL)
        staged_delivery.replace(DELIVERY)
    return verify_outputs()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = verify_outputs() if args.verify_only else build(prepare_only=args.prepare_only)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (BuildError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
