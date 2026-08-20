#!/usr/bin/env python3
"""Apply reviewed round-3 visible text to a fixed eight-file allowlist."""

from __future__ import annotations

import argparse, csv, json, os, re, shutil, sys, tempfile
from pathlib import Path
from typing import Any, Iterable

SCRIPT = Path(__file__).resolve()
DEFAULT_REPO = SCRIPT.parents[1]
DEFAULT_REVIEW = DEFAULT_REPO / (
    "magica/research/totentanz-full-localization-20260817/"
    "manual-visible-round3/manual_translation_round3.tsv"
)
ALLOWED = {
    "magica/resource/image_web/_json/help.json": "help",
    "magica/resource/image_web/_json/SecondPartLastInfo.json": "second",
    "magica/js/event/EventWalpurgis/json/stamp/commentList.json": "stamp",
    "magica/css/patrol/PatrolDeckView.css": "css",
    "magica/css/regularEvent/groupBattle/RegularEventGroupBattleRanking.css": "css",
    "magica/css/regularEvent/groupBattle/RegularEventGroupBattleUser.css": "css",
    "magica/json/announcements/announcements.json": "announcement",
    "magica/json/event_banner/event_banner.json": "banner",
}
LAYERED_PRODUCT_TRANSFORMS = {
    "magica/resource/image_web/_json/help.json": (
        "属性相性", "属性克制", 1,
    ),
    "magica/css/regularEvent/groupBattle/RegularEventGroupBattleRanking.css": (
        "必要GP", "所需GP", 1,
    ),
    "magica/css/regularEvent/groupBattle/RegularEventGroupBattleUser.css": (
        "必要GP", "所需GP", 1,
    ),
}
COLUMNS = (
    "item_id", "target_path", "stable_key", "field", "source_text", "final_cn",
    "upstream_source_path",
)


class GateError(RuntimeError):
    pass


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        try: os.unlink(temp)
        except FileNotFoundError: pass
        raise


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def confined(root: Path, path: Path) -> Path:
    root, path = root.resolve(), path.resolve()
    try: path.relative_to(root)
    except ValueError as exc: raise GateError(f"path escapes root: {path}") from exc
    return path


def source_allowed(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try: path.resolve().relative_to(root.resolve()); return True
        except ValueError: pass
    return False


def read_rows(review: Path) -> tuple[bytes, list[dict[str, str]]]:
    if not review.is_file(): raise GateError(f"review TSV missing: {review}")
    raw = review.read_bytes()
    with review.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = sorted(set(COLUMNS) - set(reader.fieldnames or []))
        if missing: raise GateError(f"review TSV missing columns: {missing}")
        rows = list(reader)
    if not rows: raise GateError("review TSV is empty")
    ids, keys = set(), set()
    for number, row in enumerate(rows, 2):
        row["target_path"] = row["target_path"].replace("\\", "/")
        if not row["item_id"] or row["item_id"] in ids:
            raise GateError(f"blank/duplicate item_id at row {number}")
        ids.add(row["item_id"])
        if row["target_path"] not in ALLOWED:
            raise GateError(f"target outside allowlist at row {number}: {row['target_path']}")
        key = (row["target_path"], row["stable_key"])
        if not row["stable_key"] or key in keys:
            raise GateError(f"blank/duplicate stable key at row {number}: {key}")
        keys.add(key)
        if not row["final_cn"]: raise GateError(f"blank final_cn at row {number}")
    return raw, rows


def shape(value: Any) -> Any:
    if isinstance(value, dict): return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list): return [shape(item) for item in value]
    return type(value).__name__


def value_gate(before: str, after: str, item: str) -> None:
    if re.findall(r"<[^>]+>", before) != re.findall(r"<[^>]+>", after):
        raise GateError(f"HTML tag/attribute drift: {item}")
    pattern = r"<%[\s\S]*?%>|\\x[0-9A-Fa-f]{2}|%[0-9$.*+-]*[A-Za-z]|\{\{[^{}]+\}\}"
    if re.findall(pattern, before) != re.findall(pattern, after):
        raise GateError(f"format/EJS token drift: {item}")
    if before.count("＠") != after.count("＠"):
        raise GateError(f"dialogue separator drift: {item}")


