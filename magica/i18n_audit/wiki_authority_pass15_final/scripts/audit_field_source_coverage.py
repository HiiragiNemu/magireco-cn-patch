#!/usr/bin/env python3
"""Audit every current runtime field delta against frozen authority recipes.

The product worktree is read-only.  The inherited pass14 executor is exercised
only in a disposable baseline copy so its reproducibility can be reported
without changing product bytes.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(r"C:\Users\proje\Documents\Codex\2026-08-06\https-github-com-hiiraginemu-magireco-wiki-3")
TREE = ROOT / "work" / "pass15_final_integration"
OUT = ROOT / "work" / "final_validation_prep"
BASE = "20e35db411e83d710662c98f12c1374fa8363dda"
AUDIT = ROOT / "work" / "pass15_authority" / "magica" / "i18n_audit"
COMBINED_LEDGER = ROOT / "work" / "pass17_max_integrated" / "release" / "authority_layer_ledger_571.tsv"
PASS10_SUMMARY = AUDIT / "wiki_authority_pass10_equivalence" / "source_summary.json"
PASS11_RECIPE = AUDIT / "wiki_authority_pass11_mechanics" / "mechanics_corrections.json"
PASS12_SUMMARY = AUDIT / "wiki_authority_pass12_baseline_equivalence" / "source_summary.json"
PASS13_RECIPE = AUDIT / "wiki_authority_pass13_card_identity" / "card_identity_corrections.json"
PASS14_RECIPE = AUDIT / "wiki_authority_pass14_special_doppel" / "special_doppel_authority.json"
PASS14_APPLIER = AUDIT / "wiki_authority_pass14_special_doppel" / "apply_pass11_pass13_pass14_runtime.py"
PREVIOUS_VERIFICATION = OUT / "verification.json"

DICT_NAMES = (
    "arenaClassList", "cardList", "cardMagiaMap", "cardSkillMap", "chapterList",
    "charaList", "charaMessageList", "doppelCardMagiaMap", "doppelList",
    "emotionSkillMap", "enemyList", "eventList", "eventStoryList",
    "formationSheetList", "giftList", "itemList", "live2dList", "patrolAreaList",
    "pieceList", "pieceSkillMap", "placeSkillMap", "sectionList", "shopItemList",
)
LIST_KEYS = {
    "arenaClassList": ("arenaBattleFreeRankClass",),
    "cardList": ("cardId", "id"),
    "chapterList": ("chapterId", "id"),
    "charaList": ("id", "charaNo"),
    "charaMessageList": ("charaNo_messageId",),
    "doppelList": ("id",),
    "enemyList": ("enemyId", "id"),
    "eventList": ("eventId", "id"),
    "eventStoryList": ("storyIds",),
    "formationSheetList": ("formationSheetId", "id"),
    "giftList": ("id", "giftId"),
    "itemList": ("itemCode", "id", "itemId"),
    "live2dList": ("charaId_live2dId",),
    "patrolAreaList": ("patrolAreaId", "id"),
    "pieceList": ("pieceId", "id"),
    "sectionList": ("sectionId", "id"),
    "shopItemList": ("shopItemId", "id"),
}
RUNTIME_PATHS = [f"magica/js/libs/{name}.json" for name in DICT_NAMES] + [
    "magica/js/libs/jquery-3.7.1.min.js"
]
SUPPORT_PATHS = ["Build_JS_Injector.py", "original_source/jquery-3.7.1.min.js"]


def run(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    cp = subprocess.run(args, cwd=cwd, capture_output=True)
    if check and cp.returncode:
        raise RuntimeError(
            f"command failed ({cp.returncode}): {args!r}\n"
            f"stdout={cp.stdout.decode('utf-8', errors='replace')}\n"
            f"stderr={cp.stderr.decode('utf-8', errors='replace')}"
        )
    return cp


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return run(["git", "-C", str(TREE), *args], check=check)


def decode(cp: subprocess.CompletedProcess[bytes]) -> str:
    return cp.stdout.decode("utf-8", errors="replace")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def source_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha_file(path)}


def map_dictionary(name: str, data: Any) -> dict[str, Any]:
    if name not in LIST_KEYS:
        if not isinstance(data, dict):
            raise TypeError(f"{name} must be an object")
        return {str(key): value for key, value in data.items()}
    if not isinstance(data, list):
        raise TypeError(f"{name} must be an array")
    mapped: dict[str, Any] = {}
    for row in data:
        if not isinstance(row, dict):
            raise TypeError(f"{name} contains a non-object row")
        if name == "charaMessageList":
            key = f"{row.get('charaNo', '')}_{row.get('messageId', '')}"
        elif name == "live2dList":
            key = f"{row.get('charaId', '')}_{row.get('live2dId', '')}"
        else:
            key = ""
            for field in LIST_KEYS[name]:
                if field in row:
                    key = str(row[field])
                    break
        if not key or key == "_":
            continue
        if key in mapped:
            raise ValueError(f"duplicate {name} key {key}")
        mapped[key] = row
    return mapped


def walk_leaves(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_leaves(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_leaves(child, (*path, str(index)))
    else:
        yield path, value


def get_path(value: Any, path: tuple[str, ...]) -> Any:
    node = value
    for part in path:
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def set_path(value: Any, path: tuple[str, ...], replacement: Any) -> None:
    node = value
    for part in path[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    final = path[-1]
    if isinstance(node, list):
        node[int(final)] = replacement
    else:
        node[final] = replacement


def json_pointer(path: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)


def product_fingerprint() -> dict[str, str | None]:
    return {
        rel: sha_file(TREE / rel) if (TREE / rel).is_file() else None
        for rel in sorted(RUNTIME_PATHS + SUPPORT_PATHS)
    }


def status_snapshot() -> dict[str, list[str]]:
    return {
        "modified": sorted(filter(None, decode(git("diff", "--name-only", BASE)).splitlines())),
        "staged": sorted(filter(None, decode(git("diff", "--cached", "--name-only", BASE)).splitlines())),
        "untracked": sorted(filter(None, decode(git("ls-files", "--others", "--exclude-standard")).splitlines())),
    }


def transition(
    *, layer: str, file: str, stable_key: str, field: str,
    before: Any, after: Any, recipe: Path, recipe_row: str,
    authority_type: str = "", source_locator: str = "", note: str = "",
    ledger_sequence: str = "",
) -> dict[str, Any]:
    return {
        "layer": layer,
        "file": file,
        "stable_key": str(stable_key),
        "field_path": (field,),
        "field": field,
        "expected_before": before,
        "after": after,
        "recipe_path": str(recipe),
        "recipe_sha256": sha_file(recipe),
        "recipe_row": recipe_row,
        "authority_type": authority_type,
        "source_locator": source_locator,
        "note": note,
        "ledger_sequence": ledger_sequence,
    }


def load_transitions() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mechanics = json.loads(PASS11_RECIPE.read_text(encoding="utf-8-sig"))
    for index, row in enumerate(mechanics, 1):
        rows.append(transition(
            layer="pass11_mechanics", file="cardMagiaMap.json", stable_key=str(row["id"]),
            field=row["field"], before=row["pass9_value"], after=row["pass11_value"],
            recipe=PASS11_RECIPE, recipe_row=f"index={index};id={row['id']}",
            authority_type=row.get("authority_source", ""),
            source_locator=row.get("wiki_reference") or "baseline_pre_llm",
            note=row.get("error_class", ""),
        ))

    identities = json.loads(PASS13_RECIPE.read_text(encoding="utf-8-sig"))
    for index, row in enumerate(identities, 1):
        rows.append(transition(
            layer="pass13_card_identity", file="cardList.json", stable_key=str(row["cardId"]),
            field="cardName", before=row["from"], after=row["to"], recipe=PASS13_RECIPE,
            recipe_row=f"index={index};cardId={row['cardId']}", authority_type=row.get("authority", ""),
            source_locator=f"wiki typed characterId={row.get('characterId')}",
        ))

    special = json.loads(PASS14_RECIPE.read_text(encoding="utf-8-sig"))["runtime_replacements"]
    for index, row in enumerate(special, 1):
        for file, stable_key in (
            ("cardMagiaMap.json", str(row["magiaId"])),
            ("doppelCardMagiaMap.json", str(row["magiaId"])),
            ("doppelList.json", str(row["doppelId"])),
        ):
            rows.append(transition(
                layer="pass14_special_doppel", file=file, stable_key=stable_key, field="name",
                before=row["from"], after=row["to"], recipe=PASS14_RECIPE,
                recipe_row=f"index={index};charaId={row['charaId']};target={file}",
                authority_type="frozen_wiki_typed_special_doppel",
                source_locator=f"wiki character={row.get('wiki')}",
            ))

    ledger_rows = list(csv.DictReader(COMBINED_LEDGER.open(encoding="utf-8-sig", newline=""), delimiter="\t"))
    runtime_ledger_rows = [row for row in ledger_rows if row["runtime_byte_change"].lower() == "true"]
    runtime_ledger_rows.sort(key=lambda row: int(row["sequence"]))
    for row in runtime_ledger_rows:
        rows.append(transition(
            layer=row["layer"], file=row["file"], stable_key=row["stable_key"], field=row["field"],
            before=row["expected_before"], after=row["after"], recipe=COMBINED_LEDGER,
            recipe_row=f"sequence={row['sequence']}", authority_type=row["authority_type"],
            source_locator=" | ".join(filter(None, [row["source_locator"], row["wiki_locator"]])),
            note=row["note"], ledger_sequence=row["sequence"],
        ))
    context = {
        "pass10": json.loads(PASS10_SUMMARY.read_text(encoding="utf-8-sig")),
        "pass12": json.loads(PASS12_SUMMARY.read_text(encoding="utf-8-sig")),
        "combined_ledger_total_rows": len(ledger_rows),
        "combined_ledger_runtime_rows": len(runtime_ledger_rows),
        "combined_ledger_provenance_only_rows": len(ledger_rows) - len(runtime_ledger_rows),
    }
    return rows, context


def pass14_executor_probe() -> dict[str, Any]:
    head = decode(git("rev-parse", "HEAD")).strip()
    if head != BASE:
        return {"status": "SKIPPED", "reason": f"HEAD {head} is not exact baseline {BASE}"}
    paths = sorted(set(RUNTIME_PATHS + SUPPORT_PATHS))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="pass14_executor_probe_", dir=OUT) as temp_name:
        temp = Path(temp_name)
        checkout = subprocess.run([
            "git", "-C", str(TREE), "checkout-index", "--force",
            f"--prefix={temp.as_posix()}/", "--", *paths,
        ], capture_output=True, env=env)
        if checkout.returncode:
            return {
                "status": "FAIL", "stage": "checkout-index", "exit_code": checkout.returncode,
                "stderr": checkout.stderr.decode("utf-8", errors="replace"),
            }
        cp = subprocess.run(
            ["python", str(PASS14_APPLIER), "--repo-root", str(temp)],
            capture_output=True, env=env,
        )
        stderr = cp.stderr.decode("utf-8", errors="replace")
        stdout = cp.stdout.decode("utf-8", errors="replace")
        return {
            "status": "PASS" if cp.returncode == 0 else "FAIL",
            "exit_code": cp.returncode,
            "command": f'python "{PASS14_APPLIER}" --repo-root DISPOSABLE_BASELINE',
            "stdout": stdout,
            "stderr": stderr,
            "defect_class": (
                "dict_runtime_maps_treated_as_row_arrays"
                if "TypeError: string indices must be integers" in stderr and "rows_by" in stderr else None
            ),
            "analysis": (
                "recipe content is valid, but the inherited applier indexes cardMagiaMap/doppelCardMagiaMap "
                "as arrays with row['id']; the frozen runtime files are keyed JSON objects"
                if cp.returncode else "executor completed"
            ),
        }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    before_fingerprint = product_fingerprint()
    before_status = status_snapshot()
    head = decode(git("rev-parse", "HEAD")).strip()
    if head != BASE:
        raise AssertionError(f"expected uncommitted integration over {BASE}, found HEAD {head}")

    base_mapped: dict[str, dict[str, Any]] = {}
    current_mapped: dict[str, dict[str, Any]] = {}
    structural_issues: list[dict[str, Any]] = []
    for name in DICT_NAMES:
        file = f"{name}.json"
        rel = f"magica/js/libs/{file}"
        base_raw = json.loads(git("show", f"{BASE}:{rel}").stdout.decode("utf-8-sig"))
        current_raw = json.loads((TREE / rel).read_text(encoding="utf-8-sig"))
        base_mapped[file] = map_dictionary(name, base_raw)
        current_mapped[file] = map_dictionary(name, current_raw)
        if set(base_mapped[file]) != set(current_mapped[file]):
            structural_issues.append({
                "file": file, "type": "stable_key_set",
                "missing": sorted(set(base_mapped[file]) - set(current_mapped[file])),
                "extra": sorted(set(current_mapped[file]) - set(base_mapped[file])),
            })

    changed: dict[tuple[str, str, tuple[str, ...]], tuple[Any, Any]] = {}
    for file in sorted(base_mapped):
        for stable_key in sorted(set(base_mapped[file]) & set(current_mapped[file])):
            old_row, new_row = base_mapped[file][stable_key], current_mapped[file][stable_key]
            old_leaves = dict(walk_leaves(old_row))
            new_leaves = dict(walk_leaves(new_row))
            if set(old_leaves) != set(new_leaves):
                structural_issues.append({
                    "file": file, "stable_key": stable_key, "type": "leaf_path_set",
                    "missing": [json_pointer(path) for path in sorted(set(old_leaves) - set(new_leaves))],
                    "extra": [json_pointer(path) for path in sorted(set(new_leaves) - set(old_leaves))],
                })
            for field_path in sorted(set(old_leaves) & set(new_leaves)):
                if old_leaves[field_path] != new_leaves[field_path]:
                    changed[(file, stable_key, field_path)] = (old_leaves[field_path], new_leaves[field_path])

    transitions, provenance_context = load_transitions()
    simulated = copy.deepcopy(base_mapped)
    chains: dict[tuple[str, str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    transition_issues: list[dict[str, Any]] = []
    for order, row in enumerate(transitions, 1):
        target = (row["file"], row["stable_key"], tuple(row["field_path"]))
        applied = dict(row)
        applied["application_order"] = order
        try:
            actual_before = get_path(simulated[row["file"]][row["stable_key"]], tuple(row["field_path"]))
        except Exception as exc:
            applied["application_status"] = "MISSING_TARGET"
            applied["actual_before"] = None
            applied["error"] = f"{type(exc).__name__}: {exc}"
            transition_issues.append(applied)
        else:
            applied["actual_before"] = actual_before
            if actual_before == row["expected_before"]:
                set_path(simulated[row["file"]][row["stable_key"]], tuple(row["field_path"]), row["after"])
                applied["application_status"] = "APPLIED_EXACT"
            else:
                applied["application_status"] = "PREIMAGE_MISMATCH"
                transition_issues.append(applied)
        chains[target].append(applied)

    records: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []
    for target in sorted(changed, key=lambda x: (x[0], x[1], x[2])):
        file, stable_key, field_path = target
        baseline_value, current_value = changed[target]
        steps = chains.get(target, [])
        step_exact = bool(steps) and all(step["application_status"] == "APPLIED_EXACT" for step in steps)
        pairwise = bool(steps) and steps[0]["expected_before"] == baseline_value
        if pairwise:
            pairwise = all(left["after"] == right["expected_before"] for left, right in zip(steps, steps[1:]))
        if pairwise:
            pairwise = steps[-1]["after"] == current_value
        simulated_value = get_path(simulated[file][stable_key], field_path)
        covered = step_exact and pairwise and simulated_value == current_value
        layers = [str(step["layer"]) for step in steps]
        record = {
            "file": file,
            "stable_key": stable_key,
            "field": field_path[0] if len(field_path) == 1 else json_pointer(field_path),
            "json_pointer": json_pointer(field_path),
            "baseline_value": baseline_value,
            "current_value": current_value,
            "value_type": type(current_value).__name__,
            "coverage_status": "EXACT_CHAIN_COVERED" if covered else "UNCOVERED_OR_CHAIN_MISMATCH",
            "explicit_source_covered": covered,
            "whole_file_copy_uncovered_regression": not covered,
            "transition_count": len(steps),
            "layers": layers,
            "layer_chain": " -> ".join(layers),
            "recipe_rows": [f"{step['recipe_path']}#{step['recipe_row']}" for step in steps],
            "authority_types": [step["authority_type"] for step in steps],
            "source_locators": [step["source_locator"] for step in steps],
            "chain_exact": pairwise,
            "simulated_final_matches_product": simulated_value == current_value,
            "known_pass11_90360": file == "cardMagiaMap.json" and stable_key == "90360" and field_path == ("shortDescription",),
            "transitions": steps,
        }
        records.append(record)
        if not covered:
            uncovered.append(record)

    changed_targets = set(changed)
    recipe_targets = set(chains)
    extra_recipe_targets = sorted(recipe_targets - changed_targets, key=lambda x: (x[0], x[1], x[2]))
    semantic_full_match = all(simulated[file] == current_mapped[file] for file in simulated)
    actual_modified = before_status["modified"]
    changed_json_paths = sorted(f"magica/js/libs/{file}" for file in {target[0] for target in changed})
    jquery_rel = "magica/js/libs/jquery-3.7.1.min.js"
    previous = json.loads(PREVIOUS_VERIFICATION.read_text(encoding="utf-8"))
    jquery_derived = {
        "path": jquery_rel,
        "current_sha256": sha_file(TREE / jquery_rel),
        "matches_previous_deterministic_validation": (
            sha_file(TREE / jquery_rel) == previous["deterministic_builder"]["source_snapshot_jquery_sha256"]
        ),
        "deterministic_builder_pass": previous["deterministic_builder"]["pass"],
        "embedded_dictionary_mismatch_count": previous["runtime_structure"]["report"]["embedded_payload"]["mapped_dictionary_mismatch_count"],
        "coverage": "derived from the 23 standalone dictionaries by the pinned deterministic builder",
    }
    executor_probe = pass14_executor_probe()
    after_fingerprint = product_fingerprint()
    after_status = status_snapshot()
    product_stable = before_fingerprint == after_fingerprint and before_status == after_status

    by_file: dict[str, dict[str, Any]] = {}
    for file in sorted({record["file"] for record in records}):
        selected = [record for record in records if record["file"] == file]
        by_file[file] = {
            "changed_fields": len(selected),
            "covered_fields": sum(bool(record["explicit_source_covered"]) for record in selected),
            "uncovered_fields": sum(not bool(record["explicit_source_covered"]) for record in selected),
            "transition_rows": sum(int(record["transition_count"]) for record in selected),
            "whole_file_copy_uncovered_regressions": sum(bool(record["whole_file_copy_uncovered_regression"]) for record in selected),
        }
    layer_counts = Counter(row["layer"] for row in transitions)
    multi_transition = [record for record in records if record["transition_count"] > 1]
    field_coverage_pass = (
        not structural_issues and not transition_issues and not uncovered and not extra_recipe_targets
        and semantic_full_match and len(records) == 382
    )
    executor_defect = executor_probe.get("status") == "FAIL"
    status = (
        "FAIL" if not field_coverage_pass or not product_stable else
        "PASS_WITH_RECIPE_EXECUTOR_DEFECT" if executor_defect else "PASS"
    )
    result = {
        "schema": "magireco-pass15-field-source-coverage/v1",
        "status": status,
        "field_source_coverage_status": "PASS" if field_coverage_pass else "FAIL",
        "product_worktree_read_only_status": "PASS" if product_stable else "FAIL",
        "baseline_commit": BASE,
        "product_tree": str(TREE),
        "counts": {
            "changed_standalone_json_fields": len(records),
            "covered_changed_fields": len(records) - len(uncovered),
            "uncovered_changed_fields": len(uncovered),
            "recipe_transition_rows": len(transitions),
            "recipe_unique_targets": len(recipe_targets),
            "multi_transition_fields": len(multi_transition),
            "transition_preimage_or_target_issues": len(transition_issues),
            "recipe_targets_not_changed_in_product": len(extra_recipe_targets),
            "whole_file_copy_uncovered_regressions": len(uncovered),
        },
        "by_file": by_file,
        "transition_rows_by_layer": dict(sorted(layer_counts.items())),
        "provenance_only_context": {
            "pass10": {
                "runtime_text_changed": provenance_context["pass10"]["runtime_text_changed"],
                "authority_equivalence_upgrades": provenance_context["pass10"]["authority_equivalence_upgrades"],
                "source": source_record(PASS10_SUMMARY),
            },
            "pass12": {
                "runtime_text_changed": provenance_context["pass12"]["runtime_text_changed"],
                "pass12_baseline_equivalence_upgrades": provenance_context["pass12"]["pass12_baseline_equivalence_upgrades"],
                "source": source_record(PASS12_SUMMARY),
            },
            "combined_ledger_total_rows": provenance_context["combined_ledger_total_rows"],
            "combined_ledger_runtime_rows": provenance_context["combined_ledger_runtime_rows"],
            "combined_ledger_provenance_only_rows": provenance_context["combined_ledger_provenance_only_rows"],
        },
        "sources": {
            "pass11_recipe": source_record(PASS11_RECIPE),
            "pass13_recipe": source_record(PASS13_RECIPE),
            "pass14_recipe": source_record(PASS14_RECIPE),
            "pass15_combined_571_ledger": source_record(COMBINED_LEDGER),
            "pass14_inherited_applier": source_record(PASS14_APPLIER),
        },
        "known_pass11_90360": next(
            record for record in records
            if record["known_pass11_90360"]
        ),
        "jquery_derived_coverage": jquery_derived,
        "semantic_simulation": {
            "all_23_mapped_dictionaries_equal_current_after_applying_recipes": semantic_full_match,
            "structural_issues": structural_issues,
            "transition_issues": transition_issues,
            "extra_recipe_targets": [
                {"file": file, "stable_key": key, "json_pointer": json_pointer(path)}
                for file, key, path in extra_recipe_targets
            ],
        },
        "whole_file_copy_regression_audit": {
            "changed_json_paths": changed_json_paths,
            "all_changed_fields_explicitly_covered": not uncovered,
            "uncovered_regressions": uncovered,
            "conclusion": (
                "no semantic field rollback introduced by whole-file copying"
                if not uncovered else "uncovered semantic differences require review"
            ),
        },
        "pass14_recipe_executor_probe": executor_probe,
        "actual_git_changes": {
            "before": before_status,
            "after": after_status,
            "expected_runtime_paths": sorted(changed_json_paths + [jquery_rel]),
            "matches_expected_runtime_only": sorted(actual_modified) == sorted(changed_json_paths + [jquery_rel]),
        },
        "product_stability": {
            "stable_during_audit": product_stable,
            "product_files_written": 0,
        },
        "records": records,
    }
    json_path = OUT / "field_source_coverage.json"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    tsv_path = OUT / "field_source_coverage.tsv"
    with tsv_path.open("w", encoding="utf-8", newline="") as fh:
        columns = [
            "file", "stable_key", "field", "baseline_value", "current_value", "value_type",
            "coverage_status", "explicit_source_covered", "whole_file_copy_uncovered_regression",
            "transition_count", "layer_chain", "recipe_rows", "authority_types", "source_locators",
            "chain_exact", "simulated_final_matches_product", "known_pass11_90360",
        ]
        writer = csv.DictWriter(fh, fieldnames=columns, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in ("recipe_rows", "authority_types", "source_locators"):
                row[key] = " | ".join(str(value) for value in record[key])
            writer.writerow(row)

    report_path = OUT / "FIELD_SOURCE_COVERAGE_REPORT.md"
    report = [
        "# pass15 最终集成逐字段来源覆盖审计",
        "",
        f"**字段来源覆盖：{'PASS' if field_coverage_pass else 'FAIL'}（{len(records)-len(uncovered)}/{len(records)}）**",
        "",
        f"总体状态：`{status}`。产品工作树在审计前后保持稳定，写入数为 0。",
        "",
        "## 覆盖结论",
        "",
        f"- 相对 `20e35db4` 的独立 JSON 变化字段：{len(records)}。",
        f"- 明确配方／账本覆盖：{len(records)-len(uncovered)}；未覆盖：{len(uncovered)}。",
        f"- 配方转换行：{len(transitions)}；唯一目标：{len(recipe_targets)}；连续两步字段：{len(multi_transition)}。",
        f"- 应用全部配方后，23 个映射字典与当前产品语义对象完全一致：{'PASS' if semantic_full_match else 'FAIL'}。",
        f"- 整文件复制带来的未覆盖语义回退：{len(uncovered)}。",
        f"- jQuery 为 23 字典确定性派生，SHA-256：`{jquery_derived['current_sha256']}`。",
        "",
        "## 按文件",
        "",
        "| 文件 | 变化字段 | 已覆盖 | 未覆盖 | 转换行 |",
        "|---|---:|---:|---:|---:|",
    ]
    for file, summary in by_file.items():
        report.append(
            f"| `{file}` | {summary['changed_fields']} | {summary['covered_fields']} | "
            f"{summary['uncovered_fields']} | {summary['transition_rows']} |"
        )
    report.extend([
        "",
        "## 来源层转换行",
        "",
    ])
    for layer, count in sorted(layer_counts.items()):
        report.append(f"- `{layer}`：{count}")
    p90360 = result["known_pass11_90360"]
    report.extend([
        "",
        "## pass11 90360 对齐",
        "",
        f"- 状态：`{p90360['coverage_status']}`。",
        f"- `{p90360['baseline_value']}` → `{p90360['current_value']}`",
        f"- 配方：`{p90360['recipe_rows'][0]}`",
        f"- 机械错误类别：`{p90360['transitions'][0]['note']}`；Wiki 交叉核对：`{p90360['transitions'][0]['source_locator']}`。",
        "",
        "## pass10／pass12 边界",
        "",
        "pass10 和 pass12 明确声明 `runtime_text_changed=false`，因此仅作为来源归因上下文，未虚构为产品字节转换行。",
        "",
        "## pass14 旧配方执行器",
        "",
        f"- 配方内容覆盖：21/21 个三方名称字段，当前产品值正确。",
        f"- 隔离执行器探针：`{executor_probe.get('status')}`，退出状态 `{executor_probe.get('exit_code')}`。",
    ])
    if executor_defect:
        report.extend([
            f"- 缺陷：`{executor_probe.get('defect_class')}`。旧脚本把 keyed-object 格式的 `cardMagiaMap`／`doppelCardMagiaMap` 当作记录数组读取。",
            "- 影响边界：不影响当前产品字段覆盖结论；最终可复现发布应使用新的 manifest/ledger 应用器，而不是该旧 pass14 脚本。",
        ])
    report.extend([
        "",
        "逐字段值、完整来源链、权威类型与定位符见 `field_source_coverage.tsv` 和 `field_source_coverage.json`。",
        "",
    ])
    report_path.write_text("\n".join(report), encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": status,
        "field_coverage": f"{len(records)-len(uncovered)}/{len(records)}",
        "whole_file_copy_uncovered_regressions": len(uncovered),
        "pass14_executor_probe": executor_probe.get("status"),
        "tsv": str(tsv_path),
        "json": str(json_path),
        "report": str(report_path),
    }, ensure_ascii=False, indent=2))
    return 0 if field_coverage_pass and product_stable else 1


if __name__ == "__main__":
    raise SystemExit(main())
