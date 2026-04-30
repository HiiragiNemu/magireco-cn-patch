import json
import hashlib
import pickle
import argparse
from pathlib import Path


def calc_md5_cached(file_path: Path, cache: dict):
    """计算文件MD5，优先使用缓存（基于文件大小+修改时间）"""
    stat  = file_path.stat()
    size  = stat.st_size
    mtime = stat.st_mtime
    key   = str(file_path)

    if (key in cache
            and cache[key]['size']  == size
            and cache[key]['mtime'] == mtime):
        return cache[key]['md5'], size, True  # (md5, size, 命中缓存)

    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    md5 = h.hexdigest()
    cache[key] = {'md5': md5, 'size': size, 'mtime': mtime}
    return md5, size, False


def main():
    parser = argparse.ArgumentParser(
        description="非破坏性更新 asset_main.json 中的 MD5/size（仅更新本地存在的文件）"
    )
    parser.add_argument('--resource-dir', required=True,
                        help="解压后的游戏 resource 根目录，如 _game_res/madomagi/resource")
    parser.add_argument('--json-path', required=True,
                        help="需要被更新的 asset_main.json 路径")
    args = parser.parse_args()

    resource_dir = Path(args.resource_dir)
    json_path    = Path(args.json_path)
    cache_file   = Path(".md5_cache")

    # ── 前置检查 ──────────────────────────────────────────────
    if not json_path.exists():
        print(f"❌ 找不到清单: {json_path}")
        return
    if not resource_dir.exists():
        print(f"❌ 找不到资源目录: {resource_dir}")
        return

    # ── 加载 MD5 缓存 ─────────────────────────────────────────
    cache = {}
    if cache_file.exists():
        try:
            with open(cache_file, 'rb') as f:
                cache = pickle.load(f)
        except Exception:
            cache = {}

    # ── 读取 asset_main.json ──────────────────────────────────
    # 结构: [ {"path": "...", "md5": "...", "file_list": [{"size": N, "url": "..."}]} ]
    print(f"📂 读取清单: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if not isinstance(manifest, list):
        print("❌ asset_main.json 顶层不是数组，格式不符")
        return
    print(f"   清单条目数: {len(manifest)}")

    # ── 构建本地文件索引 ──────────────────────────────────────
    # key = 相对于 resource_dir 的正斜杠路径，与 JSON 里 "path" 字段一致
    print(f"🔍 扫描本地资源: {resource_dir}")
    local_files: dict[str, Path] = {
        f.relative_to(resource_dir).as_posix(): f
        for f in resource_dir.rglob("*")
        if f.is_file()
    }
    print(f"   本地文件数: {len(local_files)}")

    # ── 遍历清单，非破坏性更新 ────────────────────────────────
    count_replaced  = 0   # MD5/size 发生变化，已更新
    count_unchanged = 0   # 本地文件存在，MD5/size 与清单一致，跳过
    count_no_local  = 0   # 本地不存在（movie 等），保留清单原始值
    count_bad_item  = 0   # 清单条目格式异常，跳过

    for item in manifest:
        # 验证必要字段
        if not isinstance(item, dict):
            count_bad_item += 1
            continue
        path = item.get("path", "")
        if not path:
            count_bad_item += 1
            continue

        # ── 本地不存在：保留清单原始 MD5/size，不做任何修改 ──
        # movie 文件夹、未下载的资源都走这条路
        if path not in local_files:
            count_no_local += 1
            continue

        # ── 本地存在：计算真实 MD5 ────────────────────────────
        local_file = local_files[path]
        try:
            new_md5, new_size, from_cache = calc_md5_cached(local_file, cache)
        except Exception as e:
            print(f"⚠️  计算MD5失败，跳过: {path} ({e})")
            count_bad_item += 1
            continue

        # 读取清单中的旧值
        old_md5  = item.get("md5", "")
        old_size = -1
        fl = item.get("file_list")
        if isinstance(fl, list) and len(fl) > 0:
            old_size = fl[0].get("size", -1)

        # 相同则跳过（非破坏性核心逻辑）
        if old_md5 == new_md5 and old_size == new_size:
            count_unchanged += 1
            continue

        # ── 执行更新（只改 md5 和 file_list[0].size，其余字段不动）──
        item["md5"] = new_md5

        if isinstance(fl, list) and len(fl) > 0:
            fl[0]["size"] = new_size
            # url 字段保持不变

        count_replaced += 1

    # ── 保存更新后的清单（原地覆盖）────────────────────────────
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"), ensure_ascii=False)

    # ── 保存 MD5 缓存 ─────────────────────────────────────────
    with open(cache_file, 'wb') as f:
        pickle.dump(cache, f)

    # ── 输出报告 ──────────────────────────────────────────────
    print("\n========= 📊 update_asset_main 报告 =========")
    print(f"  ✍️  MD5已更新    : {count_replaced}  个")
    print(f"  ✅ 无变化跳过   : {count_unchanged} 个")
    print(f"  🎬 本地无此文件  : {count_no_local}  个  ← movie等保留原始MD5")
    print(f"  ⚠️  格式异常跳过 : {count_bad_item}  个")
    print(f"  📄 清单总条目   : {len(manifest)} 个")
    print("=============================================\n")


if __name__ == "__main__":
    main()