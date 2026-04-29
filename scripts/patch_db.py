#!/usr/bin/env python3
"""
patch_db.py
用途：将 asset_main.json 中所有条目的 path/md5 批量注入 madomagi.db
用法：
    python3 scripts/patch_db.py \
        --json-path madomagi/asset_main.json \
        --db-path   madomagi/madomagi.db
"""

import argparse
import json
import sqlite3
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--json-path", required=True,
                   help="已更新好 MD5 的 asset_main.json 路径")
    p.add_argument("--db-path",   required=True,
                   help="madomagi.db 路径")
    return p.parse_args()


def main():
    args = parse_args()
    json_path = Path(args.json_path)
    db_path   = Path(args.db_path)

    if not json_path.exists():
        raise FileNotFoundError(f"找不到 JSON 文件：{json_path}")
    if not db_path.exists():
        raise FileNotFoundError(f"找不到数据库：{db_path}")

    print(f"📂 读取清单：{json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"💾 连接数据库：{db_path}")
    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 确保表存在（兼容旧 DB）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_asset (
            path TEXT PRIMARY KEY,
            md5  TEXT NOT NULL
        )
    """)

    # 清空 asset_json 缓存，强制游戏重新信任本地文件
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_json'"
    )
    if cursor.fetchone():
        cursor.execute("DELETE FROM asset_json")
        print("🧹 asset_json 缓存已清空")

    print("💉 批量注入 MD5...")
    conn.execute("BEGIN TRANSACTION")
    count = 0
    for item in manifest:
        path = item["path"]
        md5  = item["md5"]
        cursor.execute(
            "INSERT OR REPLACE INTO download_asset (path, md5) VALUES (?, ?)",
            (path, md5)
        )
        count += 1

    conn.commit()
    conn.close()

    print(f"\n✅ 数据库更新完成！共写入 {count} 条记录。")


if __name__ == "__main__":
    main()