def locate(document: Any, kind: str, row: dict[str, str]) -> tuple[Any, str]:
    key, field, target, parsed = row["stable_key"], row["field"], None, ""
    if kind == "help":
        parts = key.split("/")
        if len(parts) == 3 and parts[0] == "help" and parts[2] == "@title":
            parsed = "title"; target = next((x for x in document.get("help", []) if str(x.get("type")) == parts[1]), None)
        elif len(parts) == 4 and parts[0] == "help":
            parsed = parts[3]
            group = next((x for x in document.get("help", []) if str(x.get("type")) == parts[1]), None)
            if group is not None: target = next((x for x in group.get("cols", []) if str(x.get("id")) == parts[2]), None)
        else: raise GateError(f"invalid help key: {key}")
    elif kind == "second":
        parts = key.split("/"); info = document.get("secondPartLastInfo", {}).get("enemyInfo", {})
        if parts == ["secondPartLastInfo", "enemyInfo", "name"]: target, parsed = info, "name"
        elif len(parts) == 5 and parts[:3] == ["secondPartLastInfo", "enemyInfo", "list"]:
            try: target = info.get("list", [])[int(parts[3])]
            except (ValueError, IndexError): target = None
            parsed = parts[4]
        else: raise GateError(f"invalid SecondPart key: {key}")
    elif kind == "stamp":
        match = re.fullmatch(r"commentList/(\d+)", key)
        if not match or field != "comment": raise GateError(f"invalid stamp key: {key}")
        values, index = document.get("commentList", []), int(match.group(1))
        if index >= len(values): raise GateError(f"stamp key absent: {key}")
        return values, str(index)
    elif kind in ("announcement", "banner"):
        id_field = "id" if kind == "announcement" else "bannerId"
        match = re.fullmatch(rf"{id_field}=([^/]+)/([^/]+)", key)
        if not match: raise GateError(f"invalid {kind} key: {key}")
        expected_id, parsed = match.groups()
        matches = [x for x in document if str(x.get(id_field)) == expected_id]
        target = matches[0] if len(matches) == 1 else None
    if target is None or parsed != field or field not in target:
        raise GateError(f"stable key/field absent: {key}/{field}")
    return target, field


def get_value(container: Any, field: str) -> Any:
    return container[int(field)] if isinstance(container, list) else container[field]


def set_value(container: Any, field: str, value: str) -> None:
    if isinstance(container, list): container[int(field)] = value
    else: container[field] = value


def build_css(base: bytes, rows: list[dict[str, str]]) -> tuple[bytes, str]:
    original = base.decode("utf-8-sig"); result = original
    for row in rows:
        if row["field"] != "content" or not row["stable_key"].startswith("css-content/"):
            raise GateError(f"invalid CSS key/field: {row['item_id']}")
        value_gate(row["source_text"], row["final_cn"], row["item_id"])
        pattern = re.compile(rf"(content\s*:\s*)([\"'])({re.escape(row['source_text'])})(\2)")
        matches = list(pattern.finditer(result))
        if len(matches) != 1: raise GateError(f"CSS occurrence drift: {row['item_id']}: {len(matches)}")
        quote = matches[0].group(2)
        translated = row["final_cn"].replace("\\", "\\\\").replace(quote, "\\" + quote)
        result = pattern.sub(lambda m: m.group(1) + quote + translated + quote, result, count=1)
    skeleton = lambda text: re.sub(r"(content\s*:\s*)([\"']).*?\2", r"\1\2<CN>\2", text)
    if skeleton(original) != skeleton(result) or result.count("{") != result.count("}"):
        raise GateError(f"CSS structure drift: {rows[0]['target_path']}")
    return result.encode(), "CSS content only; skeleton/braces preserved"


