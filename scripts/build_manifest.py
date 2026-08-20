#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为热更包生成文件清单，并维护一份「历史上下发过什么」的累计账本。

## 为什么需要账本，而不只是包本身

热更包的解压是**只写不删**的（客户端 `RestClient.unzip` / `CNHotUpdateTx` 都只
`mkdirs` + 写文件）。把一个文件从包里拿掉，只是「以后不再更新它」——设备上那份
会永远留着，而且因为 `shouldInterceptRequest` 是本地优先且忽略 `?<md5>` 查询串，
它会**永远盖住服务端的版本**。历史篇（Puella Historia）入口就是这么丢的。

客户端现在会自己记清单、跨版本清理孤儿（见 `CNHotUpdateTx.listEntries` /
`findOrphans`），但那只对**装了新客户端之后**下发的版本有效。仓库这边仍然需要
一份账本，用来回答两个人类问题：

  · 「第 N 版发了哪些文件？」——`<package>_manifest.json`
  · 「历史上一共往玩家设备上写过哪些路径？」——`manifests/<package>_ledger.json`

第二个尤其重要：它是**已经污染了设备的路径全集**。任何一条从账本里消失（即某一
版把它从包里拿掉了）都值得警觉——那正是制造孤儿的时刻，脚本会在这时候把它列出来。
尚未转正的 ``*_new`` 预览包必须传 ``--ledger-mode check``：照常生成候选清单并与
现有账本比对，但不把未发布路径写进这份历史账本。

## 输出

    <package>_manifest.json      本次这一版的完整清单（路径 / 大小 / crc32）
    manifests/<package>_ledger.json
                                 累计账本：每个路径首次/最后出现在哪一版

用法：
    python3 scripts/build_manifest.py --zip cn_js_update_new.zip \\
        --package cn_js_update --version 21
