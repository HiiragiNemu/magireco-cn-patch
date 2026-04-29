#!/usr/bin/env python3
"""
update_asset_main.py
用途：扫描本地汉化资源目录，重新计算 MD5/Size，更新 asset_main.json
用法：
    python3 scripts/update_asset_main.py \
        --resource-dir  _game_res/madomagi/resource \
        --original-json madomagi/asset_main.json \
        --output-json   madomagi/asset_main.json
"""

import argparse
import hashlib
import json
import os
import pickle
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--resource-dir",  required=True,
                   help="汉化资源根目录（包含 image_native/scenario 等）")
    p.add_argument("--original-json", required=True,
                   help="原始 asset_main.json 路径（作为模板）")
    p.add_argument("--output-json",   required=True,
                   help="输出的新 asset_main.json 路径（可与原始相同，即原地更新）")
    p.add_argument("--cache-file",    default=".md5_cache",
                   help="MD5 增量缓存文件路径（默认 .md5_cache）")
    return p.parse_args()


def compute_md5_with_cache(file_path: Path, cache: dict):
    stat  = file_path.stat()
    key   = str(file_path)
    entry = cache.get(key)

    if entry and entry["size"] == stat.st_size and entry["mtime"] == stat.st_mtime:
        return entry["md5"], stat.st_size, True   # True = 命中缓存

    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    md5 = h.hexdigest()

    cache[key] = {"md5": md5, "size": stat.st_size, "mtime": stat.st_mtime}
    return md5, stat.st_size, False


def main():
    args = parse_args()

    resource_dir  = Path(args.resource_dir)
    original_json = Path(args.original_json)
    output_json   = Path(args.output_json)
    cache_file    = Path(args.cache_file)

    if not original_json.exists():
        raise FileNotFoundError(f"找不到原始清单：{original_json}")
    if not resource_dir.exists():
        raise FileNotFoundError(f"找不到资源目录：{resource_dir}")

    # 加载缓存
    cache = {}
    if cache_file.exists():
        with open(cache_file, "rb") as f:
            cache = pickle.load(f)

    print(f"📂 读取清单：{original_json}")
    with open(original_json, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"🔍 扫描资源目录：{resource_dir}")
    # 建立 相对路径 → 绝对路径 的映射（正斜杠对齐 JSON 的 path 字段）
    local_files = {
        fp.relative_to(resource_dir).as_posix(): fp
        for fp in resource_dir.rglob("*")
        if fp.is_file()
    }

    json_paths = {item["path"] for item in manifest}

    replaced = 0
    cached   = 0
    missing  = []

    print("⚙️  对比并更新 MD5/Size...")
    for item in manifest:
        path = item["path"]

        if path not in local_files:
            missing.append(path)
            continue

        fp = local_files[path]
        new_md5, new_size, was_cached = compute_md5_with_cache(fp, cache)

        # 取出原始 size（兼容两种 JSON 结构）
        old_size = 0
        if item.get("file_list"):
            old_size = item["file_list"][0].get("size", 0)

        if item["md5"] == new_md5 and old_size == new_size:
            cached += 1
            continue

        item["md5"] = new_md5
        if item.get("file_list"):
            item["file_list"][0]["size"] = new_size
        replaced += 1

    # 保存结果
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"), ensure_ascii=False)

    # 保存缓存
    with open(cache_file, "wb") as f:
        pickle.dump(cache, f)

    # 统计报告
    unlisted = [p for p in local_files if p not in json_paths]
    print("\n================ 📊 处理报告 ================")
    print(f"✅ 输出文件          : {output_json}")
    print(f"🚀 命中缓存（跳过）  : {cached} 个")
    print(f"✍️  实际更新（写入）  : {replaced} 个")
    print(f"❌ 清单有本地无      : {len(missing)} 个")
    print(f"👻 本地有清单无      : {len(unlisted)} 个")
    print("=============================================")

    if missing:
        miss_path = output_json.parent / "missing_files.txt"
        miss_path.write_text("\n".join(missing), encoding="utf-8")
        print(f"   缺失列表 → {miss_path}")


if __name__ == "__main__":
    main()
