import os
import sys
import json
import re
import time
import shutil
from datetime import datetime
import logging

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
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
        self.logs = []
        self.summary_parts = []

    def _log(self, level, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = LOG_COLORS.get(level, '')
        reset = LOG_COLORS['RESET']
        
        # 终端彩色输出
        print(f"{color}[{timestamp}] [{level}] {message}{reset}")
        
        # 存储纯文本日志
        self.logs.append(f"[{timestamp}] [{level}] {message}")

    def info(self, msg): self._log("INFO", msg)
    def warn(self, msg): self._log("WARN", msg)
    def error(self, msg): self._log("ERROR", msg)

    def add_summary_header(self, text):
        self.summary_parts.append(f"## {text}\n")

    def add_summary_table(self, headers, rows):
        # 简易表格生成器
        header_line = "| " + " | ".join(headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        body = "\n".join(["| " + " | ".join(row) + " |" for row in rows])
        self.summary_parts.append("\n".join([header_line, separator, body]) + "\n")

    def add_summary_text(self, text):
        self.summary_parts.append(text + "\n")

    def get_summary_output(self):
        return "\n".join(self.summary_parts)

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
            logger.info(f"[{self.name}] 成功删除旧文件: {filename}")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warn(f"[{self.name}] 文件 {filename} 不存在，无需删除。")
            else:
                raise

    def upload_file(self, local_path, filename):
        try:
            self.s3_client.upload_file(local_path, self.bucket, filename)
            logger.info(f"[{self.name}] 成功上传文件: {filename}")
        except Exception as e:
            logger.error(f"[{self.name}] 上传文件 {filename} 失败: {e}")
            raise

# ==========================================
# 3. edge 缓存刷新类 (已修复腾讯云新版SDK兼容性)
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
            # 新版 SDK 使用 CreatePurgeTaskRequest 替代了 PurgePathCacheRequest
            req = models.CreatePurgeTaskRequest()
            target_url = f"http://{domain}/{filename}"
            params = {
                "ZoneId": self.zone_id,
                "Type": "purge_url",  # 刷新单个文件 URL
                "Targets": [target_url]
            }
            req.from_json_string(json.dumps(params))
            
            resp = self.client.CreatePurgeTask(req)
            logger.info(f"[edge] 成功提交缓存刷新任务: {target_url}, 任务ID: {resp.RequestId}")
        except Exception as e:
            logger.error(f"[edge] 刷新缓存 {domain}/{filename} 失败: {e}")
            raise

# ==========================================
# 4. 主逻辑
# ==========================================
def main():
    start_time = time.time()
    logger.add_summary_header("🚀 Action 运行报告")
    logger.add_summary_text(f"⏱️ **开始时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")

    # --- 4.1 读取环境变量 ---
    logger.info("正在从环境变量加载配置...")
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
        logger.info("✅ 配置加载成功。")
    except KeyError as e:
        logger.error(f"❌ 缺少必要的环境变量: {e}")
        sys.exit(1)

    # --- 4.2 获取 Latest Release 文件列表 ---
    logger.info(f"正在获取仓库 {repo_name} 的最新 Release 文件列表...")
    import urllib.request
    
    gh_token = os.environ.get('', '')
    req = urllib.request.Request(f"https://api.github.com/repos/{repo_name}/releases/latest")
    if gh_token:
        req.add_header('Authorization', f'token {gh_token}')
    
    try:
        with urllib.request.urlopen(req) as response:
            release_data = json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"获取 Release 信息失败: {e}")
        sys.exit(1)

    current_files = []
    for asset in release_data.get('assets', []):
        if not asset['name'].startswith('source code'):
            current_files.append(asset['name'])
    
    logger.info(f"当前 Release 包含 {len(current_files)} 个文件。")

    # --- 4.3 文件变化检测 ---
    cache_file = '.github/workflows/.file_cache.json'
    previous_files = []
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            previous_files = json.load(f)
    
    new_files = [f for f in current_files if f not in previous_files]
    
    if not new_files:
        logger.info("✅ 没有检测到新的或变更的文件。任务结束。")
        logger.add_summary_text("🟢 **状态**: 无变更，无需同步。")
        sys.exit(0)
    
    logger.info(f"检测到 {len(new_files)} 个新文件: {', '.join(new_files)}")
    logger.add_summary_text(f"🟡 **状态**: 检测到 {len(new_files)} 个新文件，开始处理...")

    # --- 4.4 分类、下载、上传、刷新 ---
    results = []
    for filename in new_files:
        logger.info(f"--- 开始处理文件: {filename} ---")
        
        # 分类判断 (已修复正则表达式，增加了 cn_base_0X.zip 的匹配)
        pattern = r'^(cn_base_0[0-6]_db\.zip|cn_base_0[0-6]\.json\.zip|cn_base_0[2-6]\.zip|cn_hotupdate\.zip|cn_js_update\.zip|cn_magica_resource\.zip)$'
        if re.match(pattern, filename):
            target_s3 = s3_1_handler
        else:
            target_s3 = s3_2_handler
            
        logger.info(f"文件 {filename} 被分类到 {target_s3.name}")
        
        download_url = next((a['browser_download_url'] for a in release_data['assets'] if a['name'] == filename), None)
        if not download_url:
            logger.error(f"未找到文件 {filename} 的下载链接。")
            results.append([filename, "失败", "未找到下载链接"])
            continue
            
        local_path = f"/tmp/{filename}"
        try:
            logger.info(f"正在下载文件: {filename}...")
            urllib.request.urlretrieve(download_url, local_path)
            logger.info(f"文件 {filename} 下载完成。")
            
            logger.info(f"正在将 {filename} 上传到 {target_s3.name}...")
            target_s3.delete_file(filename)
            target_s3.upload_file(local_path, filename)
            
            logger.info(f"正在刷新 CDN 缓存: {target_s3.domain}/{filename}")
            edge_one_handler.purge_cache(target_s3.domain, filename)
            
            results.append([filename, "成功", ""])
            logger.info(f"--- 文件 {filename} 处理完成 ---")
            
        except Exception as e:
            logger.error(f"处理文件 {filename} 时发生错误: {e}")
            results.append([filename, "失败", str(e)])
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    # --- 4.5 更新缓存文件 ---
    logger.info(f"正在更新文件缓存列表...")
    with open(cache_file, 'w') as f:
        json.dump(current_files, f, indent=2)
        
    # Git 提交缓存更新
    os.system('git config user.name "github-actions[bot]"')
    os.system('git config user.email "github-actions[bot]@users.noreply.github.com"')
    os.system(f'git add {cache_file}')
    os.system('git commit -m "chore: update file cache" || echo "No changes to commit"')
    os.system('git push || echo "No changes to push"')

    # --- 4.6 输出总结 ---
    logger.add_summary_text("### 📊 处理结果:")
    headers = ["文件名", "状态", "错误信息"]
    logger.add_summary_table(headers, results)
    
    end_time = time.time()
    logger.add_summary_text(f"⏱️ **总耗时**: `{round(end_time - start_time, 2)}` 秒")

    # 将总结写入 GitHub Actions Step Summary
    summary_content = logger.get_summary_output()
    github_step_summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if github_step_summary_path:
        with open(github_step_summary_path, 'a', encoding='utf-8') as f:
            f.write(summary_content)

    logger.info("🎉 所有任务执行完毕！")

if __name__ == "__main__":
    main()
