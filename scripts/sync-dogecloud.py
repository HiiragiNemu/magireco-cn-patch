#!/usr/bin/env python3
"""DogeCloud 同步流水线（Doge 系）—— 在 mainland 自托管 runner 上执行。

多吉云存储与 object-storage 不同：数据面不能直接用静态 AccessKey/SecretKey 访问，
必须先走控制面 /auth/tmp_token.json 换「三段式 STS 临时密钥」再用 boto3
（仅 Virtual Hosted Style）。

2026-08-13 起改用**多吉云服务端拉取**（/oss/fetch.json + query.json 轮询）：
runner 不再自己下载再上传（省流量、省跨网带宽），而是提交一个国内 CDN URL，
让多吉云的服务器从 CDN 抓文件落桶。runner 只做控制面（换 token、提交任务、
轮询、列桶校验）。源 URL 用 race_source_cdn() 竞速选出最快的国内 CDN
（edge/esa/hkcdn/r2，吞吐会变，运行时就地测）；多吉云/123云盘都排在
object-storage 系之后跑，等 CDN 清缓存+拉到新内容。

设计：
  - 密钥由 GitHub Secrets 原生注入（DOGE_*，不落盘）
  - 同步指纹存 GitHub repository variable `LAST_DOGE_FINGERPRINTS`
    （与 object-storage 系的 LAST_SYNC_FINGERPRINTS 同款，runner 上  由
    GitHub Actions 注入，统一在 Settings→Variables 一处管理）；
    旧桶内 __doge_fingerprint.json 仅作首次迁移源，迁移后删除
  - 增量按指纹 diff：只对新增/变更文件提交 fetch 任务，未变的跳过
  - confirm_cleanup=true 才删 Doge 桶过时文件，否则仅列出
  - 拉取未全部成功即 exit 1：避免静默失效

环境变量：
  DOGE_ACCESS_KEY / DOGE_SECRET_KEY / DOGE_BUCKET / DOGE_DOMAIN / DOGE_API_BASE
  CONFIRM_CLEANUP
"""
import hashlib
import hmac
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(line_buffering=True)

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

