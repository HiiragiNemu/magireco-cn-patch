import os
import sys
import json
from datetime import datetime
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.teo.v20220901 import teo_client, models

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    colors = {"INFO": "\033[92m", "WARN": "\033[93m", "ERROR": "\033[91m", "RESET": "\033[0m"}
    color = colors.get(level, colors["RESET"])
    print(f"{color}[{timestamp}] [{level}] {message}{colors['RESET']}")

def purge_domain_cache(secret_id, secret_key, zone_id, domain, domain_label):
    log(f"开始清除域名缓存: {domain_label} ({domain})")
    
    try:
        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "teo.tencentcloudapi.com"
        
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        
        client = teo_client.TeoClient(cred, "", client_profile)
        
        # 使用新版 API CreatePurgeTaskRequest
        req = models.CreatePurgeTaskRequest()
        # 使用 purge_prefix 清空整个域名下的所有文件缓存
        params = {
            "ZoneId": zone_id,
            "Type": "purge_prefix", 
            "Targets": [f"http://{domain}/*"] 
        }
        req.from_json_string(json.dumps(params))
        
        resp = client.CreatePurgeTask(req)
        log(f"✅ 成功提交 {domain_label} 的全站缓存清除任务，任务ID: {resp.RequestId}")
        return True, resp.RequestId
        
    except Exception as e:
        log(f"❌ 清除 {domain_label} 缓存失败: {e}", "ERROR")
        return False, str(e)

def main():
    log("🚨 开始执行全站CDN缓存清除操作 🚨")
    
    domain_choice = os.environ.get('DOMAIN_CHOICE', 'both')
    
    summary_lines = [
        "## 🧹 CDN缓存清除操作报告",
        f"**开始时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"**目标域名**: `{domain_choice}`",
        ""
    ]
    
    success_count = 0
    fail_count = 0
    
    if domain_choice in ['domain1', 'both']:
        domain = os.environ.get('S3_1_DOMAIN', '')
        if domain:
            success, result = purge_domain_cache(
                os.environ['QCLOUD_SECRET_ID'],
                os.environ['QCLOUD_SECRET_KEY'],
                os.environ['EDGEONE_ZONE_ID'],
                domain,
                "域名1"
            )
            if success:
                success_count += 1
                summary_lines.append(f"- ✅ **域名1 ({domain})**: 清除成功，任务ID: {result}")
            else:
                fail_count += 1
                summary_lines.append(f"- ❌ **域名1 ({domain})**: 清除失败 - {result}")
        else:
            summary_lines.append(f"- ⚠️ **域名1**: 未配置域名")
    
    if domain_choice in ['domain2', 'both']:
        domain = os.environ.get('S3_2_DOMAIN', '')
        if domain:
            success, result = purge_domain_cache(
                os.environ['QCLOUD_SECRET_ID'],
                os.environ['QCLOUD_SECRET_KEY'],
                os.environ['EDGEONE_ZONE_ID'],
                domain,
                "域名2"
            )
            if success:
                success_count += 1
                summary_lines.append(f"- ✅ **域名2 ({domain})**: 清除成功，任务ID: {result}")
            else:
                fail_count += 1
                summary_lines.append(f"- ❌ **域名2 ({domain})**: 清除失败 - {result}")
        else:
            summary_lines.append(f"- ⚠️ **域名2**: 未配置域名")
    
    summary_lines.extend([
        "",
        f"**操作结果**: 成功 {success_count} 个，失败 {fail_count} 个",
        f"**结束时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    ])
    
    # 写入 GitHub Step Summary
    github_step_summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if github_step_summary_path:
        with open(github_step_summary_path, 'a', encoding='utf-8') as f:
            f.write("\n".join(summary_lines))

if __name__ == "__main__":
    main()
