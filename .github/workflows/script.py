#!/usr/bin/env python3
import os
import sys
import json
import time
import shutil
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from github import Github
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.teo.v20220901 import teo_client, models

# ==========================================
# 1. GitHub Actions 工具函数
# ==========================================
def set_output(name, value):
    """设置 GitHub Actions 输出"""
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f'{name}={value}\n')

def start_group(title):
    print(f"::group::{title}")

def end_group():
    print("::endgroup::")

# ==========================================
# 2. 日志与状态管理
# ==========================================
class Logger:
    def __init__(self):
        self.step_summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
        self.state_file = Path('.github/workflows/state.json')
        self.current_state = self.load_state()
        
    def load_state(self):
        """加载持久化状态"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "last_release_id": None,
            "synced_files": [],
            "last_sync_time": None
        }
    
    def save_state(self):
        """保存状态到文件"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.current_state, f, indent=2)
    
    def init_summary(self):
        """初始化 Step Summary"""
        if self.step_summary_path:
            with open(self.step_summary_path, 'w', encoding='utf-8') as f:
                f.write("## 🔄 Release 同步报告\n\n")
                f.write(f"⏱️ **开始时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n")
                f.write("| 步骤 | 状态 | 详情 |\n")
                f.write("|------|------|------|\n")
                f.write("| 🔍 检测变更 | 🟡 进行中 | 检查最新 Release |\n")
    
    def update_step(self, step, status_icon, details):
        """更新步骤状态"""
        if self.step_summary_path:
            # 重新读取并更新
            with open(self.step_summary_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if step in line:
                    lines[i] = f"| {step} | {status_icon} | {details} |"
                    break
            
            with open(self.step_summary_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
    
    def finalize(self, success, message):
        """完成报告"""
        if self.step_summary_path:
            with open(self.step_summary_path, 'a', encoding='utf-8') as f:
                f.write(f"\n⏱️ **结束时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n")
                if success:
                    f.write(f"🟢 **最终结果**: {message}\n")
                else:
                    f.write(f"🔴 **最终结果**: {message}\n")

logger = Logger()

# ==========================================
# 3. GitHub API 客户端
# ==========================================
class GitHubClient:
    def __init__(self, token, repo_name):
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_name)
    
    def get_latest_release(self):
        """获取最新 Release"""
        releases = list(self.repo.get_releases())
        if releases:
            return releases[0]
        return None
    
    def get_release_files(self, release):
        """获取 Release 文件列表"""
        files = []
        for asset in release.get_assets():
            if not asset.name.startswith('source code'):
                files.append({
                    'name': asset.name,
                    'url': asset.browser_download_url,
                    'size': asset.size,
                    'id': asset.id
                })
        return files

# ==========================================
# 4. S3 操作类
# ==========================================
class S3Handler:
    def __init__(self, endpoint, access_key, secret_key, region, bucket, domain, name="S3"):
        self.name = name
        self.bucket = bucket
        self.domain = domain
        
        if endpoint.endswith('/'):
            endpoint = endpoint[:-1]
            
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
    
    def exists(self, filename):
        """检查文件是否存在"""
        try:
            self.client.head_object(Bucket=self.bucket, Key=filename)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def upload(self, local_path, filename):
        """上传文件"""
        self.client.upload_file(local_path, self.bucket, filename)
        return True

# ==========================================
# 5. edge 缓存刷新
# ==========================================
class EdgeOneHandler:
    def __init__(self, secret_id, secret_key, zone_id):
        self.zone_id = zone_id
        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "teo.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        self.client = teo_client.TeoClient(cred, "", client_profile)
    
    def purge(self, url):
        """刷新缓存"""
        req = models.CreatePurgeTaskRequest()
        params = {
            "ZoneId": self.zone_id,
            "Type": "purge_url",
            "Targets": [url]
        }
        req.from_json_string(json.dumps(params))
        resp = self.client.CreatePurgeTask(req)
        return resp.RequestId

# ==========================================
# 6. 主逻辑
# ==========================================
def main():
    start_time = time.time()
    
    # 初始化
    logger.init_summary()
    
    try:
        # 1. 初始化客户端
        start_group("🔧 初始化客户端")
        github_client = GitHubClient(
            os.environ[''],
            os.environ['REPO_NAME']
        )
        
        s3_1 = S3Handler(
            endpoint=os.environ['S3_1_ENDPOINT'],
            access_key=os.environ['S3_1_ACCESS_KEY'],
            secret_key=os.environ['S3_1_SECRET_KEY'],
            region=os.environ['S3_1_REGION'],
            bucket=os.environ['S3_1_BUCKET'],
            domain=os.environ['S3_1_DOMAIN'],
            name="存储桶1"
        )
        
        s3_2 = S3Handler(
            endpoint=os.environ['S3_2_ENDPOINT'],
            access_key=os.environ['S3_2_ACCESS_KEY'],
            secret_key=os.environ['S3_2_SECRET_KEY'],
            region=os.environ['S3_2_REGION'],
            bucket=os.environ['S3_2_BUCKET'],
            domain=os.environ['S3_2_DOMAIN'],
            name="存储桶2"
        )
        
        edge = EdgeOneHandler(
            secret_id=os.environ['QCLOUD_SECRET_ID'],
            secret_key=os.environ['QCLOUD_SECRET_KEY'],
            zone_id=os.environ['EDGEONE_ZONE_ID']
        )
        end_group()
        
        # 2. 检测最新 Release
        start_group("🔍 检测最新 Release")
        logger.update_step("🔍 检测变更", "🟡", "获取最新 Release...")
        
        latest_release = github_client.get_latest_release()
        if not latest_release:
            logger.update_step("🔍 检测变更", "⚪", "没有找到 Release")
            logger.finalize(True, "没有 Release，无需同步")
            return
        
        release_id = latest_release.id
        release_tag = latest_release.tag_name
        
        # 检查是否是新 Release
        if release_id == logger.current_state.get('last_release_id'):
            logger.update_step("🔍 检测变更", "⚪", f"Release {release_tag} 已处理")
            logger.finalize(True, "无新 Release，跳过同步")
            return
        
        logger.update_step("🔍 检测变更", "🟢", f"发现新 Release: {release_tag}")
        end_group()
        
        # 3. 获取文件列表
        start_group("📁 获取文件列表")
        files = github_client.get_release_files(latest_release)
        
        if not files:
            logger.update_step("📁 获取文件", "⚪", "Release 中没有文件")
            logger.finalize(True, "Release 为空")
            return
        
        logger.update_step("📁 获取文件", "🟢", f"找到 {len(files)} 个文件")
        end_group()
        
        # 4. 处理文件
        bucket1_files = {
            'cn_base_00_db.zip',
            'cn_base_01.json.zip',
            'cn_base_02.zip',
            'cn_base_03.zip',
            'cn_base_04.zip',
            'cn_base_05.zip',
            'cn_base_06.zip',
            'cn_hotupdate.zip',
            'cn_js_update.zip',
            'cn_magica_resource.zip'
        }
        
        synced_files = []
        failed_files = []
        
        for i, file_info in enumerate(files, 1):
            filename = file_info['name']
            
            start_group(f"📦 文件 {i}/{len(files)}: {filename}")
            
            # 检查是否已同步过
            if filename in logger.current_state.get('synced_files', []):
                print(f"⚪ 文件 {filename} 已同步过，跳过")
                end_group()
                continue
            
            # 选择存储桶
            if filename in bucket1_files:
                s3 = s3_1
                domain = os.environ['S3_1_DOMAIN']
            else:
                s3 = s3_2
                domain = os.environ['S3_2_DOMAIN']
            
            print(f"📤 上传到 {s3.name}...")
            
            # 下载文件
            print(f"⬇️ 下载文件: {filename}")
            local_path = f"/tmp/{filename}"
            os.system(f"curl -L '{file_info['url']}' -o {local_path}")
            
            # 上传到 S3
            print(f"⬆️ 上传到 S3...")
            s3.upload(local_path, filename)
            
            # 刷新 CDN
            url = f"http://{domain}/{filename}"
            print(f"🔄 刷新 CDN: {url}")
            task_id = edge.purge(url)
            
            # 记录成功
            synced_files.append(filename)
            print(f"✅ 文件 {filename} 处理完成")
            
            # 清理临时文件
            if os.path.exists(local_path):
                os.remove(local_path)
            
            end_group()
        
        # 5. 更新状态
        logger.current_state['last_release_id'] = release_id
        logger.current_state['synced_files'].extend(synced_files)
        logger.current_state['last_sync_time'] = datetime.now().isoformat()
        logger.save_state()
        
        # 6. 完成报告
        duration = int(time.time() - start_time)
        logger.finalize(True, f"同步完成！处理了 {len(synced_files)} 个文件，耗时 {duration} 秒")
        
        # 设置输出
        set_output('summary', f"同步完成！处理了 {len(synced_files)} 个文件")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.finalize(False, f"执行失败: {str(e)}")
        set_output('summary', f"执行失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
