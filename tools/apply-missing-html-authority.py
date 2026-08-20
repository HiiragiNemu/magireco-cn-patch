#!/usr/bin/env python3
"""Materialize reviewed HTML dependencies without changing existing files."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import tempfile
from pathlib import Path


REPO_DEFAULT = Path(__file__).resolve().parents[1]
SOURCE_DEFAULT = Path(r"A:\magicaOLD")
STATE_REL = Path(
    "magica/research/totentanz-full-localization-20260817/"
    "missing-html-authority-20260819/runtime"
)
CURRENT_SOURCE_REL = Path(
    "magica/research/totentanz-full-localization-20260817/"
    "missing-html-authority-20260819/current-upstream-source"
)
ROUND6_MANIFEST_REL = Path(
    "magica/research/totentanz-full-localization-20260817/"
    "visible-closure-round6/runtime/manifest.json"
)
ROUND6_ALLOWED_SUPERSESSIONS = {
    "magica/template/quest/MainQuest.html",
    "magica/template/quest/SubQuest.html",
}


SPECS = [
    {
        "path": "template/arena/ArenaCurePop.html",
        "source_kind": "current-upstream",
        "source_url": "https://raw.githubusercontent.com/Puella-Care/en-text/5c149cb829ea3d8ee5a71cac174419fb45a1fdbc/magica/template/arena/ArenaCurePop.html",
        "required": ['id="popupBp"', 'id="bpTextWrap"', 'id="bpImageWrap"', '<%= quantity %>'],
        "replacements": [
            ('You have MAX BP.', 'BP已达到最大值。', 'official-cn'),
            ('You have no BP Potions.', '无BP回复药。', 'official-cn'),
            ('Use a BP Potion to Restore your BP?', '要使用BP回复药回复全部BP吗？', 'official-cn'),
            ('BP Potion', 'BP回复药', 'official-cn'),
            ('Stock:', '持有数', 'official-cn'),
            ('Restore', '回复', 'official-cn'),
        ],
        "official": [],
    },
    {
        "path": "template/config/deleteUserData/popupComplete.html",
        "source_kind": "current-upstream",
        "source_url": "https://raw.githubusercontent.com/Puella-Care/en-text/5c149cb829ea3d8ee5a71cac174419fb45a1fdbc/magica/template/config/deleteUserData/popupComplete.html",
        "required": [],
        "replacements": [('Player Data has been deleted.', '玩家数据已删除。')],
        "official": [],
    },
    {
        "path": "template/config/deleteUserData/popupConfirm.html",
        "source_kind": "current-upstream",
        "source_url": "https://raw.githubusercontent.com/Puella-Care/en-text/5c149cb829ea3d8ee5a71cac174419fb45a1fdbc/magica/template/config/deleteUserData/popupConfirm.html",
        "required": ["<span class='c_red'>"],
        "replacements": [
            ('Are you sure you want to delete your player data stored on the server?', '是否删除保存在服务器上的玩家数据？'),
            ('※Even if your transfer password and account links are set,', '※即使已设置数据转移密码或关联外部账号，'),
            ('once your player data has been deleted,', '玩家数据删除后'),
            ('it will NOT be possible to recover your data later.', '也将无法恢复数据。'),
        ],
        "official": [],
    },
    {
        "path": "template/config/deleteUserData/popupError.html",
        "source_kind": "current-upstream",
        "source_url": "https://raw.githubusercontent.com/Puella-Care/en-text/5c149cb829ea3d8ee5a71cac174419fb45a1fdbc/magica/template/config/deleteUserData/popupError.html",
        "required": ["<span class='c_gold'>"],
        "replacements": [
            ('The Player ID entered is incorrect.', '玩家ID有误。'),
            ('※Your Player ID can be found on the Game Settings menu.', '※玩家ID可在菜单中查看。'),
        ],
        "official": [],
    },
    {
        "path": "template/config/deleteUserData/popupInputPlayerID.html",
        "source_kind": "current-upstream",
        "source_url": "https://raw.githubusercontent.com/Puella-Care/en-text/5c149cb829ea3d8ee5a71cac174419fb45a1fdbc/magica/template/config/deleteUserData/popupInputPlayerID.html",
        "required": ['id="playerID"', 'class="c_gold"', 'class="c_red"'],
        "replacements": [
            ('To delete you Player Data, please enter your Player ID.', '若要删除玩家数据，请输入玩家ID。'),
            ('※Player Data can only be deleted for the account currently active on this device.', '※仅可删除当前设备上正在使用的账号的玩家数据。'),
            ('※Your Player ID can be found on the Game Settings menu or your Profile Screen.', '※玩家ID可在游戏设置画面或个人资料画面中查看。'),
            ('※Once deleted, Player Data CANNOT be recovered under any circumstances.', '※已删除的玩家数据在任何情况下都无法恢复。'),
        ],
        "official": [],
    },
    {
        "path": "template/config/deleteUserData/popupReConfirm.html",
        "source_kind": "current-upstream",
        "source_url": "https://raw.githubusercontent.com/Puella-Care/en-text/5c149cb829ea3d8ee5a71cac174419fb45a1fdbc/magica/template/config/deleteUserData/popupReConfirm.html",
        "required": ['<%= model.loginName %>', '<%= model.level %>', '<%= model.isDispBirthDay %>', '<%= model.birthDay %>'],
        "replacements": [
            ('The following Player Data will be deleted from the server.', '将从服务器删除以下玩家数据。'),
            ('Are you sure you want to proceed?', '确定要删除吗？'),
            ('Player Name', '玩家名'),
            ('Player Rank', '玩家等级'),
            ('Birthday', '生日'),
            ('※If you do not wish to delete your data, please select Cancel.', '※如果不删除，请选择“取消”。'),
        ],
        "official": [],
    },
    {
        "path": "template/event/EventWitch/parts/MemoriaDetailPopup.html",
        "required": ['<%= model.pieceType %>', 'data-nativeimgkey="memoria_<%= model.pieceId %>_c"', '<%= model.displayName %>', '<%= model.pieceSkill.name %>', '<%= model.pieceSkill.shortDescription %>'],
        "replacements": [('MAX HP', '最大HP'), ('MAX ATK', '最大ATK'), ('MAX DEF', '最大DEF')],
        "official": [],
    },
    {
        "path": "template/quest/QuestDetailPopup.html",
        "required": ['id="PopupQuestDetailParts"', '<%= model.questBattle.missionMaster1.description %>'],
        "replacements": [],
        "official": [
            ('任务', '任务', '<div class="questDetailTitle c_white">任务</div>'),
            ('获得的报酬', '获得的报酬', '<div class="questDetailTitle c_white">获得的报酬</div>'),
        ],
    },
    {
        "path": "template/quest/MainQuest.html",
        "source_kind": "current-upstream",
        "source_url": "https://raw.githubusercontent.com/Puella-Care/en-text/5c149cb829ea3d8ee5a71cac174419fb45a1fdbc/magica/template/quest/MainQuest.html",
        "required": ['id="toPuellaHistoriaTopButtonWrap"', 'id="questListWrapSeason2"', 'id="ChapterParts"', 'id="SectionParts"'],
        "replacements": [
            ('<span class="sectionNo">Ch.<%="<%= model.chapterNoForView %\\>"%>: Ep.<%="<%= model.section.genericIndex %\\>"%></span>',
             '<span class="sectionNo">Ch.<%="<%= model.chapterNoForView %\\>"%>: <%="<%= model.section.genericIndex %\\>"%>话</span>',
             'official-cn'),
        ],
        "official": [],
    },
    {
        "path": "template/quest/SubQuest.html",
        "source_kind": "current-upstream",
        "source_url": "https://raw.githubusercontent.com/Puella-Care/en-text/5c149cb829ea3d8ee5a71cac174419fb45a1fdbc/magica/template/quest/SubQuest.html",
        "required": ['id="questListWrapSeason2"', 'id="ChapterParts"', 'id="SectionParts"', 'class="prm_secondText"'],
        "replacements": [
            ('<span class="sectionNo">Ch.<%="<%= model.chapterNoForView %\\>"%>: Ep.<%="<%= model.section.genericIndex %\\>"%></span>',
             '<span class="sectionNo">Ch.<%="<%= model.chapterNoForView %\\>"%>: <%="<%= model.section.genericIndex %\\>"%>话</span>',
             'official-cn'),
        ],
        "official": [],
    },
]


def clean_text(data: bytes) -> str:
    return data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def ejs_tokens(text: str) -> list[str]:
    out: list[str] = []
    pos = 0
    while True:
        start = text.find("<%", pos)
        if start < 0:
            return out
        end = text.find("%>", start + 2)
        if end < 0:
            raise ValueError("unterminated EJS token")
        out.append(text[start : end + 2])
        pos = end + 2


def build_one(spec: dict, source: str) -> tuple[str, list[dict]]:
    for token in spec["required"]:
        if source.count(token) != 1:
            raise ValueError(f"{spec['path']}: required token count is not one: {token}")
    result = source
    records: list[dict] = []
    for replacement in spec["replacements"]:
        before, after = replacement[:2]
        tier = replacement[2] if len(replacement) > 2 else "root-reviewed"
        if result.count(before) != 1:
            raise ValueError(f"{spec['path']}: source literal count is not one: {before}")
        result = result.replace(before, after, 1)
        records.append({
            "source_text": before,
            "final_cn": after,
            "source_tier": tier,
            "operation": "replace-once",
        })
    for source_text, final_cn, anchor in spec["official"]:
        if source.count(anchor) != 1 or result.count(anchor) != 1:
            raise ValueError(f"{spec['path']}: official anchor count is not one: {anchor}")
        records.append({
            "source_text": source_text,
            "final_cn": final_cn,
            "source_tier": "official-cn",
            "operation": "preserve-exact-anchor",
            "anchor": anchor,
        })
    if ejs_tokens(source) != ejs_tokens(result):
        raise ValueError(f"{spec['path']}: EJS structure changed")
    return result, records


def safe_target(repo: Path, relative: str) -> Path:
    root = (repo / "magica").resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"target escapes magica: {relative}")
    return target


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def translation_tsv(entries: list[dict]) -> bytes:
    fields = ["product_path", "source_text", "final_cn", "source_tier", "operation", "anchor"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for entry in entries:
        for record in entry["records"]:
            writer.writerow({"product_path": entry["product_path"], **record})
    return buffer.getvalue().encode("utf-8")


def prepare(repo: Path, source_root: Path, current_source_root: Path, state: Path) -> dict:
    entries = []
    for spec in SPECS:
        target = safe_target(repo, spec["path"])
        if target.exists():
            raise ValueError(f"refusing to replace existing product file: {target}")
        selected_root = current_source_root if spec.get("source_kind") == "current-upstream" else source_root
        source_path = selected_root / spec["path"]
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        source = clean_text(source_path.read_bytes())
        prepared, records = build_one(spec, source)
        source_state = state / "source" / spec["path"]
        prepared_state = state / "prepared" / spec["path"]
        write_atomic(source_state, source.encode("utf-8"))
        write_atomic(prepared_state, prepared.encode("utf-8"))
        entries.append({
            "product_path": "magica/" + spec["path"],
            "official_source_path": str(source_path),
            "authority_reference_path": str(source_root / spec["path"]) if (source_root / spec["path"]).is_file() else None,
            "source_url": spec.get("source_url"),
            "source_state_path": str(source_state.relative_to(repo)).replace("\\", "/"),
            "prepared_state_path": str(prepared_state.relative_to(repo)).replace("\\", "/"),
            "source_bytes": len(source.encode("utf-8")),
            "prepared_bytes": len(prepared.encode("utf-8")),
            "ejs_token_count": len(ejs_tokens(source)),
            "required_structure": spec["required"],
            "records": records,
        })
    manifest = {
        "schema": 1,
        "scope": "ten-reviewed-missing-html-dependencies",
        "target_count": len(entries),
        "literal_record_count": sum(len(row["records"]) for row in entries),
        "source_tier_counts": {
            "official-cn": sum(r["source_tier"] == "official-cn" for e in entries for r in e["records"]),
            "root-reviewed": sum(r["source_tier"] == "root-reviewed" for e in entries for r in e["records"]),
        },
        "entries": entries,
    }
    rollback = {
        "schema": 1,
        "operation": "remove-created-files-after-exact-byte-gate",
        "entries": [
            {
                "product_path": row["product_path"],
                "expected_bytes_path": row["prepared_state_path"],
                "before_state": "absent",
            }
            for row in entries
        ],
    }
    write_atomic(state / "manifest.json", json_bytes(manifest))
    write_atomic(state / "rollback.json", json_bytes(rollback))
    write_atomic(state / "translations.tsv", translation_tsv(entries))
    return manifest


def load_manifest(repo: Path, state: Path) -> dict:
    manifest = json.loads((state / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("target_count") != len(SPECS):
        raise ValueError("manifest target count mismatch")
    paths = ["magica/" + spec["path"] for spec in SPECS]
    if [row.get("product_path") for row in manifest.get("entries", [])] != paths:
        raise ValueError("manifest target order/scope mismatch")
    for spec, row in zip(SPECS, manifest["entries"]):
        source = (repo / row["source_state_path"]).read_text(encoding="utf-8")
        prepared = (repo / row["prepared_state_path"]).read_text(encoding="utf-8")
        rebuilt, _ = build_one(spec, source)
        if rebuilt != prepared:
            raise ValueError(f"staged prepared file drift: {row['product_path']}")
    return manifest


def current_expected_bytes(repo: Path, row: dict) -> tuple[bytes, bool]:
    """Bind an accepted round-6 successor to this layer's exact staged bytes."""

    staged = (repo / row["prepared_state_path"]).read_bytes()
    manifest_path = repo / ROUND6_MANIFEST_REL
    if row["product_path"] not in ROUND6_ALLOWED_SUPERSESSIONS or not manifest_path.is_file():
        return staged, False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != 1
        or manifest.get("scope") != "visible-closure-round6"
        or manifest.get("target_count") != 6
        or manifest.get("literal_count") != 15
    ):
        raise ValueError("round6 supersession manifest contract mismatch")
    matches = [
        entry for entry in manifest.get("entries", [])
        if entry.get("product_path") == row["product_path"]
    ]
    if len(matches) != 1:
        raise ValueError(f"round6 supersession entry mismatch: {row['product_path']}")
    entry = matches[0]
    if entry.get("kind") != "html" or entry.get("before_state") != "present":
        raise ValueError(f"round6 supersession role mismatch: {row['product_path']}")
    before_path = repo / str(entry.get("before_path", ""))
    after_path = repo / str(entry.get("after_path", ""))
    if not before_path.is_file() or not after_path.is_file():
        raise ValueError(f"round6 supersession evidence missing: {row['product_path']}")
    if before_path.read_bytes() != staged:
        raise ValueError(f"round6 before image does not bind missing-html staging: {row['product_path']}")
    transformed = staged.decode("utf-8")
    operations = entry.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError(f"round6 supersession operations missing: {row['product_path']}")
    for operation in operations:
        before = operation.get("before")
        after = operation.get("after")
        if not isinstance(before, str) or not isinstance(after, str) or transformed.count(before) != 1:
            raise ValueError(f"round6 supersession literal drift: {row['product_path']}")
        transformed = transformed.replace(before, after, 1)
    expected = transformed.encode("utf-8")
    if expected != after_path.read_bytes() or len(expected) != entry.get("after_bytes"):
        raise ValueError(f"round6 after image drift: {row['product_path']}")
    return expected, True


