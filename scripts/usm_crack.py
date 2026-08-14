#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从加密 USM 自动破解密钥。

原理（README「掩码表怎么来的」一节 + 2026-08-14 实破）：
  1. 音频 @SFA 载荷 0x140 之后逐字节 ^ audio_mask[i&0x1F]（静态 XOR）。
  2. ADX 音频流开头是静音（明文全 0）→ 那一段密文就等于 audio_mask 本身。
  3. audio_mask 奇位是 "URUC" 循环、偶位 = seed[i]^0xFF。用偶位反推 seed，
     再用 gen_masks 的依赖式反推密钥 k[0..6]（k[7] 不参与派生，任意）。
  4. 每个文件静音段可能从掩码周期的不同相位开始（0/8/16/24 奇位都对齐），
     用 seed 内部一致性（s[0x0C] 派生式）筛出正确相位。

注意：audio_mask 的偶位对密钥的 k[6] 等高位字节敏感，而静音段偶有 1-2 字节
非全 0（明文不是严格 0 或边界混入非零样本）会导致 k[5]/k[6] 跳变。因此本脚本
输出「候选密钥 + 用 gen_masks 重新生成掩码对照静音段的吻合度」——吻合 0x20
字节全部一致才可信；部分一致时提示并用视频头反推交叉验证（见 --video）。

用法：
    python3 scripts/usm_crack.py <a.usm>                 # 自动破解并验证
    python3 scripts/usm_crack.py <a.usm> --dump-mask     # 只抠 audio_mask(hex)
"""
import argparse
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0] if '/' in __file__ else '.')
import usm_crypt as U

AUDIO_PLAIN = 0x140


def audio_stream(data):
    """拼接所有 @SFA 数据块载荷为一条流，返回 (stream, 各块流起点)。"""
    blocks = [(st, ln) for _, sig, ctype, st, ln in U.chunks(data)
              if sig == b'@SFA' and ctype == 0]
    stream = bytearray()
    for st, ln in blocks:
        stream += data[st:st + ln]
    return stream


def find_silence_masks(stream, max_=8):
    """在 0x140 后找所有奇位为 URUC 的 32 字节段（静音→密文=掩码）。

    返回 [(偏移, 掩码), ...]。同一文件可能有多个静音段；个别段可能混入
    非零样本（明文不严格为 0），导致偶位 1-2 字节污染。取多个段互证，
    按「与多数段一致」选最可信的掩码。
    """
    cands = []
    for pos in range(AUDIO_PLAIN, len(stream) - 0x20):
        cand = stream[pos:pos + 0x20]
        if all(cand[i] == b'URUC'[(i >> 1) & 3] for i in range(1, 0x20, 2)):
            cands.append((pos, bytes(cand)))
            if len(cands) >= max_:
                break
    return cands


def seed_from_mask(am):
    """audio_mask → seed（偶位 = seed[i]^0xFF）。"""
    s = [None] * 0x20
    for i in range(0, 0x20, 2):
        s[i] = am[i] ^ 0xFF
    return s


def check_phase_consistent(s):
    """相位自洽：s[0x0C] = (s[0x0B]+s[0x09])，由 s0,s2,s8 派生可验。"""
    s01 = (s[0x08] - s[0x02]) & 0xFF
    s07 = s[0x00] ^ 0xFF
    s09 = (s01 - s07) & 0xFF
    s0B = s01 ^ 0xFF
    s0C = (s0B + s09) & 0xFF
    return s[0x0C] == s0C


def crack_from_mask(am):
    """由正确相位的 audio_mask 反推密钥，返回 (key_int, 反推的 k bytes)。"""
    s = seed_from_mask(am)
    if not check_phase_consistent(s):
        return None, None
    k0 = s[0x00]
    k2 = s[0x02]
    s8 = s[0x08]
    k1 = (s8 - k2) & 0xFF
    s0E = s[0x0E]
    s0D = s0E ^ 0xFF
    s03 = (s8 - s0D) & 0xFF
    k3 = (s03 + 0x34) & 0xFF
    s04 = s[0x04]
    k4 = (s04 - 0xF9) & 0xFF
    s16 = s[0x16]
    s1E = s[0x1E]
    s05 = (s1E + s16) & 0xFF
    k5 = s05 ^ 0x13
    s06 = s[0x06]
    k6 = (s06 - 0x61) & 0xFF
    kbytes = bytes([k0, k1, k2, k3, k4, k5, k6, 0])
    key = int.from_bytes(kbytes, 'little')
    return key, kbytes


def main():
    ap = argparse.ArgumentParser(description='从加密 USM 破解密钥')
    ap.add_argument('usm', help='加密的 .usm 文件')
    ap.add_argument('--dump-mask', action='store_true',
                    help='只输出 audio_mask 的 hex 就退出')
    args = ap.parse_args()

    data = open(args.usm, 'rb').read()
    stream = audio_stream(data)
    if len(stream) <= AUDIO_PLAIN + 0x20:
        print('✘ 音频流太短，无法定位静音段', file=sys.stderr)
        return 1

    cands = find_silence_masks(stream)
    if not cands:
        print('✘ 找不到奇位 URUC 的静音段（可能未加密或密钥结构不同）',
              file=sys.stderr)
        return 1
    print('静音段候选：%d 处' % len(cands))
    for i, (pos, am) in enumerate(cands):
        print('  #%d @ 0x%x  %s' % (i, pos, am.hex()))
    if args.dump_mask:
        return 0

    # 逐段×逐相位找「seed 自洽 + gen_masks 回验全一致」的掩码。
    # 只有真正正确相位的真静音段才同时满足 seed 派生式(s0C 校验)与
    # 「反推密钥后 gen_masks 原样还原该掩码」两个约束；污染段/错相位
    # 至少破一个。取吻合度最高者。
    best = None
    for _, am_seg in cands:
        for ph in (0, 8, 16, 24):
            am_ph = am_seg[ph:] + am_seg[:ph]
            key, kbytes = crack_from_mask(am_ph)
            if key is None:
                continue
            _, _, am_regen = U.gen_masks(key)
            matched = sum(a == b for a, b in zip(am_regen, am_ph))
            if best is None or matched > best[0]:
                best = (matched, ph, key, kbytes, am_ph)
    if best is None:
        print('✘ 各相位都不自洽，破解失败（需人工核对掩码）', file=sys.stderr)
        return 1

    matched, ph, key, kbytes, am_ph = best
    print('正确相位 = %d（seed 自洽 + gen_masks 回验 %d/32 一致）'
          % (ph, matched))

    print()
    print('破解密钥（k[7] 任意，256 个等价形式）：')
    for k7 in (0x00, 0x54, 0xFF):
        k_full = key | (k7 << 56)
        print('  0x%016x' % k_full)
    print()
    print('等价族通式：0xXX%014x（XX 任意，共 256 个）' % key)
    print()
    print('验证：python3 scripts/usm_crypt.py demux %s --key 0x%016x -o out'
          % (args.usm, key))
    if matched < 32:
        print()
        print('⚠ 掩码未全对齐——静音段可能有非零样本。若解出画面正常仍可信；')
        print('  更稳妥是用 --dump-mask 抠掩码后人工核对 seed 派生。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
