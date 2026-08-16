#!/usr/bin/env python3
"""Build a fail-closed, byte-exact v26 worktree allowlist outside the repo.

The builder is intentionally read-only with respect to both the Git worktree and
the external DeepSeek staging tree.  It classifies every porcelain-status path,
verifies the release authority/hash contracts, and writes a deterministic audit
bundle to a directory that did not exist when the command started.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
from typing import Any, Iterable


SCHEMA = "magireco-v26-final-allowlist-audit/v3"
EXPECTED_NAME = "Hiiragi Nemu"
EXPECTED_EMAIL = "128921071+HiiragiNemu@users.noreply.github.com"

DS_TOTAL_BATCHES = 96
DS_TOTAL_ITEMS = 1912
DS_HANDOFF_BATCHES = 74
DS_HANDOFF_REVIEWED_ITEMS = 1472
DS_MANUAL_REQUIRED_ITEMS = 440
DS_REVIEWED_MANUAL_ITEMS = 82
DS_HUMAN_DECISION_REQUIRED = 522

MACHINE_REL = PurePosixPath(
    "magica/i18n_audit/release_v26_authority/machine_translation_review"
)
PROTECTION_REL = PurePosixPath(
    "magica/i18n_audit/release_v26_authority/protected_authority"
)

PRODUCT_RUNTIME = {
    "madomagi/engine_i18n.tsv",
    "magica/js/libs/cardList.json",
    "magica/js/libs/cardMagiaMap.json",
    "magica/js/libs/charaList.json",
    "magica/js/libs/charaMessageList.json",
    "magica/js/libs/doppelCardMagiaMap.json",
    "magica/js/libs/doppelList.json",
    "magica/js/libs/emotionSkillMap.json",
    "magica/js/libs/itemList.json",
    "magica/js/libs/jquery-3.7.1.min.js",
    "magica/js/libs/live2dList.json",
    "magica/js/libs/pieceList.json",
    "magica/js/libs/pieceSkillMap.json",
    "magica/js/libs/sectionList.json",
    "magica/js/libs/shopItemList.json",
    "magica/js/regularEvent/groupBattle/view/BossPageView.js",
    "magica/js/regularEvent/RegularEventTop.js",
    "magica/js/regularEvent/groupBattle/RegularEventGroupBattleTop.js",
    "magica/js/regularEvent/groupBattle/view/UserPageView.js",
    "magica/js/view/user/GlobalMenuView.js",
    "magica/template/formation/FormationQuest.html",
    "magica/js/event/EventArenaRankMatch/parts/CoolTime.js",
    "magica/js/event/EventWitch/parts/ExchangeMemoria.js",
    "magica/js/event/accomplish/EventAccomplishRecovery.js",
    "magica/js/event/arenaranking/view/EventArenaResultView.js",
    "magica/js/event/storyraid/EventStoryRaidTop.js",
    "magica/js/formation/DeckFormation.js",
    "magica/js/formation/DeckFormationUtil.js",
    "magica/js/gacha/GachaProbability.js",
    "magica/js/memoria/MemoriaSetEquip.js",
    "magica/js/quest/scene0/Utility.js",
    "magica/js/quest/secondPartLast/parts/StagePartsView.js",
    "magica/js/regularEvent/accomplish/view/RegularEventAccomplishRecoverView.js",
    "magica/js/view/config/ConfigTopView.js",
    "magica/js/view/gacha/GachaBtnView.js",
    "magica/js/view/memoria/UserMemoriaListView.js",
    "magica/template/arena/ArenaReward.html",
    "magica/template/chara/CharaComposeAttribute/popupItemConfirm.html",
    "magica/template/event/arenaMission/EventArenaMissionResult.html",
    "magica/template/event/arenaMission/EventArenaMissionTop.html",
    "magica/template/event/dailytower/EventDailyTowerTop.html",
    "magica/template/memoria/PieceArchive.html",
    "magica/template/purchase/PurchaseTemps.html",
    "magica/template/regularEvent/groupBattle/RegularEventGroupCommon.html",
}

# Files imported byte-for-byte from the live main branch while this release branch
# was being integrated.  They are eligible only when a second gate proves that
# their current bytes still exactly match the requested main commit.
LIVE_MAIN_IMPORT = {
    ".github/workflows/purge-all-cache.yml",
    "asset_main_cn.json",
    "configures/manifest.json",
    "configures/version_js_new.json",
    "configures/version_scenario_new.json",
    "fixes/prologueBattle3.json",
    "madomagi/asset_main.json",
    "manifests/cn_js_update_ledger.json",
    "manifests/cn_scenario_update_ledger.json",
    "scripts/build_chunk_manifest.py",
    "scripts/sync-dogecloud.py",
    "scripts/sync-pan123-webdav.py",
    "version_js_new.json",
    "version_scenario_new.json",
}

I18N_EFFECTIVE_LAYER = {
    "i18n/frontend-strings.tsv",
    "i18n/generated/conflicts.tsv",
    "i18n/generated/effective.tsv",
    "i18n/generated/input-provenance.tsv",
    "i18n/generated/summary.json",
    "i18n/reviewed-candidates.tsv",
    "i18n/migration-source-summary.json",
    "i18n/uiTextList.json",
}

RELEASE_WORKFLOW = {
    ".gitattributes",
    ".github/workflows/sync-and-upload.yml",
    "README.md",
    "i18n/README.md",
    "i18n/authority-policy.json",
    "scripts/build_manifest.py",
    "scripts/classify_hotupdate_changes.py",
    "scripts/hotupdate_promotion.py",
    "scripts/hotupdate_release_baseline.py",
    "scripts/hotupdate_version.py",
    "scripts/release_asset_transaction.py",
    "scripts/test_build_manifest.py",
    "scripts/test_classify_hotupdate_changes.py",
    "scripts/test_hotupdate_promotion.py",
    "scripts/test_hotupdate_release_baseline.py",
    "scripts/test_hotupdate_version.py",
    "scripts/test_hotupdate_workflow_contract.py",
    "scripts/test_release_asset_transaction.py",
    "tools/verify-v26-product.py",
}

RELEASE_TOOLING = {
    "tools/apply-pass20-suggested-adoptions.py",
    "tools/apply-v26-authority-corrections.py",
    "tools/apply-v26-official-static-corrections.py",
    "tools/assemble-dsv4-v3-terminal.py",
    "tools/build-v26-authority-protection.py",
    "tools/build-v26-final-allowlist.py",
    "tools/build-v26-final-delivery.py",
    "tools/build-v26-machine-review.py",
    "tools/build-v26-package.py",
    "tools/build-pass20-ds-correction-status.py",
    "tools/build-pass20-human-review-xlsx.mjs",
    "tools/build-pass20-human-review-xlsx.py",
    "tools/dsv4-v3-staging-patch.py",
    "tools/i18n-apply.py",
    "tools/i18n-build-effective.py",
    "tools/finalize-pass20-human-review-xlsx.py",
    "tools/import-pass20-human-review-xlsx.py",
    "tools/pass20_final_values_contract.py",
    "tools/prepare-pass20-human-review-xlsx.py",
    "tools/promote-pass20-product-stage.py",
    "tools/rollback-v26-pass18.ps1",
    "tools/run-v26-final-validation.py",
    "tools/test-build-v26-final-allowlist.py",
    "tools/test-build-v26-machine-review.py",
    "tools/test-build-v26-package.py",
    "tools/test-apply-pass20-suggested-adoptions.py",
    "tools/test-build-pass20-ds-correction-status.py",
    "tools/test-build-pass20-human-review-xlsx.py",
    "tools/test-import-pass20-human-review-xlsx.py",
    "tools/test-promote-pass20-product-stage.py",
    "tools/test-stage-pass20-human-review-product.py",
    "tools/test-verify-pass20-human-materialization.py",
    "tools/test-apply-v26-official-static-corrections.py",
    "tools/test-assemble-dsv4-v3-terminal.py",
    "tools/test-dsv4-v3-manual-handoff.py",
    "tools/test-verify-dsv4-terminal-handoff.py",
    "tools/test-validate-dsv4-human-review.py",
    "tools/test-i18n-apply-effective.py",
    "tools/test-i18n-build-effective.py",
    "tools/test-v26-audit-byte-clean.py",
    "tools/test-v26-authority-protection.py",
    "tools/test-v26-final-delivery.py",
    "tools/test-v26-validation-record.py",
    "tools/test-verify-v26-product.py",
    "tools/v26-final-validation-plan.json",
    "tools/v26_authority_protection.py",
    "tools/v26_final_delivery.py",
    "tools/v26_validation_record.py",
    "tools/validate-dsv4-manual-decisions.py",
    "tools/validate-dsv4-human-review.py",
    "tools/stage-pass20-human-review-product.py",
    "tools/verify-pass20-human-materialization.py",
    "tools/verify-pass18-authority.py",
    "tools/verify-runtime-layer.py",
    "tools/verify-v26-authority-protection.py",
    "tools/verify-v26-final-delivery.py",
    "tools/verify-dsv4-terminal-handoff.py",
}

LEGACY_DSV4_TOOLING = {
    "tools/assemble-dsv4-round2-canonical.py",
    "tools/build-deepseek-priority-batches.py",
    "tools/build-deepseek-review-batches.py",
    "tools/canonicalize-dsv4-round2-artifacts.py",
    "tools/probe-deepseek-agent-ultracode.py",
    "tools/run-deepseek-review-workers.py",
    "tools/test-assemble-dsv4-round2-canonical.py",
    "tools/test-canonicalize-dsv4-round2-artifacts.py",
    "tools/test-verify-dsv4-context-followup.py",
    "tools/test-verify-dsv4-cross-role-v2-review.py",
    "tools/test-verify-dsv4-round2-review.py",
    "tools/test-verify-dsv4-v2-atomic-review.py",
    "tools/verify-deepseek-first-batch.py",
    "tools/verify-dsv4-context-followup.py",
    "tools/verify-dsv4-cross-role-v2-review.py",
    "tools/verify-dsv4-round2-review.py",
    "tools/verify-dsv4-v2-atomic-review.py",
}

AUDIT_PROVENANCE_EXACT = {
    "magica/i18n_audit/manual_cn_pass16/FINAL_REPORT.md",
    "magica/i18n_audit/manual_cn_pass16/application_summary.json",
    "magica/i18n_audit/manual_cn_pass16/baseline_manifest.json",
    "magica/i18n_audit/manual_cn_pass16/manifest.json",
    "magica/i18n_audit/manual_cn_pass16/scripts/apply_manual_cn_pass16.py",
    "magica/i18n_audit/manual_cn_pass16/scripts/verify_pass16.py",
    "magica/i18n_audit/manual_cn_pass16/source_evidence/post_runtime_raw_summary.json",
    "magica/i18n_audit/release_v26_authority/README.md",
    "magica/i18n_audit/release_v26_authority/FINAL_AUDIT_GUIDE.md",
    "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx",
    "magica/i18n_audit/release_v26_authority/pass20_ds_correction_status.json",
    "magica/i18n_audit/release_v26_authority/pass20_ds_correction_status.tsv",
    "magica/i18n_audit/release_v26_authority/pass20_human_final_values.tsv",
    "magica/i18n_audit/release_v26_authority/pass20_review_contract.json",
    "magica/i18n_audit/release_v26_authority/pass20_human_review.xlsx",
    "magica/i18n_audit/release_v26_authority/pass21_user_directed_suggested_adoptions.tsv",
    "magica/i18n_audit/release_v26_authority/RUNTIME_LAYER_SHA256SUMS.txt",
    "magica/i18n_audit/release_v26_authority/UI_UNION_VALIDATION_REPORT.md",
    "magica/i18n_audit/release_v26_authority/pass17_targeted_authority_verification.json",
    "magica/i18n_audit/release_v26_authority/runtime_layer_manifest.json",
    "magica/i18n_audit/release_v26_authority/ui_union_validation.json",
    "magica/i18n_audit/wiki_authority_pass15_final/README.md",
    "magica/i18n_audit/wiki_authority_pass15_final/scripts/audit_field_source_coverage.py",
    "magica/i18n_audit/wiki_authority_pass15_final/scripts/verify_final.py",
    "magica/i18n_audit/wiki_authority_pass15_final/sources/field_source_coverage.json",
    "magica/i18n_audit/wiki_authority_pass15_final/verification.generated.json",
    "magica/i18n_audit/wiki_authority_pass9/INTEGRATION_STATUS_20260807.md",
    "magica/research/totentanz-gacha-cn-overlay/PRODUCT_APPLICATION_STATUS_20260807.md",
}

PASS18_FILES = {
    "gzip_binary_attribute_verification.json",
    "pass18_authority_corrections.tsv",
    "pass18_baseline.json",
    "pass18_battle_miss_review.tsv",
    "pass18_engine_official_additions.tsv",
    "pass18_product.patch",
    "pass18_rollback_verification.json",
    "pass18_verification.json",
    "pass19_official_static_corrections.tsv",
    "v26_product_verification.json",
}

UTF_BOMS = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff", b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00")
BINARY_SUFFIXES = {
    ".7z", ".apk", ".bin", ".gif", ".gz", ".ico", ".jpeg", ".jpg",
    ".png", ".so", ".ttf", ".webp", ".zip",
}


class AuditError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def run(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        args,
        cwd=repo,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise AuditError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            + result.stderr.decode("utf-8", errors="replace")
        )
    return result


def git(repo: Path, *args: str, check: bool = True) -> bytes:
    return run(repo, ["git", *args], check=check).stdout


def safe_rel(raw: str) -> str:
    raw = raw.replace("\\", "/")
    p = PurePosixPath(raw)
    if not raw or p.is_absolute() or ".." in p.parts or raw.startswith("/"):
        raise AuditError(f"unsafe relative path: {raw!r}")
    return p.as_posix()


def under(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def parse_porcelain(payload: bytes) -> list[dict[str, str]]:
    chunks = payload.split(b"\0")
    if chunks and chunks[-1] == b"":
        chunks.pop()
    rows: list[dict[str, str]] = []
    i = 0
    while i < len(chunks):
        record = chunks[i]
        if len(record) < 4 or record[2:3] != b" ":
            raise AuditError("unexpected porcelain v1 -z record")
        status = record[:2].decode("ascii", errors="strict")
        path = safe_rel(record[3:].decode("utf-8", errors="surrogateescape"))
        old_path = ""
        if "R" in status or "C" in status:
            i += 1
            if i >= len(chunks):
                raise AuditError("truncated porcelain rename/copy record")
            old_path = safe_rel(chunks[i].decode("utf-8", errors="surrogateescape"))
        rows.append({"status": status, "path": path, "old_path": old_path})
        i += 1
    paths = [x["path"] for x in rows]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        # Git normally sorts this output, but the audit normalizes it explicitly.
        rows.sort(key=lambda x: x["path"])
        paths = [x["path"] for x in rows]
        if len(paths) != len(set(paths)):
            raise AuditError("duplicate current paths in Git status")
    return rows


def status_snapshot(repo: Path) -> tuple[bytes, list[dict[str, str]]]:
    raw = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    return raw, parse_porcelain(raw)


def real_tracked_paths(repo: Path) -> set[str]:
    """Return tracked paths with a non-EOL change versus HEAD in one Git call."""
    raw = git(repo, "diff", "--name-only", "-z", "--ignore-cr-at-eol", "HEAD", "--")
    values = raw.split(b"\0")
    if values and values[-1] == b"":
        values.pop()
    return {safe_rel(x.decode("utf-8", errors="surrogateescape")) for x in values}


def is_binary(path: str, data: bytes) -> bool:
    if PurePosixPath(path).suffix.lower() in BINARY_SUFFIXES or b"\0" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def line_kind(path: str, data: bytes) -> str:
    if is_binary(path, data):
        return "binary"
    has_crlf = b"\r\n" in data
    stripped = data.replace(b"\r\n", b"")
    has_cr = b"\r" in stripped
    has_lf = b"\n" in stripped
    if has_crlf and (has_cr or has_lf):
        return "mixed"
    if has_crlf:
        return "crlf"
    if has_cr:
        return "cr"
    return "lf" if has_lf else "none"


def classify_known(path: str, *, eol_only: bool, extra_repo: set[str]) -> tuple[str, str, str]:
    if eol_only:
        return "exclude", "eol_only_tracked", "tracked bytes differ from HEAD only by line endings"
    if path in extra_repo:
        return "allow", "explicit_extra", "explicit caller allow path"
    if path in PRODUCT_RUNTIME:
        return "allow", "product_runtime", "v26 JS or engine runtime product path"
    if path in LIVE_MAIN_IMPORT:
        return "allow", "live_main_import", "byte-exact live-main import; separately commit-bound"
    if path in I18N_EFFECTIVE_LAYER:
        return "allow", "i18n_effective_layer", "deterministic effective/provenance translation layer"
    if path in RELEASE_WORKFLOW:
        return "allow", "release_workflow", "v26 release workflow, policy, or test path"
    if path in RELEASE_TOOLING:
        return "allow", "release_tooling", "v26 release audit, packaging, validation, or rollback tool"
    prefix = "magica/i18n_audit/release_v26_authority/"
    if path.startswith((MACHINE_REL.as_posix() + "/")):
        return "allow", "audit_machine_review", "stable v26 machine/provenance review set"
    if path.startswith((PROTECTION_REL.as_posix() + "/")):
        return "allow", "audit_authority_protection", "authority protection manifest or verification"
    if path.startswith("magica/i18n_audit/release_v26_authority/dsv4_terminal_handoff/"):
        return "allow", "audit_dsv4_terminal_handoff", "sealed DSV4 manual-handoff evidence and decision tables"
    if path.startswith("magica/i18n_audit/release_v26_authority/manual_queue_analysis/"):
        return "allow", "audit_manual_queue_analysis", "read-only per-item human-queue risk and routing analysis"
    if path.startswith("magica/i18n_audit/release_v26_authority/pass21_suggested_adoption/"):
        return "allow", "audit_pass21_suggested_adoption", "Pass21 adoption patch, verification, and rollback evidence"
    if path.startswith(prefix) and path[len(prefix):] in PASS18_FILES:
        return "allow", "audit_pass18_v26", "Pass18 baseline, patch, verification, or product report"
    if path in AUDIT_PROVENANCE_EXACT:
        return "allow", "audit_provenance", "Pass15/16/17/v26 authority provenance or research status"
    name = PurePosixPath(path).name
    if path.startswith("outputs/"):
        return "exclude", "repo_local_temp_output", "repo-local generated output is not a release source"
    if path.startswith("magica/i18n_audit/release_v26_authority/deepseek_v4_review/"):
        return "exclude", "historical_dsv4_v1_v2", "historical or nonterminal DeepSeek tree"
    if path in LEGACY_DSV4_TOOLING:
        return "exclude", "legacy_dsv4_tooling", "historical DeepSeek orchestration or verifier"
    if path == "magica/i18n_audit/release_v26_authority/v26_full_validation_20260811.log":
        return "exclude", "historical_validation_log", "historical validation stdout log"
    if "/" not in path and name.lower().endswith(".zip"):
        return "exclude", "root_temp_zip", "root comparison or build ZIP"
    if "/" not in path and (
        path.startswith(".") or name.endswith(".log") or name.startswith("package_")
    ):
        return "exclude", "root_temp_log", "root temporary stdout, package, or regeneration record"
    return "exclude", "unclassified_change", "not covered by a closed release rule; explicit review required"


def bulk_hash_objects(repo: Path, paths: list[str], *, filtered: bool) -> dict[str, str]:
    if not paths:
        return {}
    if any("\n" in p or "\r" in p for p in paths):
        raise AuditError("newline in path is unsupported by hash-object --stdin-paths")
    args = ["git", "hash-object", "--stdin-paths"]
    if not filtered:
        args.append("--no-filters")
    result = subprocess.run(
        args,
        cwd=repo,
        input=("\n".join(paths) + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise AuditError(f"bulk hash-object failed: {result.stderr.decode('utf-8', errors='replace')}")
    hashes = result.stdout.decode("ascii").splitlines()
    if len(hashes) != len(paths):
        raise AuditError("bulk hash-object count mismatch")
    return dict(zip(paths, hashes, strict=True))


def bulk_attributes(repo: Path, paths: list[str]) -> dict[str, dict[str, str]]:
    if not paths:
        return {}
    payload = b"\0".join(p.encode("utf-8") for p in paths) + b"\0"
    result = subprocess.run(
        ["git", "check-attr", "-z", "--stdin", "text", "eol"],
        cwd=repo,
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise AuditError(f"bulk check-attr failed: {result.stderr.decode('utf-8', errors='replace')}")
    tokens = result.stdout.split(b"\0")
    if tokens and tokens[-1] == b"":
        tokens.pop()
    if len(tokens) % 3:
        raise AuditError("bulk check-attr returned a partial triplet")
    output = {p: {} for p in paths}
    for i in range(0, len(tokens), 3):
        path = tokens[i].decode("utf-8")
        attr = tokens[i + 1].decode("utf-8")
        value = tokens[i + 2].decode("utf-8")
        output.setdefault(path, {})[attr] = value
    return output


def capture_entries(
    repo: Path,
    rows: list[dict[str, str]],
    extra_repo: set[str],
) -> list[dict[str, Any]]:
    status_paths = {x["path"] for x in rows}
    missing_extra = sorted(extra_repo - status_paths)
    if missing_extra:
        raise AuditError(f"explicit repo allow paths are not in Git status: {missing_extra}")
    real_paths = real_tracked_paths(repo)
    result: list[dict[str, Any]] = []
    for row in rows:
        path = row["path"]
        target = repo / PurePosixPath(path)
        tracked = row["status"] != "??"
        # `git diff --ignore-cr-at-eol` is the deterministic whole-tree EOL
        # classifier.  Untracked files are always content changes.
        eol_only = tracked and path not in real_paths
        decision, category, reason = classify_known(path, eol_only=eol_only, extra_repo=extra_repo)
        exists = target.is_file()
        # Repo-local outputs are excluded before content capture.  In
        # particular, an Excel-owned `~$` lock file may reject byte reads even
        # though it is deliberately outside every release input.
        unread_excluded = category == "repo_local_temp_output"
        data = target.read_bytes() if exists and not unread_excluded else b""
        entry: dict[str, Any] = {
            **row,
            "tracked": tracked,
            "exists": exists,
            "decision": decision,
            "category": category,
            "reason": reason,
            "bytes": len(data) if exists and not unread_excluded else None,
            "sha256": sha256_bytes(data) if exists and not unread_excluded else None,
            "line_endings": line_kind(path, data) if exists and not unread_excluded else (
                "unread-excluded" if exists else "deleted"
            ),
            "bom": bool(exists and not unread_excluded and data.startswith(UTF_BOMS)),
            "eol_only": eol_only,
        }
        entry.update({
            "git_attributes": {},
            "raw_git_blob": None,
            "git_clean_blob": None,
            "git_clean_unchanged": True,
        })
        result.append(entry)
    # Git-clean byte equivalence is a release gate for allowlisted payloads only.
    allowed_existing = [x["path"] for x in result if x["decision"] == "allow" and x["exists"]]
    attrs = bulk_attributes(repo, allowed_existing)
    raw_blobs = bulk_hash_objects(repo, allowed_existing, filtered=False)
    clean_blobs = bulk_hash_objects(repo, allowed_existing, filtered=True)
    for entry in result:
        path = entry["path"]
        if path in raw_blobs:
            entry["git_attributes"] = attrs.get(path, {})
            entry["raw_git_blob"] = raw_blobs[path]
            entry["git_clean_blob"] = clean_blobs[path]
            entry["git_clean_unchanged"] = raw_blobs[path] == clean_blobs[path]
    return result


def parse_sum_file(base: Path, sums: Path, *, boundary: Path) -> dict[str, Any]:
    errors: list[str] = []
    entries: list[dict[str, Any]] = []
    names: list[str] = []
    if not sums.is_file():
        return {"status": "FAIL", "entries": [], "errors": [f"missing {sums}"]}
    raw_bytes = sums.read_bytes()
    if raw_bytes.startswith(UTF_BOMS) or b"\r" in raw_bytes:
        errors.append("SHA256SUMS.txt is not UTF-8 LF without BOM")
    for line_no, line in enumerate(raw_bytes.decode("utf-8", errors="strict").splitlines(), 1):
        if not line:
            continue
        if "  " not in line:
            errors.append(f"line {line_no}: expected two-space separator")
            continue
        expected, raw_name = line.split("  ", 1)
        try:
            # The existing deterministic manifest intentionally binds its
            # generator as ../../../../tools/build-v26-machine-review.py.
            # Traversal is accepted only while the resolved target stays in
            # the explicitly supplied repository boundary.
            name = raw_name.replace("\\", "/")
            if not name or PurePosixPath(name).is_absolute():
                raise AuditError(f"unsafe manifest path: {raw_name!r}")
            target = (base / PurePosixPath(name)).resolve()
            if not under(target, boundary):
                raise AuditError(f"manifest path escapes repository: {raw_name!r}")
        except AuditError as exc:
            errors.append(f"line {line_no}: {exc}")
            continue
        actual = sha256_file(target) if target.is_file() else None
        ok = len(expected) == 64 and all(c in "0123456789abcdef" for c in expected) and actual == expected
        if not ok:
            errors.append(f"line {line_no}: hash mismatch or invalid hash for {name}")
        entries.append({"path": name, "expected_sha256": expected, "actual_sha256": actual, "match": ok})
        names.append(name)
    if len(names) != len(set(names)):
        errors.append("SHA256SUMS entries are not unique")
    return {"status": "PASS" if not errors else "FAIL", "entries": entries, "errors": errors}


def verify_machine_bindings(repo: Path) -> dict[str, Any]:
    machine = repo / MACHINE_REL
    protected = repo / PROTECTION_REL
    sums = parse_sum_file(machine, machine / "SHA256SUMS.txt", boundary=repo)
    errors = list(sums["errors"])
    bindings: list[dict[str, Any]] = []
    manifest_path = protected / "protection_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        baseline = manifest["baseline"]
        for key in ("machine_review_master", "machine_review_summary"):
            rel = safe_rel(str(baseline[key]))
            expected = str(baseline[f"{key}_sha256"])
            target = repo / PurePosixPath(rel)
            actual = sha256_file(target) if target.is_file() else None
            match = actual == expected
            bindings.append({"binding": key, "path": rel, "expected_sha256": expected, "actual_sha256": actual, "match": match})
            if not match:
                errors.append(f"protection manifest {key} binding mismatch")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"protection manifest binding read failed: {exc}")
    return {
        "schema": "magireco-v26-machine-sha-bindings/v1",
        "status": "PASS" if not errors else "FAIL",
        "sha256sums": sums,
        "protection_manifest_bindings": bindings,
        "errors": errors,
    }


def verify_authority(repo: Path, verifier: Path | None) -> dict[str, Any]:
    verifier = (verifier or repo / "tools/verify-v26-authority-protection.py").resolve()
    if not verifier.is_file():
        return {"status": "FAIL", "errors": [f"missing authority verifier: {verifier}"]}
    result = run(repo, [sys.executable, str(verifier), "--root", str(repo), "--json"], check=False)
    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    passed = bool(
        result.returncode == 0
        and isinstance(payload, dict)
        and payload.get("status") == "PASS"
        and payload.get("machine_review_fresh") is True
    )
    return {
        "schema": "magireco-v26-authority-live-gate/v1",
        "status": "PASS" if passed else "FAIL",
        "exit_code": result.returncode,
        "report": payload,
        "stderr": stderr,
        "errors": [] if passed else ["live authority protection verifier did not return a fresh PASS"],
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AuditError(f"expected JSON object: {path}")
    return value


def verify_hash_map(base: Path, mapping: Any, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not isinstance(mapping, dict):
        return rows, [f"{label} is not an object"]
    for raw_name in sorted(mapping):
        try:
            name = safe_rel(raw_name)
            record = mapping[raw_name]
            expected = record["sha256"]
            expected_bytes = record["bytes"]
            target = base / PurePosixPath(name)
            actual = sha256_file(target) if target.is_file() else None
            actual_bytes = target.stat().st_size if target.is_file() else None
            match = actual == expected and actual_bytes == expected_bytes
            rows.append({"path": name, "expected_sha256": expected, "actual_sha256": actual, "expected_bytes": expected_bytes, "actual_bytes": actual_bytes, "match": match})
            if not match:
                errors.append(f"{label} hash/size mismatch: {name}")
        except (AuditError, KeyError, TypeError, OSError) as exc:
            errors.append(f"{label} invalid entry {raw_name!r}: {exc}")
    return rows, errors


def verify_live_main_imports(
    repo: Path,
    entries: list[dict[str, Any]],
    revision: str,
) -> dict[str, Any]:
    """Prove that every allowlisted live-main import is byte-identical.

    The revision is resolved once and recorded as an immutable commit.  A path
    that is not currently in Git status is outside this pre-commit inventory and
    therefore is not silently added to the release payload.
    """
    selected = sorted(
        entry["path"] for entry in entries
        if entry.get("category") == "live_main_import"
    )
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    resolved = ""
    if selected:
        try:
            resolved = git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").decode("ascii").strip()
        except AuditError as exc:
            errors.append(f"cannot resolve live-main revision {revision!r}: {exc}")
        if resolved:
            for path in selected:
                actual_path = repo / PurePosixPath(path)
                try:
                    expected = git(repo, "show", f"{resolved}:{path}")
                except AuditError as exc:
                    errors.append(f"live-main path missing at {resolved}: {path}: {exc}")
                    continue
                actual = actual_path.read_bytes() if actual_path.is_file() else None
                match = actual == expected
                rows.append({
                    "path": path,
                    "expected_sha256": sha256_bytes(expected),
                    "actual_sha256": sha256_bytes(actual) if actual is not None else None,
                    "expected_bytes": len(expected),
                    "actual_bytes": len(actual) if actual is not None else None,
                    "match": match,
                })
                if not match:
                    errors.append(f"live-main byte mismatch: {path}")
    passed = not errors
    return {
        "schema": "magireco-v26-live-main-import-gate/v1",
        "status": "PASS" if passed else "FAIL",
        "requested_revision": revision,
        "resolved_commit": resolved or None,
        "selected_paths": selected,
        "rows": rows,
        "errors": errors,
    }


def _record_matches(path: Path, record: Any) -> bool:
    return bool(
        isinstance(record, dict)
        and path.is_file()
        and record.get("bytes") == path.stat().st_size
        and record.get("sha256") == sha256_file(path)
    )


def _named_record_matches(stage: Path, relative: str, record: Any) -> bool:
    return bool(
        isinstance(record, dict)
        and record.get("path") == relative
        and _record_matches(stage / PurePosixPath(relative), record)
    )


def _bound_pipeline_file(stage: Path, document: dict[str, Any], relative: str) -> bool:
    files = document.get("pipeline_files")
    return isinstance(files, dict) and _record_matches(stage / PurePosixPath(relative), files.get(relative))


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_bytes().splitlines(), 1):
        if not raw:
            raise AuditError(f"blank JSONL line {line_number}: {path}")
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise AuditError(f"JSONL line {line_number} is not an object: {path}")
        rows.append(value)
    return rows


def _tsv_rows(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    if raw.startswith(UTF_BOMS) or b"\r" in raw:
        raise AuditError(f"TSV is not UTF-8 LF without BOM: {path}")
    with io.StringIO(raw.decode("utf-8"), newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def _canonical_json_sha256(value: Any) -> str:
    data = (json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n").encode("utf-8")
    return sha256_bytes(data)


def verify_dsv4(stage: Path) -> dict[str, Any]:
    """Verify either a real 96-batch DS completion or an explicit human handoff.

    A manual handoff is terminal for orchestration only.  It records that DS
    stopped after 74 batches/1,472 items and that 522 decisions remain human
    work; it must never be reported as a completed DS review.
    """
    stage = stage.resolve()
    generated = stage / "generated"
    marker = generated / "checkpoint.json"
    errors: list[str] = []
    observations: dict[str, Any] = {}
    terminal = False
    try:
        marker_before_bytes = marker.read_bytes()
        marker_before = json.loads(marker_before_bytes.decode("utf-8"))
        if not isinstance(marker_before, dict):
            raise AuditError("checkpoint is not an object")
        manifest_path = generated / "review_manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if not isinstance(manifest, dict):
            raise AuditError("review manifest is not an object")
        summary = load_json(generated / "summary.json")
        heartbeat = load_json(generated / "heartbeat.json")
        accepted_rows, accepted_errors = verify_hash_map(
            stage / "accepted", manifest.get("accepted_batches"), "accepted batch"
        )
        aggregate_rows, aggregate_errors = verify_hash_map(
            generated, manifest.get("aggregates"), "aggregate"
        )
        errors.extend(accepted_errors + aggregate_errors)
        bound_accepted = sorted(
            manifest.get("accepted_batches", {})
            if isinstance(manifest.get("accepted_batches"), dict) else []
        )
        actual_accepted = sorted(path.name for path in (stage / "accepted").glob("batch_*.json"))
        accepted_exact = actual_accepted == bound_accepted
        if not accepted_exact:
            errors.append("accepted directory is not exactly bound by review_manifest.json")

        marker_after_bytes = marker.read_bytes()
        stable = marker_before_bytes == marker_after_bytes
        if not stable:
            errors.append("checkpoint changed during snapshot")

        state = marker_before.get("state")
        if state == "complete":
            terminal_mode = "full_ds_review"
        elif state == "closed-manual-handoff":
            terminal_mode = "manual_handoff"
        else:
            terminal_mode = None

        common_checks = {
            "checkpoint_total_batches_96": marker_before.get("total_batches") == DS_TOTAL_BATCHES,
            "checkpoint_total_items_1912": marker_before.get("total_items") == DS_TOTAL_ITEMS,
            "checkpoint_next_batch_null": marker_before.get("next_batch") is None,
            "checkpoint_manifest_binding": marker_before.get("review_manifest_sha256") == sha256_bytes(manifest_bytes),
            "summary_total_batches_96": summary.get("total_batches") == DS_TOTAL_BATCHES,
            "summary_total_items_1912": summary.get("total_items") == DS_TOTAL_ITEMS,
            "source_order_verified": manifest.get("source_order_verified") is True,
            "product_tree_writes_false": manifest.get("product_tree_writes") is False,
            "network_configuration_writes_false": manifest.get("network_configuration_writes") is False,
            "protected_text_changes_zero": (
                manifest.get("protected_text_changes") == 0
                and summary.get("protected_text_changes") == 0
            ),
            "ledger_valid": (
                isinstance(manifest.get("append_only_ledger"), dict)
                and manifest["append_only_ledger"].get("valid") is True
            ),
            "accepted_directory_exact": accepted_exact,
            "snapshot_stable": stable,
        }

        job_path = stage / "job_manifest_v3.json"
        pipeline_path = stage / "pipeline_verification.json"
        job_bytes = job_path.read_bytes()
        pipeline_bytes = pipeline_path.read_bytes()
        job = json.loads(job_bytes.decode("utf-8"))
        pipeline = json.loads(pipeline_bytes.decode("utf-8"))
        if not isinstance(job, dict) or not isinstance(pipeline, dict):
            raise AuditError("top-level seal files must contain JSON objects")
        top_level_checks = {
            "job_binds_pipeline_verification": _record_matches(
                pipeline_path, job.get("pipeline_verification")
            ),
            "job_total_batches_96": job.get("total_batches") == DS_TOTAL_BATCHES,
            "job_total_items_1912": job.get("total_items") == DS_TOTAL_ITEMS,
            "pipeline_total_batches_96": pipeline.get("total_batches") == DS_TOTAL_BATCHES,
            "pipeline_total_items_1912": pipeline.get("total_items") == DS_TOTAL_ITEMS,
            "top_level_terminal_mode_matches": (
                terminal_mode is not None
                and job.get("terminal_mode") == terminal_mode
                and pipeline.get("terminal_mode") == terminal_mode
            ),
            "top_level_terminal_seal_true": (
                isinstance(job.get("terminal_seal"), dict)
                and job["terminal_seal"].get("terminal") is True
                and job["terminal_seal"].get("result") == "PASS"
                and pipeline.get("terminal_seal") is True
                and pipeline.get("result") == "PASS"
            ),
            "top_level_checkpoint_bound": (
                _bound_pipeline_file(stage, job, "generated/checkpoint.json")
                and _bound_pipeline_file(stage, pipeline, "generated/checkpoint.json")
            ),
            "top_level_heartbeat_bound": (
                _bound_pipeline_file(stage, job, "generated/heartbeat.json")
                and _bound_pipeline_file(stage, pipeline, "generated/heartbeat.json")
            ),
            "top_level_review_manifest_bound": (
                _bound_pipeline_file(stage, job, "generated/review_manifest.json")
                and _bound_pipeline_file(stage, pipeline, "generated/review_manifest.json")
            ),
            "top_level_summary_bound": (
                _bound_pipeline_file(stage, job, "generated/summary.json")
                and _bound_pipeline_file(stage, pipeline, "generated/summary.json")
            ),
        }

        mode_checks: dict[str, bool]
        manual_observations: dict[str, Any] = {}
        if terminal_mode == "full_ds_review":
            mode_checks = {
                "checkpoint_state_complete": True,
                "checkpoint_batches_complete": marker_before.get("last_completed_batch") == DS_TOTAL_BATCHES,
                "checkpoint_items_complete": marker_before.get("completed_items") == DS_TOTAL_ITEMS,
                "heartbeat_complete": heartbeat.get("status") == "complete",
                "summary_batches_complete": summary.get("accepted_batches") == DS_TOTAL_BATCHES,
                "summary_items_complete": summary.get("completed_items") == DS_TOTAL_ITEMS,
                "summary_next_batch_null": summary.get("next_batch") is None,
                "manifest_batches_complete": manifest.get("completed_batches") == DS_TOTAL_BATCHES,
                "manifest_items_complete": manifest.get("completed_items") == DS_TOTAL_ITEMS,
                "accepted_manifest_count_96": len(accepted_rows) == DS_TOTAL_BATCHES,
                "accepted_batch_sequence_1_96": actual_accepted == [
                    f"batch_{number:03d}.json" for number in range(1, DS_TOTAL_BATCHES + 1)
                ],
                "job_phase_complete": job.get("ds_phase") == "complete",
                "job_progress_complete": job.get("review_progress") == {
                    "completed_items": DS_TOTAL_ITEMS,
                    "completed_batches": DS_TOTAL_BATCHES,
                    "next_batch": None,
                },
                "pipeline_terminal_gate_complete": (
                    isinstance(pipeline.get("terminal_gate"), dict)
                    and pipeline["terminal_gate"].get("accepted_batches") == DS_TOTAL_BATCHES
                    and pipeline["terminal_gate"].get("accepted_items") == DS_TOTAL_ITEMS
                    and pipeline["terminal_gate"].get("next_batch") is None
                ),
            }
            ds_review_complete = True
        elif terminal_mode == "manual_handoff":
            state_path = generated / "manual_handoff_state.json"
            handoff_manifest_path = generated / "manual_handoff_manifest.json"
            manual_jsonl_path = generated / "manual_required.jsonl"
            manual_tsv_path = generated / "manual_required.tsv"
            manual_review_path = generated / "manual_review.tsv"
            handoff_state = load_json(state_path)
            handoff_manifest_bytes = handoff_manifest_path.read_bytes()
            handoff_manifest = json.loads(handoff_manifest_bytes.decode("utf-8"))
            if not isinstance(handoff_manifest, dict):
                raise AuditError("manual handoff manifest is not an object")
            manual_jsonl = _jsonl_rows(manual_jsonl_path)
            manual_tsv = _tsv_rows(manual_tsv_path)
            reviewed_manual = _tsv_rows(manual_review_path)
            jsonl_ids = [row.get("item_id") for row in manual_jsonl]
            tsv_ids = [row.get("item_id") for row in manual_tsv]
            reviewed_verdicts: dict[str, int] = {}
            for row in reviewed_manual:
                verdict = row.get("parent_verdict", "")
                reviewed_verdicts[verdict] = reviewed_verdicts.get(verdict, 0) + 1
            manual_files = handoff_manifest.get("files")
            if not isinstance(manual_files, dict):
                manual_files = {}
            queue_coverage = handoff_manifest.get("queue_coverage")
            if not isinstance(queue_coverage, dict):
                queue_coverage = {}
            handoff_job = job.get("manual_handoff")
            handoff_pipeline = pipeline.get("manual_handoff")
            review_handoff = manifest.get("manual_handoff")
            mode_checks = {
                "checkpoint_state_manual_handoff": True,
                "checkpoint_batches_74": marker_before.get("last_completed_batch") == DS_HANDOFF_BATCHES,
                "checkpoint_items_1472": marker_before.get("completed_items") == DS_HANDOFF_REVIEWED_ITEMS,
                "checkpoint_retry_disabled": marker_before.get("ds_retry_disabled") is True,
                "checkpoint_manual_440": marker_before.get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS,
                "checkpoint_manual_batches_22": marker_before.get("manual_required_batches") == 22,
                "checkpoint_manual_unreviewed_440": marker_before.get("manual_required_unreviewed") == DS_MANUAL_REQUIRED_ITEMS,
                "checkpoint_reviewed_manual_82": marker_before.get("reviewed_human_decision_required") == DS_REVIEWED_MANUAL_ITEMS,
                "checkpoint_human_522": marker_before.get("human_decision_required") == DS_HUMAN_DECISION_REQUIRED,
                "checkpoint_handoff_manifest_binding": (
                    marker_before.get("manual_handoff_manifest_sha256") == sha256_bytes(handoff_manifest_bytes)
                ),
                "heartbeat_manual_handoff": heartbeat.get("status") == "closed-manual-handoff",
                "heartbeat_retry_disabled": heartbeat.get("ds_retry_disabled") is True,
                "heartbeat_counts": (
                    heartbeat.get("completed_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and heartbeat.get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and heartbeat.get("human_decision_required") == DS_HUMAN_DECISION_REQUIRED
                    and heartbeat.get("next_batch") is None
                ),
                "summary_manual_handoff": (
                    summary.get("ds_phase") == "closed_manual_handoff"
                    and summary.get("ds_retry_disabled") is True
                    and summary.get("accepted_batches") == DS_HANDOFF_BATCHES
                    and summary.get("completed_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and summary.get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and summary.get("manual_review_rows") == DS_REVIEWED_MANUAL_ITEMS
                    and summary.get("next_batch") is None
                ),
                "manifest_manual_handoff": (
                    manifest.get("completed_batches") == DS_HANDOFF_BATCHES
                    and manifest.get("completed_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and isinstance(review_handoff, dict)
                    and review_handoff.get("ds_phase") == "closed_manual_handoff"
                    and review_handoff.get("ds_retry_disabled") is True
                    and review_handoff.get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and review_handoff.get("manual_handoff_manifest_sha256") == sha256_bytes(handoff_manifest_bytes)
                ),
                "accepted_manifest_count_74": len(accepted_rows) == DS_HANDOFF_BATCHES,
                "accepted_batch_sequence_1_74": actual_accepted == [
                    f"batch_{number:03d}.json" for number in range(1, DS_HANDOFF_BATCHES + 1)
                ],
                "manual_state_exact": (
                    handoff_state.get("terminal_mode") == "manual_handoff"
                    and handoff_state.get("ds_phase") == "closed_manual_handoff"
                    and handoff_state.get("ds_retry_disabled") is True
                    and handoff_state.get("accepted_batches") == DS_HANDOFF_BATCHES
                    and handoff_state.get("ds_reviewed_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and handoff_state.get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_state.get("reviewed_human_decision_required") == DS_REVIEWED_MANUAL_ITEMS
                    and handoff_state.get("human_decision_required") == DS_HUMAN_DECISION_REQUIRED
                    and handoff_state.get("manual_handoff_manifest_sha256") == sha256_bytes(handoff_manifest_bytes)
                    and handoff_state.get("ledger_entry_sha256")
                    == manifest.get("append_only_ledger", {}).get("last_entry_sha256")
                    and handoff_state.get("protected_text_changes") == 0
                    and handoff_state.get("product_tree_writes") is False
                    and handoff_state.get("network_configuration_writes") is False
                ),
                "manual_manifest_exact": (
                    handoff_manifest.get("terminal_mode") == "manual_handoff"
                    and handoff_manifest.get("ds_phase") == "closed_manual_handoff"
                    and handoff_manifest.get("ds_retry_disabled") is True
                    and handoff_manifest.get("accepted_batches") == DS_HANDOFF_BATCHES
                    and handoff_manifest.get("ds_reviewed_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and handoff_manifest.get("manual_required_batches") == 22
                    and handoff_manifest.get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_manifest.get("manual_required_unreviewed") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_manifest.get("reviewed_human_decision_required") == DS_REVIEWED_MANUAL_ITEMS
                    and handoff_manifest.get("human_decision_required") == DS_HUMAN_DECISION_REQUIRED
                    and handoff_manifest.get("protected_text_changes") == 0
                    and handoff_manifest.get("product_tree_writes") is False
                    and handoff_manifest.get("network_configuration_writes") is False
                ),
                "manual_jsonl_bound": _record_matches(
                    manual_jsonl_path, manual_files.get("manual_required.jsonl")
                ),
                "manual_tsv_bound": _record_matches(
                    manual_tsv_path, manual_files.get("manual_required.tsv")
                ),
                "manual_rows_440": len(manual_jsonl) == len(manual_tsv) == DS_MANUAL_REQUIRED_ITEMS,
                "manual_ids_unique_equal": (
                    jsonl_ids == tsv_ids
                    and len(set(jsonl_ids)) == DS_MANUAL_REQUIRED_ITEMS
                    and None not in set(jsonl_ids)
                ),
                "manual_queue_coverage_bound": (
                    queue_coverage.get("manual_item_ids_sha256") == _canonical_json_sha256(jsonl_ids)
                    and queue_coverage.get("manual_required_unreviewed") == DS_MANUAL_REQUIRED_ITEMS
                    and queue_coverage.get("accepted_manual_overlap") == 0
                    and queue_coverage.get("inventory_missing") == 0
                    and queue_coverage.get("manual_source_index_range")
                    == {"start": DS_HANDOFF_REVIEWED_ITEMS + 1, "end": DS_TOTAL_ITEMS}
                    and queue_coverage.get("manual_batch_range")
                    == {"start": 75, "end": 96, "count": 22}
                ),
                "manual_queue_range_75_96": (
                    [row.get("source_index") for row in manual_jsonl]
                    == list(range(DS_HANDOFF_REVIEWED_ITEMS + 1, DS_TOTAL_ITEMS + 1))
                    and {row.get("batch_number") for row in manual_jsonl} == set(range(75, 97))
                ),
                "manual_rows_unreviewed_no_product_write": all(
                    row.get("ds_review_status") == "not-reviewed-ds"
                    and row.get("review_status") == "manual-required"
                    and row.get("product_write_allowed") is False
                    and not row.get("human_decision")
                    for row in manual_jsonl
                ),
                "reviewed_manual_82": (
                    len(reviewed_manual) == DS_REVIEWED_MANUAL_ITEMS
                    and reviewed_verdicts == {"correction": 37, "unresolved": 45}
                ),
                "decision_validation_blank_440": (
                    isinstance(handoff_manifest.get("decision_contract"), dict)
                    and isinstance(handoff_manifest["decision_contract"].get("validation"), dict)
                    and handoff_manifest["decision_contract"]["validation"].get("rows") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_manifest["decision_contract"]["validation"].get("blank") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_manifest["decision_contract"]["validation"].get("decided") == 0
                    and handoff_manifest["decision_contract"]["validation"].get("unresolved_apply_allowed") is False
                ),
                "top_level_manual_files_bound": all(
                    _bound_pipeline_file(stage, document, relative)
                    for document in (job, pipeline)
                    for relative in (
                        "generated/manual_handoff_state.json",
                        "generated/manual_handoff_manifest.json",
                        "generated/manual_required.jsonl",
                        "generated/manual_required.tsv",
                    )
                ),
                "job_manual_handoff_exact": (
                    isinstance(handoff_job, dict)
                    and handoff_job.get("accepted_batches") == DS_HANDOFF_BATCHES
                    and handoff_job.get("ds_reviewed_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and handoff_job.get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_job.get("manual_required_unreviewed") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_job.get("reviewed_human_decision_required") == DS_REVIEWED_MANUAL_ITEMS
                    and handoff_job.get("human_decision_required") == DS_HUMAN_DECISION_REQUIRED
                    and handoff_job.get("protected_text_changes") == 0
                    and handoff_job.get("product_tree_writes") is False
                    and handoff_job.get("network_configuration_writes") is False
                    and handoff_job.get("queue_coverage") == queue_coverage
                    and _named_record_matches(stage, "generated/manual_handoff_manifest.json", handoff_job.get("manifest"))
                    and _named_record_matches(stage, "generated/manual_required.jsonl", handoff_job.get("manual_queue"))
                    and _named_record_matches(stage, "generated/manual_required.tsv", handoff_job.get("manual_table"))
                ),
                "pipeline_manual_handoff_exact": (
                    isinstance(handoff_pipeline, dict)
                    and handoff_pipeline.get("accepted_batches") == DS_HANDOFF_BATCHES
                    and handoff_pipeline.get("ds_reviewed_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and handoff_pipeline.get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_pipeline.get("manual_required_unreviewed") == DS_MANUAL_REQUIRED_ITEMS
                    and handoff_pipeline.get("reviewed_human_decision_required") == DS_REVIEWED_MANUAL_ITEMS
                    and handoff_pipeline.get("human_decision_required") == DS_HUMAN_DECISION_REQUIRED
                    and handoff_pipeline.get("protected_text_changes") == 0
                    and handoff_pipeline.get("product_tree_writes") is False
                    and handoff_pipeline.get("network_configuration_writes") is False
                    and handoff_pipeline.get("queue_coverage") == queue_coverage
                    and _named_record_matches(stage, "generated/manual_handoff_manifest.json", handoff_pipeline.get("manifest"))
                    and _named_record_matches(stage, "generated/manual_required.jsonl", handoff_pipeline.get("manual_queue"))
                    and _named_record_matches(stage, "generated/manual_required.tsv", handoff_pipeline.get("manual_table"))
                ),
                "top_level_manual_terminal_seal": (
                    job.get("ds_phase") == "closed_manual_handoff"
                    and job.get("terminal_seal", {}).get("completed_batches") == DS_HANDOFF_BATCHES
                    and job.get("terminal_seal", {}).get("completed_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and job.get("terminal_seal", {}).get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and job.get("terminal_seal", {}).get("manual_required_unreviewed") == DS_MANUAL_REQUIRED_ITEMS
                    and job.get("terminal_seal", {}).get("human_decision_required") == DS_HUMAN_DECISION_REQUIRED
                    and job.get("review_progress") == {
                        "completed_items": DS_HANDOFF_REVIEWED_ITEMS,
                        "completed_batches": DS_HANDOFF_BATCHES,
                        "next_batch": None,
                    }
                    and isinstance(pipeline.get("terminal_gate"), dict)
                    and pipeline["terminal_gate"].get("accepted_batches") == DS_HANDOFF_BATCHES
                    and pipeline["terminal_gate"].get("accepted_items") == DS_HANDOFF_REVIEWED_ITEMS
                    and pipeline["terminal_gate"].get("manual_required_items") == DS_MANUAL_REQUIRED_ITEMS
                    and pipeline["terminal_gate"].get("next_batch") is None
                ),
                "top_level_zero_writes": (
                    job.get("terminal_seal", {}).get("protected_text_changes") == 0
                    and job.get("terminal_seal", {}).get("product_tree_writes") is False
                    and job.get("terminal_seal", {}).get("network_configuration_writes") is False
                    and pipeline.get("protected_text_changes") == 0
                    and pipeline.get("product_tree_writes") is False
                    and pipeline.get("network_configuration_writes") is False
                ),
            }
            manual_observations = {
                "manual_handoff_state": handoff_state,
                "manual_handoff_manifest_sha256": sha256_bytes(handoff_manifest_bytes),
                "manual_required_jsonl": {
                    "rows": len(manual_jsonl), "bytes": manual_jsonl_path.stat().st_size,
                    "sha256": sha256_file(manual_jsonl_path),
                },
                "manual_required_tsv": {
                    "rows": len(manual_tsv), "bytes": manual_tsv_path.stat().st_size,
                    "sha256": sha256_file(manual_tsv_path),
                },
                "reviewed_manual_rows": len(reviewed_manual),
                "human_decision_required": DS_HUMAN_DECISION_REQUIRED,
            }
            ds_review_complete = False
        else:
            mode_checks = {"recognized_terminal_state": False}
            ds_review_complete = False

        terminal_checks = {**common_checks, **top_level_checks, **mode_checks}
        terminal = all(terminal_checks.values()) and not errors
        observations = {
            "terminal_mode": terminal_mode,
            "ds_review_complete": ds_review_complete,
            "manual_handoff_terminal": terminal_mode == "manual_handoff" and terminal,
            "checkpoint": marker_before,
            "summary": summary,
            "manifest_sha256": sha256_bytes(manifest_bytes),
            "top_level_seal_hashes": {
                "job_manifest_v3.json": {
                    "bytes": len(job_bytes), "sha256": sha256_bytes(job_bytes),
                },
                "pipeline_verification.json": {
                    "bytes": len(pipeline_bytes), "sha256": sha256_bytes(pipeline_bytes),
                },
            },
            "accepted_hashes": accepted_rows,
            "aggregate_hashes": aggregate_rows,
            **manual_observations,
            "terminal_checks": terminal_checks,
        }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, AuditError) as exc:
        terminal = False
        errors.append(f"DS terminal marker validation failed: {exc}")
    return {
        "schema": "magireco-v26-dsv4-terminal-gate/v2",
        "stage": str(stage),
        "marker": str(marker),
        "status": "PASS" if terminal else "NONTERMINAL",
        "terminal": terminal,
        **observations,
        "errors": errors,
    }


def external_entries(stage: Path, names: Iterable[str], *, terminal: bool) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for raw in sorted(names):
        try:
            name = safe_rel(raw)
        except AuditError as exc:
            errors.append(str(exc))
            continue
        if name in seen:
            errors.append(f"duplicate explicit DS artifact: {name}")
            continue
        seen.add(name)
        target = (stage / PurePosixPath(name)).resolve()
        if not under(target, stage) or not target.is_file():
            errors.append(f"missing or escaping explicit DS artifact: {name}")
            continue
        data = target.read_bytes()
        kind = line_kind(name, data)
        bom = data.startswith(UTF_BOMS)
        byte_clean = kind in {"lf", "none", "binary"} and not bom
        if not terminal:
            errors.append(f"DS artifact selected before terminal marker: {name}")
        if not byte_clean:
            errors.append(f"DS artifact is not LF/BOM clean: {name}")
        rows.append({
            "path": name,
            "source": "external_dsv4_terminal",
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "line_endings": kind,
            "bom": bom,
            "eligible": terminal and byte_clean,
        })
    return rows, errors


def tsv_bytes(rows: list[dict[str, Any]], fields: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    return stream.getvalue().encode("utf-8")


def aggregate_payload(entries: list[dict[str, Any]]) -> str:
    lines = [f"{x['sha256']}  {x['path']}\n" for x in entries if x.get("sha256")]
    return sha256_bytes("".join(lines).encode("utf-8"))


def repo_identity(repo: Path, expected_name: str, expected_email: str) -> dict[str, Any]:
    def config(key: str) -> str:
        return git(repo, "config", "--local", "--get", key, check=False).decode("utf-8", errors="replace").strip()
    actual_name = config("user.name")
    actual_email = config("user.email")
    checks = {"name": actual_name == expected_name, "email": actual_email == expected_email}
    return {
        "schema": "magireco-v26-git-identity-gate/v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "expected": {"name": expected_name, "email": expected_email},
        "actual": {"name": actual_name, "email": actual_email},
        "checks": checks,
    }


def build(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, bytes]]:
    repo = args.repo.resolve()
    stage = args.ds_stage.resolve()
    output = args.output_dir.resolve()
    if not (repo / ".git").exists() and git(repo, "rev-parse", "--is-inside-work-tree", check=False).strip() != b"true":
        raise AuditError(f"not a Git worktree: {repo}")
    if output.exists():
        raise AuditError(f"output directory already exists: {output}")
    if under(output, repo):
        raise AuditError("output directory must be outside the Git worktree")
    if under(stage, repo):
        raise AuditError("DS staging directory must be outside the Git worktree")

    extra_repo = {safe_rel(x) for x in args.extra_allow}
    if args.extra_allow_file:
        for line in args.extra_allow_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                extra_repo.add(safe_rel(line))

    raw_start, status_rows = status_snapshot(repo)
    entries = capture_entries(repo, status_rows, extra_repo)
    allow = [x for x in entries if x["decision"] == "allow"]
    exclude = [x for x in entries if x["decision"] == "exclude"]
    all_paths = [x["path"] for x in entries]
    allow_paths = [x["path"] for x in allow]
    exclude_paths = [x["path"] for x in exclude]

    machine = verify_machine_bindings(repo)
    authority = verify_authority(repo, args.authority_verifier)
    identity = repo_identity(repo, args.expected_name, args.expected_email)
    live_main = verify_live_main_imports(repo, entries, args.live_main_commit)
    dsv4 = verify_dsv4(stage)
    external, external_errors = external_entries(stage, args.extra_ds_artifact, terminal=dsv4["terminal"])

    raw_end, end_rows = status_snapshot(repo)
    start_hashes = {x["path"]: x.get("sha256") for x in entries}
    end_hashes: dict[str, str | None] = {}
    for row in end_rows:
        p = repo / PurePosixPath(row["path"])
        end_hashes[row["path"]] = (
            None if row["path"].startswith("outputs/")
            else sha256_file(p) if p.is_file()
            else None
        )
    repo_stable = raw_start == raw_end and start_hashes == end_hashes

    partition_checks = {
        "status_sorted_unique": all_paths == sorted(set(all_paths)),
        "allowlist_sorted_unique": allow_paths == sorted(set(allow_paths)),
        "exclude_sorted_unique": exclude_paths == sorted(set(exclude_paths)),
        "partition_no_overlap": not (set(allow_paths) & set(exclude_paths)),
        "partition_exact": set(allow_paths) | set(exclude_paths) == set(all_paths),
    }
    byte_checks = {
        "allow_git_clean_equivalent": all(x.get("git_clean_unchanged") for x in allow),
        "allow_lf_or_binary": all(x.get("line_endings") in {"lf", "none", "binary", "deleted"} for x in allow),
        "allow_no_bom": all(not x.get("bom") for x in allow),
        "external_lf_or_binary": all(x["line_endings"] in {"lf", "none", "binary"} for x in external),
        "external_no_bom": all(not x["bom"] for x in external),
    }
    unclassified = [x["path"] for x in exclude if x["category"] == "unclassified_change"]
    gate_checks = {
        **partition_checks,
        **byte_checks,
        "repo_snapshot_stable": repo_stable,
        "machine_sha_bindings": machine["status"] == "PASS",
        "authority_protection": authority["status"] == "PASS",
        "git_identity": identity["status"] == "PASS",
        "live_main_imports_exact": live_main["status"] == "PASS",
        "dsv4_terminal_marker": dsv4["terminal"],
        "explicit_dsv4_artifacts": not external_errors,
        "unclassified_changes_zero": not unclassified,
    }
    finalizable = all(gate_checks.values())

    branch = git(repo, "branch", "--show-current").decode("utf-8").strip()
    head = git(repo, "rev-parse", "HEAD").decode("ascii").strip()
    tree = git(repo, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    commit_time = git(repo, "show", "-s", "--format=%cI", "HEAD").decode("utf-8").strip()
    counts: dict[str, Any] = {
        "status_entries": len(entries),
        "tracked_status": sum(x["tracked"] for x in entries),
        "untracked_files": sum(not x["tracked"] for x in entries),
        "real_content_changes": sum(not x["eol_only"] for x in entries),
        "eol_only_tracked": sum(x["eol_only"] for x in entries),
        "allowlist_paths": len(allow),
        "exclude_paths": len(exclude),
        "external_dsv4_paths": len(external),
        "unclassified_changes": len(unclassified),
    }
    category_counts: dict[str, int] = {}
    for entry in entries:
        category_counts[entry["category"]] = category_counts.get(entry["category"], 0) + 1
    summary = {
        "schema": SCHEMA,
        "repo": str(repo),
        "branch": branch,
        "baseline_commit": head,
        "baseline_tree": tree,
        "snapshot_basis_utc": commit_time,
        "git_status_porcelain_sha256": sha256_bytes(raw_start),
        "counts": counts,
        "category_counts": dict(sorted(category_counts.items())),
        "allowlist_payload_aggregate_sha256": aggregate_payload(allow),
        "external_dsv4_payload_aggregate_sha256": aggregate_payload(external),
        "finalizable": finalizable,
        "status": "PASS" if finalizable else "BLOCKED",
        "blocking_checks": sorted(k for k, v in gate_checks.items() if not v),
    }
    verification = {
        "schema": "magireco-v26-final-allowlist-verification/v3",
        "status": "PASS" if finalizable else "BLOCKED",
        "finalizable": finalizable,
        "checks": gate_checks,
        "unclassified_paths": unclassified,
        "external_errors": external_errors,
        "repo_status_start_sha256": sha256_bytes(raw_start),
        "repo_status_end_sha256": sha256_bytes(raw_end),
    }

    fields = [
        "path", "old_path", "status", "tracked", "exists", "decision", "category", "reason",
        "bytes", "sha256", "line_endings", "bom", "eol_only", "git_attributes",
        "raw_git_blob", "git_clean_blob", "git_clean_unchanged",
    ]
    snapshot_fields = ["status", "path", "old_path", "decision", "category", "eol_only"]
    files: dict[str, bytes] = {
        "inventory_summary.json": json_bytes(summary),
        "allowlist_manifest.json": json_bytes({"schema": SCHEMA, "summary": summary, "entries": allow}),
        "exclude_manifest.json": json_bytes({"schema": SCHEMA, "summary": summary, "entries": exclude}),
        "allowlist.tsv": tsv_bytes(allow, fields),
        "exclude.tsv": tsv_bytes(exclude, fields),
        "status_snapshot.tsv": tsv_bytes(entries, snapshot_fields),
        "final_allowlist_paths.txt": "".join(f"{p}\n" for p in allow_paths).encode("utf-8"),
        "exclude_paths.txt": "".join(f"{p}\n" for p in exclude_paths).encode("utf-8"),
        "eol_only_tracked_paths.txt": "".join(f"{x['path']}\n" for x in entries if x["eol_only"]).encode("utf-8"),
        "external_dsv4_allowlist.json": json_bytes(external),
        "machine_sha_binding_verification.json": json_bytes(machine),
        "authority_protection_live_verification.json": json_bytes(authority),
        "git_identity_verification.json": json_bytes(identity),
        "live_main_import_verification.json": json_bytes(live_main),
        "dsv4_terminal_verification.json": json_bytes(dsv4),
        "git_clean_byte_equivalence.json": json_bytes({
            "schema": "magireco-v26-git-clean-equivalence/v3",
            "status": "PASS" if all(byte_checks.values()) else "FAIL",
            "checks": byte_checks,
            "entries": [{k: x[k] for k in ("path", "sha256", "line_endings", "bom", "git_attributes", "raw_git_blob", "git_clean_blob", "git_clean_unchanged")} for x in allow],
        }),
        "verification_record.json": json_bytes(verification),
    }
    report_lines = [
        "# v26 final allowlist audit",
        "",
        f"- status: `{summary['status']}`",
        f"- finalizable: `{str(finalizable).lower()}`",
        f"- HEAD: `{head}`",
        f"- status paths: `{len(entries)}`",
        f"- allow / exclude: `{len(allow)}` / `{len(exclude)}`",
        f"- real content / EOL-only: `{counts['real_content_changes']}` / `{counts['eol_only_tracked']}`",
        f"- external DSV4 selected: `{len(external)}`",
        "",
        "## Blocking checks",
        "",
    ]
    blocking = summary["blocking_checks"]
    report_lines += ([f"- `{x}`" for x in blocking] if blocking else ["- none"])
    if unclassified:
        report_lines += ["", "## Unclassified paths", ""] + [f"- `{x}`" for x in unclassified]
    files["risk_and_missing_report.md"] = ("\n".join(report_lines) + "\n").encode("utf-8")

    # SHA256SUMS intentionally excludes itself and is the final deterministic binding.
    sums = "".join(f"{sha256_bytes(files[name])}  {name}\n" for name in sorted(files))
    files["SHA256SUMS.txt"] = sums.encode("utf-8")
    return summary, files


def materialize(output: Path, files: dict[str, bytes]) -> None:
    temp = output.with_name(f".{output.name}.tmp-{os.getpid()}")
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True)
    try:
        for name in sorted(files):
            write_bytes(temp / name, files[name])
        temp.replace(output)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ds-stage", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--extra-allow", action="append", default=[], metavar="REPO_PATH")
    parser.add_argument("--extra-allow-file", type=Path)
    parser.add_argument("--extra-ds-artifact", action="append", default=[], metavar="STAGE_REL_PATH")
    parser.add_argument("--authority-verifier", type=Path)
    parser.add_argument(
        "--live-main-commit",
        default="origin/main",
        help="revision whose bytes must match every live-main-import path",
    )
    parser.add_argument("--expected-name", default=EXPECTED_NAME)
    parser.add_argument("--expected-email", default=EXPECTED_EMAIL)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary, files = build(args)
        materialize(args.output_dir.resolve(), files)
    except (AuditError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["finalizable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
