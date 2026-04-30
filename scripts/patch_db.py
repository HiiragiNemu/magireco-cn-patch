import json
import sqlite3
import argparse
from pathlib import Path


def get_db_schema(cursor) -> tuple[set, set]:
    """返回 (表名集合, download_asset的列名集合)"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    cols = set()
    if "download_asset" in tables:
        cursor.execute("PRAGMA table_info(download_asset)")
        cols = {row[1] for row in cursor.fetchall()}

    return tables, cols


def main():
    parser = argparse.ArgumentParser(
        description="将 asset_main.json 的 MD5 增量注入 madomagi.db"
    )
    parser.add_argument('--json-path', required=True,
                        help="已更新的 asset_main.json 路径")
    parser.add_argument('--db-path',   required=True,
                        help="需要注入的 madomagi.db 路径")
    args = parser.parse_args()

    json_path = Path(args.json_path)
    db_path   = Path(args.db_path)

    if not json_path.exists():
        print(f"❌ 找不到JSON: {json_path}")
        return
    if not db_path.exists():
        print(f"❌ 找不到DB: {db_path}")
        return

    # ── 读取 asset_main.json ──────────────────────────────────
    # 结构: [ {"path": "...", "md5": "...", "file_list": [{"size": N}]} ]
    with open(json_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if not isinstance(manifest, list):
        print("❌ asset_main.json 顶层不是数组，格式不符")
        return
    print(f"📋 读取清单: {len(manifest)} 条")

    # ── 连接 DB，检查结构 ─────────────────────────────────────
    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables, cols = get_db_schema(cursor)
    print(f"📋 DB表      : {sorted(tables)}")
    print(f"📋 download_asset列: {sorted(cols)}")

    has_size_col = "size" in cols

    # ── 遍历清单注入 ──────────────────────────────────────────
    count_ok     = 0
    count_skip   = 0   # movie 文件，保留DB原始值
    count_err    = 0

    for item in manifest:
        if not isinstance(item, dict):
            count_err += 1
            continue

        path = item.get("path", "")
        md5  = item.get("md5",  "")

        if not path or not md5:
            count_err += 1
            continue

        # ── movie文件：跳过，让游戏从服务器下载原版movie ────────
        # DB里本来就有movie的原始MD5，我们不覆盖它
        if "movie/" in path:
            count_skip += 1
            continue

        # ── 从 file_list[0] 取 size ──────────────────────────
        size = 0
        fl = item.get("file_list")
        if isinstance(fl, list) and len(fl) > 0:
            size = fl[0].get("size", 0)

        # ── 写入 DB ───────────────────────────────────────────
        try:
            if has_size_col:
                cursor.execute(
                    "INSERT OR REPLACE INTO download_asset (path, md5, size) VALUES (?, ?, ?)",
                    (path, md5, size)
                )
            else:
                cursor.execute(
                    "INSERT OR REPLACE INTO download_asset (path, md5) VALUES (?, ?)",
                    (path, md5)
                )
            count_ok += 1
        except sqlite3.Error as e:
            print(f"⚠️  DB写入失败: {path} → {e}")
            count_err += 1

    # ── 清除引擎缓存表（强制引擎重新信任本地文件）────────────
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

    print("\n========= 📊 patch_db 报告 ==================")
    print(f"  ✅ 成功注入    : {count_ok}  条")
    print(f"  🎬 跳过movie  : {count_skip} 条  ← DB保留原始值")
    print(f"  ⚠️  异常跳过   : {count_err} 条")
    print(f"  🧹 已清空缓存表: {cleaned}")
    print("=============================================\n")


if __name__ == "__main__":
    main()