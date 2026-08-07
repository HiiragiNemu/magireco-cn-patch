#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRI USM（Sofdec2）的解密 / 加密 / 拆流。

游戏的 `movie.zip` / `movie2.zip` 里是 516 个 `.usm`，全部在
`madomagi/resource/movie/char/` 下（角色 Magia、魔女化身的演出动画）。
载荷是加密的，不解密就既看不了内容、也没法判断「里面到底有没有需要汉化的文字」。

## 算法出处与版权

算法源自 CRI Sofdec2，公开描述见 bnnm 的 `vgm-tools/misc/crid-mod` 与
`usm_demuxer.py`、hcs64 的 `usm_deinterleave`。**本文件是按算法重新实现的，
没有抄任何第三方源码**；掩码表另经「静音已知明文」独立反推验证过（见下）。
密钥不在本仓库里，由使用者用 `--key` 传入。

## 格式

块结构一律是：

    signature(4)  size(4, BE)   —— size 是这 8 字节之后的长度
    r08(1) headerOffset(1) footerOffset(2, BE) chunkType(4, BE) …
    payload                      —— 从 8+headerOffset 起，长 size-headerOffset-footerOffset

signature ∈ {CRID, @SFV(视频), @SFA(音频), @ALP(alpha), @SBT(字幕), @CUE}；
chunkType：1 = 头(@UTF 表)，0 = 数据，2 = 索引/seek，3 = 结束。

## 加密

**音频 @SFA**：载荷 `0x140` 之后逐字节 `^ audio_mask[i & 0x1F]`。静态 XOR，自逆。

**视频 @SFV**：载荷前 `0x40` 字节明文，其后分两段，**带反馈**——这一点是关键，
按静态 XOR 去解是解不开的（我最初试了 16 种掩码组合全军覆没，方向就错在这）：

    尾段 [0x100, n)   明文 = 密文 ^ m[j]，随后 m[j] = 明文 ^ vm2[j]
    头段 [0, 0x100)   m[j] ^= 后段明文[0x100+i]，随后 明文 = 密文 ^ m[j]

所以**解密必须先尾后头**（头依赖尾解出来的明文）；而加密时两段都只依赖明文，
互不相干，先做谁都行。两个方向共用同一段代码，靠 `encrypt` 开关切换。

载荷去掉 0x40 之后不足 `0x200` 的块整块不加密。

## 掩码表怎么来的（以及为什么可信）

`gen_masks` 是从 8 字节密钥推出 0x20 字节 seed，再派生三张表：

    video_mask1 = seed
    video_mask2 = seed ^ 0xFF
    audio_mask[i] = "URUC"[(i>>1)&3]  （i 为奇数）
                  = seed[i] ^ 0xFF     （i 为偶数）

这套派生**另有一条独立验证**：真机素材里 ADX 音频开头是静音（明文全 0），
于是那一段密文**就等于掩码本身**。抠出来的 32 字节与本文件算出的 `audio_mask`
逐字节一致，且奇数位正好是 `URUC` 循环。两条路径互证，不是猜的。

## 用法

    python3 scripts/usm_crypt.py info     <a.usm> --key 0x…
    python3 scripts/usm_crypt.py selftest <a.usm> --key 0x…   # 解密→加密 是否逐字节还原
    python3 scripts/usm_crypt.py demux    <a.usm> --key 0x… -o outdir
    python3 scripts/usm_crypt.py decrypt  <a.usm> --key 0x… -o plain.usm
    python3 scripts/usm_crypt.py encrypt  <plain.usm> --key 0x… -o a.usm

`demux` 出来的视频是**裸码流**（H.264 Annex-B 或 IVF/VP9，看原片），
音频是 ADX。喂 ffmpeg 即可：

    ffmpeg -i out/xxx.video -i out/xxx.adx -c:v copy -c:a aac xxx.mp4

## ⚠ 关于「重新压制回去」

