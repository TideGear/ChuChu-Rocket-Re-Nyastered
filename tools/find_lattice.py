import sys, os
GOOD = {0x09, 0x0a, 0x07, 0x3d, 0x3e, 0x3f, 0x40, 0x47, 0x48, 0x49, 0x4a, 0x08, 0x0b, 0x0c}
def scan(path):
    d = open(path, 'rb').read(); hits = []
    for off in range(0, len(d) - 475):
        # row0 mostly walls, row1 col0 wall, odd cols valid cell codes
        if d[off + 1 * 25] not in (0, 1): continue
        r1 = d[off + 25:off + 50]
        if sum(1 for c in range(1, 25, 2) if r1[c] in GOOD) < 10: continue
        r0 = d[off:off + 25]
        if sum(1 for b in r0 if b == 1) < 12 or any(b > 1 for b in r0): continue
        cells = [d[off + (2 * r + 1) * 25 + 2 * c + 1] for r in range(9) for c in range(12)]
        if sum(1 for x in cells if x in GOOD) >= 100: hits.append(off)
    return hits
if __name__ == '__main__':
    for p in sys.argv[1:]:
        h = scan(p); print(os.path.basename(p), len(h), h[:12], 'strides:', sorted({b - a for a, b in zip(h, h[1:])})[:8])
