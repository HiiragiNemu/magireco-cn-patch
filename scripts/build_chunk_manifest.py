#!/usr/bin/env python3
"""生成/更新 16MB 分块哈希清单（分块校验用的 manifest.json）。

背景：下载校验从「整包重读 md5」演进到「16MB 分块哈希」。客户端下载时
每个分片线程段内顺序喂 MessageDigest，下完一块立即比对清单指纹，坏块
只重下那 16MB，不再整包重来（2026-08-11 cn_base_03 事故的根治方案）。

用法：
  # 全新生成（首次/全量，覆盖 base 包）
  python3 scripts/build_chunk_manifest.py --out manifest.json \
      --chunk-size 16777216 cn_base_00_db.zip ...

  # 增量更新（热更包重打后，只更新这些文件，base 包指纹保留）。
  # --as NAME 把输入文件按 NAME 键写入（例如 _new 的指纹存到 official 名，
  # 因为客户端下载的是 official 名）。
  python3 scripts/build_chunk_manifest.py --update configures/manifest.json \
      --out configures/manifest.json \
      --as cn_js_update.zip=cn_js_update_new.zip \
      --as cn_scenario_update.zip=cn_scenario_update_new.zip

输出 JSON 结构：
  {
    "<zip 文件名>": {
      "size": 1422289288,
      "chunk_size": 16777216,
      "chunks": ["<md5hex>", ...]        # 每块 16MB，最后一块不足 16MB
    },
    ...
  }

设计约束：
  - 流式读文件（分块读，不整包载入内存）——base 包最大 1.98GB
  - 只算 md5（发布侧一次顺序读可接受；客户端不重读，下载中边写边喂）
  - 块大小固定 16MB，最后一块是余数（客户端按同规则切块对齐）
  - 增量模式（--update）：从现有 manifest 读 base 包指纹，只更新传入的 zip，
    保证每次构建不用重拉 10GB base 包
"""
import argparse
import hashlib
import json
import sys


def chunk_hashes(path, chunk_size):
    """流式切块算 md5。返回 (file_size, [md5hex...])。"""
    digests = []
    size = 0
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            digests.append(hashlib.md5(block).hexdigest().lower())
            size += len(block)
    return size, digests


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("zips", nargs="+", help="zip 文件路径")
    ap.add_argument("--out", default="manifest.json", help="输出路径")
    ap.add_argument("--chunk-size", type=int, default=16 * 1024 * 1024,
                    help="块大小（字节），默认 16MB")
    ap.add_argument("--update", metavar="EXISTING",
                    help="增量更新：读这个现有 manifest，只覆盖传入的 zip，"
                         "其余条目（base 包）保留")
    ap.add_argument("--as", action="append", default=[],
                    help="NAME=FILE 映射：把 FILE 的指纹写入 NAME 键。"
                         "用于 _new 的指纹存到 official 名（客户端下载 official）。")
    args = ap.parse_args()

    # --as 映射：NAME -> 真实文件（argparse 的属性名是 'as'，Python 保留字
    # 不能写成 args.as，用 getattr 取）
    as_map = {}
    as_list = getattr(args, "as") or []
    for item in as_list:
        if "=" in item:
            name, real = item.split("=", 1)
            as_map[name] = real
        else:
            sys.stderr.write(f"✘ --as 格式应为 NAME=FILE: {item}\n")
            sys.exit(1)

    # 增量模式：先读现有清单作为底
    manifest = {}
    if args.update:
        try:
            with open(args.update, encoding="utf-8") as f:
                manifest = json.load(f)
            print(f"ℹ 载入现有清单 {args.update}: {len(manifest)} 个文件")
        except OSError as e:
            sys.stderr.write(f"✘ 无法读现有清单 {args.update}: {e}\n")
            sys.exit(1)

    for z in args.zips:
        # 计算指纹用的真实文件；manifest 键名可能是官方名（--as 映射）
        real = z
        key  = z.split("/")[-1]
        for name, f in as_map.items():
            if f == z:
                real = f
                key  = name
                break
        try:
            size, chunks = chunk_hashes(real, args.chunk_size)
        except OSError as e:
            sys.stderr.write(f"✘ 无法读取 {real}: {e}\n")
            sys.exit(1)
        manifest[key] = {
            "size": size,
            "chunk_size": args.chunk_size,
            "chunks": chunks,
        }
        print(f"✔ {key} ({real}): {size} 字节, {len(chunks)} 块")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"✔ 清单已写入 {args.out}（{len(manifest)} 个文件）")


if __name__ == "__main__":
    main()
