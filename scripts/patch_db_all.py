# scripts/patch_db_all.py
# 完全复刻本地 ADB 推送时的 DB 注入逻辑：
# 本地有的文件 → INSERT OR REPLACE；本地没有（movie等）→ 不动DB原始值
# 最后清空 asset_json 缓存表（与当年脚本完全一致）

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


def get_db_info(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    cols   = set()
    if "download_asset" in tables:
        cursor.execute("PRAGMA table_info(download_asset)")
        cols = {row[1] for row in cursor.fetchall()}
    return tables, cols


def inject_manifest(cursor, manifest_path: Path,
                    has_size: bool, local_paths: set):
    """返回 (ok, skipped, err)"""
    if not manifest_path.exists():
        print(f"  ⚠️  不存在: {manifest_path.name}")
        return 0, 0, 0

    with open(manifest_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"  ❌ 解析失败: {manifest_path.name} → {e}")
            return 0, 0, 1

    if not isinstance(data, list):
        return 0, 0, 1

    ok = skipped = err = 0

    for item in data:
        if not isinstance(item, dict):
            err += 1
            continue

        path = item.get("path", "")
        md5  = item.get("md5",  "")
        if not path or not md5:
            err += 1
            continue

        # movie → 不动DB（保留官方原始MD5）
        if "movie/" in path:
            skipped += 1
            continue

        # 本地不存在 → 不动DB
        if path not in local_paths:
            skipped += 1
            continue

        size = 0
        fl = item.get("file_list")
        if isinstance(fl, list) and fl:
            size = fl[0].get("size", 0)

        try:
            if has_size:
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
            ok += 1
        except sqlite3.Error as e:
            print(f"  ⚠️  写入失败: {path} → {e}")
            err += 1

    return ok, skipped, err


def main():
    parser = argparse.ArgumentParser(
        description="用所有manifest JSON覆盖注入DB（movie和本地无文件的不动）"
    )
    parser.add_argument("--manifest-dir", required=True,
                        help="manifest目录（madomagi/）")
    parser.add_argument("--db-path",      required=True,
                        help="madomagi.db路径")
    parser.add_argument("--resource-dir", required=True,
                        help="resource根目录，判断哪些文件本地存在")
    args = parser.parse_args()

    manifest_dir = Path(args.manifest_dir)
    db_path      = Path(args.db_path)
    resource_dir = Path(args.resource_dir)

    if not db_path.exists():
        print(f"❌ DB不存在: {db_path}")
        return

    print(f"🔍 扫描本地文件: {resource_dir}")
    local_paths = set()
    if resource_dir.exists():
        local_paths = {
            fp.relative_to(resource_dir).as_posix()
            for fp in resource_dir.rglob("*") if fp.is_file()
        }
    print(f"   本地文件数: {len(local_paths)}\n")

    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables, cols = get_db_info(cursor)
    print(f"📋 DB表: {sorted(tables)}")

    if "download_asset" not in tables:
        print("❌ download_asset表不存在")
        conn.close()
        return

    has_size = "size" in cols
    print(f"📋 列: {sorted(cols)}\n")

    total_ok = total_skip = total_err = 0

    for name in MANIFEST_FILES:
        mp = manifest_dir / name
        print(f"📄 注入 {name}")
        ok, skip, err = inject_manifest(cursor, mp, has_size, local_paths)
        print(f"   ✅写入={ok}  📂跳过(本地无/movie)={skip}  ⚠️错误={err}")
        total_ok   += ok
        total_skip += skip
        total_err  += err

    # ★ 清空所有缓存表（与当年本地脚本完全一致）
    cleaned = []
    for t in ("asset_json", "asset_json_cache", "download_asset_cache"):
        if t in tables:
            try:
                cursor.execute(f"DELETE FROM {t}")
                cleaned.append(t)
                print(f"🧹 清空缓存表: {t}")
            except sqlite3.Error:
                pass

    conn.commit()
    conn.close()

    print(f"\n====== 📊 patch_db_all 汇总 ======")
    print(f"  ✅ 写入   : {total_ok}")
    print(f"  📂 跳过   : {total_skip}  (movie + 本地无)")
    print(f"  ⚠️ 错误   : {total_err}")
    print(f"  🧹 清空表 : {cleaned}")
    print(f"==================================\n")


if __name__ == "__main__":
    main()
