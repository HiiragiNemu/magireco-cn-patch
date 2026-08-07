#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核对热更包里的 CSS 有没有「冻住」——即和游戏服务端现役版本不一致。

## 为什么需要它（这条规则是拿一次事故换来的）

前端 CSS 有两条加载路径，**两条都会被客户端拦截**：

  · `index.html` 的静态 `<link>`：sanitize / common / base / fonts 四个；
  · 其余每个页面的 CSS 走 requirejs 的 text 插件当**文本**读进来再注进
    `<style id="headStyle">`。比如 `js/quest/MainQuest.js` 的依赖里写着
    `text!css/quest/MainQuest.css`，取到后 `a.setStyle(k+l)`。

两条路径最终都是对 `/magica/css/**` 发请求，而
`WebViewImpl$WebViewClientImpl.shouldInterceptRequest` **只按路径匹配、会把
`?<md5>` 查询串丢掉**：只要 `<files>/magica/css/...` 存在就用本地的，服务端
改了也不生效。

再叠上热更的语义——`RestClient.unzip` 只写不删，**包里没有的文件不会被删也
不会被还原**。于是「往热更包里放过一次某个 CSS」这件事是**不可逆**的：从包里
移除它，只是以后不再更新它，设备上那份**永远留着、永远赢**。

现实后果：曾经有人为了改样式把某个页面 CSS 整份放进热更包，那份快照缺了
`#QuestMap #toPuellaHistoriaTopButtonWrap` 的规则。那个 div 在
`template/quest/MainQuest.html` 里是**无条件渲染**的，全部尺寸/背景图/定位都
由 CSS 给——规则一没，它塌成 0 高度的空 div，历史篇（Puella Historia）入口
就这么无声无息地没了。模板、js、图片全都是好的，查也查不出来。

**唯一的解毒办法是用服务端现役内容把它覆盖回去。** 所以只要我们往包里放过
CSS，就永远得负责让它跟服务端同步——这个脚本就是那个闸门。

## 判据

服务端的 `js/system/replacement.js` 里有 `fileTimeStamp` 表，记着每个文件的
md5（`index.html` 的 `?<hash>` 就是从这来的）。脚本把包里每个 CSS 和它比：

  · 在豁免名单里的（我们**故意**要覆盖的）跳过，但 `common.css` 例外——
    它是「服务端原文 + 末尾追加 cn-patch」，所以校验它的**前 N 字节**必须
    等于服务端原文；
  · 其余每个 CSS 的 md5 必须和 `fileTimeStamp` 一致。不一致就是冻住了。

本仓库版：直接查 `magica/css/` 这棵源码树（CI 打包前跑），也可以传一个
已经打好的 zip 进来查。

用法：
    python3 scripts/check_css_freeze.py                       # 查 magica/css/
    python3 scripts/check_css_freeze.py --zip cn_js_update_new.zip
    python3 scripts/check_css_freeze.py --host dorothy.magi-reco.com
"""

import argparse
import hashlib
import os
import re
import sys
import urllib.request
import zipfile

# 我们故意覆盖、不参与 md5 比对的文件（包内路径，不带 magica/ 前缀）
INTENTIONAL = {
    # 把 koruri 的 src 改指包内 GB 字体；服务端原文只有一条 @font-face
    "css/_common/fonts.css",
}
# 「服务端原文 + 末尾追加」型：校验前缀而非整体 md5
PREFIX_OF_SERVER = {"css/_common/common.css"}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "css-freeze-check"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", help="改查这个 zip，而不是 magica/css/ 源码树")
    ap.add_argument("--root", default="magica", help="源码树根目录（默认 magica）")
    ap.add_argument("--host", default="dorothy.magi-reco.com", help="游戏服务端主机名")
    args = ap.parse_args()

    base = "https://%s/magica/" % args.host
    try:
        rep = fetch(base + "js/system/replacement.js").decode("utf-8", "replace")
    except Exception as e:
        sys.stderr.write("✘ 取不到 replacement.js：%s\n" % e)
        return 2
    stamps = dict(re.findall(r'"([^"]+\.css)":"([0-9a-f]{32})"', rep))
    if not stamps:
        sys.stderr.write("✘ replacement.js 里没解析出 fileTimeStamp\n")
        return 2
    sys.stderr.write("服务端清单：%d 个 css\n" % len(stamps))

    if args.zip:
        z = zipfile.ZipFile(args.zip)
        names = [n for n in z.namelist()
                 if n.startswith("magica/css/") and n.endswith(".css")]
        read = z.read
        where = args.zip
    else:
        names = []
        for dirpath, _, files in os.walk(os.path.join(args.root, "css")):
            for f in files:
                if f.endswith(".css"):
                    p = os.path.join(dirpath, f)
                    names.append("magica/" + os.path.relpath(p, args.root)
                                 .replace(os.sep, "/"))
        read = lambda n: open(os.path.join(args.root, n[len("magica/"):]), "rb").read()
        where = args.root + "/css"
    if not names:
        print("%s 下没有任何 css —— 没有冻结风险。" % where)
        return 0

    frozen, unknown, ok = [], [], 0
    for n in sorted(names):
        rel = n[len("magica/"):]
        if rel in INTENTIONAL:
            sys.stderr.write("  · %s 故意覆盖，跳过\n" % rel)
            continue
        if rel not in stamps:
            unknown.append(rel)
            continue
        body = read(n)
        if rel in PREFIX_OF_SERVER:
            try:
                srv = fetch(base + rel)
            except Exception as e:
                sys.stderr.write("  ! %s 取不到服务端原文：%s\n" % (rel, e))
                unknown.append(rel)
                continue
            if body[:len(srv)] == srv:
                ok += 1
                sys.stderr.write("  · %s 前 %d 字节与服务端一致，追加了 %d 字节\n"
                                 % (rel, len(srv), len(body) - len(srv)))
            else:
                frozen.append((rel, "快照前缀 ≠ 服务端现役原文"))
            continue
        if hashlib.md5(body).hexdigest() == stamps[rel]:
            ok += 1
        else:
            frozen.append((rel, "md5 %s ≠ 服务端 %s"
                           % (hashlib.md5(body).hexdigest()[:12], stamps[rel][:12])))

    print("包内 css %d 个：与服务端一致 %d，冻住 %d，服务端清单里没有 %d"
          % (len(names), ok, len(frozen), len(unknown)))
    for rel in unknown:
        print("  ? %s（服务端清单里没有——多半是废弃文件，确认后加进豁免名单）" % rel)
    if frozen:
        print("\n✘ 下面这些 CSS 冻住了。装过含它们的热更包的设备上，"
              "这份内容会永远盖住服务端版本：")
        for rel, why in frozen:
            print("    %s —— %s" % (rel, why))
        print("\n修法：把服务端现役内容原样放回包里再发一次（只写不删，"
              "覆盖是唯一的解毒手段）。")
        return 1
    print("✔ 没有冻住的 CSS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
