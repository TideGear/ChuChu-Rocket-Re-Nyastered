#!/usr/bin/env python3
"""Per-pixel error heatmap between a Flycast reference frame and a port frame.

usage: diff_heatmap.py <reference.bmp> <port.bmp> <out.png> [--crop x0,y0,x1,y1]

Writes a side-by-side sheet: reference | port | heatmap (black = identical, blue = 1-8 levels, then yellow, red and white
for large errors; a +-1 level difference is drawn dark blue so rounding residue is distinguishable from real misses).
Prints the full-frame mean RGB error, the count of pixels above 1 level, and the mean error of an 8 x 8 grid."""
import sys
import numpy as np
from PIL import Image


def main():
    ref_path, port_path, out_path = sys.argv[1:4]
    crop = None
    if '--crop' in sys.argv:
        crop = tuple(int(v) for v in sys.argv[sys.argv.index('--crop') + 1].split(','))
    ref = Image.open(ref_path).convert('RGB')
    port = Image.open(port_path).convert('RGB')
    if port.size != ref.size:
        port = port.resize(ref.size, Image.BILINEAR)
    if crop:
        ref, port = ref.crop(crop), port.crop(crop)
    r = np.asarray(ref).astype(int)
    p = np.asarray(port).astype(int)
    err = np.abs(r - p).max(2)
    heat = np.zeros(err.shape + (3,), np.uint8)
    heat[err == 1] = (0, 0, 90)
    heat[(err > 1) & (err <= 8)] = (0, 90, 255)
    heat[(err > 8) & (err <= 32)] = (255, 220, 0)
    heat[(err > 32) & (err <= 96)] = (255, 60, 0)
    heat[err > 96] = (255, 255, 255)
    w, h = ref.size
    sheet = Image.new('RGB', (w * 3, h))
    sheet.paste(ref, (0, 0))
    sheet.paste(port, (w, 0))
    sheet.paste(Image.fromarray(heat), (2 * w, 0))
    sheet.save(out_path)
    mean = np.abs(r - p).mean()
    print('mean RGB error %.5f, pixels >1 level: %d of %d' % (mean, int((err > 1).sum()), err.size))
    gh, gw = max(1, h // 8), max(1, w // 8)
    for y in range(0, h, gh):
        print(' '.join('%5.1f' % np.abs(r - p)[y:y + gh, x:x + gw].mean() for x in range(0, w, gw)))


if __name__ == '__main__':
    main()
