import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.error
from datetime import datetime
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.teo.v20220901 import teo_client, models

# ==========================================
# 1. GitHub Actions 分组日志工具
# ==========================================
class ActionGroup:
    """用于在 GitHub Actions 中创建折叠的分组"""
    @staticmethod
    def start_group(title):
        print(f"::group::{title}")
    
    @staticmethod
    def end_group():
        print("::endgroup::")

# ==========================================
# 2. 日志与输出设置
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
        self.file_statuses = {}
        self.obsolete_files = []  # 存储过时文件信息
        self.ignored_files = []   # 存储被忽略的文件信息
        self.token_info = {}      # 存储 token 调用信息
        self.start_time = datetime.now()
        
    def init_summary(self):
        """初始化 Step Summary"""
        if self.step_summary_path:
            with open(self.step_summary_path, 'w', encoding='utf-8') as f:
                f.write("## 🚀 Action 运行报告\n\n")
                f.write(f"⏱️ **开始时间**: `{self.start_time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n")
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
                f.write(f"⏱️ **开始时间**: `{self.start_time.strftime('%Y-%m-%d %H:%M:%S')}`\n\n")
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
                    '已忽略': '⚫',
                    '失败': '❌'
                }
                
                for fname, info in self.file_statuses.items():
                    icon = status_icons.get(info['status'], '⚪')
                    f.write(f"| {fname} | {icon} {info['status']} | {info['details']} |\n")
                
                f.write("\n")
    
    def add_obsolete_files_section(self):
        """添加过时文件报告部分"""
        if self.step_summary_path and self.obsolete_files:
            with open(self.step_summary_path, 'a', encoding='utf-8') as f:
                f.write("### 🗑️ 过时文件清理报告\n\n")
                f.write("| 存储桶 | 文件名 | 状态 | 详细信息 |\n")
                f.write("|--------|--------|------|----------|\n")
                
                for item in self.obsolete_files:
                    bucket = item['bucket']
                    filename = item['filename']
                    status = item['status']
                    details = item['details']
                    
                    status_icon = '✅' if status in ['已删除', '已纠正位置'] else '❌'
                    f.write(f"| {bucket} | {filename} | {status_icon} {status} | {details} |\n")
                
                f.write("\n")
    
    def add_token_info_section(self):
        """添加 Token 调用信息部分"""
        if self.step_summary_path and self.token_info:
            with open(self.step_summary_path, 'a', encoding='utf-8') as f:
                f.write("### 🔑 GitHub API Token 调用信息\n\n")
                f.write("| 项目 | 值 |\n")
                f.write("|------|----|\n")
                
                for key, value in self.token_info.items():
                    f.write(f"| {key} | {value} |\n")
                
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
    
    def finalize_summary(self, processed_files):
        """完成 Summary 的最终更新"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        if self.step_summary_path:
            with open(self.step_summary_path, 'a', encoding='utf-8') as f:
                f.write(f"\n⏱️ **结束时间**: `{end_time.strftime('%Y-%m-%d %H:%M:%S')}`\n")
                f.write(f"⏱️ **总耗时**: `{duration:.2f}` 秒\n\n")
                
                # 添加 Token 调用信息
                self.add_token_info_section()
                
                # 统计结果
                success_count = sum(1 for f in processed_files if f['success'])
                fail_count = sum(1 for f in processed_files if not f['success'])
                
                if fail_count == 0:
                    f.write("🟢 **状态**: 所有文件处理成功！\n")
                else:
                    f.write(f"🟡 **状态**: 处理完成，{success_count} 个成功，{fail_count} 个失败。\n")

logger = ActionLogger()

# ==========================================
# 3. GitHub API 客户端（使用 Fine-grained Token）
# ==========================================
class GitHubAPIClient:
    def __init__(self, token=None):
        self.token = token
        self.headers = {
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        
        if token:
            self.headers['Authorization'] = f'Bearer {token}'
            logger.log("使用 Fine-grained Personal Access Token 访问 GitHub API", "INFO")
            logger.token_info['Token 类型'] = 'Fine-grained Personal Access Token'
            logger.token_info['认证方式'] = 'Bearer Token'
            
            # 掩码显示 token（只显示前4位和后4位）
            if len(token) > 8:
                masked_token = token[:4] + '*' * (len(token) - 8) + token[-4:]
            else:
                masked_token = '*' * len(token)
            logger.token_info['Token 预览'] = masked_token
        else:
            logger.log("未提供 Token，将以匿名方式访问 GitHub API（可能受限于速率限制）", "WARN")
            logger.token_info['Token 类型'] = '匿名访问'
            logger.token_info['认证方式'] = '无'
            logger.token_info['Token 预览'] = '无'
    
    def get_latest_release(self, repo_owner, repo_name):
        """获取仓库的最新 Release 信息"""
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
        
        logger.log(f"正在调用 GitHub API: GET {url}", "INFO")
        logger.token_info['API 调用次数'] = logger.token_info.get('API 调用次数', 0) + 1
        
        req = urllib.request.Request(url, headers=self.headers)
        
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                rate_limit = response.headers.get('X-RateLimit-Limit', '未知')
                rate_remaining = response.headers.get('X-RateLimit-Remaining', '未知')
                rate_reset = response.headers.get('X-RateLimit-Reset', '未知')
                
                logger.log(f"API 调用成功，状态码: {response.status}", "INFO")
                logger.token_info['速率限制'] = rate_limit
                logger.token_info['剩余调用次数'] = rate_remaining
                logger.token_info['重置时间'] = datetime.fromtimestamp(int(rate_reset)).strftime('%Y-%m-%d %H:%M:%S') if rate_reset != '未知' else '未知'
                
                return data
        except urllib.error.HTTPError as e:
            logger.log(f"API 调用失败，HTTP 错误: {e.code} {e.reason}", "ERROR")
            logger.token_info['最后一次调用状态'] = f"失败 ({e.code} {e.reason})"
            raise
        except Exception as e:
            logger.log(f"API 调用失败: {e}", "ERROR")
            logger.token_info['最后一次调用状态'] = f"失败 ({str(e)})"
            raise

# ==========================================
# 4. S3 操作类（优化：直接流式上传）
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

    def list_files(self):
        """列出存储桶中的所有文件"""
        files = []
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        files.append(obj['Key'])
            
            logger.log(f"[{self.name}] 成功列出存储桶中的 {len(files)} 个文件", "INFO")
            return files
        except Exception as e:
            logger.log(f"[{self.name}] 列出文件失败: {e}", "ERROR")
            return []
    
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

    def upload_file_from_url(self, url, filename):
        """直接从 URL 流式上传文件到 S3，无需本地存储"""
        try:
            logger.log(f"[{self.name}] 开始从 URL 流式上传: {filename}", "INFO")
            
            # 使用 urllib 打开 URL 并获取文件大小
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                file_size = int(response.headers.get('Content-Length', 0))
                logger.log(f"[{self.name}] 文件大小: {file_size / 1024 / 1024:.2f} MB", "INFO")
                
                # 使用 put_object 直接上传流
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=filename,
                    Body=response.read(),
                    ContentLength=file_size
                )
            
            logger.log(f"[{self.name}] 成功流式上传文件: {filename}", "INFO")
            return True
        except Exception as e:
            logger.log(f"[{self.name}] 流式上传文件 {filename} 失败: {e}", "ERROR")
            return False

# ==========================================
# 5. edge 缓存刷新类（支持部分隐藏任务ID）
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

    def _mask_task_id(self, task_id):
        """部分隐藏任务ID，只显示前4位和后4位"""
        if not task_id or len(task_id) <= 8:
            return '*' * len(task_id) if task_id else '未知'
        return task_id[:4] + '*' * (len(task_id) - 8) + task_id[-4:]

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
            masked_task_id = self._mask_task_id(resp.RequestId)
            logger.log(f"[edge] 成功提交缓存刷新任务: {target_url}，任务ID: {masked_task_id}", "INFO")
            return True, masked_task_id
        except Exception as e:
            logger.log(f"[edge] 刷新缓存 {domain}/{filename} 失败: {e}", "ERROR")
            return False, str(e)

# ==========================================
# 6. 主逻辑
# ==========================================
def main():
    # 初始化 Step Summary
    logger.init_summary()
    
    # 定义过滤列表（不希望同步的文件）
    IGNORE_FILES = {'history-data-splited.tar.xz'}
    
    # --- 6.1 读取环境变量 ---
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
        
        # 使用 
        github_token = os.environ.get('', '')
        github_client = GitHubAPIClient(github_token)
        
        repo_name = os.environ.get('GH_REPO', 'HiiragiNemu/patch-front')
        repo_parts = repo_name.split('/')
        repo_owner = repo_parts[0] if len(repo_parts) > 1 else 'HiiragiNemu'
        repo_repo = repo_parts[1] if len(repo_parts) > 1 else 'patch-front'
        
        logger.log("✅ 配置加载成功。", "INFO")
    except KeyError as e:
        logger.log(f"❌ 缺少必要的环境变量: {e}", "ERROR")
        sys.exit(1)

    # --- 6.2 获取 Latest Release 文件列表 ---
    logger.log(f"正在获取仓库 {repo_name} 的最新 Release 文件列表...", "INFO")
    
    try:
        release_data = github_client.get_latest_release(repo_owner, repo_repo)
        logger.token_info['最后一次调用状态'] = '成功'
    except Exception as e:
        logger.log(f"获取 Release 信息失败: {e}", "ERROR")
        logger.token_info['最后一次调用状态'] = f'失败 ({str(e)})'
        sys.exit(1)

    current_files = []
    for asset in release_data.get('assets', []):
        if not asset['name'].startswith('source code'):
            current_files.append(asset['name'])
    
    logger.log(f"当前 Release 包含 {len(current_files)} 个文件。", "INFO")

    # --- 6.3 文件变化检测 ---
    cache_file = '.github/workflows/.file_cache.json'
    previous_files = []
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            previous_files = json.load(f)
    
    # 找出新文件和已存在的文件
    new_files = [f for f in current_files if f not in previous_files]
    existing_files = [f for f in current_files if f in previous_files]
    
    # 找出被忽略的文件
    ignored_files = [f for f in current_files if f in IGNORE_FILES]
    
    # 初始化所有文件的状态
    for filename in existing_files:
        if filename in IGNORE_FILES:
            logger.update_file_status(filename, "已忽略", "文件在过滤列表中，不同步")
            logger.ignored_files.append(filename)
        else:
            logger.update_file_status(filename, "无需操作", "文件已同步，无需处理")
    
    for filename in new_files:
        if filename in IGNORE_FILES:
            logger.update_file_status(filename, "已忽略", "文件在过滤列表中，不同步")
            logger.ignored_files.append(filename)
        else:
            logger.update_file_status(filename, "排队中", "等待处理")
    
    # --- 6.4 检测并清理过时文件（包括纠正位置）---
    ActionGroup.start_group("🗑️ 检测并清理过时文件")
    logger.log("开始检测存储桶中的过时文件...", "INFO")
    
    # 获取两个存储桶中的文件列表
    bucket1_files_list = s3_1_handler.list_files()
    bucket2_files_list = s3_2_handler.list_files()
    
    # 定义存储桶1应该包含的文件
    bucket1_should_contain = {
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
    
    # 处理存储桶1中的文件
    for filename in bucket1_files_list:
        # 检查是否是过时文件（不在当前Release中）
        if filename not in current_files:
            logger.log(f"发现存储桶1中的过时文件: {filename}", "WARN")
            logger.update_file_status(filename, "排队中", "准备删除过时文件")
            
            try:
                if s3_1_handler.delete_file(filename):
                    logger.update_file_status(filename, "已完成", "已删除过时文件")
                    logger.obsolete_files.append({
                        'bucket': '存储桶1',
                        'filename': filename,
                        'status': '已删除',
                        'details': '已从存储桶中删除'
                    })
                else:
                    logger.update_file_status(filename, "失败", "删除过时文件失败")
                    logger.obsolete_files.append({
                        'bucket': '存储桶1',
                        'filename': filename,
                        'status': '失败',
                        'details': '删除失败'
                    })
            except Exception as e:
                logger.log(f"删除过时文件 {filename} 时发生错误: {e}", "ERROR")
                logger.update_file_status(filename, "失败", f"删除失败: {str(e)}")
                logger.obsolete_files.append({
                    'bucket': '存储桶1',
                    'filename': filename,
                    'status': '失败',
                    'details': str(e)
                })
        else:
            # 文件在当前Release中，检查是否放错了桶
            if filename not in bucket1_should_contain:
                logger.log(f"文件 {filename} 在存储桶1中但应属于存储桶2，准备纠正位置", "WARN")
                logger.update_file_status(filename, "排队中", "文件放错位置，准备纠正")
                
                try:
                    # 从GitHub获取下载链接
                    download_url = next((a['browser_download_url'] for a in release_data['assets'] if a['name'] == filename), None)
                    if not download_url:
                        logger.log(f"未找到文件 {filename} 的下载链接。", "ERROR")
                        logger.update_file_status(filename, "失败", "未找到下载链接")
                        continue
                    
                    # 直接流式上传到正确的存储桶（存储桶2）
                    if s3_2_handler.upload_file_from_url(download_url, filename):
                        # 从错误存储桶删除
                        if s3_1_handler.delete_file(filename):
                            logger.update_file_status(filename, "已完成", "已纠正位置（移至存储桶2）")
                            logger.obsolete_files.append({
                                'bucket': '存储桶1→存储桶2',
                                'filename': filename,
                                'status': '已纠正位置',
                                'details': '文件从存储桶1移至存储桶2'
                            })
                        else:
                            logger.update_file_status(filename, "失败", "从原存储桶删除失败")
                            logger.obsolete_files.append({
                                'bucket': '存储桶1→存储桶2',
                                'filename': filename,
                                'status': '失败',
                                'details': '从原存储桶删除失败'
                            })
                    else:
                        logger.update_file_status(filename, "失败", "上传到正确存储桶失败")
                        logger.obsolete_files.append({
                            'bucket': '存储桶1→存储桶2',
                            'filename': filename,
                            'status': '失败',
                            'details': '上传到正确存储桶失败'
                        })
                        
                except Exception as e:
                    logger.log(f"纠正文件 {filename} 位置时发生错误: {e}", "ERROR")
                    logger.update_file_status(filename, "失败", f"纠正位置失败: {str(e)}")
                    logger.obsolete_files.append({
                        'bucket': '存储桶1→存储桶2',
                        'filename': filename,
                        'status': '失败',
                        'details': str(e)
                    })
    
    # 处理存储桶2中的文件
    for filename in bucket2_files_list:
        # 检查是否是过时文件（不在当前Release中）
        if filename not in current_files:
            logger.log(f"发现存储桶2中的过时文件: {filename}", "WARN")
            logger.update_file_status(filename, "排队中", "准备删除过时文件")
            
            try:
                if s3_2_handler.delete_file(filename):
                    logger.update_file_status(filename, "已完成", "已删除过时文件")
                    logger.obsolete_files.append({
                        'bucket': '存储桶2',
                        'filename': filename,
                        'status': '已删除',
                        'details': '已从存储桶中删除'
                    })
                else:
                    logger.update_file_status(filename, "失败", "删除过时文件失败")
                    logger.obsolete_files.append({
                        'bucket': '存储桶2',
                        'filename': filename,
                        'status': '失败',
                        'details': '删除失败'
                    })
            except Exception as e:
                logger.log(f"删除过时文件 {filename} 时发生错误: {e}", "ERROR")
                logger.update_file_status(filename, "失败", f"删除失败: {str(e)}")
                logger.obsolete_files.append({
                    'bucket': '存储桶2',
                    'filename': filename,
                    'status': '失败',
                    'details': str(e)
                })
        else:
            # 文件在当前Release中，检查是否放错了桶
            if filename in bucket1_should_contain:
                logger.log(f"文件 {filename} 在存储桶2中但应属于存储桶1，准备纠正位置", "WARN")
                logger.update_file_status(filename, "排队中", "文件放错位置，准备纠正")
                
                try:
                    # 从GitHub获取下载链接
                    download_url = next((a['browser_download_url'] for a in release_data['assets'] if a['name'] == filename), None)
                    if not download_url:
                        logger.log(f"未找到文件 {filename} 的下载链接。", "ERROR")
                        logger.update_file_status(filename, "失败", "未找到下载链接")
                        continue
                    
                    # 直接流式上传到正确的存储桶（存储桶1）
                    if s3_1_handler.upload_file_from_url(download_url, filename):
                        # 从错误存储桶删除
                        if s3_2_handler.delete_file(filename):
                            logger.update_file_status(filename, "已完成", "已纠正位置（移至存储桶1）")
                            logger.obsolete_files.append({
                                'bucket': '存储桶2→存储桶1',
                                'filename': filename,
                                'status': '已纠正位置',
                                'details': '文件从存储桶2移至存储桶1'
                            })
                        else:
                            logger.update_file_status(filename, "失败", "从原存储桶删除失败")
                            logger.obsolete_files.append({
                                'bucket': '存储桶2→存储桶1',
                                'filename': filename,
                                'status': '失败',
                                'details': '从原存储桶删除失败'
                            })
                    else:
                        logger.update_file_status(filename, "失败", "上传到正确存储桶失败")
                        logger.obsolete_files.append({
                            'bucket': '存储桶2→存储桶1',
                            'filename': filename,
                            'status': '失败',
                            'details': '上传到正确存储桶失败'
                        })
                        
                except Exception as e:
                    logger.log(f"纠正文件 {filename} 位置时发生错误: {e}", "ERROR")
                    logger.update_file_status(filename, "失败", f"纠正位置失败: {str(e)}")
                    logger.obsolete_files.append({
                        'bucket': '存储桶2→存储桶1',
                        'filename': filename,
                        'status': '失败',
                        'details': str(e)
                    })
    
    # 添加过时文件报告到 Step Summary
    logger.add_obsolete_files_section()
    
    ActionGroup.end_group()
    
    # 检查是否有工作需要做
    filtered_new_files = [f for f in new_files if f not in IGNORE_FILES]
    
    if not filtered_new_files and not logger.obsolete_files and not logger.ignored_files:
        logger.log("✅ 没有检测到新的或变更的文件，也没有过时文件，也没有被忽略的文件。任务结束。", "INFO")
        logger.finalize_summary([])
        sys.exit(0)
    
    if not filtered_new_files:
        logger.log("✅ 没有检测到新的或变更的文件，但已处理过时文件或被忽略的文件。任务结束。", "INFO")
        logger.finalize_summary([])
        sys.exit(0)
    
    logger.log(f"检测到 {len(filtered_new_files)} 个新文件需要处理。", "INFO")

    # --- 6.5 分类、下载、上传、刷新 ---
    processed_files = []
    
    for i, filename in enumerate(filtered_new_files, 1):
        # 为每个文件创建一个折叠的分组
        ActionGroup.start_group(f"📦 文件 {i}/{len(filtered_new_files)}: {filename}")
        
        logger.log(f"--- 开始处理文件: {filename} ---", "INFO")
        logger.update_file_status(filename, "下载中", "正在从 GitHub 下载文件")
        
        # 分类判断
        if filename in bucket1_should_contain:
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
            ActionGroup.end_group()
            continue
            
        try:
            # 直接流式上传到 S3
            logger.update_file_status(filename, "上传中", f"正在上传到 {target_s3.name}")
            if target_s3.upload_file_from_url(download_url, filename):
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
        
        ActionGroup.end_group()
    
    # --- 6.6 更新缓存文件 ---
    logger.log(f"正在更新文件缓存列表...", "INFO")
    with open(cache_file, 'w') as f:
        json.dump(current_files, f, indent=2)
        
    # Git 提交缓存更新
    os.system('git config user.name "github-actions[bot]"')
    os.system('git config user.email "github-actions[bot]@users.noreply.github.com"')
    os.system(f'git add {cache_file}')
    os.system('git commit -m "chore: update file cache" || echo "No changes to commit"')
    os.system('git push || echo "No changes to push"')

    # --- 6.7 完成 Summary ---
    logger.finalize_summary(processed_files)
    
    logger.log("🎉 所有任务执行完毕！", "INFO")

if __name__ == "__main__":
    main()
