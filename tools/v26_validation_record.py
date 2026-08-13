#!/usr/bin/env python3
"""Execute and attest the final v26 validation command matrix.

The runner is intentionally independent from the delivery-bundle builder.  It
does not stage files, invoke a shell, or alter Git/network configuration.  A
local, detached clone is created for baseline commands; modified commands run
against the caller-selected worktree.  Every subprocess is recorded with its
literal argv, cwd, declared-input digest, byte-exact stdout/stderr, exit status,
and UTC interval.

Large streams are stored in content-addressed sidecars next to the single JSON
record.  ``verify_record`` reopens every stream and every retained output, so a
record whose evidence was changed after the run fails closed.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping


PLAN_SCHEMA = "magireco-cn-v26-validation-plan/v1"
RECORD_SCHEMA = "magireco-cn-v26-command-validation/v1"
ENGINE_SCHEMA = "magireco-cn-engine-i18n-behavior/v1"
HANDOFF_SCHEMA = "magireco-cn-v26-delivery-validation-handoff/v1"
DEFAULT_PLAN = Path(__file__).with_name("v26-final-validation-plan.json")
DEFAULT_BASELINE = "d5e8f75d93f6760a588e592c22a3754d19370c68"
DEFAULT_INLINE_LIMIT = 64 * 1024
READ_ONLY_GIT_ENV = {"GIT_OPTIONAL_LOCKS": "0"}
SENSITIVE_ENV = re.compile(r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY)", re.I)
PLACEHOLDER_RE = re.compile(r"%(?:\d+\$)?[a-zA-Z]|\{\d+\}")


class ValidationError(RuntimeError):
    """A fail-closed validation contract error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _inside(candidate: Path, parent: Path) -> bool:
    try:
        candidate.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        env={**os.environ, **READ_ONLY_GIT_ENV},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise ValidationError(
            f"git {' '.join(args)} failed ({result.returncode}): "
            + result.stderr.decode("utf-8", errors="replace")
        )
    return result


def repository_root(path: Path) -> Path:
    root = Path(
        _git(path.resolve(), "rev-parse", "--show-toplevel").stdout.decode(
            "utf-8", errors="strict"
        ).strip()
    ).resolve()
    if os.path.normcase(str(root)) != os.path.normcase(str(path.resolve())):
        raise ValidationError(f"--repo must be the exact Git top level: {root}")
    return root


def git_revision(repo: Path, revision: str) -> tuple[str, str]:
    commit = (
        _git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}")
        .stdout.decode("ascii")
        .strip()
    )
    tree = (
        _git(repo, "show", "-s", "--format=%T", commit).stdout.decode("ascii").strip()
    )
    return commit, tree


def git_index_state(repo: Path) -> dict[str, Any]:
    index = git_index_path(repo)
    exists = index.is_file()
    return {
        "path": str(index),
        "exists": exists,
        "bytes": index.stat().st_size if exists else None,
        "sha256": sha256_file(index) if exists else None,
    }


def git_index_path(repo: Path) -> Path:
    raw_path = (
        _git(repo, "rev-parse", "--git-path", "index").stdout.decode("utf-8").strip()
    )
    index = Path(raw_path)
    if not index.is_absolute():
        index = (repo / index).resolve()
    return index


def acquire_git_index_guard(repo: Path) -> tuple[Path, bytes, dict[str, Any]]:
    """Create Git's conventional index lock for the complete validation window.

    ``GIT_OPTIONAL_LOCKS=0`` protects every subprocess launched by this runner.
    The explicit lock additionally prevents an unrelated process from refreshing
    the same linked-worktree index while byte-exact before/after evidence is being
    captured.  Commands that genuinely need to stage are therefore rejected by
    Git rather than silently invalidating the supposedly read-only validation.
    """

    index = git_index_path(repo)
    lock = index.with_name(index.name + ".lock")
    payload = canonical_json_bytes(
        {
            "schema": "magireco-cn-v26-git-index-guard/v1",
            "pid": os.getpid(),
            "repo_root": str(repo.resolve()),
            "index_path": str(index),
            "nonce": secrets.token_hex(16),
            "created_at_utc": utc_now(),
        }
    )
    try:
        with lock.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ValidationError(f"Git index lock already exists: {lock}") from exc
    evidence = {
        "schema": "magireco-cn-v26-git-index-guard/v1",
        "index_path": str(index),
        "lock_path": str(lock),
        "payload_sha256": sha256_bytes(payload),
        "created": True,
        "removed": False,
        "payload_unchanged": None,
    }
    return lock, payload, evidence


