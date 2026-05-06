import os
import sys
import json
import time
import shutil
from datetime import datetime
import logging

import boto3
from botocore.exceptions import ClientError
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.teo.v20220901 import teo_client, models

# ==========================================
# 1. 日志与输出设置 (全中文、带颜色、带Markdown摘要)
# ==========================================
LOG_COLORS = {
    'INFO': '\033[92m',    # 绿色
    'WARN': '\033[93m',    # 黄色
    'ERROR': '\033[91m',   # 红色
    'RESET': '\033[0m'     # 重置
}

class ActionLogger:
    def __init__(self):
        self.step_summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
        self.file_statuses = {}  # 存储每个文件的状态
        
    def init_summary(self):
        """初始化 Step Summary"""
        if self.step_summary_path:
            with open(self.step_summary_path, 'w', encoding='utf-8') as f:
                f.write("## 🚀 Action 运行报告\n\n")
                f.write(f"⏱️ **开始时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n")
                f.write("### 📋 文件处理状态\n\n")
                f.write("| 文件名 | 状态 | 详细信息 |\n")
                f.write("|--------|------|----------|\n")
    
    def update_file_status(self, filename, status, details=""):
        """更新单个文件的状态"""
        self.file_statuses[filename] = {'status': status, 'details': details}
        
        if self.step_summary_path:
            # 重新写入整个表格
            with open(self.step_summary_path, 'w', encoding='utf-8') as f:
                f.write("## 🚀 Action 运行报告\n\n")
                f.write(f"⏱️ **开始时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n")
                f.write("### 📋 文件处理状态\n\n")
                f.write("| 文件名 | 状态 | 详细信息 |\n")
                f.write("|--------|------|----------|\n")
                
                status_icons = {
                    '无需操作': '⚪',
                    '排队中': '🟡',
                    '下载中': '🔵',
                    '上传中': '🟣',
                    '已上传': '🟢',
                    '已完成': '✅',
                    '失败': '❌'
                }
                
                for fname, info in self.file_statuses.items():
                    icon = status_icons.get(info['status'], '⚪')
                    f.write(f"| {fname} | {icon} {info['status']} | {info['details']} |\n")
                
                f.write("\n")
    
    def log(self, message, level="INFO", filename=None, status=None, details=""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = LOG_COLORS.get(level, '')
        reset = LOG_COLORS['RESET']
        
        # 终端彩色输出
        print(f"{color}[{timestamp}] [{level}] {message}{reset}")
        
        # 如果提供了文件名和状态，更新 Step Summary
        if filename and status:
            self.update_file_status(filename, status, details)

logger = ActionLogger()

# ==========================================
# 2. S3 操作类
# ==========================================
class S3Handler:
    def __init__(self, endpoint, access_key, secret_key, region, bucket, domain, name="S3"):
        self.name = name
        self.bucket = bucket
        self.domain = domain
        
        if endpoint.endswith('/'):
            endpoint = endpoint[:-1]
            
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

    def delete_file(self, filename):
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=filename)
            logger.log(f"[{self.name}] 成功删除旧文件: {filename}", "INFO")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.log(f"[{self.name}] 文件 {filename} 不存在，无需删除。", "WARN")
                return True
            else:
                logger.log(f"[{self.name}] 删除文件 {filename} 失败: {e}", "ERROR")
                return False

    def upload_file(self, local_path, filename):
        try:
            self.s3_client.upload_file(local_path, self.bucket, filename)
            logger.log(f"[{self.name}] 成功上传文件: {filename}", "INFO")
            return True
        except Exception as e:
            logger.log(f"[{self.name}] 上传文件 {filename} 失败: {e}", "ERROR")
            return False

