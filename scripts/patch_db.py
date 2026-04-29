import json
import sqlite3
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Patch madomagi.db with latest asset_main.json")
    parser.add_argument('--json-path', required=True, help="最新版 asset_main.json 的路径")
    parser.add_argument('--db-path', required=True, help="需要被增量更新的 madomagi.db 路径")
    args = parser.parse_args()

    json_path = Path(args.json_path)
    db_path = Path(args.db_path)

    if not json_path.exists() or not db_path.exists():
        print(f"❌ 文件不存在，请检查路径！\nJSON: {json_path}\nDB: {db_path}")
        return

    # 读取新的 MD5 数据
    with open(json_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"💉 正在将汉化 MD5 增量注入数据库 {db_path.name}...")
    count = 0
    for item in manifest:
        path = item["path"]
        md5 = item["md5"]
        # INSERT OR REPLACE：如果有这个文件就更新MD5，如果没有就强行插入
        cursor.execute("INSERT OR REPLACE INTO download_asset (path, md5) VALUES (?, ?)", (path, md5))
        count += 1

    # 清理 asset_json 表里的 etag 缓存（强制引擎信任我们的本地文件）
    try:
        cursor.execute("DELETE FROM asset_json")
    except sqlite3.OperationalError:
        pass # 如果表不存在则忽略

    conn.commit()
    conn.close()
    print(f"✅ 数据库篡改完成！共原地更新/插入 {count} 条核心记录。")

if __name__ == "__main__":
    main()
