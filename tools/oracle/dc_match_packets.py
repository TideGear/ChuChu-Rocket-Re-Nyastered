#!/usr/bin/env python3
"""Resolve a Flycast state's 2D draw packets to disc textures and print the layout (position, size, depth) in draw order.

usage: dc_match_packets.py <file.state> [assets dir=local/cache/assets] [--all]

Packets are PowerVR sprite headers with ctrl 0x828c0028 in the 2D list (state offsets 0x1500003..0x1c00000, 32-byte aligned from 3). The VRAM base is found by
locating a non-twiddled disc image of the packet's size in the state; every texture is then decoded (Dreamcast twiddle, ARGB1555/RGB565/ARGB4444) and matched to
the disc PNG with the smallest difference (both orientations). Output is sorted by depth (1/w, ascending = drawn first), ties in submission order, which is how the
PowerVR sorts translucent quads. Use it to lay out a screen; textures with a score above ~1 are not on the disc as a PNG (run-time text or unknown source)."""
import glob, os, struct, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def twiddle_index(w, h):
    bits = int(np.log2(min(w, h)))
    idx = np.zeros((h, w), dtype=np.int64)
    for y in range(h):
        for x in range(w):
            v = 0
            for i in range(bits):
                v |= (((x >> i) & 1) << (2 * i + 1)) | (((y >> i) & 1) << (2 * i))
            if w > h: v |= (x >> bits) << (2 * bits)
            elif h > w: v |= (y >> bits) << (2 * bits)
            idx[y, x] = v
    return idx

_twiddle = {}

def decode(state, base, tex, tsp):
    w = 8 << ((tsp >> 3) & 7); h = 8 << (tsp & 7)
    fmt = (tex >> 27) & 7; plain = (tex >> 26) & 1; o = base + (tex & 0x1fffff) * 8
    raw = np.frombuffer(state[o:o + w * h * 2], dtype='<u2')
    if len(raw) < w * h or fmt > 2: return None
    if plain: t = raw.reshape(h, w)
    else:
        if (w, h) not in _twiddle: _twiddle[(w, h)] = twiddle_index(w, h)
        t = raw[_twiddle[(w, h)]]
    a = np.zeros((h, w, 4), np.uint8)
    if fmt == 0:
        a[..., 0] = ((t >> 10) & 31) * 255 // 31; a[..., 1] = ((t >> 5) & 31) * 255 // 31; a[..., 2] = (t & 31) * 255 // 31; a[..., 3] = (t >> 15) * 255
    elif fmt == 1:
        a[..., 0] = ((t >> 11) & 31) * 255 // 31; a[..., 1] = ((t >> 5) & 63) * 255 // 63; a[..., 2] = (t & 31) * 255 // 31; a[..., 3] = 255
    else:
        a[..., 0] = ((t >> 8) & 15) * 17; a[..., 1] = ((t >> 4) & 15) * 17; a[..., 2] = (t & 15) * 17; a[..., 3] = ((t >> 12) & 15) * 17
    return a

def packets(state):
    out = []
    for o in range(0x1500003, min(len(state) - 200, 0x1c00000), 32):
        w = struct.unpack_from('<4I', state, o)
        if (w[0] >> 29) in (4, 5) and w[1] == 0xc8800000 and (w[0] & 0xffffff) == 0x8c0028:
            v = [struct.unpack_from('<8f', state, o + 32 + 32 * j) for j in range(4)]
            if all(abs(x[1]) < 3000 and abs(x[2]) < 3000 for x in v): out.append((o, w, v))
    return out

def enc(im, fmt):
    a = np.array(im.convert('RGBA')).astype(np.uint16)
    if fmt == 0: return (((a[..., 3] > 127).astype(np.uint16) << 15) | ((a[..., 0] >> 3) << 10) | ((a[..., 1] >> 3) << 5) | (a[..., 2] >> 3)).astype('<u2')
    if fmt == 1: return (((a[..., 0] >> 3) << 11) | ((a[..., 1] >> 2) << 5) | (a[..., 2] >> 3)).astype('<u2')
    return (((a[..., 3] >> 4) << 12) | ((a[..., 0] >> 4) << 8) | ((a[..., 1] >> 4) << 4) | (a[..., 2] >> 4)).astype('<u2')