def apply(repo: Path, state: Path, fail_after: int | None = None) -> dict:
    manifest = load_manifest(repo, state)
    for row in manifest["entries"]:
        if (repo / row["product_path"]).exists():
            raise ValueError(f"target already exists: {row['product_path']}")
    created: list[Path] = []
    try:
        for index, row in enumerate(manifest["entries"], 1):
            target = repo / row["product_path"]
            staged = repo / row["prepared_state_path"]
            write_atomic(target, staged.read_bytes())
            created.append(target)
            if fail_after is not None and index == fail_after:
                raise RuntimeError("synthetic apply failure")
    except Exception:
        for target in reversed(created):
            target.unlink(missing_ok=True)
        raise
    record = {"operation": "apply", "created_count": len(created), "result": "passed"}
    write_atomic(state / "apply-record.json", json_bytes(record))
    return record


def verify(repo: Path, state: Path) -> dict:
    manifest = load_manifest(repo, state)
    checked = []
    superseded = []
    for spec, row in zip(SPECS, manifest["entries"]):
        target = repo / row["product_path"]
        expected_bytes, is_superseded = current_expected_bytes(repo, row)
        if not target.is_file() or target.read_bytes() != expected_bytes:
            raise ValueError(f"product bytes differ from reviewed staging: {row['product_path']}")
        source = (repo / row["source_state_path"]).read_text(encoding="utf-8")
        staged_expected, _ = build_one(spec, source)
        if (repo / row["prepared_state_path"]).read_text(encoding="utf-8") != staged_expected:
            raise ValueError(f"product structure/literals differ: {row['product_path']}")
        if is_superseded:
            superseded.append(row["product_path"])
        checked.append({"product_path": row["product_path"], "bytes": len(target.read_bytes())})
    report = {
        "result": "passed",
        "checked_files": len(checked),
        "literal_records": manifest["literal_record_count"],
        "source_tier_counts": manifest["source_tier_counts"],
        "approved_supersessions": superseded,
        "entries": checked,
    }
    write_atomic(state / "verification.json", json_bytes(report))
    return report


