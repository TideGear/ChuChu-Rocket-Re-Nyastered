"""Very small GBA frame renderer for debugging the harness (mode 0 text backgrounds + sprites, no blending/windows/affine)."""
import struct
from PIL import Image

def render(g):
    r16 = g.r16; uc = g.uc
    IO = 0x04000000
    dispcnt = r16(IO)
    pal = [r16(0x05000000 + 2 * i) for i in range(512)]
    def rgb(c): return ((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, ((c >> 10) & 31) * 255 // 31)
    vram = bytes(uc.mem_read(0x06000000, 0x18000)); img = Image.new('RGB', (240, 160), rgb(pal[0])); px = img.load()
    mode = dispcnt & 7
    if mode in (3, 4, 5):
        for y in range(160):
            for x in range(240):
                if mode == 3: px[x, y] = rgb(struct.unpack_from('<H', vram, (y * 240 + x) * 2)[0])
                elif mode == 4: px[x, y] = rgb(pal[vram[(y * 240 + x) + (0xA000 if dispcnt & 0x10 else 0)]])
        return img
    layers = []
    for bg in range(4):
        if not dispcnt & (0x100 << bg): continue
        cnt = r16(IO + 8 + 2 * bg); prio = cnt & 3; cb = ((cnt >> 2) & 3) * 0x4000; c256 = bool(cnt & 0x80); sb = ((cnt >> 8) & 31) * 0x800; size = (cnt >> 14) & 3
        hs = r16(IO + 0x10 + 4 * bg) & 0x1ff; vs = r16(IO + 0x12 + 4 * bg) & 0x1ff
        layers.append((prio, bg, cb, c256, sb, size, hs, vs))
    for prio, bg, cb, c256, sb, size, hs, vs in sorted(layers, key=lambda l: (-l[0], -l[1])):
        w = 256 if size in (0, 2) else 512; h = 256 if size in (0, 1) else 512
        for y in range(160):
            for x in range(240):
                X = (x + hs) % w; Y = (y + vs) % h; blk = (X // 256) + (Y // 256) * (2 if w == 512 else 1) if size else 0
                me = sb + blk * 0x800 + (((Y % 256) // 8) * 32 + ((X % 256) // 8)) * 2
                if me + 2 > len(vram): continue
                e = struct.unpack_from('<H', vram, me)[0]; tile = e & 0x3ff; hf = e & 0x400; vf = e & 0x800; pb = (e >> 12) & 15
                tx = (X % 8); ty = (Y % 8); tx = 7 - tx if hf else tx; ty = 7 - ty if vf else ty
                if c256:
                    o = cb + tile * 64 + ty * 8 + tx; idx = vram[o] if o < len(vram) else 0
                    if idx: px[x, y] = rgb(pal[idx])
                else:
                    o = cb + tile * 32 + ty * 4 + tx // 2
                    if o >= len(vram): continue
                    v = vram[o]; idx = (v >> 4) if tx & 1 else (v & 15)
                    if idx: px[x, y] = rgb(pal[pb * 16 + idx])
    if dispcnt & 0x1000:
        oam = bytes(uc.mem_read(0x07000000, 0x400)); obj_tiles_base = 0x10000
        for i in range(127, -1, -1):
            a0, a1, a2 = struct.unpack_from('<HHH', oam, i * 8)
            if (a0 >> 8) & 3 in (2, 3): continue
            shape = (a0 >> 14) & 3; sz = (a1 >> 14) & 3
            dims = {0: [(8, 8), (16, 16), (32, 32), (64, 64)], 1: [(16, 8), (32, 8), (32, 16), (64, 32)], 2: [(8, 16), (8, 32), (16, 32), (32, 64)]}.get(shape)
            if not dims: continue
            sw, sh = dims[sz]; y0 = a0 & 255; x0 = a1 & 511; x0 -= 512 if x0 >= 240 else 0; y0 -= 256 if y0 >= 160 else 0
            c256 = bool(a0 & 0x2000); tile = a2 & 0x3ff; pb = (a2 >> 12) & 15; hf = a1 & 0x1000; vf = a1 & 0x2000; onedim = bool(dispcnt & 0x40)
            for yy in range(sh):
                for xx in range(sw):
                    sx = (sw - 1 - xx) if hf else xx; sy = (sh - 1 - yy) if vf else yy
                    tx, ty = sx // 8, sy // 8
                    t = tile + (ty * (sw // 8) + tx) * (2 if c256 else 1) if onedim else tile + ty * 32 + tx * (2 if c256 else 1)
                    o = obj_tiles_base + t * 32 + (sy % 8) * (8 if c256 else 4) + ((sx % 8) if c256 else (sx % 8) // 2)
                    if c256: o = obj_tiles_base + t * 32 + (sy % 8) * 8 + (sx % 8)
                    if o >= len(vram) + 0x8000: continue
                    b = bytes(uc.mem_read(0x06000000 + o, 1))[0] if o < 0x18000 else 0
                    idx = b if c256 else ((b >> 4) if sx & 1 else (b & 15))
                    X, Y = x0 + xx, y0 + yy
                    if idx and 0 <= X < 240 and 0 <= Y < 160: px[X, Y] = rgb(pal[256 + (idx if c256 else pb * 16 + idx)])
    return img

if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, '.')
    from gba_oracle import GBA
    g = GBA(sys.argv[1]); frames = int(sys.argv[2]); keyscript = {}
    for part in (sys.argv[4].split(',') if len(sys.argv) > 4 and sys.argv[4] else []):          # "frame:KEYS" e.g. 100:A
        f, k = part.split(':'); keyscript[int(f)] = k
    kmap = {'A': 1, 'B': 2, 'S': 4, 'T': 8, 'R': 16, 'L': 32, 'U': 64, 'D': 128, 'r': 256, 'l': 512}
    keys = 0; hold = 0
    for f in range(frames):
        if f in keyscript: keys = sum(kmap[c] for c in keyscript[f] if c in kmap); hold = 8
        elif hold: hold -= 1
        else: keys = 0
        g.run_frames(1, keys)
        if str(f + 1) in os.environ.get('SNAPS', '').split(','): render(g).resize((480, 320), Image.NEAREST).save(sys.argv[3].replace('.png', '_%d.png' % (f + 1)))
    render(g).resize((480, 320), Image.NEAREST).save(sys.argv[3])
    print('frame', g.frame, 'pc', hex(g.pc), 'DISPCNT', hex(g.r16(0x04000000)))
