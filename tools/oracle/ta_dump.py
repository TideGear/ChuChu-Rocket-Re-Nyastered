#!/usr/bin/env python3
"""Inspect the PowerVR polygon stream in a flyhost FLY_DUMP save state without hand-tuned offsets.

usage:
  ta_dump.py <file.state> info                         list start/end, polygon count, VRAM base and its vote count
  ta_dump.py <file.state> list [--box x0,y0,x1,y1] [--tex hex]
                                                       polygons touching the screen box: header words, face colour, vertex count, bbox, intensity range
  ta_dump.py <file.state> tex <hex tex> <hex tsp> <out.png>   decode one texture from VRAM
  ta_dump.py <file.state> render <out.png> [--box ...] [--tex hex] [--shot file.bmp] [--face 1|header]
                                                       rasterise the selected polygons (perspective-correct UV, texture x clamp(face x base intensity))
                                                       into a 640x480 RGBA image; with --shot, also writes <out>_cmp.png (shot | render over shot | diff) and prints the mean error over covered pixels

Why it exists: the opaque list does not start at a fixed offset (0x253e10 in recent states, earlier states differed), vertices can sit 16 bytes off
the state's 32-byte grid, and the VRAM base differs per run. The list start is found by scanning for a polygon header followed by a plausible vertex;
the VRAM base is voted for by re-encoding the exported models.bin textures (Dreamcast twiddle, 1555/565/4444) and finding them in the state.
Vertex fields (Intensity mode, ctrl 0x808c002a / 0x828c0028): x, y, 1/w, u, v, base intensity, offset intensity. Face colour is header words 4-7 as
floats (A, R, G, B)."""
import argparse, glob, os, struct, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_parse
import dc_match_packets as D

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def plausible_vertex(st, o):
    w = struct.unpack_from('<I', st, o)[0]
    if w >> 29 != 7: return False
    x, y, z = struct.unpack_from('<3f', st, o + 4)
    return -200 < x < 900 and -200 < y < 700 and 0 < z < 100


def find_list(st, lo=0x200000, hi=0x400000):
    """First 16-byte-aligned polygon header (type 4) followed by two plausible vertices; the list runs until 64 consecutive non-parameter words."""
    for o in range(lo, hi, 16):
        w = struct.unpack_from('<I', st, o)[0]
        if w >> 29 == 4 and plausible_vertex(st, o + 32) and plausible_vertex(st, o + 64):
            end = o; junk = 0; p = o
            while p + 32 <= len(st) and junk < 64:
                t = struct.unpack_from('<I', st, p)[0] >> 29
                if t in (4, 5, 7): junk = 0; end = p + 32
                else: junk += 1
                p += 32
            return o, end
    return None, None


def models_textures():
    cands = sorted(glob.glob(os.path.join(ROOT, 'local', '**', 'dreamcast', 'models.bin'), recursive=True), key=os.path.getmtime, reverse=True)
    if not cands: return []
    d = open(cands[0], 'rb').read(); n = struct.unpack('<I', d[4:8])[0]; p = 8; out = []
    for _ in range(n):
        w, h = struct.unpack('<HH', d[p:p + 4]); p += 4
        out.append(Image.frombytes('RGBA', (w, h), d[p:p + w * h * 4])); p += w * h * 4
    return out


