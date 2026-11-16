"""Export character sprite sheets (pre-rendered 32-view turntables) from the extracted iOS ccrret pack into the simple
atlas format used by the dev viewer: <name>.tex.bin = u32 w, u32 h, RGBA8888 pixels; <name>.frames.bin = u32 n, then n x 9 floats (u0 v0 u1 v1 ...).
usage: export_sprites.py <ccrret pack dir (extracted)> <output dir>"""
import os, struct, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textures as T

# (texture record, frame-table record, name) for iOS v1.1.2 ccrret
SHEETS = [(447, 459, 'cat'), (503, 509, 'mouse'), (522, 529, 'mouse_red'), (484, 490, 'mouse_gold')]
PLAYFIELD_SHEETS = (23, 420, 429, 438, 447, 472, 476, 480, 484, 491, 495,
                    499, 503, 645, 651, 663, 675, 687, 726, 729, 732, 749)
BASE_PACKS = {
    'retina_11': ((22, 453, 462, 471, 480, 505, 509, 513, 517, 524, 528,
                   532, 536, 678, 684, 696, 708, 720, 759, 762, 765, 789), 1001),
    'ipad_hd10': ((24, 337, 346, 355, 364, 389, 393, 397, 401, 408, 412,
                   416, 420, 565, 571, 583, 595, 607, 646, 649, 652, 677), 872),
    'android_phone': ((23, 199, 202, 205, 208, 220, 223, 226, 229, 232, 235,
                       238, 241, 331, 337, 342, 347, 352, 370, 373, 376, 391), 528),
    'iphone_102': ((22, 265, 269, 273, 277, 291, 294, 297, 300, 304, 307,
                     310, 313, 411, 417, 422, 427, 432, 450, 453, 456, 477), 633),
    'iphone_10': ((24, 179, 183, 187, 191, 206, 209, 212, 215, 219, 222,
                    225, 228, 327, 333, 338, 343, 348, 366, 369, 372, 393), 551),
}

def export_base(pack, out, layout):
    if layout == 'retina_112':
        return export_all(pack, out)
    records, atlas = BASE_PACKS[layout]
    textures = {t['rec']: t for t in T.textures(pack)}
    os.makedirs(out, exist_ok=True)
    for original, target in zip(records, PLAYFIELD_SHEETS):
        t = textures[original]
        name = os.path.join(out, 'r%04d' % target)
        im = T.to_image(t).convert('RGBA')
        with open(name + '.tex.bin', 'wb') as f:
            f.write(struct.pack('<2I', t['w'], t['h']))
            f.write(im.tobytes())
        with open(os.path.join(pack, '%04d.bin' % t['next']), 'rb') as source:
            frames = source.read()
        with open(name + '.frames.bin', 'wb') as f:
            f.write(frames)
    for record, suffix in ((atlas, 'tex'), (atlas + 1, 'frames')):
        with open(os.path.join(pack, '%04d.bin' % record), 'rb') as source:
            data = source.read()
        with open(os.path.join(out, 'r0930.' + suffix + '.bin'), 'wb') as f:
            f.write(data)
    return layout

def export_all(pack, out):
    """every texture of the pack as r<rec>.tex.bin + r<rec>.frames.bin (frame table = the record after the pixel data, when it has the 4+36n layout)"""
    os.makedirs(out, exist_ok=True)
    n = 0
    for t in T.textures(pack):
        im = T.to_image(t).convert('RGBA'); name = 'r%04d' % t['rec']
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', t['w'], t['h'])); f.write(im.tobytes())
        fp = os.path.join(pack, '%04d.bin' % t['next'])
        if os.path.exists(fp):
            data = open(fp, 'rb').read()
            if len(data) >= 4 and 4 + 36 * struct.unpack('<I', data[:4])[0] == len(data):
                open(os.path.join(out, name + '.frames.bin'), 'wb').write(data)
        n += 1
    for a, b in (('0930', 'r0930.tex'), ('0931', 'r0930.frames')):          # iOS 1.1.2 tile atlas (RGBA8888, single record) + its frame table
        src = os.path.join(pack, a + '.bin')
        if os.path.exists(src): open(os.path.join(out, b + '.bin'), 'wb').write(open(src, 'rb').read())
    print(n, 'textures exported')

def main(pack, out):
    os.makedirs(out, exist_ok=True)
    ts = {t['rec']: t for t in T.textures(pack)}
    for rec, tab, name in SHEETS:
        t = ts[rec]; im = T.to_image(t).convert('RGBA')
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f:
            f.write(struct.pack('<2I', t['w'], t['h'])); f.write(im.tobytes())
        data = open(os.path.join(pack, '%04d.bin' % tab), 'rb').read()
        with open(os.path.join(out, name + '.frames.bin'), 'wb') as f:
            f.write(data)
        print(name, t['w'], t['h'], 'frames', struct.unpack('<I', data[:4])[0])

if __name__ == '__main__':
    if len(sys.argv) > 3 and sys.argv[3] == 'all': export_all(sys.argv[1], sys.argv[2])
    else: main(sys.argv[1], sys.argv[2])
