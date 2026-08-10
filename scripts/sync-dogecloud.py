#!/usr/bin/env python3
"""DogeCloud 独立同步流水线（Doge 系）。

多吉云存储与 R2 不同：数据面不能直接用静态 AccessKey/SecretKey 访问，
必须先走控制面 /auth/tmp_token.json 换「三段式 STS 临时密钥」再用 boto3
（仅 Virtual Hosted Style）。因此 DogeCloud **自成一系、独立成步**，
不混进 sync-and-upload.yml 的 R2 系（R2 桶 + EdgeOne/ESA/Cloudflare）。

本脚本流程：
  1. tmp_token 换 STS（POST /auth/tmp_token.json，TOKEN 签名）
  2. 列 Doge 桶现有文件
  3. 取上游 latest Release asset 清单（name → digest + browser_download_url）
  4. 与 LAST_DOGE_FINGERPRINTS 比对 → to_upload / unchanged / to_delete
  5. 流式上传 to_upload（boto3，virtual hosted style，与 R2 同款边下边传）
  6. confirm_cleanup=true 时删除 to_delete，否则仅列出警告（与 R2 语义一致）
  7. 刷新 DOGE_DOMAIN 的 CDN 缓存（POST /cdn/refresh/add.json，rtype=url）
  8. 保存 LAST_DOGE_FINGERPRINTS

环境变量：
  DOGE_ACCESS_KEY / DOGE_SECRET_KEY / DOGE_BUCKET / DOGE_DOMAIN / DOGE_API_BASE
  GH_TOKEN、UPSTREAM_OWNER / UPSTREAM_REPO、CONFIRM_CLEANUP
"""
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(line_buffering=True)

import boto3
from botocore.client import Config

# ══════════════════════════════════════════════════════════════════
# 样式 / 日志
# ══════════════════════════════════════════════════════════════════
class C:
    RESET         = "\033[0m"
    BOLD          = "\033[1m"
    DIM           = "\033[2m"
    RED           = "\033[31m"
    BRIGHT_GREEN  = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE   = "\033[94m"
    BRIGHT_CYAN   = "\033[96m"
    BRIGHT_WHITE  = "\033[97m"
    CYAN          = "\033[36m"


def c(col, t):
    return f"{col}{t}{C.RESET}"


def header(t):
    bar = "═" * 60
    print(f"\n{c(C.BOLD + C.BRIGHT_BLUE, bar)}")
    print(c(C.BOLD + C.BRIGHT_WHITE, f"  {t}"))
    print(f"{c(C.BOLD + C.BRIGHT_BLUE, bar)}\n", flush=True)


def section(t):
    print(f"\n{c(C.BOLD + C.CYAN, '┌─ ' + t)}", flush=True)


def info(t, indent=0):
    print(f"{'  ' * indent}{c(C.BRIGHT_BLUE, 'ℹ')} {t}", flush=True)


def ok(t, indent=0):
    print(f"{'  ' * indent}{c(C.BRIGHT_GREEN, '✔')} {t}", flush=True)


def warn(t, indent=0):
    print(f"{'  ' * indent}{c(C.BRIGHT_YELLOW, '⚠')} {t}", flush=True)


def err(t, indent=0):
    print(f"{'  ' * indent}{c(C.RED, '✘')} {t}", flush=True)


