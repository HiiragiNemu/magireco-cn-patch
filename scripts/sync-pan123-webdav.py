#!/usr/bin/env python3
"""123云盘 WebDAV 同步流水线 —— 在 mainland 自托管 runner 上执行。

123云盘（123pan.com）暴露标准 WebDAV（https://dav.123pan.com），用 Basic Auth
+ PROPFIND/MKCOL/PUT/DELETE 操作。作用：给「下载引擎不可靠」的玩家多一条网盘
兜底线路（配合离线包静态站手动下载）。

设计（与 sync-dogecloud.py 同款节奏）：
  - 在 mainland 自托管 runner 上跑：国内机 → 国内 CDN / 123云盘（境内）都直连快；
    GitHub 官方 runner 跨太平洋 PUT 大文件会极慢
  - 密钥由 GitHub Secrets 注入（PAN123_*，不落盘）
  - 源站用国内 CDN 竞速：edgeone/esa/hkcdn/r2 测吞吐选最快（2026-08-13）。
    源 URL 不再走 GitHub（objects.githubusercontent.com 从 mainland 被墙）；
    竞速逻辑写在脚本里，吞吐会变，运行时就地测
  - 增量：PROPFIND 列远端目录，拿 getcontentlength 与 Release asset size 比对，
    相同跳过，只传新增/变更（幂等，重跑不重传）
  - 过时文件（远端有、Release 已删）不主动删，confirm_cleanup=true 才删；
    目标目录应专用作镜像，别混放其它文件
  - 上传未全部成功即 exit 1：避免静默失效
  - 123pan WebDAV 单文件上限 100GB，本项目最大 cn_voice_01.zip ~1.85GB 远在限内

关键实现点：WebDAV PUT 用 http.client 流式 + 显式 Content-Length（requests 对
生成器 body 会强制 Transfer-Encoding: chunked，很多 WebDAV 服务器拒绝）；
源文件 GET 用 requests（自动跟 302 重定向 + 流式读）。

环境变量：
  PAN123_WEBDAV_URL / PAN123_USER / PAN123_PASS / PAN123_DIR（可选目标子目录）
  UPSTREAM_OWNER / UPSTREAM_REPO / GH_TOKEN / CONFIRM_CLEANUP
"""
import base64
import http.client
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(line_buffering=True)

import requests
from requests.auth import HTTPBasicAuth

# 兜底超时：防止某个传输无限挂起，把整个 job 卡到 6 小时上限
socket.setdefaulttimeout(900)

# 与 R2/Doge 系一致的忽略规则：puella-historia 前缀（原版自带资源，无需镜像）
IGNORE_PREFIXES = ('puella-historia',)

# 并发上传路数：123pan WebDAV 每连接吞吐有限、单个 PUT 响应极慢（真机实测进程
# 长时间卡在 poll() 等响应，串行上传被延迟拖死）。多路并发把等待重叠掉；别开太
# 多，123pan 并发限制未知，4 路折中。
PAN123_CONCURRENCY = 4