def build_json(kind: str, base: bytes, rows: list[dict[str, str]]) -> tuple[bytes, str]:
    try: original = json.loads(base.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc: raise GateError(f"invalid JSON base: {rows[0]['target_path']}") from exc
    result = json.loads(json.dumps(original, ensure_ascii=False))
    for row in rows:
        container, field = locate(result, kind, row); before = get_value(container, field)
        if not isinstance(before, str) or before != row["source_text"]: raise GateError(f"before-value drift: {row['item_id']}")
        value_gate(before, row["final_cn"], row["item_id"]); set_value(container, field, row["final_cn"])
    if shape(original) != shape(result): raise GateError(f"JSON shape drift: {rows[0]['target_path']}")
    return (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), "JSON stable keys; shape/HTML/tokens preserved"


def area(state: Path, name: str, target: str) -> Path:
    return confined(state / name, state / name / target)


def manifest_file(state: Path) -> Path: return state / "manual_round3_manifest.json"
def rollback_file(state: Path) -> Path: return state / "manual_round3_rollback.json"


def layered_product_bytes(target: str, prepared: bytes) -> bytes | None:
    """Return the sole accepted post-round3 product layer for known CSS files."""
    transform = LAYERED_PRODUCT_TRANSFORMS.get(target)
    if transform is None:
        return None
    before, after, expected_count = transform
    before_bytes, after_bytes = before.encode(), after.encode()
    if prepared.count(before_bytes) != expected_count or prepared.count(after_bytes) != 0:
        raise GateError(f"layered transform baseline drift: {target}")
    result = prepared.replace(before_bytes, after_bytes, expected_count)
    if result.count(before_bytes) != 0 or result.count(after_bytes) != expected_count:
        raise GateError(f"layered transform result drift: {target}")
    return result


def prepare(repo: Path, review: Path, state: Path, roots: list[Path]):
    review_bytes, rows = read_rows(review); grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows: grouped.setdefault(row["target_path"], []).append(row)
    temp = state / f".prepare-{os.getpid()}"; entries = []
    if temp.exists(): shutil.rmtree(temp)
    try:
        for target in sorted(grouped):
            target_rows = grouped[target]; sources = {Path(x["upstream_source_path"]).resolve() for x in target_rows}
            if len(sources) != 1: raise GateError(f"per-target source conflict: {target}")
            source = next(iter(sources))
            if not source_allowed(source, roots) or not source.is_file(): raise GateError(f"source outside roots or absent: {source}")
            source_bytes = source.read_bytes(); product = confined(repo, repo / target)
            if product.exists() and not product.is_file(): raise GateError(f"product target is not a file: {target}")
            base = product.read_bytes() if product.is_file() else source_bytes
            expected, validation = (build_css(base, target_rows) if ALLOWED[target] == "css" else build_json(ALLOWED[target], base, target_rows))
            for name, data in (
                ("prepared", expected), ("sources", source_bytes), ("bases", base),
                ("checks/prepared", expected), ("checks/sources", source_bytes),
                ("checks/bases", base),
            ):
                path = temp / name / target; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            entries.append({"target": target, "kind": ALLOWED[target], "item_count": len(target_rows), "item_ids": [x["item_id"] for x in target_rows], "source": str(source), "source_size": len(source_bytes), "base_size": len(base), "expected_size": len(expected), "base_exists": product.is_file(), "validation": validation})
        state.mkdir(parents=True, exist_ok=True)
        for name in ("prepared", "sources", "bases", "checks"):
            destination = state / name
            if destination.exists(): shutil.rmtree(destination)
            os.replace(temp / name, destination)
        manifest = {"schema": 1, "mode": "prepared-not-applied", "repo_root": str(repo), "review_tsv": str(review), "review_size": len(review_bytes), "item_count": len(rows), "target_count": len(entries), "targets": entries, "product_tree_writes": 0}
        atomic_write(state / "review.tsv.snapshot", review_bytes)
        atomic_write(state / "review.tsv.checkpoint", review_bytes)
        write_json(manifest_file(state), manifest)
        write_json(state / "manual_round3_prepare_verification.json", {"status": "pass", "item_count": len(rows), "target_count": len(entries), "product_tree_writes": 0, "targets": entries})
        write_json(state / "manual_round3_rollback_plan.json", {"status": "prepared-not-applied", "targets": [{"target": x["target"], "before_exists": x["base_exists"], "rollback_action": "restore-base" if x["base_exists"] else "remove-created"} for x in entries]})
        return manifest
    finally:
        if temp.exists(): shutil.rmtree(temp)


def load_state(repo: Path, review: Path, state: Path):
    path = manifest_file(state)
    if not path.is_file(): raise GateError(f"missing prepared state: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if Path(manifest.get("repo_root", "")).resolve() != repo.resolve(): raise GateError("repo-root drift")
    review_snapshot = state / "review.tsv.snapshot"
    review_checkpoint = state / "review.tsv.checkpoint"
    if (
        not review.is_file() or not review_snapshot.is_file() or not review_checkpoint.is_file()
        or review_snapshot.read_bytes() != review_checkpoint.read_bytes()
        or review.read_bytes() != review_snapshot.read_bytes()
    ):
        raise GateError("review TSV/checkpoint drift")
    targets = [x.get("target") for x in manifest.get("targets", [])]
    if len(targets) != len(set(targets)) or not set(targets).issubset(ALLOWED): raise GateError("prepared target set invalid")
    for item in manifest["targets"]:
        target = item["target"]; source = Path(item["source"])
        source_snapshot = area(state, "sources", target)
        source_checkpoint = area(state, "checks/sources", target)
        prepared = area(state, "prepared", target)
        prepared_checkpoint = area(state, "checks/prepared", target)
        base = area(state, "bases", target)
        base_checkpoint = area(state, "checks/bases", target)
        if not all(x.is_file() for x in (source_snapshot, source_checkpoint, prepared, prepared_checkpoint, base, base_checkpoint)):
            raise GateError(f"prepared checkpoint missing: {target}")
        if source_snapshot.read_bytes() != source_checkpoint.read_bytes():
            raise GateError(f"source snapshot drift: {target}")
        if prepared.read_bytes() != prepared_checkpoint.read_bytes():
            raise GateError(f"prepared snapshot drift: {target}")
        if base.read_bytes() != base_checkpoint.read_bytes():
            raise GateError(f"base snapshot drift: {target}")
        if not source.is_file() or source.read_bytes() != source_snapshot.read_bytes():
            raise GateError(f"source drift: {target}")
        if len(prepared.read_bytes()) != item["expected_size"] or len(base.read_bytes()) != item["base_size"]:
            raise GateError(f"prepared/base size drift: {target}")
    return manifest


def verify_product(repo: Path, state: Path, manifest: dict[str, Any]):
    rows = []
    for item in manifest["targets"]:
        target = confined(repo, repo / item["target"]); expected = area(state, "prepared", item["target"]).read_bytes()
        if not target.is_file(): raise GateError(f"product drift: {item['target']}")
        current = target.read_bytes(); layered = layered_product_bytes(item["target"], expected)
        if current == expected:
            status = "exact-manual-round3"
        elif layered is not None and current == layered:
            status = "layered-round4-visible-closure"
        else:
            raise GateError(f"product drift: {item['target']}")
        rows.append({
            "target": item["target"],
            "status": status,
            "size": len(current),
            "manual_round3_bytes_preserved": True,
            "layered_change": (
                "→".join(LAYERED_PRODUCT_TRANSFORMS[item["target"]][:2])
                if status == "layered-round4-visible-closure" else None
            ),
        })
    return {"status": "pass", "target_count": len(rows), "targets": rows}


def restore_base(repo: Path, state: Path, records: Iterable[dict[str, Any]]) -> None:
    for record in records:
        target = confined(repo, repo / record["target"])
        if record["before_exists"]: atomic_write(target, area(state, "bases", record["target"]).read_bytes())
        else:
            try: target.unlink()
            except FileNotFoundError: pass


def apply(repo: Path, review: Path, state: Path, fail_after: int | None = None):
    manifest = load_state(repo, review, state); records = []
    for item in manifest["targets"]:
        target = confined(repo, repo / item["target"]); base = area(state, "bases", item["target"]).read_bytes(); expected = area(state, "prepared", item["target"]).read_bytes(); current = target.read_bytes() if target.is_file() else None
        layered = layered_product_bytes(item["target"], expected)
        allowed_states = (None, base, expected) if layered is None else (None, base, expected, layered)
        if current not in allowed_states: raise GateError(f"unexpected product state: {item['target']}")
        if item["base_exists"] and current is None: raise GateError(f"base disappeared: {item['target']}")
        accepted_applied_states = (expected,) if layered is None else (expected, layered)
        if not item["base_exists"] and current is not None and current not in accepted_applied_states:
            raise GateError(f"unplanned target appeared: {item['target']}")
        records.append({"target": item["target"], "before_exists": item["base_exists"]})
    receipt = {"schema": 1, "status": "applying", "repo_root": str(repo), "targets": records}; write_json(rollback_file(state), receipt); written = []
    try:
        for record in records:
            target = confined(repo, repo / record["target"]); expected = area(state, "prepared", record["target"]).read_bytes()
            layered = layered_product_bytes(record["target"], expected)
            current = target.read_bytes() if target.is_file() else None
            accepted_applied_states = (expected,) if layered is None else (expected, layered)
            if current not in accepted_applied_states:
                atomic_write(target, expected); written.append(record)
                if fail_after is not None and len(written) >= fail_after: raise OSError("synthetic write failure")
        verification = verify_product(repo, state, manifest)
    except BaseException:
        restore_base(repo, state, reversed(written)); receipt["status"] = "apply-failed-restored"; write_json(rollback_file(state), receipt); raise
    receipt["status"] = "applied"; write_json(rollback_file(state), receipt); manifest.update(mode="applied-and-verified", product_tree_writes=len(written), verification=verification); write_json(manifest_file(state), manifest); return verification


def rollback(repo: Path, review: Path, state: Path):
    manifest = load_state(repo, review, state); receipt = json.loads(rollback_file(state).read_text(encoding="utf-8"))
    if receipt.get("status") != "applied" or Path(receipt.get("repo_root", "")).resolve() != repo: raise GateError("rollback state/root mismatch")
    records = receipt["targets"]
    if {x["target"] for x in records} != {x["target"] for x in manifest["targets"]}: raise GateError("rollback target set drift")
    verify_product(repo, state, manifest); restored = []
    try:
        for record in records: restore_base(repo, state, [record]); restored.append(record)
    except BaseException:
        for record in restored: atomic_write(confined(repo, repo / record["target"]), area(state, "prepared", record["target"]).read_bytes())
        receipt["status"] = "rollback-failed-restored-to-applied"; write_json(rollback_file(state), receipt); raise
    receipt["status"] = "rolled-back"; write_json(rollback_file(state), receipt); manifest.update(mode="rolled-back", product_tree_writes=0); write_json(manifest_file(state), manifest)
    return {"status": "rolled-back", "target_count": len(records)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); modes = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "apply", "verify", "rollback"): modes.add_argument(f"--{name}", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO); parser.add_argument("--review-tsv", type=Path, default=DEFAULT_REVIEW); parser.add_argument("--state-dir", type=Path); parser.add_argument("--allowed-source-root", type=Path, action="append"); parser.add_argument("--test-fail-after", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv); repo, review = args.repo_root.resolve(), args.review_tsv.resolve(); state = (args.state_dir or review.parent / "runtime").resolve(); roots = args.allowed_source_root or [Path(r"A:\totentanz-frontend"), Path(r"A:\magicaOLD")]
    try:
        if args.test_fail_after is not None and os.environ.get("MANUAL_ROUND3_TEST_MODE") != "1": raise GateError("synthetic failure is test-only")
        result = prepare(repo, review, state, roots) if args.prepare else apply(repo, review, state, args.test_fail_after) if args.apply else verify_product(repo, state, load_state(repo, review, state)) if args.verify else rollback(repo, review, state)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (OSError, UnicodeError, json.JSONDecodeError, GateError) as exc:
        print(f"manual-round3: {exc}", file=sys.stderr); return 2


if __name__ == "__main__": raise SystemExit(main())
