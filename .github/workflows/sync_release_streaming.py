#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error
from io import BytesIO

# 强制禁用输出缓冲，解决 GitHub Actions 日志卡顿问题
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
os.environ['PYTHONUNBUFFERED'] = '1'

def print_progress(current, total, prefix='', suffix='', length=30):
    """打印进度条"""
    percent = (current / total) * 100
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '░' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent:.1f}% ({current}/{total}) {suffix}', end='', flush=True)
    if current == total:
        print(flush=True)

def stream_sync_release():
    """流式同步 Release，不落盘，带实时进度显示"""
    
    # 只使用一个环境变量：GitHub Token
    token = os.environ.get('')
    if not token:
        print("❌ 错误：未设置  环境变量", flush=True)
        sys.exit(1)
    
    # 硬编码仓库信息（可根据需要修改）
    UPSTREAM_OWNER = "HiiragiNemu"
    UPSTREAM_REPO = "patch-front"
    ORG_OWNER = "MagirecoCN-Revival-Project"
    ORG_REPO = "patch-front"
    
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    print("🚀 开始同步上游 Release（流式传输，无落盘）", flush=True)
    print(f"📦 上游: {UPSTREAM_OWNER}/{UPSTREAM_REPO}", flush=True)
    print(f"📦 目标: {ORG_OWNER}/{ORG_REPO}", flush=True)
    
    try:
        # 1. 获取上游 Release
        print("\n🔍 获取上游 Release 信息...", flush=True)
        upstream_url = f"https://api.github.com/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/releases/latest"
        req = urllib.request.Request(upstream_url, headers=headers)
        
        with urllib.request.urlopen(req) as response:
            upstream_release = json.loads(response.read().decode())
        
        tag_name = upstream_release['tag_name']
        release_name = upstream_release['name']
        release_body = upstream_release['body']
        assets = upstream_release.get('assets', [])
        
        print(f"✅ 发现 Release: {tag_name} (包含 {len(assets)} 个文件)", flush=True)
        
        # 2. 删除组织仓库的旧 Release（如果存在）
        print("\n🗑️ 检查并清理旧 Release...", flush=True)
        try:
            old_release_url = f"https://api.github.com/repos/{ORG_OWNER}/{ORG_REPO}/releases/tags/{tag_name}"
            req = urllib.request.Request(old_release_url, headers=headers)
            with urllib.request.urlopen(req) as response:
                old_release = json.loads(response.read().decode())
                old_release_id = old_release['id']
                
                # 删除旧 Release
                delete_url = f"https://api.github.com/repos/{ORG_OWNER}/{ORG_REPO}/releases/{old_release_id}"
                req = urllib.request.Request(delete_url, headers=headers, method='DELETE')
                urllib.request.urlopen(req)
                print(f"✅ 已删除旧 Release: {tag_name}", flush=True)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"ℹ️ 没有旧 Release 需要清理", flush=True)
            else:
                raise
        
        # 3. 创建新的 Release
        print("\n📦 创建新 Release...", flush=True)
        create_url = f"https://api.github.com/repos/{ORG_OWNER}/{ORG_REPO}/releases"
        release_data = {
            'tag_name': tag_name,
            'name': release_name,
            'body': release_body,
            'draft': False,
            'prerelease': False
        }
        
        req = urllib.request.Request(
            create_url,
            data=json.dumps(release_data).encode(),
            headers={**headers, 'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            new_release = json.loads(response.read().decode())
            release_id = new_release['id']
        
        print(f"✅ 创建 Release 成功 (ID: {release_id})", flush=True)
        
        # 4. 流式同步每个资产（带进度条）
        print(f"\n📡 开始流式同步 {len(assets)} 个文件...", flush=True)
        
        for i, asset in enumerate(assets, 1):
            asset_name = asset['name']
            asset_url = asset['browser_download_url']
            asset_digest = asset.get('digest', '')
            asset_size = asset.get('size', 0)
            
            print_progress(i-1, len(assets), prefix=f"[{i}/{len(assets)}]", suffix=f"准备: {asset_name}")
            
            # 获取上传 URL
            upload_url = f"https://uploads.github.com/repos/{ORG_OWNER}/{ORG_REPO}/releases/{release_id}/assets?name={asset_name}&label={asset_digest}"
            
            # 流式传输：从上游读取，直接上传到组织仓库
            try:
                # 获取上游文件
                upstream_req = urllib.request.Request(asset_url)
                with urllib.request.urlopen(upstream_req) as upstream_response:
                    asset_data = upstream_response.read()
                    actual_size = len(asset_data)
                
                # 上传到组织仓库
                upload_req = urllib.request.Request(
                    upload_url,
                    data=asset_data,
                    headers={
                        **headers,
                        'Content-Type': 'application/octet-stream',
                        'Content-Length': str(actual_size)
                    },
                    method='POST'
                )
                
                with urllib.request.urlopen(upload_req) as upload_response:
                    print_progress(i, len(assets), prefix=f"[{i}/{len(assets)}]", suffix=f"完成: {asset_name} ({actual_size/1024/1024:.1f}MB)")
                    
            except Exception as e:
                print(f"\n❌ 同步 {asset_name} 失败: {e}", flush=True)
                raise
        
        print(f"\n🎉 Release {tag_name} 同步完成！共同步 {len(assets)} 个文件", flush=True)
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if hasattr(e, 'read') else str(e)
        print(f"\n❌ HTTP 错误 {e.code}: {error_body}", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 同步失败: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    stream_sync_release()
