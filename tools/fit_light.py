"""Fits the light of the 3D characters (CCR_LIGHT=lx,ly,lz,amb,diff) to the mobile cat turntable sprites (local/shots/cat_frames.png: 8 x 4 frames of 100 px; frames 0 / 8 / 16 / 24 are the front, side, back, other side
views at pitch ~10 degrees). Renders the base-pose cat with `ccr <assets> models` (CCR_LIGHTFIT=1) and compares luminance inside the common silhouette.
usage: fit_light.py <ccr.exe> <assets>"""
import itertools, os, subprocess, sys
import numpy as np
from PIL import Image
exe, assets = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
sheet = Image.open('local/shots/cat_frames.png').convert('RGB'); BG = np.array([35, 35, 70])
def cell(i): return sheet.crop(((i % 8) * 100, (i // 8) * 100, (i % 8) * 100 + 100, (i // 8) * 100 + 100))
def mask_of(im, bg, thr=40): a = np.asarray(im).astype(float); return np.abs(a - np.array(bg)).sum(axis=2) > thr
def norm(im, bg):
    m = mask_of(im, bg); ys, xs = np.where(m)
    box = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)).resize((48, 64), Image.BILINEAR)
    return np.asarray(box).astype(float).mean(axis=2) / 255.0, mask_of(box, bg)
sprites = [norm(cell(i), BG) for i in (0, 8, 16, 24)]
def render(light):
    env = dict(os.environ, CCR_LIGHT=','.join(map(str, light)), CCR_LIGHTFIT='1', CCR_SHOT='local/lf.bmp', CCR_TICKS='3')
    subprocess.run([exe, assets, 'models'], env=env, capture_output=True)
    im = Image.open('local/lf.bmp').convert('RGB'); out = []
    for i in range(4): out.append(norm(im.crop((130 + 250 * i - 120, 400 - 330, 130 + 250 * i + 120, 400 + 150)), (70, 80, 110)))
    return out
def score(light, swap):
    views = render(light); order = (0, 1, 2, 3) if not swap else (0, 3, 2, 1); tot = 0; n = 0
    for k, (sp, sm) in enumerate(sprites):
        v, vm = views[order[k]]; common = sm & vm
        if common.sum() < 50: tot += 1; n += 1; continue
        tot += np.abs(sp[common] - v[common]).mean(); n += 1
    return tot / n
best = None
cands = [(lx, ly, lz, amb, diff) for lx in (-0.6, 0.0, 0.6) for ly in (0.2, 0.7) for lz in (0.5, 0.9) for amb in (0.35, 0.5, 0.65) for diff in (0.5, 0.8)]
if os.environ.get('FINE'):   # second pass around the coarse best (0.6, 0.2, 0.5, 0.65, 0.8)
    cands = [(lx, ly, lz, amb, diff) for lx in (0.4, 0.6, 0.8) for ly in (0.1, 0.2, 0.4) for lz in (0.4, 0.5, 0.7) for amb in (0.6, 0.65, 0.75) for diff in (0.8, 1.0, 1.2)]
for swap in ((False,) if os.environ.get('FINE') else (False, True)):
    for c in cands:
        sc = score(c, swap)
        if best is None or sc < best[0]: best = (sc, c, swap); print('best so far', best, flush=True)
print('BEST', best)
