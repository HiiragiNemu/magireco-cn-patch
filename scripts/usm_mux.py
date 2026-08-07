#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRI USM 的拆包 / 重打包：把重编码后的视频塞回 USM。

依赖同目录的 `usm_crypt.py`（加解密与块遍历）。

## 容器长什么样（实测 op_movie2.usm，37 MB / 4870 个块）

块的框架比想象中简单，而且**没有逐帧的 seek 表**——那三个 `chunkType=2` 的块
只是 32 字节的 ASCII 段标记（`#HEADER END`、`#METADATA END`、`#CONTENTS END`），
不含任何偏移量。这一点决定了重打包是可做的：帧长变了不需要重算索引。

实测出来的不变量（本工具依赖它们，`rebuild` 会逐条断言）：

  · `headerOffset` 恒为 24，`r08` 恒为 0；
  · **整块长度（8 + size）恒为 32 的倍数**，`footerOffset` 就是尾部补零的字节数，
    即 `pad = (-载荷长) mod 32`；补的全是 `0x00`；
  · 块头 `[12:32]` 里装着 chunkType 与该帧的时间戳（每帧 +125）与 fps×100。
    **同帧数重打包时原样照抄**，不需要重算。

## 要重算的字段（都在 @UTF 表里，定宽，就地改）

| 表 | 字段 | 怎么算 |
|---|---|---|
| `CRIUSF_DIR_STREAM` row0 | `filesize` | 整个文件的字节数 |
| 同上 row1/row2 | `filesize` | **该流全部数据块的载荷长度之和**（不含块头与补零） |
| 同上 row1 | `minbuf` | 该流**最大载荷**长度（不含块头与补零） |
| `VIDEO_HDRINFO` | `ixsize` | 该流**最大整块**长度（含块头与补零） |

`minbuf` 与 `ixsize` 差一个块头加补零，很容易写混——实测 op_movie2 是
`ixsize=276896`、`minbuf=276845`，差 51 = 32 + 19。identity 测试就是靠这处卡住
才把两者分开的。`avbps`／`minchk` 不动：音频那一侧的取值规律没摸清
（`minbuf=27860` 与最大音频载荷完全对不上），而我们本来就不改音频，动它没有收益只有风险。

这几条公式不是猜的：拿原片跑出来的数与文件里写着的**逐个对上**
（视频 32192027、音频 4865166、整文件 37314784、ixsize 276896）。

`@UTF` 表这里只做**就地改值**，不重排版：要改的都是定宽数值列，改完偏移量、
字符串区、行宽全都不变，省掉了整张表重新序列化的风险。

## 硬约束：帧数必须与原片一致

`rebuild` 要求新视频的帧数与原片的 `@SFV` 数据块数**完全相同**，然后逐个替换
载荷、其余（音频、块序、时间戳、段标记）原样保留。

这不是偷懒，是刻意把变量压到最少：交织顺序、音视频同步、时间戳全都不动，
真机上万一播不了，就只可能是「编码器产物本身不被 CriMana 接受」，不会与
「我们把容器拼错了」混在一起。用 ffmpeg 同帧率、不丢帧地重编即可满足。

## 自证：identity 测试

`extract` 出来的流原样 `rebuild` 回去，**必须与原文件逐字节相同**。
`selftest` 子命令就是干这个的。这条过了，才说明块框架、补零、@UTF 改值、
加密四件事都没写错；之后换成重编码的流，唯一的变量就只剩编码器。

## 用法

    python3 scripts/usm_mux.py selftest <in.usm> --key 0x…
    python3 scripts/usm_mux.py extract  <in.usm> --key 0x… -o work/
    # …用 ffmpeg 解码 work/video.bin、烧字幕、按原参数重编 …
    python3 scripts/usm_mux.py rebuild  <in.usm> --key 0x… \\
            --video new.ivf -o out.usm

`--frames <lengths.txt>` 可以显式指定每帧的字节数（`extract` 会写一份）；
不给的话按码流自己切：IVF 按帧记录切，H.264 Annex-B 按 AUD（`00 00 00 01 09`）切。
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import usm_crypt as UC          # noqa: E402

HDR_OFF = 24          # headerOffset，实测恒为 24
ALIGN   = 32          # 整块长度对齐


# ------------------------------------------------------------------ @UTF

_TYPES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 8, 7: 8, 8: 4, 9: 8, 0xA: 4, 0xB: 8}