# ══════════════════════════════════════════════════════════════════
# 多吉云控制面（tmp_token / CDN refresh 同一套 TOKEN 签名）
# ══════════════════════════════════════════════════════════════════
class Doge:
    """多吉云 S3 兼容镜像 + 自有 CDN 刷新（临时密钥）。"""

    def __init__(self):
        self.ak       = os.environ.get('DOGE_ACCESS_KEY', '').strip()
        self.sk       = os.environ.get('DOGE_SECRET_KEY', '').strip()
        self.bucket   = os.environ.get('DOGE_BUCKET', '').strip()      # 空间名（进 scopes）
        self.domain   = os.environ.get('DOGE_DOMAIN', '').strip()      # CDN 域名（刷新目标）
        self.api_base = (os.environ.get('DOGE_API_BASE', '')
                         or 'https://api.dogecloud.com').rstrip('/')
        self._s3      = None
        self._s3_bucket = None
        self._expire_at = 0
        self._enabled = bool(self.ak and self.sk and self.bucket)
        if not self._enabled:
            warn("[Doge] 未配置 DOGE_ACCESS_KEY/DOGE_SECRET_KEY/DOGE_BUCKET，跳过多吉云", indent=1)

    # ── 控制面签名：TOKEN <AK>:<hex(hmac_sha1(uri+"\n"+body, SK))> ──
    def _sign(self, path, body_bytes):
        sig = hmac.new(self.sk.encode(), path.encode() + b"\n" + body_bytes,
                       hashlib.sha1).hexdigest()
        return f"TOKEN {self.ak}:{sig}"

    def _post_json(self, path, payload):
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        req = urllib.request.Request(
            f"{self.api_base}{path}", data=body,
            headers={"Authorization": self._sign(path, body),
                     "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())

    def _post_form(self, path, form):
        # 文档示例为表单编码（urls 传 JSON 数组字符串），签名对原始 body 字节
        body = "&".join(f"{k}={v}" for k, v in form.items()).encode()
        req = urllib.request.Request(
            f"{self.api_base}{path}", data=body,
            headers={"Authorization": self._sign(path, body),
                     "Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())

    # ── 换临时密钥 → boto3 S3 ──
    def _ensure_s3(self):
        # 剩余 >5 分钟复用；临近过期才续期，避免长任务中途 401
        if self._s3 is not None and time.time() < self._expire_at - 300:
            return
        data = self._post_json("/auth/tmp_token.json", {
            # OSS_FULL：需要上传+删除（stale 清理）。OSS_UPLOAD 只有上传权限。
            # scopes 限定单空间，最小授权。
            "channel": "OSS_FULL",
            "scopes": [self.bucket],
            "ttl": 7200,
        })
        if str(data.get("code", "")) != "200":
            raise RuntimeError(f"[Doge] tmp_token 失败: {data}")
        creds       = data["data"]["Credentials"]
        bucket_info = data["data"]["Buckets"][0]
        self._s3_bucket = bucket_info["s3Bucket"]      # 底层桶名，非空间名
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=creds["accessKeyId"],
            aws_secret_access_key=creds["secretAccessKey"],
            aws_session_token=creds["sessionToken"],
            endpoint_url=bucket_info["s3Endpoint"],
            config=Config(
                # 多吉云只支持 Virtual Hosted Style，不支持 Path Style
                s3={"addressing_style": "virtual"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        self._expire_at = time.time() + 7200
        info(f"[Doge] 已换取 STS 临时凭证 endpoint={bucket_info['s3Endpoint']} "
             f"s3Bucket={self._s3_bucket}")

    def list_files(self):
        if not self._enabled:
            return []
        self._ensure_s3()
        paginator = self._s3.get_paginator('list_objects_v2')
        return [obj['Key'] for page in paginator.paginate(Bucket=self._s3_bucket)
                if 'Contents' in page for obj in page['Contents']]

    def delete_file(self, filename):
        if not self._enabled:
            return False
        self._ensure_s3()
        try:
            self._s3.delete_object(Bucket=self._s3_bucket, Key=filename)
            ok(f"[Doge] 删除: {filename}", indent=1)
            return True
        except Exception as e:
            err(f"[Doge] 删除失败: {e}", indent=1)
            return False

    def upload_file_from_url(self, url, filename):
        if not self._enabled:
            return False
        self._ensure_s3()
        try:
            info(f"[Doge] 流式上传: {filename}", indent=1)
            with urllib.request.urlopen(urllib.request.Request(url)) as response:
                self._s3.upload_fileobj(response, self._s3_bucket, filename)
            ok(f"[Doge] 上传完成: {filename}", indent=1)
            return True
        except Exception as e:
            err(f"[Doge] 上传失败: {e}", indent=1)
            return False

    def purge_cache(self, filename):
        if not self._enabled or not self.domain:
            warn("[Doge] 未配置 DOGE 密钥/域名，跳过 CDN 刷新", indent=1)
            return False
        try:
            target_url = (f"http://{self.domain}/{filename}" if filename
                          else f"http://{self.domain}/")
            data = self._post_form("/cdn/refresh/add.json", {
                "rtype": "url",
                "urls": json.dumps([target_url], separators=(",", ":")),
            })
            if str(data.get("code", "")) != "200":
                raise RuntimeError(str(data))
            ok(f"[Doge] 缓存刷新: {target_url}", indent=1)
            return True
        except Exception as e:
            err(f"[Doge] 刷新失败: {e}", indent=1)
            return False


# ══════════════════════════════════════════════════════════════════
# 上游 Release 资产 + 仓库变量
# ══════════════════════════════════════════════════════════════════
IGNORE_PREFIXES = ('puella-historia',)   # 与 R2 系同一份过滤规则


def should_ignore(name):
    return any(name.startswith(p) for p in IGNORE_PREFIXES)


def get_variable(name):
    r = subprocess.run(['gh', 'variable', 'get', name],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def set_variable(name, body):
    subprocess.run(['gh', 'variable', 'set', name, '--body', body],
                   capture_output=True, text=True)


def fetch_release_assets():
    """返回 {name: {'digest': str, 'url': str}}（已过滤黑名单）。"""
    owner = os.environ.get('UPSTREAM_OWNER', 'HiiragiNemu')
    repo  = os.environ.get('UPSTREAM_REPO', 'magireco-cn-patch')
    headers = {'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = f"Bearer {os.environ['GH_TOKEN']}"
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
        headers=headers)
    with urllib.request.urlopen(req) as resp:
        release = json.loads(resp.read().decode())
    return {
        a['name']: {'digest': a.get('digest', ''), 'url': a['browser_download_url']}
        for a in release.get('assets', [])
        if not should_ignore(a['name'])
    }


# ══════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════
def main():
    CONFIRM_CLEANUP = os.environ.get('CONFIRM_CLEANUP', 'false') == 'true'

    header("DogeCloud 同步（Doge 系，独立流水线）")
    doge = Doge()
    if not doge._enabled:
        warn("多吉云未配置，跳过 Doge 系同步")
        return

    current_map = fetch_release_assets()
    info(f"上游 latest Release 共 {len(current_map)} 个待同步 asset")

    header("比对文件指纹（LAST_DOGE_FINGERPRINTS）")
    old_map = {}
    old_raw = get_variable('LAST_DOGE_FINGERPRINTS')
    if old_raw:
        try:
            old_map = json.loads(old_raw)
            info(f"历史指纹: {len(old_map)} 个文件")
        except Exception:
            warn("历史指纹解析失败，视为首次同步")

    to_process, unchanged, deleted = [], [], []
    for fname, meta in current_map.items():
        sha = meta['digest']
        if fname not in old_map:
            info(f"{fname} → 新文件")
            to_process.append(fname)
        elif sha and old_map[fname] != sha:
            info(f"{fname} → 已更新")
            to_process.append(fname)
        elif not sha:
            to_process.append(fname)
        else:
            unchanged.append(fname)
    for fname in old_map:
        if fname not in current_map:
            deleted.append(fname)

    # 过时文件：默认只列不删，confirm_cleanup=true 才删（与 R2 系同语义）
    section("检查 Doge 桶过时文件（GitHub 已不存在）")
    doge_files = doge.list_files()
    stale = sorted({f for f in doge_files if not should_ignore(f)
                    and f not in current_map})
    if stale:
        if not CONFIRM_CLEANUP:
            warn(f"检测到 {len(stale)} 个过时文件，按规则【不主动删除】：")
            for f in stale:
                warn(f"待清理: {f}", indent=1)
            warn("如需清理，请手动运行本 workflow 并勾选 confirm_cleanup=true")
        else:
            header(f"确认清理：删除 {len(stale)} 个 Doge 过时文件")
            for f in stale:
                if doge.delete_file(f):
                    doge.purge_cache(f)
    else:
        ok("无过时文件")

    if not to_process:
        header("无新增/更新文件")
        ok("Doge 桶已与上游一致")
        final_map = old_map.copy()
        for fname in deleted:
            final_map.pop(fname, None)
        set_variable('LAST_DOGE_FINGERPRINTS', json.dumps(final_map))
        return

    header(f"上传 {len(to_process)} 个文件到多吉云")
    uploaded = []
    for fname in to_process:
        url = current_map[fname]['url']
        if doge.upload_file_from_url(url, fname):
            doge.purge_cache(fname)
            uploaded.append(fname)

    if uploaded:
        header("刷新多吉云根目录 CDN 缓存")
        doge.purge_cache("")

    header("保存 Doge 指纹")
    final_map = old_map.copy()
    for fname in unchanged:
        final_map[fname] = old_map[fname]
    for fname in to_process:
        final_map[fname] = current_map[fname]['digest']
    for fname in deleted:
        final_map.pop(fname, None)
    set_variable('LAST_DOGE_FINGERPRINTS', json.dumps(final_map))
    ok(f"指纹已保存（{len(final_map)} 个）")

    if len(uploaded) != len(to_process):
        err(f"Doge 上传完成 {len(uploaded)}/{len(to_process)}，有文件失败——"
            "下次同步会按指纹自动补齐")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        err(f"Doge 系同步失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
