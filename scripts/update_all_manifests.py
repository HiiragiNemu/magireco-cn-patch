# scripts/update_all_manifests.py
# 完全复刻本地 ADB 推送时的 JSON 更新逻辑：
# 本地有的文件 → 计算真实MD5写回JSON；本地没有的 → 保留原始值（movie等）

import json
import hashlib
import pickle
import argparse
from pathlib import Path

MANIFEST_FILES = [
    "asset_main.json",
    "asset_voice.json",
    "asset_fullvoice.json",
    "asset_char_list.json",
    "asset_config.json",
    "asset_movieall_high.json",
]


def calc_md5(file_path: Path, cache: dict):
    stat  = file_path.stat()
    size  = stat.st_size
    mtime = stat.st_mtime
    key   = str(file_path)

    if (key in cache
            and cache[key]['size']  == size
            and cache[key]['mtime'] == mtime):
        return cache[key]['md5'], size

    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    md5 = h.hexdigest()
    cache[key] = {'md5': md5, 'size': size, 'mtime': mtime}
    return md5, size


def update_one(manifest_path: Path, local_files: dict, cache: dict) -> dict:
    stats = dict(replaced=0, unchanged=0, no_local=0, bad=0,
                 total=0, name=manifest_path.name)

    if not manifest_path.exists():
        print(f"  ⚠️  不存在，跳过: {manifest_path.name}")
        return stats

    with open(manifest_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"  ❌ JSON解析失败: {manifest_path.name} → {e}")
            stats['bad'] += 1
            return stats

    if not isinstance(data, list):
        print(f"  ⚠️  顶层非数组，跳过: {manifest_path.name}")
        stats['bad'] += 1
        return stats

    stats['total'] = len(data)

    for item in data:
        if not isinstance(item, dict):
            stats['bad'] += 1
            continue

        path = item.get("path", "")
        if not path:
            stats['bad'] += 1
            continue

        # movie 一律不改（保留原版MD5，游戏用官方CDN下movie）
        if "movie/" in path:
            stats['no_local'] += 1
            continue

        # 本地不存在 → 保留原始值
        if path not in local_files:
            stats['no_local'] += 1
            continue

        try:
            new_md5, new_size = calc_md5(local_files[path], cache)
        except Exception as e:
            print(f"  ⚠️  MD5失败: {path} ({e})")
            stats['bad'] += 1
            continue

        old_md5  = item.get("md5", "")
        fl       = item.get("file_list")
        old_size = fl[0].get("size", -1) if isinstance(fl, list) and fl else -1

        if old_md5 == new_md5 and old_size == new_size:
            stats['unchanged'] += 1
            continue

        item["md5"] = new_md5
        if isinstance(fl, list) and fl:
            fl[0]["size"] = new_size   # url字段不动

        stats['replaced'] += 1

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="非破坏性更新所有 manifest JSON 的 MD5/size"
    )
    parser.add_argument("--resource-dir", required=True,
                        help="resource根目录（含image_native/sound_native等）")
    parser.add_argument("--manifest-dir", required=True,
                        help="manifest所在目录（madomagi/）")
    args = parser.parse_args()

    resource_dir = Path(args.resource_dir)
    manifest_dir = Path(args.manifest_dir)
    cache_file   = Path(".md5_cache")

    if not resource_dir.exists():
        print(f"❌ resource_dir不存在: {resource_dir}")
        return
    if not manifest_dir.exists():
        print(f"❌ manifest_dir不存在: {manifest_dir}")
        return

    cache = {}
    if cache_file.exists():
        try:
            with open(cache_file, "rb") as f:
                cache = pickle.load(f)
        except Exception:
            cache = {}

    print(f"🔍 扫描本地资源: {resource_dir}")
    local_files = {
        fp.relative_to(resource_dir).as_posix(): fp
        for fp in resource_dir.rglob("*") if fp.is_file()
    }
    print(f"   本地文件数: {len(local_files)}\n")

    total_r = total_u = total_n = total_b = 0

    for name in MANIFEST_FILES:
        print(f"📄 {name}")
        s = update_one(manifest_dir / name, local_files, cache)
        print(f"   条目={s['total']}  ✍️更新={s['replaced']}  "
              f"✅不变={s['unchanged']}  "
              f"📂本地无/movie={s['no_local']}  ⚠️异常={s['bad']}")
        total_r += s['replaced']
        total_u += s['unchanged']
        total_n += s['no_local']
        total_b += s['bad']

    with open(cache_file, "wb") as f:
        pickle.dump(cache, f)

    print(f"\n====== 📊 汇总 ======")
    print(f"  ✍️ 更新      : {total_r}")
    print(f"  ✅ 未变化    : {total_u}")
    print(f"  📂 本地无/movie: {total_n}")
    print(f"  ⚠️ 异常      : {total_b}")
    print(f"=====================\n")


if __name__ == "__main__":
    main()