def utf_parse(b):
    """只解析到能定位「某列某行的值在哪几个字节」为止，不做完整反序列化。"""
    if b[:4] != b'@UTF':
        return None
    base = 8
    rows_off = struct.unpack('>H', b[base + 2:base + 4])[0]
    str_off  = struct.unpack('>I', b[base + 4:base + 8])[0]
    cols, row_w = struct.unpack('>HH', b[base + 16:base + 20])
    rows = struct.unpack('>I', b[base + 20:base + 24])[0]
    S = base + str_off

    def name_at(o):
        e = b.index(b'\0', S + o)
        return b[S + o:e].decode('utf-8', 'replace')

    p = base + 24
    schema = {}
    roff = 0
    for _ in range(cols):
        flags = b[p]
        p += 1
        typ = flags & 0x0F
        store = flags & 0xF0
        nm = None
        if store & 0x10:
            nm = name_at(struct.unpack('>I', b[p:p + 4])[0])
            p += 4
        w = _TYPES[typ]
        ent = {'width': w, 'const_at': None, 'row_off': None}
        if store & 0x20:
            ent['const_at'] = p
            p += w
        elif store & 0x40:
            ent['row_off'] = roff
            roff += w
        if nm:
            schema[nm] = ent
    return {'rows': rows, 'row_w': row_w, 'rows_at': base + rows_off, 'schema': schema}


def utf_set(b, table, col, row, value):
    """就地写一个定宽无符号整数。b 必须是 bytearray。"""
    ent = table['schema'].get(col)
    if ent is None:
        raise KeyError('@UTF 表里没有列 %s' % col)
    if ent['const_at'] is not None:
        off = ent['const_at']
    elif ent['row_off'] is not None:
        off = table['rows_at'] + row * table['row_w'] + ent['row_off']
    else:
        raise KeyError('列 %s 既不是常量也不是每行，改不了' % col)
    w = ent['width']
    if value >= (1 << (8 * w)):
        raise ValueError('%s 放不下：%d 超出 %d 字节' % (col, value, w))
    b[off:off + w] = value.to_bytes(w, 'big')


def utf_get(b, table, col, row=0):
    ent = table['schema'][col]
    off = ent['const_at'] if ent['const_at'] is not None else \
        table['rows_at'] + row * table['row_w'] + ent['row_off']
    return int.from_bytes(b[off:off + ent['width']], 'big')


# ------------------------------------------------------------------ 块

class Chunk(object):
    __slots__ = ('sig', 'ctype', 'head', 'payload', 'orig_len', 'orig_pad')

    def __init__(self, sig, ctype, head, payload, orig_pad=None):
        self.sig = sig          # b'@SFV' 等
        self.ctype = ctype
        self.head = head        # 块头的 [8:8+24]，原样保留（含时间戳）
        self.payload = payload
        self.orig_len = len(payload)
        # 载荷没被换过的块，补零长度照抄原文件。
        # 因为有一个例外不服从 32 对齐的通用式：**CRID 头块被固定补到 2048 字节**
        # （实测 384 载荷 + 1632 补零），那是 CRI 预留的定长头区。按通用式重算会
        # 把它压回 384+0，整个文件就对不上了。
        self.orig_pad = orig_pad

    def _pad(self):
        if self.orig_pad is not None and len(self.payload) == self.orig_len:
            return self.orig_pad
        return (-len(self.payload)) % ALIGN

    def serialize(self):
        pad = self._pad()
        size = HDR_OFF + len(self.payload) + pad
        out = bytearray()
        out += self.sig
        out += struct.pack('>I', size)
        out += self.head
        out += self.payload
        out += b'\0' * pad
        assert len(out) % ALIGN == 0, '整块长度必须 32 对齐'
        return bytes(out)

    def whole_len(self):
        return 8 + HDR_OFF + len(self.payload) + self._pad()


def parse(data):
    out = []
    for off, sig, ctype, st, ln in UC.chunks(data):
        hoff = data[off + 9]
        if hoff != HDR_OFF:
            raise ValueError('headerOffset=%d，本工具只支持 24' % hoff)
        if data[off + 8] != 0:
            raise ValueError('r08=%d，本工具只支持 0' % data[off + 8])
        foff = struct.unpack('>H', data[off + 10:off + 12])[0]
        out.append(Chunk(sig, ctype, data[off + 8:off + 8 + HDR_OFF],
                         data[st:st + ln], orig_pad=foff))
    used = sum(c.whole_len() for c in out)
    if used != len(data):
        raise ValueError('块长合计 %d ≠ 文件长 %d，容器里有本工具不认识的东西'
                         % (used, len(data)))
    return out


