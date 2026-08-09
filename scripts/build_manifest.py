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

## 输出

    <package>_manifest.json      本次这一版的完整清单（路径 / 大小 / crc32）
    manifests/<package>_ledger.json
                                 累计账本：每个路径首次/最后出现在哪一版

用法：
    python3 scripts/build_manifest.py --zip cn_js_update_new.zip \\
        --package cn_js_update --version 21
"""

import argparse
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
    "cn_js_update": {"madomagi/engine_i18n.tsv"},
}
FORBIDDEN_FILES = {
    "cn_scenario_update": {"madomagi/engine_i18n.tsv"},
}

# 已知的跨包所有权迁移。它只影响报告文案，不扩大客户端删除范围；旧 scenario
# 清单拿掉该文件时，设备保留旧副本，随后 JS 事务在同一路径原子覆盖。
OWNERSHIP_TRANSFERS = {
    ("cn_scenario_update", "madomagi/engine_i18n.tsv"): "cn_js_update",
}

LEDGER_DIR = "manifests"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--package", required=True,
                    help="cn_js_update / cn_scenario_update")
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--out", default=".", help="manifest 写到哪个目录")
    ap.add_argument("--ledger-dir", default=LEDGER_DIR)
    args = ap.parse_args()

    if not os.path.isfile(args.zip):
        sys.stderr.write("✘ 找不到 %s\n" % args.zip)
        return 2

    z = zipfile.ZipFile(args.zip)
    files = {}
    for it in z.infolist():
        if it.is_dir():
            continue
        files[it.filename] = {"size": it.file_size, "crc32": "%08x" % (it.CRC & 0xFFFFFFFF)}
    if not files:
        sys.stderr.write("✘ 包里没有文件条目\n")
        return 1

    missing_required = sorted(REQUIRED_FILES.get(args.package, set()) - set(files))
    forbidden_present = sorted(FORBIDDEN_FILES.get(args.package, set()) & set(files))
    if missing_required or forbidden_present:
        for path in missing_required:
            sys.stderr.write("✘ %s 缺少必需文件 %s\n" % (args.package, path))
        for path in forbidden_present:
            sys.stderr.write("✘ %s 仍含已迁出的文件 %s\n" % (args.package, path))
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
    mpath = os.path.join(args.out, "%s_manifest.json" % args.package)
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=False)
    print("✅ %s：%d 个文件，%.1f MB"
          % (mpath, len(files), manifest["total_size"] / 1048576.0))

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

    paths = ledger["paths"]
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
    with open(lpath, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)
    print("✅ %s：历史累计 %d 条路径，本版在用 %d 条（新增 %d，移除 %d）"
          % (lpath, len(paths), len(files), len(added), len(dropped)))

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