def release_git_index_guard(
    lock: Path, payload: bytes, evidence: dict[str, Any]
) -> None:
    if not lock.is_file():
        raise ValidationError(f"Git index guard disappeared during validation: {lock}")
    actual = lock.read_bytes()
    evidence["payload_unchanged"] = actual == payload
    if actual != payload:
        raise ValidationError(f"Git index guard changed during validation: {lock}")
    lock.unlink()
    evidence["removed"] = not lock.exists()
    if not evidence["removed"]:
        raise ValidationError(f"Git index guard could not be removed: {lock}")


def _hash_directory(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total = 0
    for item in sorted(path.rglob("*"), key=lambda value: value.relative_to(path).as_posix()):
        rel = item.relative_to(path).as_posix()
        if ".git" in item.relative_to(path).parts:
            continue
        if item.is_symlink():
            raise ValidationError(f"declared input contains a symlink: {item}")
        if not item.is_file():
            continue
        size = item.stat().st_size
        total += size
        rows.append({"path": rel, "bytes": size, "sha256": sha256_file(item)})
    aggregate = sha256_bytes(canonical_json_bytes(rows))
    return {
        "type": "directory",
        "bytes": total,
        "file_count": len(rows),
        "sha256": aggregate,
        "digest_algorithm": "sha256(canonical-json(relative-path,bytes,file-sha256))",
    }


def hash_path(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "type": None,
            "bytes": None,
            "file_count": 0,
            "sha256": None,
        }
    if path.is_symlink():
        raise ValidationError(f"declared path must not be a symlink: {path}")
    if path.is_file():
        return {
            "path": str(path),
            "exists": True,
            "type": "file",
            "bytes": path.stat().st_size,
            "file_count": 1,
            "sha256": sha256_file(path),
            "digest_algorithm": "sha256(file-bytes)",
        }
    if path.is_dir():
        result = _hash_directory(path)
        result.update({"path": str(path), "exists": True})
        return result
    raise ValidationError(f"unsupported declared path type: {path}")


def aggregate_paths(rows: Iterable[Mapping[str, Any]]) -> str:
    material = [
        {
            "declared": row["declared"],
            "optional": row["optional"],
            "exists": row["snapshot"]["exists"],
            "type": row["snapshot"]["type"],
            "bytes": row["snapshot"]["bytes"],
            "file_count": row["snapshot"]["file_count"],
            "sha256": row["snapshot"]["sha256"],
        }
        for row in rows
    ]
    return sha256_bytes(canonical_json_bytes(material))


def _expand(value: str, tokens: Mapping[str, str]) -> str:
    result = value
    for key, replacement in tokens.items():
        result = result.replace("${" + key + "}", replacement)
    unknown = re.findall(r"\$\{[A-Z0-9_]+\}", result)
    if unknown:
        raise ValidationError(f"unknown plan token(s) in {value!r}: {unknown}")
    return result


def _resolve_declared_path(
    raw: str, *, group_root: Path, tokens: Mapping[str, str]
) -> Path:
    expanded = Path(_expand(raw, tokens))
    if not expanded.is_absolute():
        expanded = group_root / expanded
    return expanded.resolve()


def _input_snapshot(
    specs: list[Any], *, group_root: Path, tokens: Mapping[str, str]
) -> tuple[dict[str, Any], list[str]]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for item in specs:
        if isinstance(item, str):
            declared, optional = item, False
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            declared, optional = item["path"], bool(item.get("optional", False))
        else:
            raise ValidationError(f"invalid input declaration: {item!r}")
        resolved = _resolve_declared_path(declared, group_root=group_root, tokens=tokens)
        snapshot = hash_path(resolved)
        row = {
            "declared": declared,
            "resolved": str(resolved),
            "optional": optional,
            "snapshot": snapshot,
        }
        rows.append(row)
        if not optional and not snapshot["exists"]:
            failures.append(f"required input missing: {declared}")
    return {
        "paths": rows,
        "aggregate_sha256": aggregate_paths(rows),
        "digest_algorithm": "sha256(canonical-json(declared-input-summaries))",
    }, failures


def _output_snapshot(
    specs: list[Any], *, group_root: Path, tokens: Mapping[str, str]
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for item in specs:
        if isinstance(item, str):
            declared, retention, role = item, "persistent", None
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            declared = item["path"]
            retention = item.get("retention", "persistent")
            role = item.get("delivery_role")
        else:
            raise ValidationError(f"invalid output declaration: {item!r}")
        if retention not in {"persistent", "ephemeral"}:
            raise ValidationError(f"invalid output retention for {declared}: {retention}")
        resolved = _resolve_declared_path(declared, group_root=group_root, tokens=tokens)
        snapshot = hash_path(resolved)
        row = {
            "declared": declared,
            "resolved": str(resolved),
            "retention": retention,
            "delivery_role": role,
            "snapshot": snapshot,
        }
        rows.append(row)
        if not snapshot["exists"]:
            failures.append(f"declared output missing: {declared}")
    return rows, failures


def _safe_sidecar_name(command_id: str, stream_name: str, digest: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", command_id).strip("._") or "command"
    return f"{stem}.{stream_name}.{digest[:16]}.bin"


def store_stream(
    value: bytes,
    *,
    command_id: str,
    stream_name: str,
    inline_limit: int,
    sidecar_dir: Path,
    record_parent: Path,
) -> dict[str, Any]:
    digest = sha256_bytes(value)
    base = {
        "bytes": len(value),
        "sha256": digest,
        "utf8_preview": value[:4096].decode("utf-8", errors="replace"),
    }
    if len(value) <= inline_limit:
        base.update(
            {
                "storage": "inline-base64",
                "base64": base64.b64encode(value).decode("ascii"),
            }
        )
        return base
    name = _safe_sidecar_name(command_id, stream_name, digest)
    sidecar = sidecar_dir / name
    atomic_write(sidecar, value)
    base.update(
        {
            "storage": "sidecar",
            "path": sidecar.relative_to(record_parent).as_posix(),
        }
    )
    return base


def _run_process(
    *,
    command_id: str,
    argv: list[str],
    cwd: Path,
    timeout_seconds: float,
    env_overrides: dict[str, str],
    inline_limit: int,
    sidecar_dir: Path,
    record_parent: Path,
) -> dict[str, Any]:
    for name in env_overrides:
        if SENSITIVE_ENV.search(name):
            raise ValidationError(
                f"sensitive environment override is forbidden in validation plans: {name}"
            )
    started = utc_now()
    monotonic = time.monotonic()
    timed_out = False
    launch_error = None
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env={**os.environ, **env_overrides},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        exit_status: int | None = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_status = None
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8", errors="replace")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8", errors="replace")
        stderr += f"\nvalidation runner timeout after {timeout_seconds}s\n".encode("ascii")
    except OSError as exc:
        exit_status = None
        stdout = b""
        stderr = (f"validation runner launch error: {exc}\n").encode(
            "utf-8", errors="replace"
        )
        launch_error = f"{type(exc).__name__}: {exc}"
    ended = utc_now()
    return {
        "literal_argv": argv,
        "literal_command_windows": subprocess.list2cmdline(argv),
        "cwd": str(cwd),
        "environment_overrides": env_overrides,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "duration_ms": round((time.monotonic() - monotonic) * 1000, 3),
        "exit_status": exit_status,
        "timed_out": timed_out,
        "launch_error": launch_error,
        "stdout": store_stream(
            stdout,
            command_id=command_id,
            stream_name="stdout",
            inline_limit=inline_limit,
            sidecar_dir=sidecar_dir,
            record_parent=record_parent,
        ),
        "stderr": store_stream(
            stderr,
            command_id=command_id,
            stream_name="stderr",
            inline_limit=inline_limit,
            sidecar_dir=sidecar_dir,
            record_parent=record_parent,
        ),
    }


def _validate_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise ValidationError(f"plan schema must be {PLAN_SCHEMA}")
    groups = plan.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValidationError("plan groups must be a non-empty array")
    group_ids: set[str] = set()
    command_ids: set[str] = set()
    for group in groups:
        if not isinstance(group, dict) or group.get("root") not in {"modified", "baseline"}:
            raise ValidationError("every group root must be modified or baseline")
        group_id = group.get("id")
        if not isinstance(group_id, str) or not group_id or group_id in group_ids:
            raise ValidationError(f"invalid or duplicate group id: {group_id!r}")
        group_ids.add(group_id)
        commands = group.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ValidationError(f"group {group_id} commands must be non-empty")
        for command in commands:
            if not isinstance(command, dict):
                raise ValidationError(f"group {group_id} contains a non-object command")
            command_id = command.get("id")
            if (
                not isinstance(command_id, str)
                or not command_id
                or command_id in command_ids
            ):
                raise ValidationError(f"invalid or duplicate command id: {command_id!r}")
            command_ids.add(command_id)
            argv = command.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
                raise ValidationError(f"command {command_id} argv must be string array")
            if command.get("cwd", ".").startswith(("/", "\\")):
                raise ValidationError(f"command {command_id} cwd must be group-relative")
            if not isinstance(command.get("inputs", []), list):
                raise ValidationError(f"command {command_id} inputs must be an array")
            if not isinstance(command.get("outputs", []), list):
                raise ValidationError(f"command {command_id} outputs must be an array")
    comparisons = plan.get("comparisons", [])
    if not isinstance(comparisons, list):
        raise ValidationError("plan comparisons must be an array")
    seen_comparisons: set[str] = set()
    for comparison in comparisons:
        if not isinstance(comparison, dict):
            raise ValidationError("comparison must be an object")
        comparison_id = comparison.get("id")
        if (
            not isinstance(comparison_id, str)
            or not comparison_id
            or comparison_id in seen_comparisons
        ):
            raise ValidationError(f"invalid or duplicate comparison id: {comparison_id!r}")
        seen_comparisons.add(comparison_id)
        if comparison.get("expect", "equal") != "equal":
            raise ValidationError("only fail-closed equal comparisons are supported")
        if not all(isinstance(comparison.get(key), str) for key in ("left", "right")):
            raise ValidationError(f"comparison {comparison_id} needs left/right paths")
    return plan


def load_plan(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.resolve().read_bytes()
    plan = json.loads(raw.decode("utf-8"))
    return _validate_plan(plan), sha256_bytes(raw)


def _setup_baseline_clone(
    *,
    repo: Path,
    clone: Path,
    baseline_commit: str,
    baseline_tree: str,
    inline_limit: int,
    sidecar_dir: Path,
    record_parent: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    commands = [
        (
            "setup-baseline-clone",
            [
                "git",
                "clone",
                "--shared",
                "--no-hardlinks",
                "--no-checkout",
                "--",
                str(repo),
                str(clone),
            ],
            clone.parent,
        ),
        (
            "setup-baseline-checkout",
            ["git", "-C", str(clone), "checkout", "--detach", baseline_commit],
            clone.parent,
        ),
    ]
    for command_id, argv, cwd in commands:
        git_object_input = {
            "commit": baseline_commit,
            "tree": baseline_tree,
            "source_repository": str(repo),
        }
        input_snapshot = {
            "paths": [],
            "git_object": git_object_input,
            "aggregate_sha256": sha256_bytes(canonical_json_bytes(git_object_input)),
            "digest_algorithm": "sha256(canonical-json(baseline-commit-tree-source))",
        }
        record = _run_process(
            command_id=command_id,
            argv=argv,
            cwd=cwd,
            timeout_seconds=300,
            env_overrides={},
            inline_limit=inline_limit,
            sidecar_dir=sidecar_dir,
            record_parent=record_parent,
        )
        record.update(
            {
                "id": command_id,
                "group": "setup",
                "status": "PASS" if record["exit_status"] == 0 else "FAIL",
                "input_snapshot": input_snapshot,
                "outputs": [],
                "contract_failures": [],
            }
        )
        records.append(record)
        if record["exit_status"] != 0:
            break
    return records


def _command_record(
    command: dict[str, Any],
    *,
    group_id: str,
    group_root: Path,
    tokens: Mapping[str, str],
    inline_limit: int,
    sidecar_dir: Path,
    record_parent: Path,
) -> dict[str, Any]:
    command_id = command["id"]
    inputs, failures = _input_snapshot(
        command.get("inputs", []), group_root=group_root, tokens=tokens
    )
    argv = [_expand(value, tokens) for value in command["argv"]]
    requested_env = {str(k): str(v) for k, v in command.get("env", {}).items()}
    if "GIT_OPTIONAL_LOCKS" in requested_env and requested_env["GIT_OPTIONAL_LOCKS"] != "0":
        raise ValidationError(
            f"command {command_id} cannot enable Git optional locks in the modified worktree"
        )
    effective_env = {**requested_env, **READ_ONLY_GIT_ENV}
    cwd_rel = Path(_expand(command.get("cwd", "."), tokens))
    cwd = (group_root / cwd_rel).resolve()
    try:
        cwd.relative_to(group_root.resolve())
    except ValueError as exc:
        raise ValidationError(f"command {command_id} cwd escapes its group root") from exc
    if not cwd.is_dir():
        failures.append(f"cwd missing: {cwd}")
    if failures:
        empty = store_stream(
            b"",
            command_id=command_id,
            stream_name="stdout",
            inline_limit=inline_limit,
            sidecar_dir=sidecar_dir,
            record_parent=record_parent,
        )
        error_bytes = ("; ".join(failures) + "\n").encode("utf-8")
        error = store_stream(
            error_bytes,
            command_id=command_id,
            stream_name="stderr",
            inline_limit=inline_limit,
            sidecar_dir=sidecar_dir,
            record_parent=record_parent,
        )
        stamp = utc_now()
        process = {
            "literal_argv": argv,
            "literal_command_windows": subprocess.list2cmdline(argv),
            "cwd": str(cwd),
            "environment_overrides": effective_env,
            "started_at_utc": stamp,
            "ended_at_utc": stamp,
            "duration_ms": 0.0,
            "exit_status": None,
            "timed_out": False,
            "launch_error": "input-contract-failure",
            "stdout": empty,
            "stderr": error,
        }
        outputs: list[dict[str, Any]] = []
    else:
        process = _run_process(
            command_id=command_id,
            argv=argv,
            cwd=cwd,
            timeout_seconds=float(command.get("timeout_seconds", 1800)),
            env_overrides=effective_env,
            inline_limit=inline_limit,
            sidecar_dir=sidecar_dir,
            record_parent=record_parent,
        )
        outputs, output_failures = _output_snapshot(
            command.get("outputs", []), group_root=group_root, tokens=tokens
        )
        failures.extend(output_failures)
    status = "PASS" if process["exit_status"] == 0 and not failures else "FAIL"
    return {
        "id": command_id,
        "group": group_id,
        "status": status,
        "input_snapshot": inputs,
        **process,
        "outputs": outputs,
        "contract_failures": failures,
    }


def _comparison_record(
    comparison: dict[str, Any], *, tokens: Mapping[str, str], modified_root: Path
) -> dict[str, Any]:
    left = _resolve_declared_path(comparison["left"], group_root=modified_root, tokens=tokens)
    right = _resolve_declared_path(comparison["right"], group_root=modified_root, tokens=tokens)
    left_record = hash_path(left)
    right_record = hash_path(right)
    equal = (
        left_record["exists"]
        and right_record["exists"]
        and left_record["type"] == "file"
        and right_record["type"] == "file"
        and left_record["bytes"] == right_record["bytes"]
        and left_record["sha256"] == right_record["sha256"]
    )
    return {
        "id": comparison["id"],
        "expect": "equal",
        "status": "PASS" if equal else "FAIL",
        "equal": equal,
        "left": left_record,
        "right": right_record,
    }


def _delivery_handoff(commands: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    roles: dict[str, list[dict[str, Any]]] = {}
    for command in commands:
        for item in command.get("outputs", []):
            role = item.get("delivery_role")
            if role and item["snapshot"]["exists"]:
                roles.setdefault(role, []).append(item)
    return {
        "schema": HANDOFF_SCHEMA,
        "record_file": output.name,
        "stream_sidecar_directory": output.name + ".streams",
        "strict_delivery_bundle_placement": "adjacent-supporting-evidence",
        "roles": roles,
    }


def run_validation(
    *,
    repo: Path,
    baseline: str,
    plan_path: Path,
    output: Path,
    artifact_dir: Path,
    inline_limit: int = DEFAULT_INLINE_LIMIT,
) -> dict[str, Any]:
    repo = repository_root(repo)
    output = output.resolve()
    artifact_dir = artifact_dir.resolve()
    if _inside(output, repo) or _inside(artifact_dir, repo):
        raise ValidationError("record and artifact directory must remain outside the repository")
    if output.exists():
        raise ValidationError(f"record already exists: {output}")
    if artifact_dir.exists():
        raise ValidationError(f"artifact directory already exists: {artifact_dir}")
    if inline_limit < 0:
        raise ValidationError("inline limit must be non-negative")
    plan, plan_sha = load_plan(plan_path)
    baseline_commit, baseline_tree = git_revision(repo, baseline)
    output.parent.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    sidecar_dir = output.with_name(output.name + ".streams")
    if sidecar_dir.exists():
        raise ValidationError(f"sidecar directory already exists: {sidecar_dir}")
    sidecar_dir.mkdir(parents=True)
    index_lock, index_lock_payload, index_guard = acquire_git_index_guard(repo)
    try:
        started = utc_now()
        index_before = git_index_state(repo)
        commands: list[dict[str, Any]] = []
        comparisons: list[dict[str, Any]] = []
        baseline_required = any(group["root"] == "baseline" for group in plan["groups"])
        with tempfile.TemporaryDirectory(prefix="v26-validation-baseline-") as temp:
            baseline_root = Path(temp) / "baseline"
            if baseline_required:
                setup = _setup_baseline_clone(
                    repo=repo,
                    clone=baseline_root,
                    baseline_commit=baseline_commit,
                    baseline_tree=baseline_tree,
                    inline_limit=inline_limit,
                    sidecar_dir=sidecar_dir,
                    record_parent=output.parent,
                )
                commands.extend(setup)
            setup_ok = all(record["status"] == "PASS" for record in commands)
            tokens = {
                "PYTHON": sys.executable,
                "RUNNER": str(Path(__file__).resolve()),
                "MODIFIED_ROOT": str(repo),
                "BASELINE_ROOT": str(baseline_root),
                "ARTIFACT_ROOT": str(artifact_dir),
                "RECORD_PARENT": str(output.parent),
            }
            for group in plan["groups"]:
                group_root = repo if group["root"] == "modified" else baseline_root
                for command in group["commands"]:
                    if group["root"] == "baseline" and not setup_ok:
                        # Preserve the literal command in the record, but fail closed instead
                        # of running against a nonexistent or partially checked-out clone.
                        broken = dict(command)
                        broken["inputs"] = [{"path": "__baseline_setup_failed__"}]
                        record = _command_record(
                            broken,
                            group_id=group["id"],
                            group_root=group_root,
                            tokens=tokens,
                            inline_limit=inline_limit,
                            sidecar_dir=sidecar_dir,
                            record_parent=output.parent,
                        )
                    else:
                        record = _command_record(
                            command,
                            group_id=group["id"],
                            group_root=group_root,
                            tokens=tokens,
                            inline_limit=inline_limit,
                            sidecar_dir=sidecar_dir,
                            record_parent=output.parent,
                        )
                    commands.append(record)
            for comparison in plan.get("comparisons", []):
                comparisons.append(
                    _comparison_record(comparison, tokens=tokens, modified_root=repo)
                )
        index_after = git_index_state(repo)
    finally:
        release_git_index_guard(index_lock, index_lock_payload, index_guard)
    index_unchanged = index_before == index_after
    command_failures = [item["id"] for item in commands if item["status"] != "PASS"]
    comparison_failures = [
        item["id"] for item in comparisons if item["status"] != "PASS"
    ]
    status = "PASS" if not command_failures and not comparison_failures and index_unchanged else "FAIL"
    ended = utc_now()
    record = {
        "schema": RECORD_SCHEMA,
        "status": status,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "runner": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_file(Path(__file__).resolve()),
            "python": sys.version,
            "platform": platform.platform(),
            "shell_used": False,
            "network_configuration_mutated": False,
        },
        "plan": {
            "path": str(plan_path.resolve()),
            "sha256": plan_sha,
            "schema": PLAN_SCHEMA,
            "content": plan,
        },
        "modified": {
            "repo_root": str(repo),
            "head_commit": git_revision(repo, "HEAD")[0],
            "index_before": index_before,
            "index_after": index_after,
            "real_index_unchanged": index_unchanged,
            "index_guard": index_guard,
        },
        "baseline": {
            "requested_revision": baseline,
            "commit": baseline_commit,
            "tree": baseline_tree,
            "execution": "temporary-local-shared-clone-detached-checkout",
            "clone_removed_after_capture": True,
        },
        "output": {
            "record": str(output),
            "sidecar_directory": str(sidecar_dir),
            "artifact_directory": str(artifact_dir),
            "inline_limit_bytes": inline_limit,
        },
        "commands": commands,
        "comparisons": comparisons,
        "summary": {
            "command_count": len(commands),
            "command_passed": len(commands) - len(command_failures),
            "command_failed": len(command_failures),
            "command_failure_ids": command_failures,
            "comparison_count": len(comparisons),
            "comparison_failed": len(comparison_failures),
            "comparison_failure_ids": comparison_failures,
            "nonzero_or_unlaunched_commands": [
                item["id"] for item in commands if item["exit_status"] != 0
            ],
        },
        "delivery_handoff": _delivery_handoff(commands, output),
    }
    atomic_write(output, canonical_json_bytes(record))
    # A just-written record must pass the same byte-level reopen checks used by
    # downstream delivery tooling.  Failure changes the exit decision, never the
    # captured command evidence.
    try:
        verify_record(output)
    except ValidationError:
        if record["status"] == "PASS":
            record["status"] = "FAIL"
            record["summary"]["record_reopen_verification_failed"] = True
            atomic_write(output, canonical_json_bytes(record))
        raise
    return record


def _load_stream(record_parent: Path, stream: Mapping[str, Any]) -> bytes:
    storage = stream.get("storage")
    if storage == "inline-base64":
        try:
            raw = base64.b64decode(stream["base64"], validate=True)
        except Exception as exc:
            raise ValidationError("invalid inline stream base64") from exc
    elif storage == "sidecar":
        relative = Path(stream.get("path", ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValidationError(f"unsafe stream sidecar path: {relative}")
        sidecar = (record_parent / relative).resolve()
        if not _inside(sidecar, record_parent):
            raise ValidationError(f"stream sidecar escapes record directory: {sidecar}")
        if not sidecar.is_file() or sidecar.is_symlink():
            raise ValidationError(f"stream sidecar missing or unsafe: {sidecar}")
        raw = sidecar.read_bytes()
    else:
        raise ValidationError(f"unsupported stream storage: {storage!r}")
    if len(raw) != stream.get("bytes") or sha256_bytes(raw) != stream.get("sha256"):
        raise ValidationError("stream byte count or SHA-256 mismatch")
    return raw


def verify_record(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file() or path.is_symlink():
        raise ValidationError(f"verification record is missing or unsafe: {path}")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid verification record JSON: {exc}") from exc
    if record.get("schema") != RECORD_SCHEMA:
        raise ValidationError(f"unsupported verification record schema: {record.get('schema')!r}")
    commands = record.get("commands")
    comparisons = record.get("comparisons")
    if not isinstance(commands, list) or not isinstance(comparisons, list):
        raise ValidationError("record commands/comparisons must be arrays")
    failed_commands: list[str] = []
    persistent_outputs = 0
    for command in commands:
        if not isinstance(command, dict) or not isinstance(command.get("id"), str):
            raise ValidationError("record contains malformed command")
        _load_stream(path.parent, command.get("stdout", {}))
        _load_stream(path.parent, command.get("stderr", {}))
        contract_failures = command.get("contract_failures", [])
        expected_status = (
            "PASS"
            if command.get("exit_status") == 0 and not contract_failures
            else "FAIL"
        )
        if command.get("status") != expected_status:
            raise ValidationError(f"command status mismatch: {command['id']}")
        if expected_status != "PASS":
            failed_commands.append(command["id"])
        for output in command.get("outputs", []):
            if output.get("retention") != "persistent":
                continue
            persistent_outputs += 1
            current = hash_path(Path(output["resolved"]))
            if current != output.get("snapshot"):
                raise ValidationError(
                    f"persistent output changed or disappeared: {output['resolved']}"
                )
    failed_comparisons: list[str] = []
    for comparison in comparisons:
        if comparison.get("expect") != "equal":
            raise ValidationError("record contains unsupported comparison")
        equal = (
            comparison.get("left", {}).get("exists")
            and comparison.get("right", {}).get("exists")
            and comparison.get("left", {}).get("type") == "file"
            and comparison.get("right", {}).get("type") == "file"
            and comparison.get("left", {}).get("bytes")
            == comparison.get("right", {}).get("bytes")
            and comparison.get("left", {}).get("sha256")
            == comparison.get("right", {}).get("sha256")
        )
        if comparison.get("equal") is not equal:
            raise ValidationError(f"comparison equality mismatch: {comparison.get('id')}")
        expected_status = "PASS" if equal else "FAIL"
        if comparison.get("status") != expected_status:
            raise ValidationError(f"comparison status mismatch: {comparison.get('id')}")
        if not equal:
            failed_comparisons.append(comparison["id"])
    modified = record.get("modified", {})
    index_guard = modified.get("real_index_unchanged") is True
    guard_evidence = modified.get("index_guard", {})
    index_guard = index_guard and all(
        guard_evidence.get(key) is True
        for key in ("created", "payload_unchanged", "removed")
    )
    expected_record_status = (
        "PASS" if not failed_commands and not failed_comparisons and index_guard else "FAIL"
    )
    if record.get("status") != expected_record_status:
        raise ValidationError(
            f"overall status mismatch: expected {expected_record_status}, got {record.get('status')}"
        )
    summary = record.get("summary", {})
    if summary.get("command_count") != len(commands):
        raise ValidationError("summary command count mismatch")
    return {
        "schema": RECORD_SCHEMA,
        "status": expected_record_status,
        "record": str(path),
        "record_bytes": path.stat().st_size,
        "record_sha256": sha256_file(path),
        "commands": len(commands),
        "failed_commands": failed_commands,
        "comparisons": len(comparisons),
        "failed_comparisons": failed_comparisons,
        "persistent_outputs_reopened": persistent_outputs,
        "literal_streams_reopened": len(commands) * 2,
    }


def inspect_engine(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file() or path.is_symlink():
        raise ValidationError(f"engine table missing or unsafe: {path}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValidationError("engine table must not contain a UTF-8 BOM")
    if b"\r" in raw:
        raise ValidationError("engine table must use LF line endings")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"engine table is not UTF-8: {exc}") from exc
    rows: list[tuple[str, str]] = []
    comment_lines = 0
    blank_lines = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            blank_lines += 1
            continue
        if line.startswith("#"):
            comment_lines += 1
            continue
        if line.count("\t") != 1:
            raise ValidationError(f"engine row {line_number} must contain exactly one TAB")
        source, target = line.split("\t")
        if not source:
            raise ValidationError(f"engine row {line_number} has an empty source")
        if sorted(PLACEHOLDER_RE.findall(source)) != sorted(PLACEHOLDER_RE.findall(target)):
            raise ValidationError(f"engine row {line_number} placeholder mismatch")
        rows.append((source, target))
    sources = [source for source, _ in rows]
    if len(sources) != len(set(sources)):
        raise ValidationError("engine source keys are not unique")
    return {
        "schema": ENGINE_SCHEMA,
        "status": "PASS",
        "path": str(path),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "encoding": "UTF-8-no-BOM",
        "line_endings": "LF",
        "rows": len(rows),
        "exact_rows": sum(not source.startswith("^") for source in sources),
        "prefix_rows": sum(source.startswith("^") for source in sources),
        "empty_target_rows": sum(target == "" for _, target in rows),
        "comment_lines": comment_lines,
        "blank_lines": blank_lines,
        "unique_sources": True,
        "placeholder_parity": True,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)

    run_parser = subparsers.add_parser("run", help="execute a validation plan")
    run_parser.add_argument("--repo", type=Path, required=True)
    run_parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    run_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--artifact-dir", type=Path, required=True)
    run_parser.add_argument("--inline-limit", type=int, default=DEFAULT_INLINE_LIMIT)

    verify_parser = subparsers.add_parser("verify-record", help="reopen all record evidence")
    verify_parser.add_argument("record", type=Path)

    engine_parser = subparsers.add_parser("inspect-engine", help="verify runtime engine TSV behavior")
    engine_parser.add_argument("--path", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.action == "run":
            record = run_validation(
                repo=args.repo,
                baseline=args.baseline,
                plan_path=args.plan,
                output=args.output,
                artifact_dir=args.artifact_dir,
                inline_limit=args.inline_limit,
            )
            result = {
                "status": record["status"],
                "record": str(args.output.resolve()),
                "record_sha256": sha256_file(args.output.resolve()),
                "command_count": record["summary"]["command_count"],
                "command_failed": record["summary"]["command_failed"],
            }
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if record["status"] == "PASS" else 1
        if args.action == "verify-record":
            result = verify_record(args.record)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if result["status"] == "PASS" else 1
        if args.action == "inspect-engine":
            print(json.dumps(inspect_engine(args.path), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
    except (ValidationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    raise AssertionError(args.action)


if __name__ == "__main__":
    raise SystemExit(main())