# ------------------------------------------------------------------ 切帧

def split_ivf(es):
    """IVF：32 字节文件头，其后每帧 size(4 LE) + pts(8) + data。"""
    if es[:4] != b'DKIF':
        return None
    hdr_len = struct.unpack('<H', es[6:8])[0]
    frames = []
    p = hdr_len
    while p + 12 <= len(es):
        n = struct.unpack('<I', es[p:p + 4])[0]
        frames.append(es[p:p + 12 + n])      # 连同 12 字节帧头一起，与原片一致
        p += 12 + n
    return frames


def split_annexb(es):
    """H.264 Annex-B：按 AUD（00 00 00 01 09）切，与原片的分块方式一致。"""
    marker = b'\x00\x00\x00\x01\x09'
    if not es.startswith(marker):
        return None
    idx = []
    p = 0
    while True:
        i = es.find(marker, p)
        if i < 0:
            break
        idx.append(i)
        p = i + len(marker)
    return [es[idx[k]:(idx[k + 1] if k + 1 < len(idx) else len(es))]
            for k in range(len(idx))]


def split_by_lengths(es, lengths):
    frames, p = [], 0
    for n in lengths:
        frames.append(es[p:p + n])
        p += n
    if p != len(es):
        raise ValueError('长度表合计 %d ≠ 码流 %d 字节' % (p, len(es)))
    return frames


# ------------------------------------------------------------------ 重算

def recompute(chunks):
    """按实测公式重算 @UTF 里的几个数。chunks 里的载荷必须已是**明文**。"""
    vids = [c for c in chunks if c.sig == b'@SFV' and c.ctype == 0]
    auds = [c for c in chunks if c.sig == b'@SFA' and c.ctype == 0]
    v_payload = sum(len(c.payload) for c in vids)
    a_payload = sum(len(c.payload) for c in auds)
    v_maxwhole = max((c.whole_len() for c in vids), default=0)
    # minbuf 是最大**载荷**，ixsize 是最大**整块**——差的就是 32 字节块头加补零。
    # 实测 op_movie2：ixsize 276896、minbuf 276845，差 51 = 32 + 19(补零)。
    # 一开始两个都按整块算，identity 测试就卡在 CRID 的 minbuf 上，靠它才发现。
    v_maxpay = max((len(c.payload) for c in vids), default=0)
    total = sum(c.whole_len() for c in chunks)

    for c in chunks:
        if c.ctype != 1:
            continue
        b = bytearray(c.payload)
        t = utf_parse(b)
        if t is None:
            continue
        if c.sig == b'CRID' and 'filesize' in t['schema']:
            # row0 = 整个文件；row1 = 视频流；row2 = 音频流
            utf_set(b, t, 'filesize', 0, total)
            if t['rows'] > 1:
                utf_set(b, t, 'filesize', 1, v_payload)
                if 'minbuf' in t['schema']:
                    utf_set(b, t, 'minbuf', 1, v_maxpay)
            if t['rows'] > 2:
                utf_set(b, t, 'filesize', 2, a_payload)
        elif c.sig == b'@SFV' and 'ixsize' in t['schema']:
            utf_set(b, t, 'ixsize', 0, v_maxwhole)
        c.payload = bytes(b)
    return dict(total=total, v_payload=v_payload, a_payload=a_payload,
                v_max=v_maxwhole, v_maxpay=v_maxpay,
                n_video=len(vids), n_audio=len(auds))


def build(chunks, key):
    vm1, vm2, am = UC.gen_masks(key)
    out = bytearray()
    for c in chunks:
        payload = c.payload
        if c.ctype == 0:
            if c.sig == b'@SFV':
                payload = UC.crypt_video(payload, vm1, vm2, encrypt=True)
            elif c.sig == b'@SFA':
                payload = UC.crypt_audio(payload, am)
        out += Chunk(c.sig, c.ctype, c.head, payload,
                     orig_pad=c.orig_pad if len(payload) == c.orig_len else None
                     ).serialize()
    return bytes(out)


def load_plain(path, key):
    """读进来并把数据块载荷解密成明文。"""
    data = open(path, 'rb').read()
    chunks = parse(data)
    vm1, vm2, am = UC.gen_masks(key)
    for c in chunks:
        if c.ctype != 0:
            continue
        if c.sig == b'@SFV':
            c.payload = UC.crypt_video(c.payload, vm1, vm2, encrypt=False)
        elif c.sig == b'@SFA':
            c.payload = UC.crypt_audio(c.payload, am)
    return data, chunks


