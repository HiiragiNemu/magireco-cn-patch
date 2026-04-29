import json
import hashlib
import pickle
import argparse
from pathlib import Path

def get_file_info_with_cache(file_path, cache):
    stat = file_path.stat()
    size = stat.st_size
    mtime = stat.st_mtime
    path_str = str(file_path)

    if path_str in cache and cache[path_str]['size'] == size and cache[path_str]['mtime'] == mtime:
        return cache[path_str]['md5'], size, True

    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    md5 = h.hexdigest()
    
    cache[path_str] = {'md5': md5, 'size': size, 'mtime': mtime}
    return md5, size, False

def main():
    parser = argparse.ArgumentParser(description="Update asset_main.json in-place based on actual files")
    parser.add_argument('--resource-dir', required=True, help="解压后的游戏 resource 根目录路径")
    parser.add_argument('--json-path', required=True, help="需要被更新的 asset_main.json 路径")
    args = parser.parse_args()

    resource_dir = Path(args.resource_dir)
    json_path = Path(args.json_path)
    cache_file = Path(".md5_cache")

    if not json_path.exists():
        print(f"❌ 错误: 找不到清单 {json_path}")
        return
    if not resource_dir.exists():
        print(f"❌ 错误: 找不到资源目录 {resource_dir}")
        return

    cache = {}
    if cache_file.exists():
        with open(cache_file, 'rb') as f:
            cache = pickle.load(f)

    print(f"📂 正在读取清单: {json_path.name}")
    with open(json_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    print(f"🔍 正在扫描本地目录: {resource_dir}")
    # 建立本地文件的相对路径映射（统一使用正斜杠对齐 JSON）
    local_files = {f.relative_to(resource_dir).as_posix(): f for f in resource_dir.rglob("*") if f.is_file()}
    json_paths = {item["path"] for item in manifest_data}

    replaced_count = 0
    cached_count = 0
    missing_in_local =[]
    
    print("⚙️ 正在对比并原地更新清单数据...")
    for item in manifest_data:
        target_path = item["path"]
        
        if target_path in local_files:
            local_file_path = local_files[target_path]
            new_md5, new_size, was_cached = get_file_info_with_cache(local_file_path, cache)
            
            # 如果 MD5 和 Size 已经完全匹配，则跳过
            if item["md5"] == new_md5 and item["file_list"][0]["size"] == new_size:
                cached_count += 1
                continue
            
            # 执行更新 (原地修改)
            item["md5"] = new_md5
            item["file_list"][0]["size"] = new_size
            replaced_count += 1
        else:
            missing_in_local.append(target_path)

    # 原地覆盖保存新的 JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, separators=(",", ":"), ensure_ascii=False)

    unlisted_files =[p for p in local_files.keys() if p not in json_paths]

    # 保存缓存文件
    with open(cache_file, 'wb') as f:
        pickle.dump(cache, f)

    print("\n================ 📊 处理报告 ================")
    print(f"✅ 原地更新文件: {json_path}")
    print(f"🚀 命中缓存（未变更直接跳过）: {cached_count} 个")
    print(f"✍️ 实际写入（MD5/Size已变动）: {replaced_count} 个")
    print(f"❌ 缺失文件（清单有本地无）: {len(missing_in_local)} 个")
    print(f"👻 增量文件（本地有清单无）: {len(unlisted_files)} 个")
    print("=============================================\n")

if __name__ == "__main__":
    main()