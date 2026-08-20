#!/usr/bin/env python3
"""Fail-closed round-3 authority recovery for eight manifest targets."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Iterable


SCRIPT = Path(__file__).resolve()
DEFAULT_REPO = SCRIPT.parents[1]
DEFAULT_EVIDENCE = (
    DEFAULT_REPO
    / "magica/research/totentanz-full-localization-20260817"
    / "authority-source-exhaustion-round3"
)
DEFAULT_UPSTREAM = Path(r"A:\totentanz-frontend")
DEFAULT_OFFICIAL = Path(r"A:\magicaOLD")

TARGETS = (
    "magica/js/event/raid/EventRaidMessage.json",
    "magica/resource/image_web/_json/help.json",
    "magica/resource/image_web/_json/puellaHistoria/overview.json",
    "magica/template/chara/CharaList.html",
    "magica/template/collection/CharaCollection.html",
    "magica/template/quest/CharaQuest.html",
    "magica/template/terms/Terms.html",
    "magica/template/user/MyPage.html",
)
ROW_COUNTS = {
    "official_help_stable_reuse.tsv": 229,
    "wiki_puella_historia_overview.tsv": 12,
    "official_samepath_static_reuse.tsv": 13,
    "official_event_raid_messages.tsv": 21,
}


class Round3Error(RuntimeError):
    pass


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise Round3Error(f"missing evidence: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def under(root: Path, path: Path) -> Path:
    root, path = root.resolve(), path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise Round3Error(f"path escapes root: {path}") from exc
    return path


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Round3Error(f"invalid JSON: {path}: {exc}") from exc


def json_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_shape(item) for item in value]
    return type(value).__name__


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def ejs_tokens(value: str) -> list[str]:
    return re.findall(r"<%[\s\S]*?%>", value)


def build_help(evidence: Path, upstream: Path) -> tuple[bytes, dict[str, Any], bytes]:
    rows = read_tsv(evidence / "official_help_stable_reuse.tsv")
    if len(rows) != ROW_COUNTS["official_help_stable_reuse.tsv"]:
        raise Round3Error(f"help row count drift: {len(rows)}")
    source = upstream / "resource/image_web/_json/help.json"
    source_bytes = source.read_bytes()
    original = load_json(source)
    result = json.loads(json.dumps(original, ensure_ascii=False))
    groups = {str(group["type"]): group for group in result["help"]}
    seen: set[str] = set()
    for row in rows:
        key = row["stable_key"]
        if key in seen:
            raise Round3Error(f"duplicate help key: {key}")
        seen.add(key)
        group = groups.get(row["group_type"])
        if group is None:
            raise Round3Error(f"missing help group: {row['group_type']}")
        if row["col_id"]:
            target = {str(item["id"]): item for item in group["cols"]}.get(row["col_id"])
            if target is None:
                raise Round3Error(f"missing help entry: {row['group_type']}/{row['col_id']}")
        else:
            target = group
        field = row["field"]
        if target.get(field) != row["upstream_value"]:
            raise Round3Error(f"help before-value drift: {key}")
        target[field] = row["official_cn_value"]
    if json_shape(original) != json_shape(result):
        raise Round3Error("help JSON structure changed")
    return json_bytes(result), {
        "source": str(source),
        "records": len(rows),
        "validation": "type/id/field before gate; JSON shape preserved",
    }, source_bytes


def build_overview(evidence: Path, upstream: Path) -> tuple[bytes, dict[str, Any], bytes]:
    rows = read_tsv(evidence / "wiki_puella_historia_overview.tsv")
    if len(rows) != ROW_COUNTS["wiki_puella_historia_overview.tsv"]:
        raise Round3Error(f"overview row count drift: {len(rows)}")
    source = upstream / "resource/image_web/_json/puellaHistoria/overview.json"
    source_bytes = source.read_bytes()
    original = load_json(source)
    result = json.loads(json.dumps(original, ensure_ascii=False))
    seen: set[str] = set()
    for row in rows:
        key = row["stable_key"]
        if key in seen:
            raise Round3Error(f"duplicate overview key: {key}")
        seen.add(key)
        item = result["overviewList"].get(row["overview_id"])
        if item is None or item.get(row["field"]) != row["japanese_value"]:
            raise Round3Error(f"overview before-value drift: {key}")
        item[row["field"]] = row["wiki_cn_value"]
    if json_shape(original) != json_shape(result):
        raise Round3Error("overview JSON structure changed")
    return json_bytes(result), {
        "source": str(source),
        "records": len(rows),
        "validation": "overview id/field before gate; JSON shape preserved",
    }, source_bytes


def build_raid(evidence: Path, official: Path) -> tuple[bytes, dict[str, Any], bytes]:
    rows = read_tsv(evidence / "official_event_raid_messages.tsv")
    if len(rows) != ROW_COUNTS["official_event_raid_messages.tsv"]:
        raise Round3Error(f"Raid row count drift: {len(rows)}")
    source = official / "js/event/raid/EventRaidMessage.json"
    source_bytes = source.read_bytes()
    records = load_json(source)
    if not isinstance(records, list) or len(records) != len(rows):
        raise Round3Error("Raid source schema/count drift")
    for row, record in zip(rows, records):
        values = (
            str(record.get("group", "")),
            str(record.get("type", "")),
            str(record.get("threshold", "")),
            str(record.get("force", "")).lower(),
            str(record.get("text", "")),
        )
        expected = (
            row["group"], row["type"], row["threshold"], row["force"], row["official_cn_text"]
        )
        if values != expected:
            raise Round3Error(f"Raid evidence drift at index {row['index']}")
    return source_bytes, {
        "source": str(source),
        "records": len(rows),
        "validation": "official schema and 21 records exact",
    }, source_bytes


def build_templates(
    evidence: Path, upstream: Path
) -> dict[str, tuple[bytes, dict[str, Any], bytes]]:
    rows = read_tsv(evidence / "official_samepath_static_reuse.tsv")
    if len(rows) != ROW_COUNTS["official_samepath_static_reuse.tsv"]:
        raise Round3Error(f"template row count drift: {len(rows)}")
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        target = row["target_path"].replace("\\", "/")
        if target not in TARGETS:
            raise Round3Error(f"template target outside allowlist: {target}")
        grouped.setdefault(target, []).append(row)
    outputs = {}
    for target, target_rows in grouped.items():
        source = upstream / target.removeprefix("magica/")
        source_bytes = source.read_bytes()
        original = source_bytes.decode("utf-8-sig")
        result = original
        # Contained literals are handled by replacing the longest value first.
        for row in sorted(target_rows, key=lambda item: len(item["upstream_value"]), reverse=True):
            before = row["upstream_value"]
            if result.count(before) != 1:
                raise Round3Error(f"template before-value count drift: {target}: {before!r}")
            result = result.replace(before, row["official_cn_value"], 1)
        if ejs_tokens(original) != ejs_tokens(result):
            raise Round3Error(f"EJS token drift: {target}")
        outputs[target] = result.encode("utf-8"), {
            "source": str(source),
            "records": len(target_rows),
            "validation": "literal count=1 after longest-first ordering; EJS tokens preserved",
        }, source_bytes
    return outputs


def build_outputs(evidence: Path, upstream: Path, official: Path):
    outputs = {
        "magica/resource/image_web/_json/help.json": build_help(evidence, upstream),
        "magica/resource/image_web/_json/puellaHistoria/overview.json": build_overview(
            evidence, upstream
        ),
        "magica/js/event/raid/EventRaidMessage.json": build_raid(evidence, official),
    }
    outputs.update(build_templates(evidence, upstream))
    if set(outputs) != set(TARGETS):
        raise Round3Error(
            f"target set drift: missing={sorted(set(TARGETS)-set(outputs))}, "
            f"extra={sorted(set(outputs)-set(TARGETS))}"
        )
    return outputs


def prepared_file(state: Path, target: str) -> Path:
    return under(state / "prepared", state / "prepared" / target)


def source_file(state: Path, target: str) -> Path:
    return under(state / "sources", state / "sources" / target)


def manifest_file(state: Path) -> Path:
    return state / "round3_apply_manifest.json"


def rollback_file(state: Path) -> Path:
    return state / "round3_rollback.json"


def rollback_plan_file(state: Path) -> Path:
    return state / "round3_rollback_plan.json"


def prepare_verification_file(state: Path) -> Path:
    return state / "round3_prepare_verification.json"


def prepare(repo: Path, evidence: Path, state: Path, upstream: Path, official: Path):
    outputs = build_outputs(evidence, upstream, official)
    temp = state / f".prepare-{os.getpid()}"
    if temp.exists():
        shutil.rmtree(temp)
    entries = []
    try:
        for target in sorted(outputs):
            expected, metadata, source_bytes = outputs[target]
            product_target = under(repo, repo / target)
            if product_target.exists() and not product_target.is_file():
                raise Round3Error(f"product target is not a file: {target}")
            if product_target.is_file() and product_target.read_bytes() != expected:
                raise Round3Error(f"unexpected pre-existing product target: {target}")
            target_state = "already-expected" if product_target.is_file() else "absent"
            (temp / "prepared" / target).parent.mkdir(parents=True, exist_ok=True)
            (temp / "prepared" / target).write_bytes(expected)
            (temp / "sources" / target).parent.mkdir(parents=True, exist_ok=True)
            (temp / "sources" / target).write_bytes(source_bytes)
            entries.append(
                {
                    "target": target,
                    "expected_size": len(expected),
                    "source_size": len(source_bytes),
                    "target_state_at_prepare": target_state,
                    **metadata,
                }
            )
        state.mkdir(parents=True, exist_ok=True)
        for name in ("prepared", "sources"):
            destination = state / name
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(temp / name, destination)
        result = {
            "schema": 1,
            "mode": "prepared-not-applied",
            "repo_root": str(repo.resolve()),
            "authority_records": 275,
            "target_count": len(entries),
            "targets": entries,
            "product_tree_writes": 0,
        }
        write_json(manifest_file(state), result)
        write_json(
            prepare_verification_file(state),
            {
                "status": "pass",
                "authority_records": 275,
                "target_count": len(entries),
                "product_tree_writes": 0,
                "targets": [
                    {
                        "target": item["target"],
                        "source_size": item["source_size"],
                        "expected_size": item["expected_size"],
                        "target_state": item["target_state_at_prepare"],
                        "validation": item["validation"],
                    }
                    for item in entries
                ],
            },
        )
        write_json(
            rollback_plan_file(state),
            {
                "schema": 1,
                "status": "prepared-not-applied",
                "target_count": len(entries),
                "targets": [
                    {
                        "target": item["target"],
                        "before_exists": item["target_state_at_prepare"] == "already-expected",
                        "rollback_action": (
                            "preserve-pre-existing-exact-file"
                            if item["target_state_at_prepare"] == "already-expected"
                            else "remove-file-created-by-apply"
                        ),
                    }
                    for item in entries
                ],
            },
        )
        return result
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def load_manifest(state: Path, repo: Path):
    path = manifest_file(state)
    if not path.is_file():
        raise Round3Error(f"missing manifest; run --prepare: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if Path(manifest.get("repo_root", "")).resolve() != repo.resolve():
        raise Round3Error("manifest repo-root mismatch")
    listed = [item.get("target") for item in manifest.get("targets", [])]
    if len(listed) != len(TARGETS) or set(listed) != set(TARGETS):
        raise Round3Error("manifest target-set mismatch")
    for item in manifest["targets"]:
        expected = prepared_file(state, item["target"]).read_bytes()
        source = source_file(state, item["target"]).read_bytes()
        if len(expected) != item["expected_size"] or len(source) != item["source_size"]:
            raise Round3Error(f"prepared artifact size drift: {item['target']}")
    return manifest


def verify_sources(state: Path, manifest: dict[str, Any]) -> None:
    for item in manifest["targets"]:
        source = Path(item["source"])
        if not source.is_file() or source.read_bytes() != source_file(state, item["target"]).read_bytes():
            raise Round3Error(f"source byte drift: {item['target']}")


def verify_layered_help_authority(repo: Path, evidence: Path, expected: bytes) -> int:
    """Allow later reviewed help entries while protecting all official fields."""
    actual = load_json(repo / "magica/resource/image_web/_json/help.json")
    prepared = json.loads(expected.decode("utf-8-sig"))
    if json_shape(actual) != json_shape(prepared):
        raise Round3Error("layered help JSON structure changed")
    groups = {str(group["type"]): group for group in actual["help"]}
    rows = read_tsv(evidence / "official_help_stable_reuse.tsv")
    if len(rows) != ROW_COUNTS["official_help_stable_reuse.tsv"]:
        raise Round3Error(f"help row count drift: {len(rows)}")
    for row in rows:
        group = groups.get(row["group_type"])
        if group is None:
            raise Round3Error(f"layered help group missing: {row['group_type']}")
        target = group
        if row["col_id"]:
            target = {str(item["id"]): item for item in group["cols"]}.get(row["col_id"])
        if target is None or target.get(row["field"]) != row["official_cn_value"]:
            raise Round3Error(f"layered help authority drift: {row['stable_key']}")
    return len(rows)


def verify_product(
    repo: Path,
    state: Path,
    manifest: dict[str, Any],
    evidence: Path = DEFAULT_EVIDENCE,
):
    rows = []
    for item in manifest["targets"]:
        target = under(repo, repo / item["target"])
        expected = prepared_file(state, item["target"]).read_bytes()
        if not target.is_file():
            raise Round3Error(f"product target absent: {item['target']}")
        actual = target.read_bytes()
        if actual == expected:
            status, protected_records = "exact", item["records"]
        elif item["target"] == "magica/resource/image_web/_json/help.json":
            protected_records = verify_layered_help_authority(repo, evidence, expected)
            status = "layered-exact-authority-fields"
        else:
            raise Round3Error(f"product target byte-different: {item['target']}")
        if target.suffix == ".json":
            json.loads(actual.decode("utf-8-sig"))
        rows.append({
            "target": item["target"], "size": len(actual), "status": status,
            "protected_records": protected_records,
        })
    return {"status": "pass", "target_count": len(rows), "targets": rows}


def restore_before(repo: Path, records: Iterable[dict[str, Any]]) -> None:
    for record in records:
        target = under(repo, repo / record["target"])
        if record["before_exists"]:
            atomic_write(target, base64.b64decode(record["before_base64"]))
        else:
            try:
                target.unlink()
            except FileNotFoundError:
                pass


def restore_after(repo: Path, state: Path, records: Iterable[dict[str, Any]]) -> None:
    for record in records:
        atomic_write(
            under(repo, repo / record["target"]), prepared_file(state, record["target"]).read_bytes()
        )


def apply(repo: Path, state: Path, fail_after: int | None = None):
    manifest = load_manifest(state, repo)
    verify_sources(state, manifest)
    records = []
    for item in manifest["targets"]:
        target = under(repo, repo / item["target"])
        expected = prepared_file(state, item["target"]).read_bytes()
        if target.exists() and not target.is_file():
            raise Round3Error(f"target is not a file: {item['target']}")
        before = target.read_bytes() if target.is_file() else b""
        if target.is_file() and before != expected:
            raise Round3Error(f"unexpected pre-existing target: {item['target']}")
        records.append(
            {
                "target": item["target"],
                "before_exists": target.is_file(),
                "before_base64": base64.b64encode(before).decode("ascii") if target.is_file() else None,
                "before_size": len(before) if target.is_file() else None,
                "after_size": len(expected),
            }
        )
    receipt = {"schema": 1, "status": "applying", "repo_root": str(repo), "targets": records}
    write_json(rollback_file(state), receipt)
    written = []
    try:
        for record in records:
            if not record["before_exists"]:
                atomic_write(
                    under(repo, repo / record["target"]),
                    prepared_file(state, record["target"]).read_bytes(),
                )
                written.append(record)
                if fail_after is not None and len(written) >= fail_after:
                    raise OSError("synthetic apply failure")
        verification = verify_product(repo, state, manifest)
    except BaseException:
        restore_before(repo, reversed(written))
        receipt["status"] = "apply-failed-restored"
        write_json(rollback_file(state), receipt)
        raise
    receipt["status"] = "applied"
    write_json(rollback_file(state), receipt)
    manifest.update(mode="applied-and-verified", product_tree_writes=len(written), verification=verification)
    write_json(manifest_file(state), manifest)
    return verification


def rollback(repo: Path, state: Path, fail_after: int | None = None):
    manifest = load_manifest(state, repo)
    path = rollback_file(state)
    if not path.is_file():
        raise Round3Error("missing rollback receipt")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("status") not in ("applied", "rollback-failed-restored-to-applied"):
        raise Round3Error(f"rollback receipt state is {receipt.get('status')!r}")
    if Path(receipt.get("repo_root", "")).resolve() != repo.resolve():
        raise Round3Error("rollback repo-root mismatch")
    records = receipt.get("targets", [])
    if {item.get("target") for item in records} != set(TARGETS):
        raise Round3Error("rollback target-set mismatch")
    verify_product(repo, state, manifest)
    restored = []
    try:
        for record in records:
            restore_before(repo, [record])
            restored.append(record)
            if fail_after is not None and len(restored) >= fail_after:
                raise OSError("synthetic rollback failure")
    except BaseException:
        restore_after(repo, state, restored)
        receipt["status"] = "rollback-failed-restored-to-applied"
        write_json(path, receipt)
        raise
    receipt["status"] = "rolled-back"
    write_json(path, receipt)
    manifest.update(mode="rolled-back", product_tree_writes=0)
    write_json(manifest_file(state), manifest)
    for record in records:
        target = under(repo, repo / record["target"])
        if record["before_exists"]:
            if target.read_bytes() != base64.b64decode(record["before_base64"]):
                raise Round3Error(f"rollback verification failed: {record['target']}")
        elif target.exists():
            raise Round3Error(f"rollback failed to remove: {record['target']}")
    return {"status": "rolled-back", "target_count": len(records)}


def parse_args(argv: list[str]):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "apply", "verify", "rollback"):
        mode.add_argument(f"--{name}", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--upstream-root", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--official-root", type=Path, default=DEFAULT_OFFICIAL)
    parser.add_argument("--test-fail-after", type=int, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo, evidence = args.repo_root.resolve(), args.evidence_dir.resolve()
    state = (args.state_dir or evidence / "runtime").resolve()
    try:
        if args.test_fail_after is not None and os.environ.get("ROUND3_TEST_MODE") != "1":
            raise Round3Error("synthetic failure option is test-only")
        if args.prepare:
            result = prepare(repo, evidence, state, args.upstream_root, args.official_root)
        elif args.apply:
            result = apply(repo, state, args.test_fail_after)
        elif args.verify:
            manifest = load_manifest(state, repo)
            verify_sources(state, manifest)
            result = verify_product(repo, state, manifest)
        else:
            result = rollback(repo, state, args.test_fail_after)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, Round3Error) as exc:
        print(f"round3: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