本文件只负责**密码学与容器解析**，这两件事已经逐字节验证过。但把重编码后的
视频塞回 USM 还差两步，而且第二步的成败**只能在真机上判定**：

  1. 容器重建：`CRID` 的 `filesize/datasize/avbps`、`@SFV` 头里的
     `total_frames/max_picture_size/ixsize`、以及 chunkType=2 的 seek 表，
     帧长一变全都要重算。这是可编程的工作量。
  2. **CriMana 认不认 ffmpeg 编出来的流。** 它不是通用解码器，对 GOP 结构、
     profile、VP9 的封装约定都有自己的假定。ffmpeg 能播 ≠ 引擎能播。

所以验证顺序应该是：先做「零改动回环」（`selftest` 通过 → 解密再加密得到与原文件
逐字节相同的 USM → 装机播），再做「不加字幕的同参数重编」，最后才谈烧字幕。
另外这批片子**编解码不统一**（有 H.264 也有 VP9），重编要逐个按原编码走。
"""

import argparse
import os
import struct
import sys

SIGS = (b'CRID', b'@SFV', b'@SFA', b'@ALP', b'@SBT', b'@CUE')

VIDEO_PLAIN = 0x40      # @SFV 载荷开头不加密的字节数
AUDIO_PLAIN = 0x140     # @SFA 的
VIDEO_MIN   = 0x200     # 去掉 VIDEO_PLAIN 后不足这么长的块整块不加密


# ------------------------------------------------------------------ 掩码

def gen_masks(key):
    """8 字节密钥 → (video_mask1, video_mask2, audio_mask)。"""
    k = (key & 0xFFFFFFFF).to_bytes(4, 'little') \
        + ((key >> 32) & 0xFFFFFFFF).to_bytes(4, 'little')
    s = bytearray(0x20)
    s[0x00] = k[0]
    s[0x01] = k[1]
    s[0x02] = k[2]
    s[0x03] = (k[3] - 0x34) & 0xFF
    s[0x04] = (k[4] + 0xF9) & 0xFF
    s[0x05] = k[5] ^ 0x13
    s[0x06] = (k[6] + 0x61) & 0xFF
    s[0x07] = s[0x00] ^ 0xFF
    s[0x08] = (s[0x02] + s[0x01]) & 0xFF
    s[0x09] = (s[0x01] - s[0x07]) & 0xFF
    s[0x0A] = s[0x02] ^ 0xFF
    s[0x0B] = s[0x01] ^ 0xFF
    s[0x0C] = (s[0x0B] + s[0x09]) & 0xFF
    s[0x0D] = (s[0x08] - s[0x03]) & 0xFF
    s[0x0E] = s[0x0D] ^ 0xFF
    s[0x0F] = (s[0x0A] - s[0x0B]) & 0xFF
    s[0x10] = (s[0x08] - s[0x0F]) & 0xFF
    s[0x11] = s[0x10] ^ s[0x07]
    s[0x12] = s[0x0F] ^ 0xFF
    s[0x13] = s[0x03] ^ 0x10
    s[0x14] = (s[0x04] - 0x32) & 0xFF
    s[0x15] = (s[0x05] + 0xED) & 0xFF
    s[0x16] = s[0x06] ^ 0xF3
    s[0x17] = (s[0x13] - s[0x0F]) & 0xFF
    s[0x18] = (s[0x15] + s[0x07]) & 0xFF
    s[0x19] = (0x21 - s[0x13]) & 0xFF
    s[0x1A] = s[0x14] ^ s[0x17]
    s[0x1B] = (s[0x16] + s[0x16]) & 0xFF
    s[0x1C] = (s[0x17] + 0x44) & 0xFF
    s[0x1D] = (s[0x03] + s[0x04]) & 0xFF
    s[0x1E] = (s[0x05] - s[0x16]) & 0xFF
    s[0x1F] = s[0x1D] ^ s[0x13]

    vm1 = bytes(s)
    vm2 = bytes(b ^ 0xFF for b in s)
    am = bytearray(0x20)
    for i in range(0x20):
        am[i] = b"URUC"[(i >> 1) & 3] if (i & 1) else (s[i] ^ 0xFF)
    return vm1, vm2, bytes(am)


# ------------------------------------------------------------------ 加解密

def crypt_video(payload, vm1, vm2, encrypt=False):
    """@SFV 载荷的解密/加密。两个方向共用，差别只在两段的先后。"""
    n = len(payload) - VIDEO_PLAIN
    if n < VIDEO_MIN:
        return bytes(payload)
    b = bytearray(payload)
    p = VIDEO_PLAIN

    def tail():
        # 掩码用**明文**推进：两个方向的更新式完全一样，所以可以共用
        m = bytearray(vm2)
        for i in range(0x100, n):
            j = i & 0x1F
            if encrypt:
                plain = b[p + i]
                b[p + i] = plain ^ m[j]
            else:
                plain = b[p + i] ^ m[j]
                b[p + i] = plain
            m[j] = plain ^ vm2[j]

    def head():
        # 掩码由后段**明文**滚动异或而来 → 解密时这里必须在 tail 之后跑
        m = bytearray(vm1)
        for i in range(0x100):
            j = i & 0x1F
            m[j] ^= b[p + 0x100 + i]
            b[p + i] ^= m[j]

    if encrypt:
        head()      # 手上全是明文，先 head，免得被 tail 就地改成密文
        tail()
    else:
        tail()      # head 依赖 tail 解出来的明文
        head()
    return bytes(b)


def crypt_audio(payload, am):
    """@SFA 载荷。静态 XOR，自逆，加解密同一个函数。"""
    if len(payload) <= AUDIO_PLAIN:
        return bytes(payload)
    b = bytearray(payload)
    for i in range(AUDIO_PLAIN, len(b)):
        b[i] ^= am[i & 0x1F]
    return bytes(b)


# ------------------------------------------------------------------ 容器

def chunks(data):
    """逐块产出 (块起点, 签名, chunkType, 载荷起点, 载荷长度)。"""
    p = 0
    while p < len(data) - 8:
        sig = data[p:p + 4]
        if sig not in SIGS:
            break
        size = struct.unpack('>I', data[p + 4:p + 8])[0]
        hoff = data[p + 9]
        foff = struct.unpack('>H', data[p + 10:p + 12])[0]
        ctype = data[p + 15]
        yield p, sig, ctype, p + 8 + hoff, size - hoff - foff
        p += 8 + size


def transform(data, key, encrypt):
    """整文件转换：只动数据块的载荷，容器一个字节不改。"""
    vm1, vm2, am = gen_masks(key)
    out = bytearray(data)
    nv = na = 0
    for _, sig, ctype, st, ln in chunks(data):
        if ctype != 0:
            continue
        payload = data[st:st + ln]
        if sig == b'@SFV':
            out[st:st + ln] = crypt_video(payload, vm1, vm2, encrypt)
            nv += 1
        elif sig == b'@SFA':
            out[st:st + ln] = crypt_audio(payload, am)
            na += 1
    return bytes(out), nv, na


def utf_strings(payload, minlen=4):
    """从 @UTF 表里粗抠可打印 ASCII。够用来看字段名和原始文件名。"""
    out, cur = [], []
    for c in payload:
        if 0x20 <= c < 0x7F:
            cur.append(chr(c))
        else:
            if len(cur) >= minlen:
                out.append(''.join(cur))
            cur = []
    if len(cur) >= minlen:
        out.append(''.join(cur))
    return out


# ------------------------------------------------------------------ 子命令

def cmd_info(args):
    data = open(args.usm, 'rb').read()
    import collections
    tally = collections.Counter()
    names = []
    for _, sig, ctype, st, ln in chunks(data):
        tally[(sig.decode('latin1'), ctype)] += 1
        if ctype == 1 and sig in (b'CRID', b'@SFV', b'@SFA'):
            names.append((sig.decode('latin1'), utf_strings(data[st:st + ln])))
    print('%s  %d 字节' % (args.usm, len(data)))
    print('块统计：')
    for (sig, ct), n in sorted(tally.items()):
        kind = {0: '数据', 1: '头', 2: '索引', 3: '结束'}.get(ct, str(ct))
        print('   %-5s %-4s ×%d' % (sig, kind, n))
    for sig, ss in names:
        print('%s 头里的字符串：%s' % (sig, ss[:24]))
    if not any(s == '@SBT' for (s, _) in tally):
        print('⚠ 没有 @SBT 字幕流——这个片子里没有可替换的字幕轨')
    return 0


def cmd_selftest(args):
    data = open(args.usm, 'rb').read()
    vm1, vm2, am = gen_masks(args.key)
    okv = badv = oka = bada = 0
    for _, sig, ctype, st, ln in chunks(data):
        if ctype != 0:
            continue
        orig = data[st:st + ln]
        if sig == b'@SFV':
            rt = crypt_video(crypt_video(orig, vm1, vm2, False), vm1, vm2, True)
            okv, badv = (okv + 1, badv) if rt == orig else (okv, badv + 1)
        elif sig == b'@SFA':
            rt = crypt_audio(crypt_audio(orig, am), am)
            oka, bada = (oka + 1, bada) if rt == orig else (oka, bada + 1)
    print('视频包 解密→加密 还原一致 %d，不一致 %d' % (okv, badv))
    print('音频包 解密→加密 还原一致 %d，不一致 %d' % (oka, bada))
    # 整文件级别再走一遍，确认容器也没被动过
    plain, _, _ = transform(data, args.key, False)
    again, _, _ = transform(plain, args.key, True)
    same = again == data
    print('整文件 解密→加密 与原文件逐字节相同：%s' % ('是' if same else '否'))
    if badv or bada or not same:
        print('✘ 自检未通过')
        return 1
    print('✔ 自检通过')
    return 0


def cmd_demux(args):
    data = open(args.usm, 'rb').read()
    vm1, vm2, am = gen_masks(args.key)
    os.makedirs(args.out, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.usm))[0]
    video, audio = bytearray(), bytearray()
    for _, sig, ctype, st, ln in chunks(data):
        if ctype != 0:
            continue
        payload = data[st:st + ln]
        if sig == b'@SFV':
            video += crypt_video(payload, vm1, vm2, False)
        elif sig == b'@SFA':
            audio += crypt_audio(payload, am)
    wrote = []
    if video:
        # 裸码流：H.264 是 Annex-B（00 00 00 01 起头），VP9 是 IVF（'DKIF' 起头）
        ext = '.ivf' if video[:4] == b'DKIF' else '.264'
        p = os.path.join(args.out, base + ext)
        open(p, 'wb').write(bytes(video))
        wrote.append((p, len(video)))
    if audio:
        p = os.path.join(args.out, base + '.adx')
        open(p, 'wb').write(bytes(audio))
        wrote.append((p, len(audio)))
    for p, n in wrote:
        print('→ %s  %d 字节' % (p, n))
    if not wrote:
        print('没有可导出的数据块')
        return 1
    return 0


def cmd_transform(args, encrypt):
    data = open(args.usm, 'rb').read()
    out, nv, na = transform(data, args.key, encrypt)
    open(args.out, 'wb').write(out)
    print('%s → %s（视频块 %d、音频块 %d，容器未改动，%d 字节）'
          % (args.usm, args.out, nv, na, len(out)))
    return 0


def parse_key(s):
    return int(s, 16) if s.lower().startswith('0x') else int(s)


def main():
    ap = argparse.ArgumentParser(description='CRI USM 解密 / 加密 / 拆流')
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p, need_key=True):
        p.add_argument('usm')
        if need_key:
            p.add_argument('--key', required=True, type=parse_key,
                           help='USM 密钥，如 0x…（不入库，自己传）')

    p = sub.add_parser('info', help='看块结构与 @UTF 字段（不需要密钥）')
    common(p, need_key=False)
    p.set_defaults(fn=cmd_info)

    p = sub.add_parser('selftest', help='解密→加密 是否逐字节还原')
    common(p)
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser('demux', help='导出解密后的裸视频码流与 ADX 音频')
    common(p)
    p.add_argument('-o', '--out', default='.')
    p.set_defaults(fn=cmd_demux)

    p = sub.add_parser('decrypt', help='整文件解密，容器不动')
    common(p)
    p.add_argument('-o', '--out', required=True)
    p.set_defaults(fn=lambda a: cmd_transform(a, False))

    p = sub.add_parser('encrypt', help='整文件加密，容器不动')
    common(p)
    p.add_argument('-o', '--out', required=True)
    p.set_defaults(fn=lambda a: cmd_transform(a, True))

    args = ap.parse_args()
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