"""

import argparse
from collections import Counter
import hashlib
import json
import os
import sys
import time
import zipfile

# 客户端允许清理孤儿的前缀，与 CNHotUpdateTx.cleanupPrefixes 一一对应。
# 写进 manifest 只是留档给人看——客户端用的是它自己那份硬编码白名单，
# 不读这里，免得「服务端下发的数据能扩大客户端的删除范围」。
CLEANUP_PREFIXES = {
    "cn_js_update": [
        "magica/js/", "magica/template/", "magica/css/", "magica/fonts/",
    ],
    "cn_scenario_update": [
        "madomagi/resource/scenario/json/",
    ],
}

# 包结构的所有权约束。清单生成是发布前最后一道看得见 ZIP 中央目录的门：
# 在这里 fail-fast，避免「版本号和 MD5 都正确，但文件装进了错误的包」。
REQUIRED_FILES = {
    "cn_js_update": {
        "madomagi/engine_i18n.tsv",
        "madomagi/repair_manifest.json",
    },
}
REQUIRED_PREFIXES = {
    "cn_js_update": {"madomagi/resource/image_native/"},
}
FORBIDDEN_FILES = {
    "cn_scenario_update": {
        "madomagi/engine_i18n.tsv",
        "madomagi/repair_manifest.json",
    },
}

ENGINE_TABLE = "madomagi/engine_i18n.tsv"
REPAIR_MANIFEST = "madomagi/repair_manifest.json"
REPAIR_PREFIX = "madomagi/resource/image_native/"
SCENARIO_PREFIX = "madomagi/resource/scenario/json/"
KNOWN_PACKAGES = {"cn_js_update", "cn_scenario_update"}

# 已知的跨包所有权迁移。它只影响报告文案，不扩大客户端删除范围；旧 scenario
# 清单拿掉该文件时，设备保留旧副本，随后 JS 事务在同一路径原子覆盖。
OWNERSHIP_TRANSFERS = {
    ("cn_scenario_update", "madomagi/engine_i18n.tsv"): "cn_js_update",
}

LEDGER_DIR = "manifests"


def is_canonical_member_path(path):
    """ZIP members must be relative POSIX paths without aliasing segments."""

    if not path or path.startswith("/") or "\\" in path:
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _object_without_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON 含重复键 %s" % key)
        result[key] = value
    return result


def read_repair_contract(raw):
    """Return ``{member_path: byte_count}`` plus fail-closed schema errors."""

    errors = []
    try:
        data = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except Exception as exc:
        return {}, ["repair_manifest.json 不是严格 UTF-8 JSON：%s" % exc]

    if not isinstance(data, dict):
        return {}, ["repair_manifest.json 顶层必须是对象"]
    if data.get("schema") != "magireco-cn-madomagi-repair/v1":
        errors.append("repair_manifest.json schema 不受支持")
    if data.get("package_prefix") != REPAIR_PREFIX:
        errors.append("repair_manifest.json package_prefix 不匹配")

    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}, errors + ["repair_manifest.json entries 必须是数组"]

    expected = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append("repair_manifest.json entries[%d] 必须是对象" % index)
            continue
        path = entry.get("path")
        size = entry.get("bytes")
        if not isinstance(path, str) or not is_canonical_member_path(path):
            errors.append("repair_manifest.json entries[%d] 路径非法" % index)
            continue
        if not path.startswith(REPAIR_PREFIX):
            errors.append("repair_manifest.json entries[%d] 路径越界：%s" % (index, path))
            continue
        if path in expected:
            errors.append("repair_manifest.json 重复声明：%s" % path)
            continue
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            errors.append("repair_manifest.json entries[%d] bytes 非法" % index)
            continue
        expected[path] = size

    if not expected:
        errors.append("repair_manifest.json 未声明 image_native 文件")
    file_count = data.get("file_count")
    if isinstance(file_count, bool) or not isinstance(file_count, int):
        errors.append("repair_manifest.json file_count 非法")
    elif file_count != len(entries):
        errors.append(
            "repair_manifest.json file_count=%d，entries=%d"
            % (file_count, len(entries))
        )
    total_bytes = data.get("total_bytes")
    if isinstance(total_bytes, bool) or not isinstance(total_bytes, int):
        errors.append("repair_manifest.json total_bytes 非法")
    elif total_bytes != sum(expected.values()):
        errors.append(
            "repair_manifest.json total_bytes=%d，声明合计=%d"
            % (total_bytes, sum(expected.values()))
        )
    return expected, errors


def validate_package_contract(package, files, repair_manifest_raw):
    """Validate package ownership before any manifest or ledger is written."""

    errors = []
    if package not in KNOWN_PACKAGES:
        return ["未知 package：%s" % package]

    noncanonical = sorted(path for path in files if not is_canonical_member_path(path))
    for path in noncanonical:
        errors.append("ZIP 路径不是规范相对路径：%s" % path)

    missing_required = sorted(REQUIRED_FILES.get(package, set()) - set(files))
    missing_prefixes = sorted(
        prefix for prefix in REQUIRED_PREFIXES.get(package, set())
        if not any(path.startswith(prefix) for path in files)
    )
    forbidden_present = sorted(FORBIDDEN_FILES.get(package, set()) & set(files))
    for path in missing_required:
        errors.append("%s 缺少必需文件 %s" % (package, path))
    for path in forbidden_present:
        errors.append("%s 仍含已迁出的文件 %s" % (package, path))
    for prefix in missing_prefixes:
        errors.append("%s 缺少必需路径前缀 %s" % (package, prefix))

    if package == "cn_js_update":
        expected_repairs = {}
        if repair_manifest_raw is not None:
            expected_repairs, repair_errors = read_repair_contract(repair_manifest_raw)
            errors.extend(repair_errors)

        actual_repairs = {
            path: metadata["size"]
            for path, metadata in files.items()
            if path.startswith(REPAIR_PREFIX)
        }
        for path in sorted(set(expected_repairs) - set(actual_repairs)):
            errors.append("repair_manifest.json 声明文件缺失：%s" % path)
        for path in sorted(set(actual_repairs) - set(expected_repairs)):
            errors.append("image_native 文件未在 repair_manifest.json 声明：%s" % path)
        for path in sorted(set(expected_repairs) & set(actual_repairs)):
            if expected_repairs[path] != actual_repairs[path]:
                errors.append(
                    "image_native 字节数不匹配：%s（manifest=%d, zip=%d）"
                    % (path, expected_repairs[path], actual_repairs[path])
                )

        allowed_exact = {ENGINE_TABLE, REPAIR_MANIFEST} | set(expected_repairs)
        unowned = sorted(
            path for path in files
            if not path.startswith("magica/") and path not in allowed_exact
        )
        for path in unowned:
            errors.append("cn_js_update 含越界路径：%s" % path)
    else:
        unowned = sorted(path for path in files if not path.startswith(SCENARIO_PREFIX))
        for path in unowned:
            errors.append("cn_scenario_update 含越界路径：%s" % path)

    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--package", required=True,
                    help="cn_js_update / cn_scenario_update")
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--out", default=".", help="manifest 写到哪个目录")
    ap.add_argument(
        "--manifest-name",
        help="输出文件名；预览构建应使用 *_manifest_new.json",
    )
    ap.add_argument("--ledger-dir", default=LEDGER_DIR)
    ap.add_argument(
        "--ledger-mode",
        choices=("update", "check"),
        default="update",
        help=(
            "update 写回累计账本；check 只对现有账本计算新增/移除，"
            "用于尚未转正的预览包"
        ),
    )
    args = ap.parse_args()

    if args.version <= 0:
        sys.stderr.write("✘ --version 必须是正整数\n")
        return 2

    manifest_name = args.manifest_name or "%s_manifest.json" % args.package
    if os.path.basename(manifest_name) != manifest_name or not manifest_name.endswith(".json"):
        sys.stderr.write("✘ --manifest-name 必须是单个 .json 文件名\n")
        return 2

    if not os.path.isfile(args.zip):
        sys.stderr.write("✘ 找不到 %s\n" % args.zip)
        return 2

    with zipfile.ZipFile(args.zip) as z:
        infos = [it for it in z.infolist() if not it.is_dir()]
        names = [it.filename for it in infos]
        if len(names) != len(set(names)):
            duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
            sys.stderr.write("✘ 包含重复文件路径：%s\n" % ", ".join(duplicates[:20]))
            return 1
        bad_crc = z.testzip()
        if bad_crc is not None:
            sys.stderr.write("✘ ZIP CRC 校验失败：%s\n" % bad_crc)
            return 1
        files = {
            it.filename: {
                "size": it.file_size,
                "crc32": "%08x" % (it.CRC & 0xFFFFFFFF),
            }
            for it in infos
        }
        repair_manifest_raw = (
            z.read(REPAIR_MANIFEST) if REPAIR_MANIFEST in files else None
        )
    if not files:
        sys.stderr.write("✘ 包里没有文件条目\n")
        return 1

    contract_errors = validate_package_contract(
        args.package,
        files,
        repair_manifest_raw,
    )
    if contract_errors:
        for error in contract_errors:
            sys.stderr.write("✘ %s\n" % error)
        return 1

    with open(args.zip, "rb") as f:
        zip_md5 = hashlib.md5(f.read()).hexdigest()

    manifest = {
        "schema": 1,
        "package": args.package,
        "version": args.version,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "zip_size": os.path.getsize(args.zip),
        "zip_md5": zip_md5,
        "file_count": len(files),
        "total_size": sum(v["size"] for v in files.values()),
        # 留档，客户端不读，见文件头注释
        "cleanup_prefixes": CLEANUP_PREFIXES.get(args.package, []),
        "files": dict(sorted(files.items())),
    }
    os.makedirs(args.out, exist_ok=True)
    mpath = os.path.join(args.out, manifest_name)

    # ---- 账本 ----
    os.makedirs(args.ledger_dir, exist_ok=True)
    lpath = os.path.join(args.ledger_dir, "%s_ledger.json" % args.package)
    ledger = {"schema": 1, "package": args.package, "paths": {}}
    if os.path.isfile(lpath):
        try:
            with open(lpath, encoding="utf-8") as f:
                ledger = json.load(f)
            ledger.setdefault("paths", {})
        except Exception as e:
            sys.stderr.write("⚠ 账本读不动，按空账本重建：%s\n" % e)
            ledger = {"schema": 1, "package": args.package, "paths": {}}

    try:
        ledger_last_version = int(ledger.get("last_version", 0) or 0)
    except (TypeError, ValueError):
        sys.stderr.write("✘ 账本 last_version 非法，拒绝覆盖\n")
        return 1
    if args.version < ledger_last_version:
        sys.stderr.write(
            "✘ 候选版本不得倒退：candidate=%d, ledger=%d\n"
            % (args.version, ledger_last_version)
        )
        return 1

    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=False)
    print("✅ %s：%d 个文件，%.1f MB"
          % (mpath, len(files), manifest["total_size"] / 1048576.0))

    paths = ledger["paths"]
    historical_paths_before = len(paths)
    prev_current = {p for p, v in paths.items() if v.get("current")}
    added, dropped = [], []

    for p in files:
        if p not in paths:
            paths[p] = {"first_version": args.version, "last_version": args.version,
                        "current": True}
            added.append(p)
        else:
            paths[p]["last_version"] = args.version
            paths[p]["current"] = True
    for p in prev_current - set(files):
        paths[p]["current"] = False
        dropped.append(p)

    ledger["paths"] = dict(sorted(paths.items()))
    ledger["last_version"] = args.version
    ledger["total_paths_ever"] = len(paths)
    ledger["current_paths"] = len(files)
    if args.ledger_mode == "update":
        with open(lpath, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=1)
        print("✅ %s：历史累计 %d 条路径，本版在用 %d 条（新增 %d，移除 %d）"
              % (lpath, len(paths), len(files), len(added), len(dropped)))
    else:
        print("✅ 只读核对 %s：账本历史累计 %d 条，候选并集 %d 条，候选包 %d 条"
              "（新增 %d，移除 %d）；账本未写回"
              % (lpath, historical_paths_before, len(paths), len(files), len(added), len(dropped)))

    if dropped:
        prefixes = CLEANUP_PREFIXES.get(args.package, [])
        cleanable = [p for p in dropped if any(p.startswith(x) for x in prefixes)]
        transferred = [p for p in dropped
                       if (args.package, p) in OWNERSHIP_TRANSFERS]
        stuck = [p for p in dropped if p not in cleanable and p not in transferred]
        print()
        print("⚠ 这一版比上一版少了 %d 个文件。" % len(dropped))
        print("  装了新客户端的设备会在下次热更时把其中 %d 个删掉（在清理白名单内）；"
              % len(cleanable))
        for p in transferred:
            print("  %s 已迁移给 %s；旧副本保留到新包在同一路径覆盖。"
                  % (p, OWNERSHIP_TRANSFERS[(args.package, p)]))
        print("  剩下 %d 个**留在所有设备上，并会继续盖住服务端的版本**：" % len(stuck))
        for p in stuck[:40]:
            print("      %s" % p)
        if len(stuck) > 40:
            print("      …还有 %d 条" % (len(stuck) - 40))
        print()
        print("  要真正撤掉它们，只能把服务端现役内容原样放回包里发一次覆盖。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