def rollback(repo: Path, state: Path, fail_after: int | None = None) -> dict:
    manifest = load_manifest(repo, state)
    for row in manifest["entries"]:
        target = repo / row["product_path"]
        staged = repo / row["prepared_state_path"]
        if not target.is_file() or target.read_bytes() != staged.read_bytes():
            raise ValueError(f"rollback gate failed: {row['product_path']}")
    removed: list[tuple[Path, bytes]] = []
    try:
        for index, row in enumerate(manifest["entries"], 1):
            target = repo / row["product_path"]
            data = target.read_bytes()
            target.unlink()
            removed.append((target, data))
            if fail_after is not None and index == fail_after:
                raise RuntimeError("synthetic rollback failure")
    except Exception:
        for target, data in removed:
            write_atomic(target, data)
        raise
    record = {"operation": "rollback", "removed_count": len(removed), "result": "passed"}
    write_atomic(state / "rollback-record.json", json_bytes(record))
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--verify", action="store_true")
    modes.add_argument("--rollback", action="store_true")
    parser.add_argument("--repo", type=Path, default=REPO_DEFAULT)
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--current-source", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--synthetic-fail-after", type=int)
    args = parser.parse_args()
    repo = args.repo.resolve()
    state = args.state.resolve() if args.state else repo / STATE_REL
    current_source = args.current_source.resolve() if args.current_source else repo / CURRENT_SOURCE_REL
    if args.prepare:
        result = prepare(repo, args.source.resolve(), current_source, state)
    elif args.apply:
        result = apply(repo, state, args.synthetic_fail_after)
    elif args.verify:
        result = verify(repo, state)
    else:
        result = rollback(repo, state, args.synthetic_fail_after)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