# ==========================================
# 3. edge 缓存刷新类
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

    def purge_cache(self, domain, filename):
        try:
            req = models.CreatePurgeTaskRequest()
            target_url = f"http://{domain}/{filename}"
            params = {
                "ZoneId": self.zone_id,
                "Type": "purge_url",
                "Targets": [target_url]
            }
            req.from_json_string(json.dumps(params))
            
            resp = self.client.CreatePurgeTask(req)
            logger.log(f"[edge] 成功提交缓存刷新任务: {target_url}", "INFO")
            return True, resp.RequestId
        except Exception as e:
            logger.log(f"[edge] 刷新缓存 {domain}/{filename} 失败: {e}", "ERROR")
            return False, str(e)

# ==========================================
# 4. 主逻辑
# ==========================================
def main():
    start_time = time.time()
    
    # 初始化 Step Summary
    logger.init_summary()
    
    # --- 4.1 读取环境变量 ---
    logger.log("正在从环境变量加载配置...", "INFO")
    try:
        s3_1_handler = S3Handler(
            endpoint=os.environ['S3_1_ENDPOINT'],
            access_key=os.environ['S3_1_ACCESS_KEY'],
            secret_key=os.environ['S3_1_SECRET_KEY'],
            region=os.environ['S3_1_REGION'],
            bucket=os.environ['S3_1_BUCKET'],
            domain=os.environ['S3_1_DOMAIN'],
            name="存储桶1"
        )
        
        s3_2_handler = S3Handler(
            endpoint=os.environ['S3_2_ENDPOINT'],
            access_key=os.environ['S3_2_ACCESS_KEY'],
            secret_key=os.environ['S3_2_SECRET_KEY'],
            region=os.environ['S3_2_REGION'],
            bucket=os.environ['S3_2_BUCKET'],
            domain=os.environ['S3_2_DOMAIN'],
            name="存储桶2"
        )
        
        edge_one_handler = EdgeOneHandler(
            secret_id=os.environ['QCLOUD_SECRET_ID'],
            secret_key=os.environ['QCLOUD_SECRET_KEY'],
            zone_id=os.environ['EDGEONE_ZONE_ID']
        )
        
        repo_name = os.environ.get('GH_REPO', 'HiiragiNemu/patch-front')
        logger.log("✅ 配置加载成功。", "INFO")
    except KeyError as e:
        logger.log(f"❌ 缺少必要的环境变量: {e}", "ERROR")
        sys.exit(1)

    # --- 4.2 获取 Latest Release 文件列表 ---
    logger.log(f"正在获取仓库 {repo_name} 的最新 Release 文件列表...", "INFO")
    import urllib.request
    
    gh_token = os.environ.get('', '')
    req = urllib.request.Request(f"https://api.github.com/repos/{repo_name}/releases/latest")
    if gh_token:
        req.add_header('Authorization', f'token {gh_token}')
    
    try:
        with urllib.request.urlopen(req) as response:
            release_data = json.loads(response.read().decode())
    except Exception as e:
        logger.log(f"获取 Release 信息失败: {e}", "ERROR")
        sys.exit(1)

    current_files = []
    for asset in release_data.get('assets', []):
        if not asset['name'].startswith('source code'):
            current_files.append(asset['name'])
    
    logger.log(f"当前 Release 包含 {len(current_files)} 个文件。", "INFO")

    # --- 4.3 文件变化检测 ---
    cache_file = '.github/workflows/.file_cache.json'
    previous_files = []
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            previous_files = json.load(f)
    
    # 找出新文件和已存在的文件
    new_files = [f for f in current_files if f not in previous_files]
    existing_files = [f for f in current_files if f in previous_files]
    
    # 初始化所有文件的状态
    for filename in existing_files:
        logger.update_file_status(filename, "无需操作", "文件已同步，无需处理")
    
    for filename in new_files:
        logger.update_file_status(filename, "排队中", "等待处理")
    
    if not new_files:
        logger.log("✅ 没有检测到新的或变更的文件。任务结束。", "INFO")
        # 更新 Summary 完成时间
        if logger.step_summary_path:
            with open(logger.step_summary_path, 'a', encoding='utf-8') as f:
                f.write(f"\n⏱️ **结束时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n")
                f.write("🟢 **状态**: 无变更，无需同步。\n")
        sys.exit(0)
    
    logger.log(f"检测到 {len(new_files)} 个新文件需要处理。", "INFO")

    # --- 4.4 分类、下载、上传、刷新 ---
    # 显式定义存储桶1的文件列表
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
    
    processed_files = []
    
    for filename in new_files:
        logger.log(f"--- 开始处理文件: {filename} ---", "INFO")
        logger.update_file_status(filename, "下载中", "正在从 GitHub 下载文件")
        
        # 分类判断
        if filename in bucket1_files:
            target_s3 = s3_1_handler
            logger.log(f"文件 {filename} 被分类到 存储桶1", "INFO")
        else:
            target_s3 = s3_2_handler
            logger.log(f"文件 {filename} 被分类到 存储桶2", "INFO")
        
        download_url = next((a['browser_download_url'] for a in release_data['assets'] if a['name'] == filename), None)
        if not download_url:
            logger.log(f"未找到文件 {filename} 的下载链接。", "ERROR")
            logger.update_file_status(filename, "失败", "未找到下载链接")
            processed_files.append({'filename': filename, 'success': False, 'error': '未找到下载链接'})
            continue
            
        local_path = f"/tmp/{filename}"
        try:
            # 下载文件
            urllib.request.urlretrieve(download_url, local_path)
            logger.log(f"文件 {filename} 下载完成。", "INFO")
            logger.update_file_status(filename, "上传中", f"正在上传到 {target_s3.name}")
            
            # 上传到 S3
            if target_s3.upload_file(local_path, filename):
                logger.update_file_status(filename, "已上传", f"已上传到 {target_s3.name}")
                
                # 刷新 CDN 缓存
                logger.update_file_status(filename, "已完成", "正在清除 CDN 缓存")
                success, task_id = edge_one_handler.purge_cache(target_s3.domain, filename)
                
                if success:
                    logger.update_file_status(filename, "已完成", f"CDN 缓存已清除 (任务ID: {task_id})")
                    processed_files.append({'filename': filename, 'success': True})
                else:
                    logger.update_file_status(filename, "失败", f"CDN 刷新失败: {task_id}")
                    processed_files.append({'filename': filename, 'success': False, 'error': f"CDN 刷新失败: {task_id}"})
            else:
                logger.update_file_status(filename, "失败", "上传失败")
                processed_files.append({'filename': filename, 'success': False, 'error': '上传失败'})
                
        except Exception as e:
            logger.log(f"处理文件 {filename} 时发生错误: {e}", "ERROR")
            logger.update_file_status(filename, "失败", str(e))
            processed_files.append({'filename': filename, 'success': False, 'error': str(e)})
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    # --- 4.5 更新缓存文件 ---
    logger.log(f"正在更新文件缓存列表...", "INFO")
    with open(cache_file, 'w') as f:
        json.dump(current_files, f, indent=2)
        
    # Git 提交缓存更新
    os.system('git config user.name "github-actions[bot]"')
    os.system('git config user.email "github-actions[bot]@users.noreply.github.com"')
    os.system(f'git add {cache_file}')
    os.system('git commit -m "chore: update file cache" || echo "No changes to commit"')
    os.system('git push || echo "No changes to push"')

    # --- 4.6 输出总结 ---
    end_time = time.time()
    
    # 更新 Summary 完成信息
    if logger.step_summary_path:
        with open(logger.step_summary_path, 'a', encoding='utf-8') as f:
            f.write(f"\n⏱️ **结束时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n")
            f.write(f"⏱️ **总耗时**: `{round(end_time - start_time, 2)}` 秒\n\n")
            
            # 统计结果
            success_count = sum(1 for f in processed_files if f['success'])
            fail_count = sum(1 for f in processed_files if not f['success'])
            
            if fail_count == 0:
                f.write("🟢 **状态**: 所有文件处理成功！\n")
            else:
                f.write(f"🟡 **状态**: 处理完成，{success_count} 个成功，{fail_count} 个失败。\n")

    logger.log("🎉 所有任务执行完毕！", "INFO")

if __name__ == "__main__":
    main()