# ── 样式 / 日志（与 sync-dogecloud.py 同款）──
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"; RED = "\033[31m"
    BRIGHT_GREEN = "\033[92m"; BRIGHT_YELLOW = "\033[93m"
    BRIGHT_WHITE = "\033[97m"

def c(col, s): return f"{col}{s}{C.RESET}"
def header(t): print(f"\n{'=' * 70}\n{t}\n{'=' * 70}", flush=True)
def section(t): print(f"\n── {t}", flush=True)
def ok(m, i=0): print(f"{'  ' * i}{c(C.BRIGHT_GREEN, '✔')} {m}", flush=True)
def warn(m, i=0): print(f"{'  ' * i}{c(C.BRIGHT_YELLOW, '⚠')} {m}", flush=True)
def err(m, i=0): print(f"{'  ' * i}{c(C.RED, '✘')} {m}", flush=True)
def info(m, i=0): print(f"{'  ' * i}  {m}", flush=True)
def skip(m): print(f"{c(C.DIM, '  -')} {m}", flush=True)

def env(k, required=True):
    v = os.environ.get(k, "").strip()
    if required and not v:
        err(f"缺少环境变量 {k}")
        sys.exit(1)
    return v

def should_ignore(name):
    return any(name.startswith(p) for p in IGNORE_PREFIXES)


def race_source_cdn():
    """竞速各国内 CDN 下载吞吐，选最快的作为拉取源。吞吐会变，运行时就地测。

    123云盘从国内 CDN 拿数据（排在 R2 系之后），源 URL 用竞速胜者。probe 用
    cn_base_00_db.zip（7MB 小文件，各 CDN 都有），测前 8MB。
    """
    candidates = [
        ("edgeone", "https://edgeone.assets.magireco.top/"),
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
            start = time.time(); got = 0
            with urllib.request.urlopen(req, timeout=20) as r:
                while got < (8 << 20):
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
            warn(f"[竞速] {name} 失败: {e}", i=1)
    if best is None:
        warn("[竞速] 全部 CDN 竞速失败，用 edgeone 兜底")
        best = candidates[0][1]
    ok(f"[竞速] 选择源: {best}")
    return best


class WebDav:
    def __init__(self, base_url, user, password):
        self.base = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(user, password)
        self.basic = base64.b64encode(f"{user}:{password}".encode()).decode()

    def url(self, name=""):
        return f"{self.base}/{name}"

    def ensure_dir(self, name):
        """MKCOL 建目录；已存在（405/301/200）当成功。"""
        r = requests.request('MKCOL', self.url(name), auth=self.auth, timeout=60)
        if r.status_code in (200, 201, 204, 301, 405):
            return True
        err(f"MKCOL {name} 失败: {r.status_code} {r.text[:200]}")
        return False

    def list_files(self):
        """PROPFIND Depth 1，返回 {文件名: 字节数}；不可列返回 None。"""
        try:
            r = requests.request('PROPFIND', self.base, auth=self.auth,
                                 timeout=120, headers={'Depth': '1'})
        except Exception as e:
            err(f"PROPFIND 请求失败: {e}")
            return None
        if r.status_code not in (200, 207):
            warn(f"PROPFIND {self.base} 返回 {r.status_code}（{r.text[:150]}），"
                 "按「远端为空」处理（全量上传）")
            return {}
        files = {}
        try:
            root = ET.fromstring(r.content)
            ns = {'d': 'DAV:'}
            for resp in root.findall('d:response', ns):
                href = (resp.findtext('d:href', '', ns) or '').split('/')[-1]
                if not href:
                    continue
                status = resp.findtext('d:propstat/d:status', '', ns)
                if status and '404' in status:
                    continue
                # 跳过集合（子目录），只把文件当镜像对象，免得子目录被误判成
                # 过时文件
                if resp.find('d:propstat/d:prop/d:resourcetype/d:collection', ns) is not None:
                    continue
                size_el = resp.find('d:propstat/d:prop/d:getcontentlength', ns)
                size = size_el.text if size_el is not None and size_el.text else '0'
                try:
                    files[href] = int(size)
                except ValueError:
                    files[href] = 0
        except Exception as e:
            err(f"解析 PROPFIND 响应失败: {e}")
            return None
        return files

    def upload_stream(self, name, src_raw, size):
        """http.client 流式 PUT：显式 Content-Length、非 chunked（WebDAV 要求）。"""
        parsed = urllib.parse.urlsplit(self.url(name))
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        is_https = parsed.scheme == 'https'
        conn_cls = (http.client.HTTPSConnection if is_https
                    else http.client.HTTPConnection)
        conn = conn_cls(parsed.hostname,
                        parsed.port or (443 if is_https else 80), timeout=900)
        try:
            conn.putrequest('PUT', path)
            conn.putheader('Authorization', f'Basic {self.basic}')
            conn.putheader('Content-Length', str(size))
            conn.endheaders()
            sent = 0
            while sent < size:
                chunk = src_raw.read(min(4 * 1024 * 1024, size - sent))
                if not chunk:
                    break
                conn.send(chunk)
                sent += len(chunk)
            if sent != size:
                # 源流提前结束：别再读响应，直接关连接让服务器拿到半截 body 报错
                err(f"PUT {name}: 源流提前结束（{sent}/{size}），中止该文件")
                return False
            resp = conn.getresponse()
            status = resp.status
            resp.read()
            return status in (200, 201, 204)
        except Exception as e:
            err(f"PUT {name} 失败: {e}")
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def delete(self, name):
        try:
            r = requests.request('DELETE', self.url(name), auth=self.auth, timeout=60)
            return r.status_code in (200, 204, 404)
        except Exception:
            return False


def main():
    header("123云盘 WebDAV 同步")
    # 密钥缺失即 exit 1 让 job 显式红——123 云盘没上传就该红，不能绿着假装成功
    base = env('PAN123_WEBDAV_URL')
    user = env('PAN123_USER')
    pwd = env('PAN123_PASS')
    sub = os.environ.get('PAN123_DIR', '').strip().strip('/')
    owner = env('UPSTREAM_OWNER')
    repo = env('UPSTREAM_REPO')
    gh = os.environ.get('GH_TOKEN', '')
    confirm = os.environ.get('CONFIRM_CLEANUP', 'false') == 'true'

    if sub:
        base = f"{base}/{sub}"
    dav = WebDav(base, user, pwd)

    header("获取上游 Release")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
        headers={'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28'})
    if gh:
        req.add_header('Authorization', f'Bearer {gh}')
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            release = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            warn("上游仓库无 Release，跳过")
            return
        raise
    current_map = {a['name']: a.get('size', 0)
                   for a in release.get('assets', [])
                   if not should_ignore(a['name'])}
    info(f"待同步 asset：{len(current_map)} 个")

    header("确保远端目录存在")
    if sub:
        ok(f"目标目录：{sub}")
        if not dav.ensure_dir(''):
            err("建目录失败，中止")
            sys.exit(1)

    header("列远端 WebDAV 目录")
    remote = dav.list_files()
    if remote is None:
        err("无法列出远端目录，中止（不要盲目全量覆盖）")
        sys.exit(1)

    to_upload, unchanged, stale = [], [], []
    for name, size in current_map.items():
        if name not in remote or remote[name] != size:
            to_upload.append((name, size))
        else:
            unchanged.append(name)
    for name in remote:
        if name not in current_map:
            stale.append(name)

    if not to_upload:
        header("无新增/变更文件")
    else:
        header(f"上传 {len(to_upload)} 个文件（并发 {PAN123_CONCURRENCY} 路）")
        source_base = race_source_cdn()
        failed = 0

        def upload_one(pair):
            name, size = pair
            url = source_base + name
            try:
                src = requests.get(url, stream=True, timeout=300,
                                   headers={'Accept': 'application/octet-stream',
                                            'User-Agent': 'magireco-cn-sync'})
                src.raise_for_status()
            except Exception as e:
                return name, False, f"读取源失败: {e}"
            try:
                # PUT 的 Content-Length 用源 CDN 响应的实际大小，而非 GitHub
                # release 的 asset size——latest APK 每次构建大小微变、CDN 可能
                # 缓存旧版本，两者会差几个 KB，用错会导致流式读取「源流提前结束」
                actual = int(src.headers.get('Content-Length') or 0) or size
                okb = dav.upload_stream(name, src.raw, actual)
                return name, okb, (None if okb else "WebDAV PUT 失败")
            finally:
                try:
                    src.close()
                except Exception:
                    pass

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=PAN123_CONCURRENCY) as pool:
            futures = [pool.submit(upload_one, pair) for pair in to_upload]
            for fut in concurrent.futures.as_completed(futures):
                name, okb, msg = fut.result()
                if okb:
                    ok(f"已上传: {name}")
                else:
                    err(f"上传失败: {name}（{msg}）")
                    failed += 1
        if failed:
            err(f"{failed} 个文件上传失败")
            sys.exit(1)

    if stale:
        header(f"远端过时文件 {len(stale)} 个")
        for name in stale:
            warn(f"待清理: {name}")
        if confirm:
            section("confirm_cleanup=true，删除")
            for name in stale:
                if dav.delete(name):
                    ok(f"已删除: {name}")
        else:
            warn("不主动删除；确认无误后手动运行并勾 confirm_cleanup=true")

    header("同步完成")
    info(f"上传 {len(to_upload)}，未变 {len(unchanged)}，过时 {len(stale)}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
