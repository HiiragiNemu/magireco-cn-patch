#!/usr/bin/env python3
"""私有仓库取 Release asset 的取法 —— 真的起两个服务器跑一遍。

仓库转私有后，`browser_download_url` 匿名取一律 404，只能走 API 的 asset
端点 + `Accept: application/octet-stream` 并带凭据。GitHub 会 302 到对象存储
的签名地址，而**那一跳必须把 Authorization 摘掉**：签名地址自带鉴权，再带一个
Authorization 过去会被拒。urllib 默认的 opener 会把请求头原样带过重定向，所以
workflow 里自己接管了 `HTTPRedirectHandler`。

这件事没法靠读代码确认——写错了在公开仓库上照样全绿（公开仓库根本不需要凭据），
要等转私有那天才炸，而且炸出来的现象是「同步悄悄什么都没传」。所以这里把
workflow 里那两份实现原样抠出来，对着真的重定向跑：第一跳必须带凭据，第二跳
必须不带，内容还得完整。
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import re
import textwrap
import threading
import unittest
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "sync-and-upload.yml"

PAYLOAD = b"magireco-latest-legacy-client.apk \xe7\x9a\x84\xe5\x81\x87\xe5\x8c\x85"
SEEN: dict[str, dict[str, str]] = {}


def extract_block(text: str, header: str) -> str:
    """按缩进把一个 def 整块抠出来（workflow 里是 YAML 里的内联脚本）。"""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == header]
    if len(starts) != 1:
        raise AssertionError(f"{header!r} 在 workflow 里出现 {len(starts)} 次")
    i = starts[0]
    indent = len(lines[i]) - len(lines[i].lstrip())
    block = [lines[i]]
    for line in lines[i + 1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        block.append(line)
    return textwrap.dedent("\n".join(block))


class _Handler(BaseHTTPRequestHandler):
    """两个角色共用：hop1 发 302，hop2 交货。"""

    def do_GET(self):                                   # noqa: N802
        SEEN[self.server.role] = {k.lower(): v for k, v in self.headers.items()}
        if self.server.role == "hop1":
            self.send_response(302)
            self.send_header("Location", self.server.target)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, *_args):                      # 别把测试输出刷满
        pass


def _serve(role, target=None):
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    srv.role, srv.target = role, target
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class PrivateAssetFetchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def _load_opener(self, header, extra_ns=None):
        """把 workflow 里那份实现抠出来，在受控的全局命名空间里跑。

        闭包读到的自由变量（镜像那份读 GH_HEADERS）就靠这个命名空间喂。
        """
        ns = {"urllib": urllib, "urllib.request": urllib.request}
        ns.update(extra_ns or {})
        exec(extract_block(self.text, header), ns)          # noqa: S102
        return ns

    def _run_roundtrip(self, call):
        SEEN.clear()
        hop2 = _serve("hop2")
        hop1 = _serve("hop1", f"http://127.0.0.1:{hop2.server_port}/signed")
        try:
            body = call(f"http://127.0.0.1:{hop1.server_port}/asset")
        finally:
            for srv in (hop1, hop2):
                srv.shutdown()
                srv.server_close()
        self.assertEqual(body, PAYLOAD, "重定向之后内容必须完整取回")
        self.assertIn("hop1", SEEN)
        self.assertIn("hop2", SEEN, "第二跳没被访问到，重定向根本没跟")
        return SEEN["hop1"], SEEN["hop2"]

    def test_r2_sync_drops_credentials_on_the_signed_hop(self):
        ns = self._load_opener("def open_asset_stream(url, headers):")
        headers = {"Authorization": "Bearer s3cr3t",
                   "Accept": "application/vnd.github+json"}

        def call(url):
            with ns["open_asset_stream"](url, headers) as resp:
                return resp.read()

        first, second = self._run_roundtrip(call)
        self.assertEqual(first.get("authorization"), "Bearer s3cr3t")
        self.assertEqual(first.get("accept"), "application/octet-stream",
                         "asset 端点要的是 octet-stream，不是 vnd.github+json")
        self.assertIsNone(second.get("authorization"),
                          "签名地址那一跳还带着 Authorization，会被对象存储拒掉")
        # 传进来的 headers 是调用方的，不能被就地改掉
        self.assertEqual(headers["Accept"], "application/vnd.github+json")

    def test_mirror_release_drops_credentials_on_the_signed_hop(self):
        ns = self._load_opener(
            "def open_asset_stream(url):",
            {"GH_HEADERS": {"Authorization": "Bearer s3cr3t",
                            "Accept": "application/vnd.github+json"}},
        )
        def call(url):
            with ns["open_asset_stream"](url) as resp:
                return resp.read()

        first, second = self._run_roundtrip(call)
        self.assertEqual(first.get("authorization"), "Bearer s3cr3t")
        self.assertEqual(first.get("accept"), "application/octet-stream")
        self.assertIsNone(second.get("authorization"))
        self.assertEqual(ns["GH_HEADERS"]["Accept"], "application/vnd.github+json")

    def test_both_copies_stay_in_sync(self):
        """四处判据同源那一条的同款：这里是两处取件实现。"""
        drops = re.findall(r"if k\.lower\(\) != ['\"]authorization['\"]", self.text)
        self.assertEqual(len(drops), 2, "r2-sync 与 mirror-release 各一份")
        self.assertEqual(
            len(re.findall(r'\["Accept"\] = "application/octet-stream"'
                           r"|\['Accept'\] = 'application/octet-stream'",
                           self.text)),
            2,
        )

    def test_no_anonymous_release_download_remains(self):
        """browser_download_url 只许以「兜底」的形状出现。

        私有仓库上它取不到内容，所以它唯一合法的用法是 asset 字典里没有 API
        地址时的回退（asset_source_url 与 upstream_map 各一处）。绝不能再有
        「直接拿它去发请求」的写法——那正是转私有当天会静默失效的形状。
        """
        fallbacks, direct = [], []
        for line in self.text.splitlines():
            if "browser_download_url" not in line:
                continue
            if line.lstrip().startswith("#"):
                continue                      # 注释里提它是为了讲清楚为什么不用
            if re.search(r"get\((['\"])url\1\)\s+or", line):
                fallbacks.append(line.strip())
            elif "Request(" in line or "urlopen(" in line or "get(" not in line:
                direct.append(line.strip())

        self.assertEqual(len(fallbacks), 2,
                         f"兜底写法应恰好两处，实得 {len(fallbacks)}: {fallbacks}")
        self.assertEqual(
            [l for l in direct if "Request(" in l or "urlopen(" in l], [],
            "有人又拿 browser_download_url 直接发请求了")


if __name__ == "__main__":
    unittest.main(verbosity=2)
