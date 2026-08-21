#!/usr/bin/env python3
"""构建完整 cn_js_update.zip，并固定携带 native 引擎翻译表。

ZIP 根布局只有两棵并行路径：

    magica/**                    WebView 前端产品树
    madomagi/engine_i18n.tsv     native/cocos2d 翻译表（必含）
    madomagi/repair_manifest.json native 修复层声明（必含）
    madomagi/resource/image_native/**  固定 native 修复层（必含）

scenario 资源不属于 JS 包。以旧 JS 包为底时，本工具保留完整 ``magica/``，用
本仓库当前 ``madomagi/engine_i18n.tsv`` 覆盖底包版本，并剔除越界根路径。只改
引擎表时可省略前端根目录和改动清单，但必须提供 ``--base``，从而仍生成完整包。

用法：
    python tools/i18n-package.py <magica 根目录> <改动清单> \
        --base <旧 cn_js_update.zip> -o <新包>
    python tools/i18n-package.py --base <旧包> -o <新包>  # engine-only 变更
    python tools/i18n-package.py --base <旧包> -o <新包> \
        --add <本地文件>=<magica 下相对路径>

``--engine`` 仅供隔离测试或显式输入；默认值是仓库唯一权威文件
``madomagi/engine_i18n.tsv``。客户端仍只读取解压后的
``<files>/madomagi/engine_i18n.tsv``。
"""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import sys
import zipfile


ENGINE_MEMBER = 'madomagi/engine_i18n.tsv'
REPAIR_MANIFEST = 'madomagi/repair_manifest.json'
REPAIR_PREFIX = 'madomagi/resource/image_native/'
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENGINE = REPO_ROOT / ENGINE_MEMBER
DEFAULT_REPAIR_MANIFEST = REPO_ROOT / REPAIR_MANIFEST
DEFAULT_REPAIR_ROOT = REPO_ROOT / REPAIR_PREFIX
RUNTIME_EXCLUDED_PREFIXES = ('magica/research/', 'magica/i18n_audit/')


def magica_member(rel):
    """把相对 magica/ 的路径规范化，并阻止越出产品树。"""
    value = rel.replace('\\', '/').lstrip('/')
    path = PurePosixPath(value)
    if not value or value.endswith('/') or value.startswith('magica/'):
        raise ValueError('包内路径应为 magica/ 下的相对文件路径：%s' % rel)
    if '..' in path.parts or '.' in path.parts:
        raise ValueError('包内路径不得越出 magica/：%s' % rel)
    member = 'magica/' + path.as_posix()
    if member.startswith(RUNTIME_EXCLUDED_PREFIXES):
        raise ValueError('审计/研究文件不得进入运行时包：%s' % rel)
    return member