# ------------------------------------------------------------------ 子命令

def cmd_extract(args):
    _, chunks = load_plain(args.usm, args.key)
    os.makedirs(args.out, exist_ok=True)
    for sig, vname, lname in ((b'@SFV', 'video.bin', 'frames_video.txt'),
                              (b'@SFA', 'audio.bin', 'frames_audio.txt')):
        parts = [c.payload for c in chunks if c.sig == sig and c.ctype == 0]
        if not parts:
            continue
        with open(os.path.join(args.out, vname), 'wb') as f:
            for p in parts:
                f.write(p)
        with open(os.path.join(args.out, lname), 'w') as f:
            for p in parts:
                f.write('%d\n' % len(p))
        print('→ %s  %d 帧 / %d 字节（长度表 %s）'
              % (vname, len(parts), sum(len(p) for p in parts), lname))
    return 0


def _frames_for(args, want):
    es = open(args.video, 'rb').read()
    if args.frames:
        lengths = [int(x) for x in open(args.frames) if x.strip()]
        frames = split_by_lengths(es, lengths)
        how = '长度表'
    else:
        frames = split_ivf(es) or split_annexb(es)
        how = 'IVF 帧记录' if es[:4] == b'DKIF' else 'Annex-B AUD'
        if frames is None:
            raise SystemExit('✘ 认不出码流格式（既不是 IVF 也不是 Annex-B），'
                             '请用 --frames 显式给长度表')
    if len(frames) != want:
        raise SystemExit('✘ 帧数不符：新视频 %d 帧，原片 %d 帧。'
                         '本工具要求同帧数（见文件头说明）——重编时保持帧率、不要丢帧。'
                         % (len(frames), want))
    return frames, how


def cmd_rebuild(args):
    _, chunks = load_plain(args.usm, args.key)
    vids = [c for c in chunks if c.sig == b'@SFV' and c.ctype == 0]
    frames, how = _frames_for(args, len(vids))
    print('新视频按%s切出 %d 帧' % (how, len(frames)))
    for c, f in zip(vids, frames):
        c.payload = f
    st = recompute(chunks)
    out = build(chunks, args.key)
    open(args.out, 'wb').write(out)
    print('→ %s  %d 字节（视频块 %d、音频块 %d；视频载荷 %d、最大整块 %d）'
          % (args.out, len(out), st['n_video'], st['n_audio'],
             st['v_payload'], st['v_max']))
    return 0


def cmd_selftest(args):
    """把原片自己的流原样重打包，必须逐字节回到原文件。"""
    data, chunks = load_plain(args.usm, args.key)
    st = recompute(chunks)
    out = build(chunks, args.key)
    same = out == data
    print('原片 %d 字节；重打包 %d 字节' % (len(data), len(out)))
    print('  视频块 %d、音频块 %d；视频载荷和 %d、音频载荷和 %d、最大整块 %d'
          % (st['n_video'], st['n_audio'], st['v_payload'],
             st['a_payload'], st['v_max']))
    if same:
        print('✔ 逐字节相同 —— 块框架、补零、@UTF 改值、加密四件事都对')
        return 0
    # 不同就把第一处差异指出来，省得干瞪眼
    n = min(len(out), len(data))
    for i in range(n):
        if out[i] != data[i]:
            print('✘ 第一处差异在 0x%X：原 %02x → 新 %02x' % (i, data[i], out[i]))
            break
    else:
        print('✘ 前缀相同但长度不同')
    return 1


def main():
    ap = argparse.ArgumentParser(description='CRI USM 拆包 / 重打包')
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('usm')
        p.add_argument('--key', required=True, type=UC.parse_key)

    p = sub.add_parser('selftest', help='原样重打包，必须逐字节回到原文件')
    common(p)
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser('extract', help='导出明文的视频/音频码流与逐帧长度表')
    common(p)
    p.add_argument('-o', '--out', default='.')
    p.set_defaults(fn=cmd_extract)

    p = sub.add_parser('rebuild', help='换掉视频码流后重打包')
    common(p)
    p.add_argument('--video', required=True, help='新的视频码流（IVF 或 Annex-B）')
    p.add_argument('--frames', help='逐帧长度表；不给就按码流自己切')
    p.add_argument('-o', '--out', required=True)
    p.set_defaults(fn=cmd_rebuild)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