def find_vram_base(st, polys):
    texs = models_textures(); votes = {}; seen = set()
    for q in polys:
        tex, tsp = q['tex'], q['tsp']; fmt = (tex >> 27) & 7; plain = (tex >> 26) & 1
        if (tex, tsp) in seen or fmt > 2: continue
        seen.add((tex, tsp)); sw, sh = 8 << ((tsp >> 3) & 7), 8 << (tsp & 7)
        for im0 in texs:
            for im in (im0, im0.transpose(Image.Transpose.TRANSPOSE)):
                if im.size != (sw, sh): continue
                dd = D.stored(im, fmt, plain)
                for start in range(0, len(dd) - 24, max(24, len(dd) // 12)):
                    seg = dd[start:start + 24]
                    if len(set(seg.tolist())) < 6: continue
                    pos = st.find(seg.tobytes())
                    if pos >= 0:
                        b = pos - start * 2 - (tex & 0x1fffff) * 8; votes[b] = votes.get(b, 0) + 1; break
    if not votes: return None, 0
    b, n = max(votes.items(), key=lambda kv: kv[1])
    return b, n


def load(path):
    st = open(path, 'rb').read()
    lo, hi = find_list(st)
    if lo is None: sys.exit('no polygon list found')
    polys = ta_parse.parse(st, lo, hi)
    for p in polys: p['face'] = struct.unpack_from('<4f', st, p['off'] + 16)
    return st, lo, hi, polys


def select(polys, box, tex):
    out = []
    for p in polys:
        vs = [v for s in p['strips'] for v in s]
        if not vs or (tex is not None and p['tex'] != tex): continue
        if box and not any(box[0] <= v[1] <= box[2] and box[1] <= v[2] <= box[3] and 0 < v[3] < 100 for v in vs): continue
        out.append(p)
    return out


def raster(img, tri, tex, face, swap=False, zbuf=None, owner=None, tid=0):
    (x0, y0), (x1, y1), (x2, y2) = [(v[1], v[2]) for v in tri]
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-6: return
    xa, xb = int(max(0, np.floor(min(x0, x1, x2)))), int(min(639, np.ceil(max(x0, x1, x2))))
    ya, yb = int(max(0, np.floor(min(y0, y1, y2)))), int(min(479, np.ceil(max(y0, y1, y2))))
    if xa > xb or ya > yb: return
    X, Y = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
    w0 = ((x1 - X) * (y2 - Y) - (x2 - X) * (y1 - Y)) / area
    w1 = ((x2 - X) * (y0 - Y) - (x0 - X) * (y2 - Y)) / area
    w2 = 1 - w0 - w1
    m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
    if not m.any(): return
    iw = np.array([v[3] for v in tri]); iwp = w0 * iw[0] + w1 * iw[1] + w2 * iw[2]
    u = (w0 * tri[0][4] * iw[0] + w1 * tri[1][4] * iw[1] + w2 * tri[2][4] * iw[2]) / iwp
    vv = (w0 * tri[0][5] * iw[0] + w1 * tri[1][5] * iw[1] + w2 * tri[2][5] * iw[2]) / iwp
    if swap: u, vv = vv, u
    base = w0 * tri[0][6] + w1 * tri[1][6] + w2 * tri[2][6]
    col = np.clip(np.array(face[1:4])[None, None, :] * base[..., None], 0, 1)
    if tex is not None:
        h, w = tex.shape[:2]
        t = tex[np.clip((vv * h).astype(int), 0, h - 1), np.clip((u * w).astype(int), 0, w - 1)].astype(float)
        rgb = t[..., :3] * col; a = t[..., 3]
    else:
        rgb = col * 255; a = np.full(col.shape[:2], 255.0)
    if zbuf is not None:   # depth test on 1/w (larger = nearer), as the PowerVR's default GREATER_EQUAL opaque compare
        zs = zbuf[ya:yb + 1, xa:xb + 1]; m &= iwp >= zs; zs[m] = iwp[m]
    sub = img[ya:yb + 1, xa:xb + 1]
    sub[m, :3] = rgb[m]; sub[m, 3] = a[m]
    if owner is not None: owner[ya:yb + 1, xa:xb + 1][m] = tid


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('state'); ap.add_argument('cmd'); ap.add_argument('args', nargs='*')
    ap.add_argument('--box'); ap.add_argument('--tex'); ap.add_argument('--shot'); ap.add_argument('--face', default='header'); ap.add_argument('--swapuv', action='store_true', help='sample texture with u and v exchanged (mouse/marker textures are stored transposed)'); ap.add_argument('--measure', help='hex texture word: report the error over the pixels it wins')
    a = ap.parse_args()
    box = [float(x) for x in a.box.split(',')] if a.box else None
    tex = int(a.tex, 16) if a.tex else None
    st, lo, hi, polys = load(a.state)
    if a.cmd == 'info':
        b, n = find_vram_base(st, polys)
        print(f'list {lo:#x}..{hi:#x}  polygons {len(polys)}  vram base {b if b is None else hex(b)} ({n} votes)'); return
    if a.cmd == 'list':
        for p in select(polys, box, tex):
            vs = [v for s in p['strips'] for v in s]
            print(f"{p['off']:#x} ctrl {p['ctrl']:08x} isp {p['isp']:08x} tsp {p['tsp']:08x} tex {p['tex']:08x} face {tuple(round(f, 3) for f in p['face'])} "
                  f"n {len(vs)} x {min(v[1] for v in vs):.0f}..{max(v[1] for v in vs):.0f} y {min(v[2] for v in vs):.0f}..{max(v[2] for v in vs):.0f} "
                  f"base {min(v[6] for v in vs):.3f}..{max(v[6] for v in vs):.3f}")
        return
    b, n = find_vram_base(st, polys)
    if b is None: sys.exit('VRAM base not found')
    if a.cmd == 'tex':
        t = D.decode(st, b, int(a.args[0], 16), int(a.args[1], 16)); Image.fromarray(t).save(a.args[2]); print(a.args[2], t.shape); return
    if a.cmd == 'render':
        img = np.zeros((480, 640, 4)); zbuf = np.full((480, 640), -1.0); owner = np.zeros((480, 640), np.int64); cache = {}
        for p in select(polys, box, tex):
            key = (p['tex'], p['tsp'])
            if key not in cache: cache[key] = D.decode(st, b, p['tex'], p['tsp']) if p['ctrl'] & 8 else None
            face = p['face'] if a.face == 'header' else (1.0, 1.0, 1.0, 1.0)
            for s in p['strips']:
                for i in range(len(s) - 2): raster(img, s[i:i + 3], cache[key], face, a.swapuv, zbuf, owner, p['tex'])
        out = a.args[0]; Image.fromarray(img.clip(0, 255).astype(np.uint8)).save(out)
        if a.shot:
            shot = np.asarray(Image.open(a.shot).convert('RGB')).astype(float)
            cov = img[..., 3] > 250
            over = shot.copy(); over[cov] = img[cov, :3]
            diff = np.abs(over - shot).mean(axis=2)
            print(f'covered {int(cov.sum())} px, mean abs error over them {diff[cov].mean() if cov.any() else 0:.2f}')
            if a.measure:   # error only over pixels won (after the depth test) by polygons with this texture
                mt = owner == int(a.measure, 16)
                print(f'texture {a.measure}: {int(mt.sum())} px, mean abs error {diff[mt].mean() if mt.any() else 0:.2f}')
            sheet = np.concatenate([shot, over, np.repeat(np.clip(diff * 4, 0, 255)[..., None], 3, axis=2)], axis=1)
            Image.fromarray(sheet.astype(np.uint8)).save(out.replace('.png', '_cmp.png'))
        print(out); return
    sys.exit('unknown command ' + a.cmd)


if __name__ == '__main__':
    main()