def stored(im, fmt, plain):
    e = enc(im, fmt); h, w = e.shape
    if plain: return e.ravel()
    if (w, h) not in _twiddle: _twiddle[(w, h)] = twiddle_index(w, h)
    d = np.zeros(w * h, dtype='<u2'); d[_twiddle[(w, h)].ravel()] = e.ravel(); return d

def find_base(state, rows, pngs):
    seen = set()
    for o, w, v in rows:
        tex, tsp = w[3], w[2]; fmt = (tex >> 27) & 7; plain = (tex >> 26) & 1
        if fmt > 2 or (tex, tsp) in seen: continue
        seen.add((tex, tsp))
        sw, sh = 8 << ((tsp >> 3) & 7), 8 << (tsp & 7)
        for f, im0 in pngs.get((sw, sh), []) + pngs.get((sh, sw), []):
            for im in (im0, im0.transpose(Image.Transpose.TRANSPOSE)):
                if im.size != (sw, sh): continue
                d = stored(im, fmt, plain)
                for start in range(0, len(d) - 24, max(24, len(d) // 12)):
                    seg = d[start:start + 24]
                    if len(set(seg.tolist())) < 6: continue
                    p = state.find(seg.tobytes())
                    if p >= 0: return p - start * 2 - (tex & 0x1fffff) * 8
    return None

def main(path, assets, show_all):
    state = open(path, 'rb').read()
    pngs = {}
    for f in glob.glob(os.path.join(assets, 'dreamcast', 'prs_png', '*.png')) + glob.glob(os.path.join(assets, 'dreamcast', 'png', 'ENGLISH__*.png')):
        im = Image.open(f).convert('RGBA'); pngs.setdefault(im.size, []).append((f, im))
    rows = packets(state)
    base = find_base(state, rows, pngs)
    print('packets', len(rows), 'vram base', None if base is None else hex(base))
    if base is None: return
    cache = {}
    def match(tex, tsp):
        k = (tex, tsp)
        if k in cache: return cache[k]
        a = decode(state, base, tex, tsp); best = None
        if a is not None:
            h, wd = a.shape[:2]
            for f, im in pngs.get((wd, h), []) + pngs.get((h, wd), []):
                for nm, t in (('id', im), ('T', im.transpose(Image.Transpose.TRANSPOSE))):
                    if t.size != (wd, h): continue
                    b = np.array(t).astype(int); m = (a[..., 3] > 127) | (b[..., 3] > 127)
                    e = np.abs(a.astype(int) - b)[..., :3].max(-1)[m].mean() if m.any() else 0
                    sc = float(e + ((a[..., 3] > 127) != (b[..., 3] > 127)).mean() * 100)
                    if best is None or sc < best[0]: best = (round(sc, 2), os.path.basename(f)[:-4] + (':T' if nm == 'T' else ''))
        cache[k] = best; return best
    order = sorted(range(len(rows)), key=lambda i: (rows[i][2][0][3], i))
    last = None
    for i in order:
        o, w, v = rows[i]
        xs = [p[1] for p in v]; ys = [p[2] for p in v]
        m = match(w[3], w[2]); line = (w[3], m, round(min(xs), 1), round(min(ys), 1))
        print(f'z={v[0][3]:.4f} tex={w[3]:08x} at ({min(xs):.1f},{min(ys):.1f}) {round(max(xs) - min(xs))}x{round(max(ys) - min(ys))} -> {m}')

if __name__ == '__main__':
    if len(sys.argv) < 2: raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'local/cache/assets', '--all' in sys.argv)