def validate_engine(path):
    """校验 engine 表的 UTF-8/TSV 合同；空译文仍表示有意删除。"""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError('engine_i18n.tsv 不可读：%s' % exc) from exc
    if not raw:
        raise ValueError('engine_i18n.tsv 为空')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('engine_i18n.tsv 必须是 UTF-8：%s' % exc) from exc
    for number, line in enumerate(text.splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        if '\t' not in line:
            raise ValueError('engine_i18n.tsv 第 %d 行缺少 TAB' % number)
    return raw


def allowed_base_member(name):
    """JS 包只继承 magica/、唯一 engine 表与固定 native 修复层。"""
    normalized = name.replace('\\', '/')
    path = PurePosixPath(normalized)
    if normalized != name or path.is_absolute() or '..' in path.parts:
        return False
    if normalized.startswith(RUNTIME_EXCLUDED_PREFIXES):
        return False
    return (
        normalized == 'magica/'
        or normalized.startswith('magica/')
        or normalized == 'madomagi/'
        or normalized == ENGINE_MEMBER
        or normalized == REPAIR_MANIFEST
        or normalized.startswith(REPAIR_PREFIX)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?',
                    help='汉化后的 magica 根目录（含 js/ 与 template/）')
    ap.add_argument('changed', nargs='?', help='i18n-apply.py 产出的改动清单')
    ap.add_argument('--base', help='旧的 cn_js_update.zip，作为完整底包')
    ap.add_argument('--add', action='append', default=[], metavar='本地文件=包内路径',
                    help='追加静态资源；包内路径相对 magica/，不得带 magica/ 前缀')
    ap.add_argument('--engine', default=str(DEFAULT_ENGINE), metavar='TSV',
                    help='引擎翻译表（默认：仓库 madomagi/engine_i18n.tsv）')
    ap.add_argument('-o', '--out', default='cn_js_update.zip')
    args = ap.parse_args()

    if not os.path.isfile(args.engine):
        print('engine_i18n.tsv 不存在：%s' % args.engine, file=sys.stderr)
        return 1
    try:
        engine_bytes = validate_engine(args.engine)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not DEFAULT_REPAIR_ROOT.is_dir():
        print('native 修复目录不存在：%s' % DEFAULT_REPAIR_ROOT, file=sys.stderr)
        return 1
    repair_files = {
        REPAIR_PREFIX + path.relative_to(DEFAULT_REPAIR_ROOT).as_posix(): path
        for path in DEFAULT_REPAIR_ROOT.rglob('*') if path.is_file()
    }
    if not repair_files:
        print('native 修复目录为空', file=sys.stderr)
        return 1
    try:
        repair_manifest_bytes = DEFAULT_REPAIR_MANIFEST.read_bytes()
        repair_manifest = json.loads(repair_manifest_bytes.decode('utf-8'))
        declared = {
            row['path']: row['bytes'] for row in repair_manifest['entries']
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print('native 修复清单不可读：%s' % exc, file=sys.stderr)
        return 1
    actual = {name: path.stat().st_size for name, path in repair_files.items()}
    if (
        repair_manifest.get('schema') != 'magireco-cn-madomagi-repair/v1'
        or repair_manifest.get('file_count') != len(declared)
        or repair_manifest.get('total_bytes') != sum(declared.values())
        or declared != actual
    ):
        print('native 修复清单与 image_native 产品树不一致', file=sys.stderr)
        return 1

    extras = {}
    for spec in args.add:
        if '=' not in spec:
            print('--add 要写成 <本地文件>=<包内路径>：%s' % spec, file=sys.stderr)
            return 1
        src, rel = spec.split('=', 1)
        if not os.path.isfile(src):
            print('--add 的源文件不存在：%s' % src, file=sys.stderr)
            return 1
        try:
            name = magica_member(rel)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        extras[name] = src

    files = []
    if args.changed:
        try:
            files = [line.strip() for line in
                     Path(args.changed).read_text(encoding='utf-8').splitlines()
                     if line.strip()]
        except OSError as exc:
            print('改动清单不可读：%s' % exc, file=sys.stderr)
            return 1
    if not files and not extras and not args.base:
        print('仅更新 engine_i18n.tsv 时必须提供 --base，以保留完整 magica 产品树',
              file=sys.stderr)
        return 1
    if files and not args.root:
        print('给了改动清单就必须给 magica 根目录', file=sys.stderr)
        return 1
    if args.base and not os.path.isfile(args.base):
        print('底包不存在：%s' % args.base, file=sys.stderr)
        return 1

    try:
        file_members = {rel: magica_member(rel) for rel in files}
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    seen = set()
    n_base = 0
    n_new = 0
    n_extra = 0
    n_rejected = 0
    with zipfile.ZipFile(args.out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        # 先铺底包；新文件同名时跳过旧项，稍后写入新内容。
        new_names = (
            set(file_members.values())
            | set(extras)
            | set(repair_files)
            | {ENGINE_MEMBER, REPAIR_MANIFEST}
        )
        if args.base:
            try:
                base = zipfile.ZipFile(args.base)
            except (OSError, zipfile.BadZipFile) as exc:
                print('底包不是有效 ZIP：%s' % exc, file=sys.stderr)
                return 1
            with base:
                for item in base.infolist():
                    name = item.filename.replace('\\', '/')
                    if name in new_names:
                        continue
                    if not allowed_base_member(name):
                        n_rejected += 1
                        print('  - 剔除 JS 包越界项：%s' % name, file=sys.stderr)
                        continue
                    if name in seen:
                        n_rejected += 1
                        print('  - 剔除重复项：%s' % name, file=sys.stderr)
                        continue
                    z.writestr(item, base.read(item.filename))
                    seen.add(name)
                    n_base += 1

        for rel in files:
            src = os.path.join(args.root, rel)
            if not os.path.isfile(src):
                print('  ⚠ 清单里有但磁盘上没有：%s' % rel, file=sys.stderr)
                continue
            name = file_members[rel]
            if name in seen:
                continue
            z.write(src, name)
            seen.add(name)
            n_new += 1

        for name, src in sorted(extras.items()):
            if name in seen:
                continue
            z.write(src, name)
            seen.add(name)
            n_extra += 1
            print('  + %s ← %s' % (name, src))

        for name, src in sorted(repair_files.items()):
            z.write(src, name)
            seen.add(name)

        z.writestr(REPAIR_MANIFEST, repair_manifest_bytes)
        seen.add(REPAIR_MANIFEST)

        # 必含且永远以当前权威源覆盖旧表。
        z.writestr(ENGINE_MEMBER, engine_bytes)
        seen.add(ENGINE_MEMBER)

    size = os.path.getsize(args.out)
    if n_extra:
        print('额外追加 %d 项' % n_extra)
    if n_rejected:
        print('已剔除 %d 个越界/重复底包项' % n_rejected)
    print('底包沿用 %d 项，新增/覆盖 %d 项，native 修复 %d 项、声明 1 项，引擎表 1 项，共 %d 项'
          % (n_base, n_new, len(repair_files), len(seen)))
    print('→ %s（%.1f MB）' % (args.out, size / 1024.0 / 1024.0))
    print('\n发布前还要做两件事：')
    print('  1. 上传 cn_js_update.zip（scenario 包保持不变）')
    print('  2. version_js.json 的 version 加 1；不要递增 version_scenario.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
