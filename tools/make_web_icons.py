"""Make the web app's home-screen icons (icon-192.png, icon-512.png) from the user's own extracted cat sprite (derived art: never committed).
usage: make_web_icons.py <cache assets dir> <web output dir>"""
import os, struct, sys
from PIL import Image
def main(assets, out):
    base = os.path.join(assets, 'ret_all', 'r0447')
    t = open(base + '.tex.bin', 'rb').read(); w, h = struct.unpack_from('<II', t, 0); img = Image.frombytes('RGBA', (w, h), t[8:8 + w * h * 4])
    fr = open(base + '.frames.bin', 'rb').read(); f = struct.unpack_from('<4f', fr, 4)           # frame 0: the cat facing the camera
    box = (int(f[0] * w), int(f[1] * h), int(round(f[2] * w)), int(round(f[3] * h))); cat = img.crop(box)
    for size in (192, 512):
        icon = Image.new('RGBA', (size, size), (16, 16, 32, 255)); c = cat.copy(); c.thumbnail((int(size * 0.8), int(size * 0.8)), Image.LANCZOS)
        icon.alpha_composite(c, ((size - c.width) // 2, (size - c.height) // 2)); icon.convert('RGB').save(os.path.join(out, 'icon-%d.png' % size))
    print('icons written to', out)
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
