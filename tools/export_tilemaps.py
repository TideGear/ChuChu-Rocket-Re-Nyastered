"""Assemble the full-screen background images of the iPad (HD) pack from their tile maps (format read from AppData::drawTilemap in the original code):
tile map record = 5 x int32 (columns, rows, tile width, tile height, tile count) then one uint32 per cell: bits 0..27 = tile (frame) index into the atlas frame table, bit 30 = flip X, bit 29 = flip Y.
The atlas is a 4-byte-per-pixel texture stored as an 8-byte (w, h) header record followed by 65,520-byte chunks; its frame table (u0 v0 u1 v1 + 5 floats per frame) is the record after the chunks.
Each frame in the atlas has a 1-pixel padding border around the 128 x 128 tile, which is cropped off.
usage: export_tilemaps.py <pack dir with index.json, e.g. .../ChuChu_Rocket_HD_v1_0/ccrpad> <out dir>   (derived data, never committed)
Writes bg_<maprecord>.png (full resolution RGB) and r<maprecord>.tex.bin/.frames.bin in the app's sheet format."""
import json, os, struct, sys
from PIL import Image

def build(pack, hdr, tab, mp):
    w, h = struct.unpack('<2I', open(os.path.join(pack, '%04d.bin' % hdr), 'rb').read())
    data = b''; j = hdr + 1
    while len(data) < w * h * 4:
        data += open(os.path.join(pack, '%04d.bin' % j), 'rb').read(); j += 1
    atlas = Image.frombytes('RGBA', (w, h), data[:w * h * 4])
    d = open(os.path.join(pack, '%04d.bin' % tab), 'rb').read(); n = struct.unpack_from('<I', d, 0)[0]
    fr = [struct.unpack_from('<4f', d, 4 + 36 * k) for k in range(n)]
    b = open(os.path.join(pack, '%04d.bin' % mp), 'rb').read(); c, r, tw, th, _ = struct.unpack_from('<5i', b, 0)
    cells = struct.unpack_from('<%dI' % (c * r), b, 0x14); out = Image.new('RGB', (c * tw, r * th))
    for k, v in enumerate(cells):
        f = fr[v & 0xfffffff]; x0, y0, x1, y1 = f[0] * w, f[1] * h, f[2] * w, f[3] * h
        px, py = ((x1 - x0) - tw) / 2.0, ((y1 - y0) - th) / 2.0                       # padding on each side
        tile = atlas.crop((round(x0 + px), round(y0 + py), round(x0 + px) + tw, round(y0 + py) + th)).convert('RGB')
        if v & 0x40000000: tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
        if v & 0x20000000: tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
        out.paste(tile, ((k % c) * tw, (k // c) * th))
    return out

def main(pack, out):
    idx = json.load(open(os.path.join(pack, 'index.json')))['records']; os.makedirs(out, exist_ok=True)
    used = set()
    for i, rec in enumerate(idx):
        if rec['size'] < 0x18: continue
        b = open(os.path.join(pack, '%04d.bin' % i), 'rb').read()
        c, r, tw, th, u = struct.unpack_from('<5i', b, 0)
        if not (1 <= c <= 200 and 1 <= r <= 200 and tw >= 64 and th >= 64 and len(b) == 0x14 + c * r * 4): continue
        tab = next((t for t in range(1, i) if idx[t]['size'] == 4 + 36 * u and t not in used), None)     # frame table with the tile count: tile maps and tile sets appear in the same order
        if tab is not None: used.add(tab)
        hdr = next((t for t in range(tab - 1, 0, -1) if idx[t]['size'] == 8), None) if tab else None
        if tab is None or hdr is None: continue
        im = build(pack, hdr, tab, i); im.save(os.path.join(out, 'bg_%04d.png' % i))
        with open(os.path.join(out, 'bg%04d.tex.bin' % i), 'wb') as f: f.write(struct.pack('<2I', *im.size)); f.write(im.convert('RGBA').tobytes())
        with open(os.path.join(out, 'bg%04d.frames.bin' % i), 'wb') as f: f.write(struct.pack('<I', 1)); f.write(struct.pack('<9f', 0, 0, 1, 1, 0, 0, 0, 0, 0))
        print('map record', i, '%dx%d tiles of %dx%d' % (c, r, tw, th), '->', im.size)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
