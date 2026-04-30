# scripts/patch_db.py
# 将所有 manifest JSON 的 MD5 注入 madomagi.db
# 规则：本地有的文件 → 注入CN版MD5；本地无的 → 不碰DB原始值

import json
import sqlite3
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


def get_db_cols(cursor) -> set:
    cursor.execute("PRAGMA table_info(download_asset)")
    return {row[1] for row in cursor.fetchall()}


def patch_from_manifest(
    cursor,
    manifest_path: Path,
    has_size_col:  bool,
    local_paths:   set,   # 本地存在的path集合（相对路径）
) -> tuple[int, int, int]:
    """
    返回 (count_ok, count_skip_movie, count_err)
    """
    if not manifest_path.exists():
        print(f"  ⚠️  不存在，跳过: {manifest_path.name}")
        return 0, 0, 0

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if not isinstance(manifest, list):
        print(f"  ❌ 非数组格式: {manifest_path.name}")
        return 0, 0, 1

    count_ok    = 0
    count_skip  = 0
    count_err   = 0

    for item in manifest:
        if not isinstance(item, dict):
            count_err += 1
            continue

        path = item.get("path", "")
        md5  = item.get("md5",  "")

        if not path or not md5:
            count_err += 1
            continue

        # ── 本地不存在（movie或未下载的文件）→ 不动DB ──
        # DB里原本有日服MD5，我们不覆盖它
        # 游戏下载movie时会用原始MD5校验，不能破坏
        if path not in local_paths:
            count_skip += 1
            continue

        # ── 本地存在 → 注入CN版MD5 ──
        size = 0
        fl = item.get("file_list")
        if isinstance(fl, list) and fl:
            size = fl[0].get("size", 0)

        try:
            if has_size_col:
                cursor.execute(
                    "INSERT OR REPLACE INTO download_asset "
                    "(path, md5, size) VALUES (?, ?, ?)",
                    (path, md5, size)
                )
            else:
                cursor.execute(
                    "INSERT OR REPLACE INTO download_asset "
                    "(path, md5) VALUES (?, ?)",
                    (path, md5)
                )
            count_ok += 1
        except sqlite3.Error as e:
            print(f"  ⚠️  写入失败: {path} → {e}")
            count_err += 1

    return count_ok, count_skip, count_err


def main():
    parser = argparse.ArgumentParser(
        description="将所有manifest JSON的MD5注入madomagi.db（不碰movie和本地无文件的条目）"
    )
    parser.add_argument('--manifest-dir', required=True,
                        help="存放所有manifest JSON的目录 (即 madomagi/)")
    parser.add_argument('--db-path', required=True,
                        help="madomagi.db 路径")
    parser.add_argument('--resource-dir', required=True,
                        help="本地resource根目录，用于判断哪些文件本地存在")
    args = parser.parse_args()

    manifest_dir = Path(args.manifest_dir)
    db_path      = Path(args.db_path)
    resource_dir = Path(args.resource_dir)

    if not db_path.exists():
        print(f"❌ DB不存在: {db_path}")
        return

    # ── 构建本地文件路径集合 ──
    print(f"🔍 扫描本地文件: {resource_dir}")
    if resource_dir.exists():
        local_paths: set = {
            fp.relative_to(resource_dir).as_posix()
            for fp in resource_dir.rglob("*")
            if fp.is_file()
        }
    else:
        local_paths = set()
    print(f"   本地文件总数: {len(local_paths)}")

    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查表结构
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    print(f"📋 DB表: {sorted(tables)}")

    if "download_asset" not in tables:
        print("❌ download_asset 表不存在！")
        conn.close()
        return

    cols         = get_db_cols(cursor)
    has_size_col = "size" in cols
    print(f"📋 download_asset列: {sorted(cols)}")

    # ── 处理所有manifest ──
    total_ok    = 0
    total_skip  = 0
    total_err   = 0

    for name in MANIFEST_FILES:
        path = manifest_dir / name
        print(f"\n📄 注入: {name}")
        ok, skip, err = patch_from_manifest(
            cursor, path, has_size_col, local_paths
        )
        print(f"   ✅ 注入={ok}  🎬 跳过(本地无)={skip}  ⚠️  错误={err}")
        total_ok   += ok
        total_skip += skip
        total_err  += err

    # ── 清除引擎缓存表 ──
    cleaned = []
    for cache_table in ["asset_json", "asset_json_cache", "download_asset_cache"]:
        if cache_table in tables:
            try:
                cursor.execute(f"DELETE FROM {cache_table}")
                cleaned.append(cache_table)
            except sqlite3.Error:
                pass

    conn.commit()
    conn.close()

    print("\n========= 📊 patch_db 汇总 ==================")
    print(f"  ✅ 成功注入    : {total_ok}")
    print(f"  🎬 跳过(本地无): {total_skip}  ← movie等DB保留原始值")
    print(f"  ⚠️  错误跳过   : {total_err}")
    print(f"  🧹 已清空缓存表: {cleaned}")
    print("=============================================\n")


if __name__ == "__main__":
    main()
