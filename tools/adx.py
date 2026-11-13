"""CRI ADX (encoding type 3, 4-bit) decoder -> 16-bit WAV. usage: adx.py <in.adx|dir> <out.wav|dir>"""
import math, os, struct, sys, wave
def decode(d):
    co = struct.unpack('>H', d[2:4])[0]; enc, bsz, bits, ch = d[4], d[5], d[6], d[7]
    rate, total = struct.unpack('>II', d[8:16]); cutoff = struct.unpack('>H', d[16:18])[0]
    assert enc == 3 and bits == 4 and bsz == 18, (enc, bits, bsz)
    a = math.sqrt(2.0) - math.cos(2.0 * math.pi * cutoff / rate); b = math.sqrt(2.0) - 1.0
    c = (a - math.sqrt((a + b) * (a - b))) / b
    c1 = int(c * 2.0 * 4096); c2 = int(-(c * c) * 4096)
    pos = co + 4; hist = [[0, 0] for _ in range(ch)]; out = [[] for _ in range(ch)]
    nblocks = (len(d) - pos) // (bsz * ch)
    for blk in range(nblocks):
        for k in range(ch):
            o = pos + (blk * ch + k) * bsz
            scale = struct.unpack('>H', d[o:o + 2])[0] & 0x1fff
            if scale == 0x1fff: break
            scale += 1; y1, y2 = hist[k]
            for i in range(32):
                nib = (d[o + 2 + i // 2] >> (4 if i % 2 == 0 else 0)) & 15
                if nib >= 8: nib -= 16
                s = nib * scale + ((c1 * y1 + c2 * y2) >> 12)
                s = max(-32768, min(32767, s)); out[k].append(s); y2, y1 = y1, s
            hist[k] = [y1, y2]
    return rate, ch, [x[:total] for x in out]
def to_wav(rate, ch, chans, path):
    n = min(len(c) for c in chans)
    frames = bytearray()
    for i in range(n):
        for c in chans: frames += struct.pack('<h', c[i])
    with wave.open(path, 'wb') as w: w.setnchannels(ch); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(frames))
if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True); n = 0
        for f in sorted(os.listdir(src)):
            if f.endswith('.adx'):
                r, c, ch = decode(open(os.path.join(src, f), 'rb').read()); to_wav(r, c, ch, os.path.join(dst, f[:-4] + '.wav')); n += 1
        print(n, 'ADX decoded')
    else:
        r, c, ch = decode(open(src, 'rb').read()); to_wav(r, c, ch, dst)
