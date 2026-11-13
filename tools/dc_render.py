"""Tiny software renderer for exported Dreamcast OBJ objects (verification only). usage: dc_render.py <obj> <out.png> <tex0.png> [tex1.png ...] [--yaw deg]"""
import sys, math
from PIL import Image
def load(p):
    V = []; T = []; F = []; mat = 0
    for l in open(p):
        k = l.split()
        if not k: continue
        if k[0] == 'v': V.append(tuple(map(float, k[1:4])))
        elif k[0] == 'vt': T.append((float(k[1]), float(k[2])))
        elif k[0] == 'usemtl': mat = int(k[1][3:])
        elif k[0] == 'f': F.append(([int(x.split('/')[0]) - 1 for x in k[1:4]], [int(x.split('/')[1]) - 1 for x in k[1:4]], mat))
    return V, T, F
def main(obj, out, texs, yaw=0.0, size=256):
    V, T, F = load(obj); tex = [Image.open(t).convert('RGBA') for t in texs]
    ca, sa = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    P = [(v[0] * ca + v[2] * sa, v[1], -v[0] * sa + v[2] * ca) for v in V]
    xs = [p[0] for p in P]; ys = [p[1] for p in P]; sc = (size - 16) / max(max(xs) - min(xs), max(ys) - min(ys), 1e-3)
    cx = (max(xs) + min(xs)) / 2; cy = (max(ys) + min(ys)) / 2
    img = Image.new('RGBA', (size, size), (70, 80, 110, 255)); px = img.load(); zb = {}
    S = [(size / 2 + (p[0] - cx) * sc, size / 2 - (p[1] - cy) * sc, p[2]) for p in P]
    for vi, ti, m in F:
        a, b, c = [S[i] for i in vi]; uv = [T[i] for i in ti]; tx = tex[m] if m < len(tex) else tex[0]
        minx = max(int(min(a[0], b[0], c[0])), 0); maxx = min(int(max(a[0], b[0], c[0])) + 1, size - 1)
        miny = max(int(min(a[1], b[1], c[1])), 0); maxy = min(int(max(a[1], b[1], c[1])) + 1, size - 1)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9: continue
        for y in range(miny, maxy + 1):
            for x in range(minx, maxx + 1):
                w0 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
                w1 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den; w2 = 1 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0: continue
                z = w0 * a[2] + w1 * b[2] + w2 * c[2]
                if (x, y) in zb and zb[(x, y)] >= z: continue
                u = (w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0]) % 1.0; v = (w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1]) % 1.0
                r = tx.getpixel((min(int(u * tx.width), tx.width - 1), min(int(v * tx.height), tx.height - 1)))
                if r[3] < 8: continue
                zb[(x, y)] = z; px[x, y] = r
    img.save(out)
if __name__ == '__main__':
    a = sys.argv[1:]; yaw = 0.0
    if '--yaw' in a: i = a.index('--yaw'); yaw = float(a[i + 1]); del a[i:i + 2]
    main(a[0], a[1], a[2:], yaw)