# 兜底超时：防止某个 urlopen / boto3 传输无限挂起，把整个 job 卡到 6 小时上限
socket.setdefaulttimeout(600)

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

    FINGERPRINT_KEY = "__doge_fingerprint.json"

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
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    def _post_form(self, path, form):
        body = "&".join(f"{k}={v}" for k, v in form.items()).encode()
        req = urllib.request.Request(
            f"{self.api_base}{path}", data=body,
            headers={"Authorization": self._sign(path, body),
                     "Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    def _get_json(self, path, query=""):
        """GET JSON（签名含 query）。用于 fetch/query 等 GET 接口。"""
        full = path + (("?" + query) if query else "")
        req = urllib.request.Request(
            f"{self.api_base}{full}",
            headers={"Authorization": self._sign(full, b"")},
            method="GET")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())

    # ── 服务端拉取（2026-08-13）：多吉云从国内 CDN URL 直接抓文件，省掉
    #    runner 下载+上传的流量。提交 fetch.json 拿任务 id，再轮询 query.json。
    def fetch_pull(self, url, key):
        """多吉云服务端从 url 抓取到 bucket/key。返回任务 id。"""
        data = self._post_json("/oss/fetch.json", {
            "url": url, "bucket": self.bucket, "key": key})
        if str(data.get("code", "")) != "200":
            raise RuntimeError(f"[Doge] fetch.json 失败: {data}")
        return data["data"]["id"]

    def fetch_query(self, task_id):
        """查询抓取任务。wait=0 进行中、-1 已完成。返回 (done, wait)。"""
        data = self._get_json("/oss/fetch/query.json", f"id={task_id}")
        if str(data.get("code", "")) != "200":
            raise RuntimeError(f"[Doge] fetch/query 失败: {data}")
        wait = int(data["data"]["wait"])
        return wait == -1, wait

    def wait_fetch(self, task_id, filename, timeout=900):
        """轮询抓取任务直到完成（wait=-1），再确认文件落桶。超时/未就位算失败。"""
        deadline = time.time() + timeout
        last_wait = 0
        while time.time() < deadline:
            done, last_wait = self.fetch_query(task_id)
            if done:
                break
            time.sleep(5)
        else:
            err(f"[Doge] 抓取超时: {filename} (wait={last_wait})", indent=1)
            return False
        if filename in self.list_files():
            ok(f"[Doge] 抓取完成: {filename}", indent=1)
            return True
        err(f"[Doge] 抓取结束但文件未就位: {filename}", indent=1)
        return False

    # ── 换临时密钥 → boto3 S3 ──
    def _ensure_s3(self):
        if self._s3 is not None and time.time() < self._expire_at - 300:
            return
        data = self._post_json("/auth/tmp_token.json", {
            "channel": "OSS_FULL",
            "scopes": [self.bucket],
            "ttl": 7200,
        })
        if str(data.get("code", "")) != "200":
            raise RuntimeError(f"[Doge] tmp_token 失败: {data}")
        creds       = data["data"]["Credentials"]
        bucket_info = data["data"]["Buckets"][0]
        self._s3_bucket = bucket_info["s3Bucket"]
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=creds["accessKeyId"],
            aws_secret_access_key=creds["secretAccessKey"],
            aws_session_token=creds["sessionToken"],
            endpoint_url=bucket_info["s3Endpoint"],
            config=Config(
                s3={"addressing_style": "virtual"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        self._expire_at = time.time() + 7200
        info(f"[Doge] 已换取 STS 临时凭证 endpoint={bucket_info['s3Endpoint']} "
             f"s3Bucket={self._s3_bucket}")

    # ── 指纹：存 GitHub repository variable LAST_DOGE_FINGERPRINTS ──
    #   hk runner 上  已由 GitHub Actions 注入，与 object-storage 系的
    #   LAST_SYNC_FINGERPRINTS 同样走 GitHub variable，统一管理。
    #   用 REST API（urllib）而非 gh CLI：不依赖 hk Docker 容器是否
    #   预装 gh。旧桶内 __doge_fingerprint.json 仅作为首次迁移的兜底来源。
    GH_FP_VAR = "LAST_DOGE_FINGERPRINTS"

    def _gh_repo(self):
        return os.environ.get("GITHUB_REPOSITORY", "")

    def _gh_api(self, path, method="GET", body=None):
        """GitHub REST API，带  鉴权。返回 (status, parsed)。"""
        token = os.environ.get("", "")
        if not token:
            return (0, None)
        req = urllib.request.Request(
            f"https://api.github.com{path}",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Content-Type": "application/json"},
            method=method)
        if body is not None:
            req.data = json.dumps(body).encode()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode()
                return (r.status, json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            return (e.code, None)
        except Exception as e:
            warn(f"[Doge] GitHub API {method} {path} 失败: {e}")
            return (0, None)

    def _read_fingerprint(self):
        repo = self._gh_repo()
        if not repo:
            warn("[Doge] 无 GITHUB_REPOSITORY，无法读 GitHub variable")
        else:
            status, data = self._gh_api(
                f"/repos/{repo}/actions/variables/{self.GH_FP_VAR}")
            if status == 200 and data and data.get("value"):
                try:
                    fp = json.loads(data["value"])
                    info(f"[Doge] GitHub variable 指纹: {len(fp)} 个文件")
                    return fp
                except Exception:
                    warn("[Doge] GitHub variable 指纹解析失败，回退桶内")
            else:
                warn(f"[Doge] 读 GitHub variable 未命中（status={status}），"
                     "尝试桶内旧指纹迁移")

        # 兜底迁移：GitHub variable 不存在/为空时，读桶内旧 json 作首次基线
        self._ensure_s3()
        try:
            r = self._s3.get_object(Bucket=self._s3_bucket,
                                    Key=self.FINGERPRINT_KEY)
            raw = r['Body'].read().decode('utf-8')
            fp = json.loads(raw)
            info(f"[Doge] 桶内旧指纹（迁移源）: {len(fp)} 个文件")
            return fp
        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey', '404', 'NoSuchBucket'):
                info("[Doge] 无指纹，视为首次同步")
                return {}
            raise
        except Exception:
            warn("[Doge] 桶内指纹解析失败，视为首次同步")
            return {}

    def _write_fingerprint(self, fp):
        repo = self._gh_repo()
        if not repo:
            err("[Doge] 无 GITHUB_REPOSITORY，无法保存指纹到 GitHub variable")
            raise RuntimeError("GITHUB_REPOSITORY 缺失")
        # 先 PATCH 更新；404 说明变量还没创建过，则 POST 新建
        status, _ = self._gh_api(
            f"/repos/{repo}/actions/variables/{self.GH_FP_VAR}",
            method="PATCH",
            body={"value": json.dumps(fp, ensure_ascii=False)})
        if status == 404:
            status, _ = self._gh_api(
                f"/repos/{repo}/actions/variables",
                method="POST",
                body={"name": self.GH_FP_VAR,
                      "value": json.dumps(fp, ensure_ascii=False)})
        if status not in (200, 201, 204):
            err(f"[Doge] 保存指纹到 GitHub variable 失败（status={status}）")
            raise RuntimeError(f"GitHub variable 写入失败 status={status}")
        ok(f"[Doge] GitHub variable 指纹已保存（{len(fp)} 个）")

        # 迁移完成：删掉桶里的旧 json，不再维护第二份指纹
        self._ensure_s3()
        try:
            self._s3.delete_object(Bucket=self._s3_bucket,
                                   Key=self.FINGERPRINT_KEY)
            ok(f"[Doge] 已删除桶内旧指纹 {self.FINGERPRINT_KEY}")
        except Exception as e:
            warn(f"[Doge] 删除桶内旧指纹失败（可忽略）: {e}")

    # ── 数据面操作 ──
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
# 上游 Release 资产
# ══════════════════════════════════════════════════════════════════
IGNORE_PREFIXES = ('history-data', 'apk-overlay-atlas.zip', 'legacy-client-archive', 'legacy-client-archieve')   # 与 object-storage 系同一份过滤规则


def should_ignore(name):
    if any(name.startswith(p) for p in IGNORE_PREFIXES):
        return True
    # 非主线 APK（非 magireco-latest*）不上传
    return name.endswith('.apk') and not name.startswith('magireco-latest')


def race_source_cdn():
    """竞速各国内 CDN 下载吞吐，选最快的作为拉取源。吞吐会变，运行时就地测。

    多吉云/123云盘都从国内 CDN 拿数据（排在 object-storage 系之后），源 URL 用竞速胜者。
    probe 用 cn_base_00_db.zip（7MB 小文件，各 CDN 都有），测前 8MB。
    """
    candidates = [
        ("edge", "https://edge.assets.magireco.top/"),
        ("esa", "https://esa.assets.magireco.top/"),
        ("hkcdn", "https://hkcdn.assets.magireco.top/g/m/releases/download/latest/"),
        ("r2", "https://r2.assets.magireco.top/"),
    ]
    probe = "cn_base_00_db.zip"
    best, best_speed = None, 0.0
    for name, base in candidates:
        try:
            req = urllib.request.Request(base + probe,
                                         headers={"User-Agent": "magireco-cn-sync"})
            start = time.time()
            got = 0
            with urllib.request.urlopen(req, timeout=20) as r:
                while got < (8 << 20):   # 测 8MB
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    got += len(chunk)
            dur = time.time() - start
            speed = got / dur if dur > 0 else 0
            info(f"[竞速] {name}: {speed / 1024:.0f} KB/s")
            if speed > best_speed:
                best, best_speed = base, speed
        except Exception as e:
            warn(f"[竞速] {name} 失败: {e}", indent=1)
    if best is None:
        warn("[竞速] 全部 CDN 竞速失败，用 edge 兜底")
        best = candidates[0][1]
    ok(f"[竞速] 选择源: {best}")
    return best


def fetch_release_assets():
    """返回 {name: {'digest': str}}（已过滤黑名单）。公开仓库无需 token。"""
    owner = os.environ.get('UPSTREAM_OWNER', 'HiiragiNemu')
    repo  = os.environ.get('UPSTREAM_REPO', 'patch-front')
    headers = {'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
        headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        release = json.loads(resp.read().decode())
    # 只留 digest 做指纹比对；上传源不再用 GitHub browser_download_url，
    # 而是 race_source_cdn() 竞速出的国内 CDN（mainland 上 objects.githubusercontent.com 被墙）
    return {
        a['name']: {'digest': a.get('digest', '')}
        for a in release.get('assets', [])
        if not should_ignore(a['name'])
    }


# ══════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════
def main():
    CONFIRM_CLEANUP = os.environ.get('CONFIRM_CLEANUP', 'false') == 'true'

    header("DogeCloud 同步（Doge 系，hk 跳板机）")
    doge = Doge()
    if not doge._enabled:
        warn("多吉云未配置，跳过 Doge 系同步")
        return

    current_map = fetch_release_assets()
    info(f"上游 latest Release 共 {len(current_map)} 个待同步 asset")

    header("比对文件指纹（GitHub variable LAST_DOGE_FINGERPRINTS）")
    old_map = doge._read_fingerprint()

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

    # 过时文件：默认只列不删，confirm_cleanup=true 才删
    section("检查 Doge 桶过时文件（GitHub 已不存在）")
    doge_files = doge.list_files()
    stale = sorted({f for f in doge_files if not should_ignore(f)
                    and f not in current_map and f != doge.FINGERPRINT_KEY})
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
        doge._write_fingerprint(final_map)
        return

    header(f"从国内 CDN 拉取 {len(to_process)} 个文件到多吉云")
    source_base = race_source_cdn()
    fetched = []
    for fname in to_process:
        url = source_base + fname
        try:
            task_id = doge.fetch_pull(url, fname)
            if doge.wait_fetch(task_id, fname):
                doge.purge_cache(fname)
                fetched.append(fname)
        except Exception as e:
            err(f"[Doge] {fname} 拉取失败: {e}", indent=1)

    if fetched:
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
    doge._write_fingerprint(final_map)

    if len(fetched) != len(to_process):
        err(f"Doge 拉取完成 {len(fetched)}/{len(to_process)}，有文件失败——"
            "下次同步会按指纹自动补齐")
        # 避免静默失效：拉取未全部成功必须让 CI 步骤失败，否则失败会被掩盖
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        err(f"Doge 系同步失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
