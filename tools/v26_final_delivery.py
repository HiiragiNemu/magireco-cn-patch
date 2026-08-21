#!/usr/bin/env python3
"""Fail-closed v26 delivery bundle generation and verification.

The bundle is deliberately written outside the repository.  Its four roles are:

* the modified ``cn_js_update.zip`` product artifact;
* a complete ``git diff --binary`` patch;
* a transactional PowerShell rollback script; and
* a machine-readable verification record.

The per-path before/after object and SHA-256 manifest is a fifth, supporting
file.  It is intentionally outside the patch, preventing artifact self-reference.

No product file is edited by this module.  A worktree source is first materialized
as a Git tree through an isolated temporary index, so the caller's real index is
never touched.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
from typing import Any, Sequence
import zipfile
import zlib


DEFAULT_BASELINE = "d5e8f75d93f6760a588e592c22a3754d19370c68"
EXPECTED_AUTHOR_NAME = "Hiiragi Nemu"
EXPECTED_AUTHOR_EMAIL = "128921071+HiiragiNemu@users.noreply.github.com"
ARTIFACT_NAME = "cn_js_update.zip"
PATCH_NAME = "v26_final_product.patch"
MANIFEST_NAME = "v26_delivery_manifest.json"
ROLLBACK_NAME = "rollback-v26-final.ps1"
VERIFICATION_NAME = "v26_delivery_verification.json"

MANIFEST_SCHEMA = "magireco-cn-v26-delivery-manifest/v1"
VERIFICATION_SCHEMA = "magireco-cn-v26-delivery-verification/v1"
ROLLBACK_REPORT_SCHEMA = "magireco-cn-v26-rollback-execution/v1"

ENGINE_MEMBER = "madomagi/engine_i18n.tsv"
REPAIR_PREFIX = "madomagi/resource/image_native/"
REPAIR_MANIFEST = "madomagi/repair_manifest.json"
SCENARIO_PREFIX = "madomagi/resource/scenario/"
RESEARCH_PREFIX = "magica/research/"
AUDIT_PREFIX = "magica/i18n_audit/"
EXPECTED_DOS_TIME = (1980, 1, 1, 0, 0, 0)
EXPECTED_UNIX_MODE = stat.S_IFREG | 0o644
DEFAULT_ARTIFACT_CONTRACT: dict[str, int | None] = {
    # Product membership is already bound byte-for-byte to the final Git tree.
    # Derive the variable product counts from that selected archive instead of
    # freezing a number that changes whenever a reviewed HTML/CSS file is added.
    "file_entries": None,
    "magica_entries": None,
    "engine_entries": 1,
    "repair_manifest_entries": 1,
    "repair_entries": None,
    "scenario_entries": 0,
    "audit_research_entries": 0,
}
DYNAMIC_ARTIFACT_CONTRACT_FIELDS = frozenset({
    "file_entries", "magica_entries", "repair_entries"
})

OID_RE = re.compile(r"^[0-9a-f]{40,64}$")


class DeliveryError(RuntimeError):
    """A fail-closed delivery contract violation."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def normalize_artifact_contract(
    value: dict[str, Any] | None,
    *,
    actual: dict[str, Any] | None = None,
) -> dict[str, int]:
    contract = dict(DEFAULT_ARTIFACT_CONTRACT if value is None else value)
    if "repair_entries" not in contract:
        contract["repair_entries"] = (
            actual["repair_entries"] if actual is not None else 0
        )
    expected_keys = set(DEFAULT_ARTIFACT_CONTRACT)
    if set(contract) != expected_keys:
        raise DeliveryError(
            f"artifact contract keys mismatch: expected={sorted(expected_keys)} "
            f"actual={sorted(contract)}"
        )
    for key, count in list(contract.items()):
        if count is None:
            if key not in DYNAMIC_ARTIFACT_CONTRACT_FIELDS:
                raise DeliveryError(f"artifact contract {key} cannot be dynamic")
            if actual is None or type(actual.get(key)) is not int:
                raise DeliveryError(
                    f"artifact contract {key} requires a discovered archive inventory"
                )
            count = actual[key]
            contract[key] = count
        if type(count) is not int or count < 0:
            raise DeliveryError(f"artifact contract {key} must be a non-negative integer")
    if contract["file_entries"] != (
        contract["magica_entries"]
        + contract["engine_entries"]
        + contract["repair_manifest_entries"]
        + contract["repair_entries"]
        + contract["scenario_entries"]
    ):
        raise DeliveryError(
            "artifact contract file_entries must equal magica + engine + repair manifest + repair + scenario"
        )
    return contract


def _normalize_zip_member(name: str) -> str:
    if not name or "\\" in name or "\x00" in name:
        raise DeliveryError(f"unsafe ZIP member path: {name!r}")
    member = PurePosixPath(name)
    if (
        member.is_absolute()
        or any(part in {"", ".", ".."} for part in member.parts)
        or member.as_posix() != name
    ):
        raise DeliveryError(f"unsafe ZIP member path: {name!r}")
    return name


