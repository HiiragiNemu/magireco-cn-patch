import os
import sys
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    colors = {"INFO": "\033[92m", "WARN": "\033[93m", "ERROR": "\033[91m", "RESET": "\033[0m"}
    color = colors.get(level, colors["RESET"])
    print(f"{color}[{timestamp}] [{level}] {message}{colors['RESET']}")

def delete_bucket_objects(endpoint, access_key, secret_key, region, bucket_name, bucket_label):
    log(f"开始清理存储桶: {bucket_label} ({bucket_name})")
    
    if endpoint.endswith('/'):
        endpoint = endpoint[:-1]
    
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    deleted_count = 0
    error_count = 0
    
    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name)
        
        for page in pages:
            if 'Contents' not in page:
                log(f"存储桶 {bucket_label} 为空")
                continue
                
            objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
            
            if objects_to_delete:
                try:
                    response = s3.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': objects_to_delete}
                    )
                    deleted = response.get('Deleted', [])
                    errors = response.get('Errors', [])
                    
                    deleted_count += len(deleted)
                    error_count += len(errors)
                    
                    for obj in deleted:
                        log(f"已删除: {obj['Key']}", "INFO")
                    for err in errors:
                        log(f"删除失败: {err['Key']} - {err['Message']}", "ERROR")
                        
                except ClientError as e:
                    log(f"批量删除失败: {e}", "ERROR")
                    error_count += len(objects_to_delete)
        
        log(f"存储桶 {bucket_label} 清理完成。成功: {deleted_count}, 失败: {error_count}")
        return deleted_count, error_count
        
    except Exception as e:
        log(f"清理存储桶 {bucket_label} 时发生错误: {e}", "ERROR")
        return 0, 0

def main():
    log("🚨 开始执行存储桶清空操作 🚨")
    
    bucket_choice = os.environ.get('BUCKET_CHOICE', 'both')
    
    summary_lines = [
        "## 🗑️ 存储桶清空操作报告",
        f"**开始时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"**目标存储桶**: `{bucket_choice}`",
        ""
    ]
    
    total_deleted = 0
    total_errors = 0
    
    if bucket_choice in ['bucket1', 'both']:
        deleted, errors = delete_bucket_objects(
            os.environ['S3_1_ENDPOINT'],
            os.environ['S3_1_ACCESS_KEY'],
            os.environ['S3_1_SECRET_KEY'],
            os.environ['S3_1_REGION'],
            os.environ['S3_1_BUCKET'],
            "存储桶1"
        )
        total_deleted += deleted
        total_errors += errors
        summary_lines.append(f"- **存储桶1**: 删除 {deleted} 个文件，失败 {errors} 个")
    
    if bucket_choice in ['bucket2', 'both']:
        deleted, errors = delete_bucket_objects(
            os.environ['S3_2_ENDPOINT'],
            os.environ['S3_2_ACCESS_KEY'],
            os.environ['S3_2_SECRET_KEY'],
            os.environ['S3_2_REGION'],
            os.environ['S3_2_BUCKET'],
            "存储桶2"
        )
        total_deleted += deleted
        total_errors += errors
        summary_lines.append(f"- **存储桶2**: 删除 {deleted} 个文件，失败 {errors} 个")
    
    summary_lines.extend([
        "",
        f"**总计删除**: {total_deleted} 个文件",
        f"**总计失败**: {total_errors} 个文件",
        f"**结束时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    ])
    
    print(f"summary<<EOF\n" + "\n".join(summary_lines) + "\nEOF")

if __name__ == "__main__":
    main()
