#!/usr/bin/env python3
"""Export a Flycast state's 2D screen as a layout: [{png, transposed, x, y, w, h}] in draw order.

usage: dc_export_layout.py <out.json> <state> [<state> ...]   (one JSON object: {state file stem: [quads]})

Uses dc_match_packets to resolve each 2D packet to a disc PNG (score < 1). The live list ends where the stale list of the previous screen begins: the first packet that is a
full-screen 512 x 512 menu background at (0,0) after at least one packet. Packets are ordered by depth (1/w ascending), ties by submission order. Positions are the quad's
top-left and size in 640 x 480 screen pixels; the layout contains no image data."""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_match_packets as m
from PIL import Image

def layout(path, assets='local/cache/assets'):
    state = open(path, 'rb').read()
    pngs = {}
    for f in glob.glob(os.path.join(assets, 'dreamcast', 'prs_png', '*.png')) + glob.glob(os.path.join(assets, 'dreamcast', 'png', 'ENGLISH__*.png')):
        im = Image.open(f).convert('RGBA'); pngs.setdefault(im.size, []).append((f, im))
    rows = [r for r in m.packets(state) if r[0] >= 0x19b0000]
    base = m.find_base(state, rows, pngs)
    if base is None: return []
    live = []
    for o, w, v in rows:
        xs = [p[1] for p in v]; ys = [p[2] for p in v]
        if live and min(xs) == 0 and min(ys) == 0 and round(max(xs) - min(xs)) == 512 and round(max(ys) - min(ys)) == 512: break
        live.append((o, w, v))
    out = []
    T = Image.Transpose.TRANSPOSE
    for o, w, v in sorted(live, key=lambda r: (r[2][0][3], r[0])):
        a = m.decode(state, base, w[3], w[2])
        if a is None: continue
        xs = [p[1] for p in v]; ys = [p[2] for p in v]
        wd, ht = a.shape[1], a.shape[0]; best = None
        for f, im in pngs.get((wd, ht), []) + pngs.get((ht, wd), []):
            for tr, t in ((0, im), (1, im.transpose(T))):
                if t.size != (wd, ht): continue
                import numpy as np
                b = np.array(t).astype(int); msk = (a[..., 3] > 127) | (b[..., 3] > 127)
                e = np.abs(a.astype(int) - b)[..., :3].max(-1)[msk].mean() if msk.any() else 0
                sc = float(e + ((a[..., 3] > 127) != (b[..., 3] > 127)).mean() * 100)
                if best is None or sc < best[0]: best = (sc, os.path.basename(f)[:-4], tr)
        if best and best[0] < 1.0:
            out.append({'png': best[1], 'transposed': best[2], 'x': round(min(xs), 1), 'y': round(min(ys), 1), 'w': round(max(xs) - min(xs)), 'h': round(max(ys) - min(ys))})
    return out

if __name__ == '__main__':
    if len(sys.argv) < 3: raise SystemExit(__doc__)
    result = {os.path.basename(p).split('.')[0]: layout(p) for p in sys.argv[2:]}
    with open(sys.argv[1], 'w', encoding='utf-8', newline='\n') as f: json.dump(result, f, indent=1)
    print({k: len(v) for k, v in result.items()})