def inspect_product_artifact(
    path: Path, contract: dict[str, Any] | None = None
) -> tuple[bytes, dict[str, Any]]:
    """Read once, reopen in memory, and enforce the complete product ZIP contract."""
    path = path.resolve()
    if not path.is_file() or path.is_symlink():
        raise DeliveryError(f"--artifact must be an existing regular ZIP file: {path}")
    data = path.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
            infos = archive.infolist()
            names = [_normalize_zip_member(info.filename) for info in infos]
            duplicate_paths = len(names) - len(set(names))
            folded: dict[str, str] = {}
            casefold_collisions: list[list[str]] = []
            for name in names:
                previous = folded.setdefault(name.casefold(), name)
                if previous != name:
                    casefold_collisions.append([previous, name])
            directory_entries = sum(info.is_dir() for info in infos)
            magica_entries = sum(name.startswith("magica/") for name in names)
            engine_entries = names.count(ENGINE_MEMBER)
            repair_manifest_entries = names.count(REPAIR_MANIFEST)
            repair_entries = sum(name.startswith(REPAIR_PREFIX) for name in names)
            scenario_entries = sum(name.startswith(SCENARIO_PREFIX) for name in names)
            research_entries = sum(name.startswith(RESEARCH_PREFIX) for name in names)
            audit_entries = sum(name.startswith(AUDIT_PREFIX) for name in names)
            unsupported_root_entries = sum(
                not (
                    name.startswith("magica/")
                    or name == ENGINE_MEMBER
                    or name == REPAIR_MANIFEST
                    or name.startswith(REPAIR_PREFIX)
                )
                for name in names
            )
            metadata_errors: list[str] = []
            for info in infos:
                if info.date_time != EXPECTED_DOS_TIME:
                    metadata_errors.append(f"timestamp:{info.filename}")
                if info.create_system != 3 or (info.external_attr >> 16) != EXPECTED_UNIX_MODE:
                    metadata_errors.append(f"mode:{info.filename}")
                if info.compress_type != zipfile.ZIP_DEFLATED:
                    metadata_errors.append(f"compression:{info.filename}")
                if info.comment or info.extra:
                    metadata_errors.append(f"entry-metadata:{info.filename}")
            bad_crc = archive.testzip()
            engine_sha256 = None
            if engine_entries == 1:
                engine_sha256 = sha256_bytes(archive.read(ENGINE_MEMBER))
            actual = {
                "file_entries": len(infos),
                "magica_entries": magica_entries,
                "engine_member": ENGINE_MEMBER,
                "engine_entries": engine_entries,
                "repair_manifest_member": REPAIR_MANIFEST,
                "repair_manifest_entries": repair_manifest_entries,
                "repair_entries": repair_entries,
                "engine_sha256": engine_sha256,
                "scenario_entries": scenario_entries,
                "research_entries": research_entries,
                "audit_entries": audit_entries,
                "audit_research_entries": research_entries + audit_entries,
                "duplicate_paths": duplicate_paths,
                "casefold_collisions": len(casefold_collisions),
                "directory_entries": directory_entries,
                "unsupported_root_entries": unsupported_root_entries,
                "crc_errors": 0 if bad_crc is None else 1,
                "entry_order_sorted": names == sorted(names),
                "archive_comment_bytes": len(archive.comment),
                "deterministic_metadata_errors": len(metadata_errors),
            }
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        if isinstance(exc, DeliveryError):
            raise
        raise DeliveryError(f"invalid product ZIP {path}: {exc}") from exc

    contract = normalize_artifact_contract(contract, actual=actual)

    mismatches = {
        key: {"expected": expected, "actual": actual[key]}
        for key, expected in contract.items()
        if actual[key] != expected
    }
    hard_failures = {
        "duplicate_paths": actual["duplicate_paths"],
        "casefold_collisions": actual["casefold_collisions"],
        "directory_entries": actual["directory_entries"],
        "unsupported_root_entries": actual["unsupported_root_entries"],
        "crc_errors": actual["crc_errors"],
        "entry_order_sorted": actual["entry_order_sorted"],
        "archive_comment_bytes": actual["archive_comment_bytes"],
        "deterministic_metadata_errors": actual["deterministic_metadata_errors"],
    }
    hard_failed = (
        hard_failures["duplicate_paths"] != 0
        or hard_failures["casefold_collisions"] != 0
        or hard_failures["directory_entries"] != 0
        or hard_failures["unsupported_root_entries"] != 0
        or hard_failures["crc_errors"] != 0
        or hard_failures["entry_order_sorted"] is not True
        or hard_failures["archive_comment_bytes"] != 0
        or hard_failures["deterministic_metadata_errors"] != 0
    )
    if mismatches or hard_failed:
        raise DeliveryError(
            "product ZIP contract mismatch: "
            + json.dumps(
                {"count_mismatches": mismatches, "hard_failures": hard_failures},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    report = {
        "schema": "magireco-cn-v26-delivery-artifact-contract/v1",
        "status": "PASS",
        "file": ARTIFACT_NAME,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "expected": contract,
        "actual": actual,
    }
    return data, report


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_git(
    repo: Path,
    arguments: Sequence[str],
    *,
    input_bytes: bytes | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    command = ["git", "-C", str(repo), *arguments]
    merged_env = os.environ.copy()
    merged_env.update({"LC_ALL": "C", "LANG": "C", "GIT_OPTIONAL_LOCKS": "0"})
    if env:
        merged_env.update(env)
    result = subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=merged_env,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise DeliveryError(
            f"git command failed ({result.returncode}): "
            f"{' '.join(arguments)}\n{stderr}"
        )
    return result


def repository_root(path: Path) -> Path:
    requested = path.resolve()
    result = run_git(requested, ["rev-parse", "--show-toplevel"])
    root = Path(result.stdout.decode("utf-8").strip()).resolve()
    if root != requested:
        raise DeliveryError(f"--repo must be the repository root: {root}")
    return root


def resolve_commit(repo: Path, revision: str) -> str:
    result = run_git(repo, ["rev-parse", "--verify", f"{revision}^{{commit}}"])
    value = result.stdout.decode("ascii").strip()
    if not OID_RE.fullmatch(value):
        raise DeliveryError(f"invalid commit object id for {revision!r}: {value!r}")
    return value


def resolve_tree(repo: Path, revision: str) -> str:
    result = run_git(repo, ["rev-parse", "--verify", f"{revision}^{{tree}}"])
    value = result.stdout.decode("ascii").strip()
    if not OID_RE.fullmatch(value):
        raise DeliveryError(f"invalid tree object id for {revision!r}: {value!r}")
    return value


def verify_submission_identity(repo: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, expected in (
        ("user.name", EXPECTED_AUTHOR_NAME),
        ("user.email", EXPECTED_AUTHOR_EMAIL),
    ):
        result = run_git(repo, ["config", "--local", "--get", key], check=False)
        actual = result.stdout.decode("utf-8", errors="replace").strip()
        if result.returncode != 0 or actual != expected:
            raise DeliveryError(
                f"repo-local {key} must be {expected!r}, found {actual!r}"
            )
        values[key] = actual
    return values


def _inside(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_output_directory(repo: Path, output: Path) -> Path:
    resolved = output.resolve()
    if _inside(resolved, repo):
        raise DeliveryError("delivery output directory must be outside the repository")
    if resolved.exists():
        raise DeliveryError(
            f"output directory must not already exist; refusing to overwrite: {resolved}"
        )
    return resolved


def normalize_repo_path(raw: str) -> str:
    if not isinstance(raw, str):
        raise DeliveryError("allowlist entries must be strings")
    if raw != raw.strip() or not raw:
        raise DeliveryError(f"allowlist path has surrounding whitespace or is empty: {raw!r}")
    if "\\" in raw or "\x00" in raw or "\n" in raw or "\r" in raw or "\t" in raw:
        raise DeliveryError(f"allowlist path is not canonical POSIX syntax: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise DeliveryError(f"unsafe allowlist path: {raw!r}")
    if path.parts[0].casefold() == ".git":
        raise DeliveryError(f".git paths are forbidden: {raw!r}")
    return path.as_posix()


def load_allowlist(path: Path) -> tuple[list[str], str]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DeliveryError(f"allowlist is not UTF-8: {path}") from exc
    if path.suffix.casefold() == ".json":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DeliveryError(f"invalid allowlist JSON: {exc}") from exc
        if isinstance(parsed, dict):
            parsed = parsed.get("paths")
        if not isinstance(parsed, list):
            raise DeliveryError("JSON allowlist must be an array or an object with a paths array")
        raw_paths = parsed
    else:
        raw_paths = [
            line for line in text.splitlines() if line and not line.startswith("#")
        ]
    paths = [normalize_repo_path(item) for item in raw_paths]
    if not paths:
        raise DeliveryError("allowlist is empty")
    if len(paths) != len(set(paths)):
        duplicates = sorted({item for item in paths if paths.count(item) > 1})
        raise DeliveryError(f"duplicate allowlist paths: {duplicates}")
    if paths != sorted(paths):
        raise DeliveryError("allowlist must be sorted by Unicode code point")
    return paths, sha256_bytes(raw)


def create_tree_from_worktree(
    repo: Path, baseline_tree: str, allowlist: Sequence[str]
) -> str:
    with tempfile.TemporaryDirectory(prefix="v26-delivery-index-") as folder:
        index = Path(folder) / "index"
        env = {"GIT_INDEX_FILE": str(index)}
        run_git(repo, ["read-tree", baseline_tree], env=env)
        for rel in allowlist:
            absolute = repo / Path(*PurePosixPath(rel).parts)
            if absolute.exists() and absolute.is_dir() and not absolute.is_symlink():
                raise DeliveryError(f"allowlist entries must name files, not directories: {rel}")
            run_git(repo, ["add", "-A", "--force", "--", rel], env=env)
        result = run_git(repo, ["write-tree"], env=env)
        value = result.stdout.decode("ascii").strip()
        if not OID_RE.fullmatch(value):
            raise DeliveryError(f"git write-tree returned invalid object id: {value!r}")
        return value


def changed_paths(repo: Path, before_tree: str, after_tree: str) -> list[str]:
    result = run_git(
        repo,
        [
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            "--no-ext-diff",
            before_tree,
            after_tree,
        ],
    )
    values = result.stdout.split(b"\x00")
    if values and values[-1] == b"":
        values.pop()
    try:
        paths = [item.decode("utf-8") for item in values]
    except UnicodeDecodeError as exc:
        raise DeliveryError("Git returned a non-UTF-8 path") from exc
    return sorted(normalize_repo_path(item) for item in paths)


def tree_entry(repo: Path, tree: str, rel: str) -> dict[str, Any] | None:
    result = run_git(repo, ["ls-tree", "-z", tree, "--", rel])
    records = [item for item in result.stdout.split(b"\x00") if item]
    if not records:
        return None
    matches: list[tuple[str, str, str, str]] = []
    for record in records:
        header, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise DeliveryError(f"malformed ls-tree output for {rel}")
        try:
            mode, object_type, oid = header.decode("ascii").split(" ")
            actual_path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError) as exc:
            raise DeliveryError(f"malformed ls-tree output for {rel}") from exc
        if actual_path == rel:
            matches.append((mode, object_type, oid, actual_path))
    if len(matches) != 1:
        raise DeliveryError(f"tree lookup was not exact for {rel}: {len(matches)} matches")
    mode, object_type, oid, _ = matches[0]
    if object_type != "blob":
        raise DeliveryError(f"unsupported non-blob path {rel}: {object_type}")
    data = run_git(repo, ["cat-file", "blob", oid]).stdout
    return {
        "exists": True,
        "mode": mode,
        "git_oid": oid,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def _product_tree_blobs(repo: Path, tree: str) -> dict[str, dict[str, Any]]:
    """Return every final-tree blob that must be shipped by cn_js_update.zip."""
    result = run_git(
        repo,
        [
            "ls-tree", "-r", "-z", tree, "--",
            "magica", ENGINE_MEMBER, REPAIR_MANIFEST, REPAIR_PREFIX.rstrip("/"),
        ],
    )
    metadata: list[tuple[str, str, str]] = []
    for record in (item for item in result.stdout.split(b"\x00") if item):
        header, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise DeliveryError("malformed recursive ls-tree output for product tree")
        try:
            mode, object_type, oid = header.decode("ascii").split(" ")
            rel = normalize_repo_path(raw_path.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise DeliveryError("malformed recursive ls-tree product record") from exc
        if not (
            rel == ENGINE_MEMBER
            or rel == REPAIR_MANIFEST
            or rel.startswith("magica/")
            or rel.startswith(REPAIR_PREFIX)
        ):
            continue
        if rel.startswith(RESEARCH_PREFIX) or rel.startswith(AUDIT_PREFIX):
            continue
        if object_type != "blob" or mode != "100644":
            raise DeliveryError(
                f"product tree path must be a regular 100644 blob: {rel} "
                f"({mode} {object_type})"
            )
        if not OID_RE.fullmatch(oid):
            raise DeliveryError(f"invalid product tree blob id for {rel}: {oid!r}")
        metadata.append((rel, mode, oid))

    paths = [item[0] for item in metadata]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise DeliveryError("product tree paths are not unique and sorted")
    if ENGINE_MEMBER not in paths:
        raise DeliveryError(f"final tree is missing required product path: {ENGINE_MEMBER}")

    requested = b"".join(oid.encode("ascii") + b"\n" for _, _, oid in metadata)
    batch = io.BytesIO(run_git(repo, ["cat-file", "--batch"], input_bytes=requested).stdout)
    blobs: dict[str, dict[str, Any]] = {}
    for rel, mode, expected_oid in metadata:
        header = batch.readline().rstrip(b"\n")
        fields = header.split(b" ")
        if len(fields) != 3:
            raise DeliveryError(f"malformed cat-file header for product path {rel}")
        try:
            actual_oid = fields[0].decode("ascii")
            object_type = fields[1].decode("ascii")
            size = int(fields[2].decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise DeliveryError(f"malformed cat-file header for product path {rel}") from exc
        data = batch.read(size)
        terminator = batch.read(1)
        if (
            actual_oid != expected_oid
            or object_type != "blob"
            or len(data) != size
            or terminator != b"\n"
        ):
            raise DeliveryError(f"cat-file blob mismatch for product path {rel}")
        blobs[rel] = {
            "mode": mode,
            "git_oid": expected_oid,
            "bytes": size,
            "sha256": sha256_bytes(data),
            "data": data,
        }
    if batch.read(1) != b"":
        raise DeliveryError("unexpected trailing cat-file output for product tree")
    return blobs


def _validate_repair_manifest_against_blobs(
    repo: Path,
    tree: str,
    blobs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Bind the final-tree native repair set to its deterministic manifest."""
    manifest_entry = tree_entry(repo, tree, REPAIR_MANIFEST)
    if manifest_entry is None:
        raise DeliveryError(f"final tree is missing required repair manifest: {REPAIR_MANIFEST}")
    if manifest_entry.get("mode") != "100644":
        raise DeliveryError(
            f"repair manifest must be a regular 100644 blob: {REPAIR_MANIFEST}"
        )
    manifest_bytes = run_git(
        repo, ["cat-file", "blob", str(manifest_entry["git_oid"])]
    ).stdout
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(f"repair manifest is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise DeliveryError("repair manifest root must be an object")
    if manifest.get("schema") != "magireco-cn-madomagi-repair/v1":
        raise DeliveryError("repair manifest schema mismatch")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise DeliveryError("repair manifest entries must be a non-empty array")

    declared: dict[str, int] = {}
    ordered_paths: list[str] = []
    for index, row in enumerate(entries):
        if not isinstance(row, dict):
            raise DeliveryError(f"repair manifest entry {index} is not an object")
        raw_path = row.get("path")
        byte_count = row.get("bytes")
        if not isinstance(raw_path, str):
            raise DeliveryError(f"repair manifest entry {index} has no path")
        path = normalize_repo_path(raw_path)
        if not path.startswith(REPAIR_PREFIX):
            raise DeliveryError(f"repair manifest path escapes repair prefix: {path}")
        if path in declared:
            raise DeliveryError(f"repair manifest contains duplicate path: {path}")
        if type(byte_count) is not int or byte_count < 0:
            raise DeliveryError(f"repair manifest byte count is invalid: {path}")
        ordered_paths.append(path)
        declared[path] = byte_count
    if ordered_paths != sorted(ordered_paths):
        raise DeliveryError("repair manifest paths are not sorted")

    if type(manifest.get("file_count")) is not int or manifest["file_count"] != len(declared):
        raise DeliveryError("repair manifest file_count mismatch")
    declared_total = sum(declared.values())
    if type(manifest.get("total_bytes")) is not int or manifest["total_bytes"] != declared_total:
        raise DeliveryError("repair manifest total_bytes mismatch")

    repair_blobs = {
        path: record for path, record in blobs.items() if path.startswith(REPAIR_PREFIX)
    }
    declared_paths = set(declared)
    tree_paths = set(repair_blobs)
    if declared_paths != tree_paths:
        raise DeliveryError(
            "repair manifest path set mismatch: "
            + json.dumps(
                {
                    "missing_from_tree": sorted(declared_paths - tree_paths),
                    "undeclared_in_tree": sorted(tree_paths - declared_paths),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    byte_mismatches = sorted(
        path for path in declared if repair_blobs[path]["bytes"] != declared[path]
    )
    if byte_mismatches:
        raise DeliveryError(
            f"repair manifest byte count differs from final tree: {byte_mismatches[:10]}"
        )

    return {
        "status": "PASS",
        "path": REPAIR_MANIFEST,
        "schema": manifest["schema"],
        "git_oid": manifest_entry["git_oid"],
        "sha256": manifest_entry["sha256"],
        "declared_entries": len(declared),
        "tree_entries": len(repair_blobs),
        "total_bytes": declared_total,
        "path_set_exact": True,
        "byte_counts_exact": True,
    }


def verify_product_artifact_against_tree(
    repo: Path, final_tree: str, artifact_bytes: bytes
) -> dict[str, Any]:
    """Bind every ZIP payload byte to the corresponding final Git-tree blob."""
    blobs = _product_tree_blobs(repo, final_tree)
    repair_manifest_binding = _validate_repair_manifest_against_blobs(
        repo, final_tree, blobs
    )
    try:
        with zipfile.ZipFile(io.BytesIO(artifact_bytes), "r") as archive:
            archive_paths = sorted(
                _normalize_zip_member(info.filename) for info in archive.infolist()
            )
            tree_paths = sorted(blobs)
            missing = sorted(set(tree_paths) - set(archive_paths))
            extra = sorted(set(archive_paths) - set(tree_paths))
            mismatches: list[str] = []
            if not missing and not extra:
                for rel in tree_paths:
                    if archive.read(rel) != blobs[rel]["data"]:
                        mismatches.append(rel)
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        if isinstance(exc, DeliveryError):
            raise
        raise DeliveryError(f"cannot compare product ZIP to final tree: {exc}") from exc

    if missing or extra or mismatches:
        raise DeliveryError(
            "product ZIP does not match final tree: "
            + json.dumps(
                {
                    "missing_paths": missing,
                    "extra_paths": extra,
                    "byte_mismatches": mismatches,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    inventory = [
        {
            "path": rel,
            "mode": blobs[rel]["mode"],
            "git_oid": blobs[rel]["git_oid"],
            "bytes": blobs[rel]["bytes"],
            "sha256": blobs[rel]["sha256"],
        }
        for rel in sorted(blobs)
    ]
    return {
        "schema": "magireco-cn-v26-artifact-final-tree-binding/v1",
        "status": "PASS",
        "final_tree": final_tree,
        "tree_entry_count": len(inventory),
        "archive_entry_count": len(archive_paths),
        "matched_entry_count": len(inventory),
        "missing_path_count": 0,
        "extra_path_count": 0,
        "byte_mismatch_count": 0,
        "inventory_sha256": sha256_bytes(canonical_json_bytes(inventory)),
        "repair_manifest_binding": repair_manifest_binding,
    }


def missing_entry() -> dict[str, Any]:
    return {
        "exists": False,
        "mode": None,
        "git_oid": None,
        "bytes": None,
        "sha256": None,
    }


def tree_path_entries(
    repo: Path, tree: str, paths: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Read all requested blob metadata with one tree walk and one batch read."""
    wanted = set(paths)
    if len(wanted) != len(paths):
        raise DeliveryError("tree entry request contains duplicate paths")

    result = run_git(repo, ["ls-tree", "-r", "-z", tree])
    metadata: dict[str, tuple[str, str]] = {}
    for record in (item for item in result.stdout.split(b"\x00") if item):
        header, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise DeliveryError("malformed recursive ls-tree output")
        try:
            mode, object_type, oid = header.decode("ascii").split(" ")
            rel = normalize_repo_path(raw_path.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise DeliveryError("malformed recursive ls-tree record") from exc
        if rel not in wanted:
            continue
        if rel in metadata:
            raise DeliveryError(f"tree lookup was not exact for {rel}: duplicate record")
        if object_type != "blob":
            raise DeliveryError(f"unsupported non-blob path {rel}: {object_type}")
        if not OID_RE.fullmatch(oid):
            raise DeliveryError(f"invalid tree blob id for {rel}: {oid!r}")
        metadata[rel] = (mode, oid)

    ordered = [(rel, *metadata[rel]) for rel in sorted(metadata)]
    requested = b"".join(oid.encode("ascii") + b"\n" for _, _, oid in ordered)
    batch = io.BytesIO(
        run_git(repo, ["cat-file", "--batch"], input_bytes=requested).stdout
    )
    entries: dict[str, dict[str, Any]] = {}
    for rel, mode, expected_oid in ordered:
        header = batch.readline().rstrip(b"\n")
        fields = header.split(b" ")
        if len(fields) != 3:
            raise DeliveryError(f"malformed cat-file header for {rel}")
        try:
            actual_oid = fields[0].decode("ascii")
            object_type = fields[1].decode("ascii")
            size = int(fields[2].decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise DeliveryError(f"malformed cat-file header for {rel}") from exc
        data = batch.read(size)
        terminator = batch.read(1)
        if (
            actual_oid != expected_oid
            or object_type != "blob"
            or len(data) != size
            or terminator != b"\n"
        ):
            raise DeliveryError(f"cat-file blob mismatch for {rel}")
        entries[rel] = {
            "exists": True,
            "mode": mode,
            "git_oid": expected_oid,
            "bytes": size,
            "sha256": sha256_bytes(data),
        }
    if batch.read(1) != b"":
        raise DeliveryError("unexpected trailing cat-file output")
    return entries


def path_manifest(
    repo: Path, before_tree: str, after_tree: str, paths: Sequence[str]
) -> list[dict[str, Any]]:
    before_entries = tree_path_entries(repo, before_tree, paths)
    after_entries = tree_path_entries(repo, after_tree, paths)
    rows: list[dict[str, Any]] = []
    for rel in paths:
        before = before_entries.get(rel, missing_entry())
        after = after_entries.get(rel, missing_entry())
        if not before["exists"] and after["exists"]:
            change_type = "A"
        elif before["exists"] and not after["exists"]:
            change_type = "D"
        elif before != after:
            change_type = "M"
        else:
            raise DeliveryError(f"allowlisted path is unchanged: {rel}")
        rows.append(
            {
                "path": rel,
                "change_type": change_type,
                "before": before,
                "after": after,
            }
        )
    return rows


def build_binary_patch(repo: Path, before_tree: str, after_tree: str) -> bytes:
    result = run_git(
        repo,
        [
            "diff",
            "--binary",
            "--full-index",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            before_tree,
            after_tree,
        ],
    )
    if not result.stdout:
        raise DeliveryError("binary patch is empty")
    return result.stdout


def _temporary_index() -> tuple[tempfile.TemporaryDirectory[str], dict[str, str]]:
    folder = tempfile.TemporaryDirectory(prefix="v26-delivery-verify-")
    return folder, {"GIT_INDEX_FILE": str(Path(folder.name) / "index")}


def verify_patch_roundtrip(
    repo: Path, patch: Path, baseline_tree: str, final_tree: str
) -> dict[str, Any]:
    forward_folder, forward_env = _temporary_index()
    reverse_folder, reverse_env = _temporary_index()
    try:
        run_git(repo, ["read-tree", baseline_tree], env=forward_env)
        forward = run_git(
            repo,
            ["apply", "--cached", "--binary", "--whitespace=nowarn", str(patch)],
            env=forward_env,
        )
        forward_tree = run_git(repo, ["write-tree"], env=forward_env).stdout.decode(
            "ascii"
        ).strip()

        run_git(repo, ["read-tree", final_tree], env=reverse_env)
        reverse = run_git(
            repo,
            [
                "apply",
                "--cached",
                "--reverse",
                "--binary",
                "--whitespace=nowarn",
                str(patch),
            ],
            env=reverse_env,
        )
        reverse_tree = run_git(repo, ["write-tree"], env=reverse_env).stdout.decode(
            "ascii"
        ).strip()
    finally:
        forward_folder.cleanup()
        reverse_folder.cleanup()
    if forward_tree != final_tree:
        raise DeliveryError(
            f"forward cached patch tree mismatch: {forward_tree} != {final_tree}"
        )
    if reverse_tree != baseline_tree:
        raise DeliveryError(
            f"reverse cached patch tree mismatch: {reverse_tree} != {baseline_tree}"
        )
    return {
        "forward": {
            "command": "git apply --cached --binary --whitespace=nowarn PATCH && git write-tree",
            "apply_exit_status": forward.returncode,
            "actual_tree": forward_tree,
            "expected_tree": final_tree,
            "tree_equal": True,
        },
        "reverse": {
            "command": "git apply --cached --reverse --binary --whitespace=nowarn PATCH && git write-tree",
            "apply_exit_status": reverse.returncode,
            "actual_tree": reverse_tree,
            "expected_tree": baseline_tree,
            "tree_equal": True,
        },
    }


def _powershell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_rollback_script(manifest_sha256: str, patch_sha256: str) -> bytes:
    manifest_literal = _powershell_single_quote(MANIFEST_NAME)
    patch_literal = _powershell_single_quote(PATCH_NAME)
    manifest_hash_literal = _powershell_single_quote(manifest_sha256)
    patch_hash_literal = _powershell_single_quote(patch_sha256)
    report_schema_literal = _powershell_single_quote(ROLLBACK_REPORT_SCHEMA)
    # The test-only switch proves compensation after a successful reverse apply.
    # It is inert unless explicitly supplied.
    script = rf'''#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [string]$ManifestPath = (Join-Path $PSScriptRoot {manifest_literal}),
    [string]$PatchPath = (Join-Path $PSScriptRoot {patch_literal}),
    [string]$ReportPath = (Join-Path $PSScriptRoot 'rollback-execution-verification.json'),
    [switch]$SimulatePostApplyFailure
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedManifestSha256 = {manifest_hash_literal}
$ExpectedPatchSha256 = {patch_hash_literal}
$ReportSchema = {report_schema_literal}
$Applied = $false
$Compensated = $false
$OriginalFailure = $null

function Invoke-GitChecked {{
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = & git -C $script:ResolvedRepo @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {{
        throw "git $($Arguments -join ' ') failed with exit status $exitCode`n$($output -join "`n")"
    }}
    return (($output | ForEach-Object {{ "$_" }}) -join "`n").Trim()
}}

function Get-Sha256Lower {{
    param([Parameter(Mandatory = $true)][string]$LiteralPath)
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $LiteralPath).Hash.ToLowerInvariant()
}}

function Assert-ExpectedState {{
    param(
        [Parameter(Mandatory = $true)][ValidateSet('before','after')][string]$Side,
        [Parameter(Mandatory = $true)][string]$ExpectedTree
    )
    $actualTree = Invoke-GitChecked write-tree
    if ($actualTree -ne $ExpectedTree) {{
        throw "$Side index tree mismatch: $actualTree != $ExpectedTree"
    }}
    foreach ($entry in $script:Manifest.paths) {{
        $rel = [string]$entry.path
        $state = $entry.$Side
        $absolute = [IO.Path]::GetFullPath((Join-Path $script:ResolvedRepo $rel))
        $existing = Get-Item -Force -LiteralPath $absolute -ErrorAction SilentlyContinue
        if ([bool]$state.exists) {{
            if ($null -eq $existing) {{
                throw "$Side expects path to exist: $rel"
            }}
            $pathArg = "--path=$rel"
            $worktreeOid = Invoke-GitChecked hash-object $pathArg -- $absolute
            if ($worktreeOid -ne [string]$state.git_oid) {{
                throw "$Side worktree Git blob SHA mismatch at $rel"
            }}
        }}
        elseif ($null -ne $existing) {{
            throw "$Side expects path to be absent: $rel"
        }}
        & git -C $script:ResolvedRepo diff --quiet --no-ext-diff -- $rel
        if ($LASTEXITCODE -ne 0) {{
            throw "$Side worktree/index mode or content mismatch at $rel"
        }}
    }}
}}

try {{
    $script:ResolvedRepo = (Resolve-Path -LiteralPath $RepoRoot).Path
    $actualRoot = Invoke-GitChecked rev-parse --show-toplevel
    if ([IO.Path]::GetFullPath($actualRoot) -ne [IO.Path]::GetFullPath($script:ResolvedRepo)) {{
        throw "RepoRoot is not the exact Git top level: $actualRoot"
    }}
    $ManifestPath = (Resolve-Path -LiteralPath $ManifestPath).Path
    $PatchPath = (Resolve-Path -LiteralPath $PatchPath).Path
    if ((Get-Sha256Lower $ManifestPath) -ne $ExpectedManifestSha256) {{
        throw 'manifest SHA-256 mismatch; no files were changed'
    }}
    if ((Get-Sha256Lower $PatchPath) -ne $ExpectedPatchSha256) {{
        throw 'patch SHA-256 mismatch; no files were changed'
    }}
    $script:Manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $ManifestPath | ConvertFrom-Json
    if ([string]$script:Manifest.schema -ne 'magireco-cn-v26-delivery-manifest/v1') {{
        throw "unsupported manifest schema: $($script:Manifest.schema)"
    }}
    $baselineTree = [string]$script:Manifest.baseline.tree
    $finalTree = [string]$script:Manifest.final.tree
    Assert-ExpectedState -Side after -ExpectedTree $finalTree

    Invoke-GitChecked apply --index --reverse --binary --whitespace=nowarn $PatchPath | Out-Null
    $Applied = $true
    if ($SimulatePostApplyFailure) {{
        throw 'simulated post-apply verification failure'
    }}
    Assert-ExpectedState -Side before -ExpectedTree $baselineTree

    $report = [ordered]@{{
        schema = $ReportSchema
        status = 'PASS'
        baseline_tree = $baselineTree
        final_tree = $finalTree
        restored_tree = $baselineTree
        path_count = @($script:Manifest.paths).Count
        patch_sha256 = $ExpectedPatchSha256
        manifest_sha256 = $ExpectedManifestSha256
        compensated = $false
    }}
    $json = $report | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($ReportPath), $json + "`n", [Text.UTF8Encoding]::new($false))
    Write-Output $json
}}
catch {{
    $OriginalFailure = $_
    if ($Applied) {{
        try {{
            Invoke-GitChecked apply --index --binary --whitespace=nowarn $PatchPath | Out-Null
            Assert-ExpectedState -Side after -ExpectedTree ([string]$script:Manifest.final.tree)
            $Compensated = $true
        }}
        catch {{
            throw "rollback failed and compensation failed; manual intervention required. rollback=$OriginalFailure compensation=$_"
        }}
    }}
    if ($Compensated) {{
        throw "rollback failed after mutation; original final tree was restored transactionally. $OriginalFailure"
    }}
    throw $OriginalFailure
}}
'''
    return script.replace("\r\n", "\n").encode("utf-8")


def _validate_manifest_against_trees(
    repo: Path, manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise DeliveryError(f"unsupported manifest schema: {manifest.get('schema')!r}")
    expected_identity = {
        "user.name": EXPECTED_AUTHOR_NAME,
        "user.email": EXPECTED_AUTHOR_EMAIL,
    }
    if manifest.get("submission_identity") != expected_identity:
        raise DeliveryError("manifest submission identity is not Hiiragi Nemu")
    baseline_tree = manifest.get("baseline", {}).get("tree")
    baseline_commit = manifest.get("baseline", {}).get("commit")
    if not isinstance(baseline_commit, str) or not OID_RE.fullmatch(baseline_commit):
        raise DeliveryError("manifest baseline commit is invalid")
    final_tree = manifest.get("final", {}).get("tree")
    if not isinstance(baseline_tree, str) or not OID_RE.fullmatch(baseline_tree):
        raise DeliveryError("manifest baseline tree is invalid")
    if not isinstance(final_tree, str) or not OID_RE.fullmatch(final_tree):
        raise DeliveryError("manifest final tree is invalid")
    if resolve_commit(repo, baseline_commit) != baseline_commit:
        raise DeliveryError("manifest baseline commit does not resolve exactly")
    if resolve_tree(repo, baseline_commit) != baseline_tree:
        raise DeliveryError("manifest baseline commit/tree relationship is invalid")
    rows = manifest.get("paths")
    if not isinstance(rows, list) or not rows:
        raise DeliveryError("manifest paths must be a non-empty array")
    paths = [normalize_repo_path(row.get("path")) for row in rows]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise DeliveryError("manifest paths are not sorted and unique")
    actual_changed = changed_paths(repo, baseline_tree, final_tree)
    if paths != actual_changed:
        raise DeliveryError(
            f"manifest path coverage mismatch: manifest={paths} changed={actual_changed}"
        )
    expected_rows = path_manifest(repo, baseline_tree, final_tree, paths)
    if rows != expected_rows:
        raise DeliveryError("manifest before/after object hashes do not match Git trees")
    counts = manifest.get("change_counts")
    expected_counts = {
        code: sum(row["change_type"] == code for row in rows)
        for code in ("A", "M", "D")
    }
    if counts != expected_counts:
        raise DeliveryError(f"manifest change counts mismatch: {counts} != {expected_counts}")
    return rows


def generate_bundle(
    *,
    repo: Path,
    baseline: str,
    allowlist_path: Path,
    artifact_path: Path,
    output_dir: Path,
    artifact_contract: dict[str, Any] | None = None,
    final_treeish: str | None = None,
    from_worktree: bool = False,
) -> dict[str, Any]:
    repo = repository_root(repo)
    submission_identity = verify_submission_identity(repo)
    output_dir = validate_output_directory(repo, output_dir)
    if (final_treeish is None) == (not from_worktree):
        raise DeliveryError("select exactly one of final_treeish or from_worktree")
    allowlist_path = allowlist_path.resolve()
    if _inside(allowlist_path, output_dir):
        raise DeliveryError("allowlist cannot be inside the generated output directory")
    allowlist, allowlist_sha = load_allowlist(allowlist_path)
    artifact_path = artifact_path.resolve()
    artifact_bytes, source_artifact_report = inspect_product_artifact(
        artifact_path, artifact_contract
    )
    baseline_commit = resolve_commit(repo, baseline)
    baseline_tree = resolve_tree(repo, baseline_commit)
    if from_worktree:
        final_tree = create_tree_from_worktree(repo, baseline_tree, allowlist)
        final_source = "allowlisted-worktree-via-isolated-index"
        final_revision = None
    else:
        assert final_treeish is not None
        final_tree = resolve_tree(repo, final_treeish)
        final_source = "git-treeish"
        final_revision = final_treeish
    actual_paths = changed_paths(repo, baseline_tree, final_tree)
    if actual_paths != allowlist:
        missing = sorted(set(allowlist) - set(actual_paths))
        extra = sorted(set(actual_paths) - set(allowlist))
        raise DeliveryError(
            f"final diff does not exactly equal allowlist; unchanged={missing}, unlisted={extra}"
        )
    artifact_tree_binding = verify_product_artifact_against_tree(
        repo, final_tree, artifact_bytes
    )
    rows = path_manifest(repo, baseline_tree, final_tree, allowlist)
    counts = {code: sum(row["change_type"] == code for row in rows) for code in ("A", "M", "D")}
    patch_bytes = build_binary_patch(repo, baseline_tree, final_tree)
    output_dir.mkdir(parents=True, exist_ok=False)
    product_path = output_dir / ARTIFACT_NAME
    patch_path = output_dir / PATCH_NAME
    manifest_path = output_dir / MANIFEST_NAME
    rollback_path = output_dir / ROLLBACK_NAME
    verification_path = output_dir / VERIFICATION_NAME
    try:
        atomic_write(product_path, artifact_bytes)
        if sha256_file(artifact_path) != source_artifact_report["sha256"]:
            raise DeliveryError("source product ZIP changed while the bundle was generated")
        copied_bytes, copied_artifact_report = inspect_product_artifact(
            product_path, source_artifact_report["expected"]
        )
        if copied_bytes != artifact_bytes:
            raise DeliveryError("copied product ZIP bytes differ from their source")
        if copied_artifact_report != source_artifact_report:
            raise DeliveryError("copied product ZIP validation differs from its source")
        copied_artifact_report["final_tree_binding"] = artifact_tree_binding
        atomic_write(patch_path, patch_bytes)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "submission_identity": submission_identity,
            "baseline": {"commit": baseline_commit, "tree": baseline_tree},
            "final": {
                "source": final_source,
                "revision": final_revision,
                "tree": final_tree,
            },
            "allowlist": {
                "source_sha256": allowlist_sha,
                "normalized_path_count": len(allowlist),
                "exact_diff_match": True,
            },
            "change_counts": counts,
            "modified_artifact": copied_artifact_report,
            "patch": {
                "file": PATCH_NAME,
                "format": "git-diff-binary-full-index-no-renames",
                "bytes": len(patch_bytes),
                "sha256": sha256_bytes(patch_bytes),
            },
            "rollback": {"file": ROLLBACK_NAME, "transactional_compensation": True},
            "paths": rows,
        }
        manifest_bytes = canonical_json_bytes(manifest)
        atomic_write(manifest_path, manifest_bytes)
        rollback_bytes = render_rollback_script(
            sha256_bytes(manifest_bytes), sha256_bytes(patch_bytes)
        )
        atomic_write(rollback_path, rollback_bytes)
        roundtrip = verify_patch_roundtrip(
            repo, patch_path, baseline_tree, final_tree
        )
        verification = {
            "schema": VERIFICATION_SCHEMA,
            "status": "PASS",
            "repo_root_check": "exact",
            "submission_identity": submission_identity,
            "baseline_commit": baseline_commit,
            "baseline_tree": baseline_tree,
            "final_tree": final_tree,
            "changed_path_count": len(rows),
            "change_counts": counts,
            "allowlist_exact": True,
            "self_reference_prevented": True,
            "output_outside_repository": True,
            "manifest_tree_hashes_verified": True,
            "modified_artifact_reopened": True,
            "product_archive_contract": copied_artifact_report,
            "cached_patch_roundtrip": roundtrip,
            "delivery_roles": {
                "modified_artifact": ARTIFACT_NAME,
                "binary_patch": PATCH_NAME,
                "rollback": ROLLBACK_NAME,
                "verification": VERIFICATION_NAME,
            },
            "supporting_files": {"per_path_manifest": MANIFEST_NAME},
            "artifacts": {
                ARTIFACT_NAME: {"bytes": product_path.stat().st_size, "sha256": sha256_file(product_path)},
                PATCH_NAME: {"bytes": patch_path.stat().st_size, "sha256": sha256_file(patch_path)},
                MANIFEST_NAME: {"bytes": manifest_path.stat().st_size, "sha256": sha256_file(manifest_path)},
                ROLLBACK_NAME: {"bytes": rollback_path.stat().st_size, "sha256": sha256_file(rollback_path)},
            },
        }
        atomic_write(verification_path, canonical_json_bytes(verification))
        # Re-open every role before returning.
        verify_bundle(repo=repo, bundle_dir=output_dir)
        return verification
    except Exception:
        # An incomplete four-role plus supporting-manifest set must not look publishable.
        for path in (
            verification_path,
            rollback_path,
            manifest_path,
            patch_path,
            product_path,
        ):
            path.unlink(missing_ok=True)
        try:
            output_dir.rmdir()
        except OSError:
            pass
        raise


def verify_bundle(*, repo: Path, bundle_dir: Path) -> dict[str, Any]:
    repo = repository_root(repo)
    bundle_dir = bundle_dir.resolve()
    if _inside(bundle_dir, repo):
        raise DeliveryError("delivery bundle must remain outside the repository")
    expected_names = {
        ARTIFACT_NAME,
        PATCH_NAME,
        MANIFEST_NAME,
        ROLLBACK_NAME,
        VERIFICATION_NAME,
    }
    entries = list(bundle_dir.iterdir())
    actual_names = {item.name for item in entries}
    if actual_names != expected_names:
        raise DeliveryError(
            f"bundle role set mismatch: expected={sorted(expected_names)} actual={sorted(actual_names)}"
        )
    if not all(item.is_file() for item in entries):
        raise DeliveryError("every delivery role must be a regular file")
    product_path = bundle_dir / ARTIFACT_NAME
    patch_path = bundle_dir / PATCH_NAME
    manifest_path = bundle_dir / MANIFEST_NAME
    rollback_path = bundle_dir / ROLLBACK_NAME
    verification_path = bundle_dir / VERIFICATION_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = _validate_manifest_against_trees(repo, manifest)
    artifact_manifest = manifest.get("modified_artifact")
    if not isinstance(artifact_manifest, dict):
        raise DeliveryError("manifest modified_artifact record is missing")
    _artifact_bytes, artifact_report = inspect_product_artifact(
        product_path, artifact_manifest.get("expected")
    )
    artifact_report["final_tree_binding"] = verify_product_artifact_against_tree(
        repo, manifest["final"]["tree"], _artifact_bytes
    )
    if artifact_report != artifact_manifest:
        raise DeliveryError("product artifact hash or ZIP contract differs from manifest")
    if manifest.get("patch", {}).get("file") != PATCH_NAME:
        raise DeliveryError("manifest patch filename is invalid")
    if manifest.get("patch", {}).get("format") != "git-diff-binary-full-index-no-renames":
        raise DeliveryError("manifest patch format is invalid")
    if manifest.get("rollback") != {
        "file": ROLLBACK_NAME,
        "transactional_compensation": True,
    }:
        raise DeliveryError("manifest rollback contract is invalid")
    if manifest["patch"]["sha256"] != sha256_file(patch_path):
        raise DeliveryError("patch SHA-256 does not match manifest")
    if manifest["patch"]["bytes"] != patch_path.stat().st_size:
        raise DeliveryError("patch byte count does not match manifest")
    expected_patch = build_binary_patch(
        repo, manifest["baseline"]["tree"], manifest["final"]["tree"]
    )
    if patch_path.read_bytes() != expected_patch:
        raise DeliveryError("patch bytes are not the complete canonical binary tree diff")
    expected_rollback = render_rollback_script(
        sha256_file(manifest_path), sha256_file(patch_path)
    )
    if rollback_path.read_bytes() != expected_rollback:
        raise DeliveryError("rollback script is not the exact generated transaction")
    roundtrip = verify_patch_roundtrip(
        repo,
        patch_path,
        manifest["baseline"]["tree"],
        manifest["final"]["tree"],
    )
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if verification.get("schema") != VERIFICATION_SCHEMA or verification.get("status") != "PASS":
        raise DeliveryError("verification record is not a PASS v1 record")
    for flag in (
        "allowlist_exact",
        "self_reference_prevented",
        "output_outside_repository",
        "manifest_tree_hashes_verified",
        "modified_artifact_reopened",
    ):
        if verification.get(flag) is not True:
            raise DeliveryError(f"verification record flag is not true: {flag}")
    expected_artifacts = {
        ARTIFACT_NAME: {"bytes": product_path.stat().st_size, "sha256": sha256_file(product_path)},
        PATCH_NAME: {"bytes": patch_path.stat().st_size, "sha256": sha256_file(patch_path)},
        MANIFEST_NAME: {"bytes": manifest_path.stat().st_size, "sha256": sha256_file(manifest_path)},
        ROLLBACK_NAME: {"bytes": rollback_path.stat().st_size, "sha256": sha256_file(rollback_path)},
    }
    checks = {
        "submission_identity": manifest.get("submission_identity"),
        "baseline_commit": manifest["baseline"]["commit"],
        "baseline_tree": manifest["baseline"]["tree"],
        "final_tree": manifest["final"]["tree"],
        "changed_path_count": len(rows),
        "change_counts": manifest["change_counts"],
        "product_archive_contract": artifact_report,
        "delivery_roles": {
            "modified_artifact": ARTIFACT_NAME,
            "binary_patch": PATCH_NAME,
            "rollback": ROLLBACK_NAME,
            "verification": VERIFICATION_NAME,
        },
        "supporting_files": {"per_path_manifest": MANIFEST_NAME},
        "artifacts": expected_artifacts,
    }
    for key, expected in checks.items():
        if verification.get(key) != expected:
            raise DeliveryError(f"verification record mismatch at {key}")
    recorded_roundtrip = verification.get("cached_patch_roundtrip", {})
    if (
        recorded_roundtrip.get("forward", {}).get("actual_tree")
        != roundtrip["forward"]["actual_tree"]
        or recorded_roundtrip.get("reverse", {}).get("actual_tree")
        != roundtrip["reverse"]["actual_tree"]
    ):
        raise DeliveryError("verification roundtrip record mismatch")
    return {
        "schema": VERIFICATION_SCHEMA,
        "status": "PASS",
        "bundle_dir": str(bundle_dir),
        "changed_path_count": len(rows),
        "change_counts": manifest["change_counts"],
        "baseline_tree": manifest["baseline"]["tree"],
        "final_tree": manifest["final"]["tree"],
        "cached_patch_roundtrip": roundtrip,
        "product_archive_contract": artifact_report,
        "delivery_roles": verification["delivery_roles"],
        "supporting_files": verification["supporting_files"],
        "artifacts": expected_artifacts,
    }
