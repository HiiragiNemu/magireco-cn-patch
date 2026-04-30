# scripts/update_all_manifests.py
# 非破坏性更新所有 manifest JSON 的 MD5/size
# 规则：本地有 → 更新为真实MD5；本地无（movie等）→ 保留原始值

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
    # asset_movieall_high.json 我们本地没有movie，完全保留原始值
    # 但仍然纳入处理，非破坏性逻辑会自动跳过
    "asset_movieall_high.json",
]


def calc_md5_cached(file_path: Path, cache: dict):
    stat  = file_path.stat()
    size  = stat.st_size
    mtime = stat.st_mtime
    key   = str(file_path)

    if (key in cache
            and cache[key]['size']  == size
            and cache[key]['mtime'] == mtime):
        return cache[key]['md5'], size, True

    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    md5 = h.hexdigest()
    cache[key] = {'md5': md5, 'size': size, 'mtime': mtime}
    return md5, size, False


def update_one_manifest(
    manifest_path: Path,
    resource_dir:  Path,
    local_files:   dict,
    cache:         dict,
) -> dict:
    """
    更新单个 manifest JSON。
    返回统计字典。
    """
    stats = dict(replaced=0, unchanged=0, no_local=0, bad_item=0)

    if not manifest_path.exists():
        print(f"  ⚠️  不存在，跳过: {manifest_path.name}")
        return stats

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if not isinstance(manifest, list):
        print(f"  ❌ 格式错误（非数组）: {manifest_path.name}")
        stats['bad_item'] += 1
        return stats

    for item in manifest:
        if not isinstance(item, dict):
            stats['bad_item'] += 1
            continue

        path = item.get("path", "")
        if not path:
            stats['bad_item'] += 1
            continue

        # ── 本地不存在 → 保留原始值（movie等） ──
        if path not in local_files:
            stats['no_local'] += 1
            continue

        local_file = local_files[path]
        try:
            new_md5, new_size, _ = calc_md5_cached(local_file, cache)
        except Exception as e:
            print(f"  ⚠️  MD5计算失败，跳过: {path} ({e})")
            stats['bad_item'] += 1
            continue

        old_md5  = item.get("md5", "")
        old_size = -1
        fl = item.get("file_list")
        if isinstance(fl, list) and fl:
            old_size = fl[0].get("size", -1)

        # 相同则跳过
        if old_md5 == new_md5 and old_size == new_size:
            stats['unchanged'] += 1
            continue

        # 更新
        item["md5"] = new_md5
        if isinstance(fl, list) and fl:
            fl[0]["size"] = new_size
            # url 字段保持不变

        stats['replaced'] += 1

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"), ensure_ascii=False)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="非破坏性更新所有manifest JSON的MD5/size"
    )
    parser.add_argument('--resource-dir', required=True,
                        help="解压后的游戏resource根目录 (含 madomagi/resource/)")
    parser.add_argument('--manifest-dir', required=True,
                        help="存放所有manifest JSON的目录 (即 madomagi/)")
    args = parser.parse_args()

    resource_dir  = Path(args.resource_dir)
    manifest_dir  = Path(args.manifest_dir)
    cache_file    = Path(".md5_cache")

    if not resource_dir.exists():
        print(f"❌ resource目录不存在: {resource_dir}")
        return
    if not manifest_dir.exists():
        print(f"❌ manifest目录不存在: {manifest_dir}")
        return

    # ── 加载MD5缓存 ──
    cache = {}
    if cache_file.exists():
        try:
            with open(cache_file, 'rb') as f:
                cache = pickle.load(f)
        except Exception:
            cache = {}

    # ── 构建本地文件索引（相对于resource_dir） ──
    print(f"🔍 扫描本地资源: {resource_dir}")
    local_files: dict[str, Path] = {
        fp.relative_to(resource_dir).as_posix(): fp
        for fp in resource_dir.rglob("*")
        if fp.is_file()
    }
    print(f"   本地文件总数: {len(local_files)}")

    # ── 逐个更新manifest ──
    total_stats = dict(replaced=0, unchanged=0, no_local=0, bad_item=0)

    for name in MANIFEST_FILES:
        path = manifest_dir / name
        print(f"\n📄 处理: {name}")
        s = update_one_manifest(path, resource_dir, local_files, cache)
        print(f"   ✍️  更新={s['replaced']}  "
              f"✅ 不变={s['unchanged']}  "
              f"🎬 本地无={s['no_local']}  "
              f"⚠️  异常={s['bad_item']}")
        for k in total_stats:
            total_stats[k] += s[k]

    # ── 保存缓存 ──
    with open(cache_file, 'wb') as f:
        pickle.dump(cache, f)

    print("\n========= 📊 update_all_manifests 汇总 =========")
    print(f"  ✍️  MD5已更新    : {total_stats['replaced']}")
    print(f"  ✅ 无变化跳过   : {total_stats['unchanged']}")
    print(f"  🎬 本地无此文件  : {total_stats['no_local']}  ← movie等保留原始值")
    print(f"  ⚠️  格式异常跳过 : {total_stats['bad_item']}")
    print("================================================\n")


if __name__ == "__main__":
    main()
