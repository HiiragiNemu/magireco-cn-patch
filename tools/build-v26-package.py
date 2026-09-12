#!/usr/bin/env python3
"""Build the deterministic v26 JS/WebView hot-update ZIP.

The runtime package has exactly two roots:

* every product file below ``magica/`` except research/audit evidence; and
* ``madomagi/engine_i18n.tsv``;
* ``madomagi/repair_manifest.json``; and
* the manifest-bound native repair overlay below
  ``madomagi/resource/image_native/``.

ZIP entry order and metadata are fixed.  The production workflow additionally
pins its runner/Python toolchain and byte-compares two complete builds so
identical input bytes reproduce the same release archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = "cn_js_update_new.zip"
ENGINE_MEMBER = "madomagi/engine_i18n.tsv"
REPAIR_PREFIX = "madomagi/resource/image_native/"
# Explicit user exclusion: existing Memoria sources stay untouched and never ship.
EXCLUDED_NATIVE_PREFIXES = ("madomagi/resource/image_native/memoria/",)
REPAIR_MANIFEST = "madomagi/repair_manifest.json"
IMAGE_WEB_PREFIX = "magica/resource/image_web/"
IMAGE_WEB_MANIFEST = (
    "magica/research/totentanz-full-localization-20260817/"
    "image-web-product-closure-20260820/image_web_product_manifest.json"
)
EXCLUDED_PREFIXES = ("magica/research/", "magica/i18n_audit/")
FORBIDDEN_PREFIXES = EXCLUDED_PREFIXES + ("madomagi/resource/scenario/",) + EXCLUDED_NATIVE_PREFIXES
FIXED_DOS_TIME = (1980, 1, 1, 0, 0, 0)
UNIX_FILE_MODE = stat.S_IFREG | 0o644
COMPRESSION = zipfile.ZIP_DEFLATED
COMPRESSLEVEL = 9


class PackageError(RuntimeError):
    """Raised when the product tree or generated package breaks its contract."""


def _image_web_inputs(root: Path) -> set[str]:
    """Return the exact evidence-bound image_web product path set."""
    manifest_path = root / IMAGE_WEB_MANIFEST
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise PackageError(f"缺少 image_web 产品清单: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"image_web 产品清单不可读: {exc}") from exc
    if manifest.get("schema") != "magireco-image-web-product-manifest/v1":
        raise PackageError("image_web 产品清单 schema 不匹配")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise PackageError("image_web 产品清单为空")
    declared: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise PackageError("image_web 产品清单条目不是对象")
        member = entry.get("path")
        if not isinstance(member, str):
            raise PackageError("image_web 产品清单路径缺失")
        _normalise_member(member)
        if not member.startswith(IMAGE_WEB_PREFIX) or member in declared:
            raise PackageError(f"image_web 路径越界或重复: {member!r}")
        declared.add(member)
        source = root.joinpath(*PurePosixPath(member).parts)
        if not source.is_file() or source.is_symlink():
            raise PackageError(f"image_web 产品文件缺失: {member}")
        if entry.get("bytes") != source.stat().st_size:
            raise PackageError(f"image_web 产品文件大小与清单不一致: {member}")
        if not isinstance(entry.get("authority"), str) or not isinstance(entry.get("evidence"), str):
            raise PackageError(f"image_web 产品文件缺少来源证据: {member}")
    actual = {
        source.relative_to(root).as_posix()
        for source in (root / IMAGE_WEB_PREFIX).rglob("*")
        if source.is_file()
    }
    if actual != declared:
        raise PackageError(
            "image_web 产品目录与清单路径集合不一致: "
            f"missing={sorted(declared - actual)[:5]} extra={sorted(actual - declared)[:5]}"
        )
    if manifest.get("entry_count") != len(declared):
        raise PackageError("image_web 产品清单计数不一致")
    return declared


def _repair_inputs(root: Path) -> list[tuple[str, Path]]:
    manifest_path = root / REPAIR_MANIFEST
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise PackageError(f"缺少 native 修复清单: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageError(f"native 修复清单不可读: {exc}") from exc
    if manifest.get("schema") != "magireco-cn-madomagi-repair/v1":
        raise PackageError("native 修复清单 schema 不匹配")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise PackageError("native 修复清单为空")
    inputs: list[tuple[str, Path]] = [(REPAIR_MANIFEST, manifest_path)]
    declared: set[str] = set()
    total_bytes = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise PackageError("native 修复清单条目不是对象")
        member = entry.get("path")
        if not isinstance(member, str):
            raise PackageError("native 修复清单路径缺失")
        _normalise_member(member)
        if not member.startswith(REPAIR_PREFIX) or member.startswith(EXCLUDED_NATIVE_PREFIXES) or member in declared:
            raise PackageError(f"native 修复路径越界或重复: {member!r}")
        declared.add(member)
        source = root.joinpath(*PurePosixPath(member).parts)
        if not source.is_file() or source.is_symlink():
            raise PackageError(f"native 修复文件缺失: {member}")
        size = source.stat().st_size
        if entry.get("bytes") != size:
            raise PackageError(f"native 修复文件大小与清单不一致: {member}")
        total_bytes += size
        inputs.append((member, source))
    actual = {
        source.relative_to(root).as_posix()
        for source in (root / REPAIR_PREFIX).rglob("*")
        if source.is_file() and not source.relative_to(root).as_posix().startswith(EXCLUDED_NATIVE_PREFIXES)
    }
    if actual != declared:
        raise PackageError(
            "native 修复目录与清单路径集合不一致: "
            f"missing={sorted(declared - actual)[:5]} extra={sorted(actual - declared)[:5]}"
        )
    if manifest.get("file_count") != len(declared) or manifest.get("total_bytes") != total_bytes:
        raise PackageError("native 修复清单计数或总字节不一致")
    return inputs


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalise_member(name: str) -> str:
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts or str(member) != name:
        raise PackageError(f"非法 ZIP 路径: {name!r}")
    return name


def discover_inputs(root: Path) -> list[tuple[str, Path]]:
    """Return globally sorted (ZIP member, source path) pairs."""
    root = root.resolve()
    magica = root / "magica"
    engine = root / ENGINE_MEMBER
    if not magica.is_dir():
        raise PackageError(f"缺少 magica 产品目录: {magica}")
    if not engine.is_file():
        raise PackageError(f"缺少 {ENGINE_MEMBER}: {engine}")
    if engine.is_symlink():
        raise PackageError(f"{ENGINE_MEMBER} 不得是符号链接")

    image_web_members = _image_web_inputs(root)
    inputs: list[tuple[str, Path]] = [(ENGINE_MEMBER, engine), *_repair_inputs(root)]
    for source in magica.rglob("*"):
        if source.is_symlink():
            raise PackageError(f"产品树不得包含符号链接: {source}")
        if not source.is_file():
            continue
        member = source.relative_to(root).as_posix()
        _normalise_member(member)
        if member.startswith(EXCLUDED_PREFIXES):
            continue
        if member.startswith(IMAGE_WEB_PREFIX) and member not in image_web_members:
            raise PackageError(f"清单外 image_web 文件不得进入产品包: {member}")
        inputs.append((member, source))

    inputs.sort(key=lambda item: item[0])
    names = [name for name, _ in inputs]
    if len(names) != len(set(names)):
        raise PackageError("产品输入存在重复 ZIP 路径")
    folded: dict[str, str] = {}
    for name in names:
        previous = folded.setdefault(name.casefold(), name)
        if previous != name:
            raise PackageError(f"产品输入存在大小写碰撞: {previous!r} / {name!r}")
    if names.count(ENGINE_MEMBER) != 1:
        raise PackageError(f"{ENGINE_MEMBER} 必须且只能出现一次")
    if names.count(REPAIR_MANIFEST) != 1:
        raise PackageError(f"{REPAIR_MANIFEST} 必须且只能出现一次")
    if any(name.startswith(FORBIDDEN_PREFIXES) for name in names):
        raise PackageError("scenario/research/i18n_audit 不得进入 JS 包")
    if not any(name.startswith("magica/") for name in names):
        raise PackageError("magica 产品树没有可打包文件")
    return inputs


def _zip_info(member: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(member, date_time=FIXED_DOS_TIME)
    info.create_system = 3  # Unix: external_attr is interpreted consistently.
    info.external_attr = UNIX_FILE_MODE << 16
    info.internal_attr = 0
    info.compress_type = COMPRESSION
    info.comment = b""
    info.extra = b""
    return info


def verify_archive(
    archive_path: Path,
    inputs: list[tuple[str, Path]],
) -> dict[str, object]:
    """Reopen and verify bytes, order, metadata, roots, duplicates, and CRC."""
    expected_names = [name for name, _ in inputs]
    expected_bytes = {name: source.read_bytes() for name, source in inputs}
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise PackageError("成品 ZIP 含重复路径")
        if names != expected_names:
            raise PackageError("成品 ZIP 路径集合或排序与产品输入不一致")
        if names.count(ENGINE_MEMBER) != 1:
            raise PackageError(f"成品 ZIP 中 {ENGINE_MEMBER} 数量不是 1")
        if names.count(REPAIR_MANIFEST) != 1:
            raise PackageError(f"成品 ZIP 中 {REPAIR_MANIFEST} 数量不是 1")
        if any(name.startswith(FORBIDDEN_PREFIXES) for name in names):
            raise PackageError("成品 ZIP 混入 scenario/research/i18n_audit")
        if any(not (
            name.startswith("magica/")
            or name == ENGINE_MEMBER
            or name == REPAIR_MANIFEST
            or name.startswith(REPAIR_PREFIX)
        ) for name in names):
            raise PackageError("成品 ZIP 含不受支持的根路径")
        if archive.comment:
            raise PackageError("成品 ZIP 含不确定的 archive comment")
        bad_crc = archive.testzip()
        if bad_crc is not None:
            raise PackageError(f"成品 ZIP CRC 失败: {bad_crc}")
        for info in infos:
            if info.is_dir():
                raise PackageError(f"成品 ZIP 不应含目录项: {info.filename}")
            if info.date_time != FIXED_DOS_TIME:
                raise PackageError(f"时间戳未固定: {info.filename}")
            if info.create_system != 3 or (info.external_attr >> 16) != UNIX_FILE_MODE:
                raise PackageError(f"Unix 权限未固定: {info.filename}")
            if info.compress_type != COMPRESSION:
                raise PackageError(f"压缩方式不一致: {info.filename}")
            if info.comment or info.extra:
                raise PackageError(f"ZIP entry 含不确定元数据: {info.filename}")
            if archive.read(info) != expected_bytes[info.filename]:
                raise PackageError(f"成品 ZIP 字节与源文件不一致: {info.filename}")

    raw = archive_path.read_bytes()
    return {
        "schema": "magireco-cn-v26-deterministic-package/v1",
        "status": "PASS",
        "path": str(archive_path.resolve()),
        "file_entries": len(expected_names),
        "bytes": len(raw),
        "sha256": sha256(raw),
        "engine_member": ENGINE_MEMBER,
        "engine_sha256": sha256(expected_bytes[ENGINE_MEMBER]),
        "engine_entries": expected_names.count(ENGINE_MEMBER),
        "repair_manifest_entries": expected_names.count(REPAIR_MANIFEST),
        "repair_entries": sum(name.startswith(REPAIR_PREFIX) for name in expected_names),
        "image_web_entries": sum(name.startswith(IMAGE_WEB_PREFIX) for name in expected_names),
        "scenario_entries": 0,
        "research_entries": 0,
        "audit_entries": 0,
        "duplicate_paths": 0,
        "entry_order": "utf-8-posix-name",
        "dos_time": list(FIXED_DOS_TIME),
        "unix_mode": "100644",
        "compression": "deflate-9",
    }


def build_package(root: Path, output: Path) -> dict[str, object]:
    root = root.resolve()
    output = output.resolve()
    try:
        output.relative_to(root / "magica")
    except ValueError:
        pass
    else:
        raise PackageError("输出 ZIP 不得位于 magica 产品树内")

    inputs = discover_inputs(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=COMPRESSION,
            compresslevel=COMPRESSLEVEL,
            allowZip64=True,
            strict_timestamps=True,
        ) as archive:
            archive.comment = b""
            for member, source in inputs:
                archive.writestr(
                    _zip_info(member),
                    source.read_bytes(),
                    compress_type=COMPRESSION,
                    compresslevel=COMPRESSLEVEL,
                )
        report = verify_archive(temporary, inputs)
        os.replace(temporary, output)
        temporary = None
        report["path"] = str(output)
        return report
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path(DEFAULT_OUTPUT),
        help=f"输出 ZIP（默认 {DEFAULT_OUTPUT}）",
    )
    args = parser.parse_args()
    try:
        report = build_package(ROOT, args.out)
    except (OSError, PackageError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"build-v26-package: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
