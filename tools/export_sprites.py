"""Export character sprite sheets (pre-rendered 32-view turntables) from the extracted iOS ccrret pack into the simple
atlas format used by the dev viewer: <name>.tex.bin = u32 w, u32 h, RGBA8888 pixels; <name>.frames.bin = u32 n, then n x 9 floats (u0 v0 u1 v1 ...).
usage: export_sprites.py <ccrret pack dir (extracted)> <output dir>"""
import os, struct, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textures as T

# (texture record, frame-table record, name) for iOS v1.1.2 ccrret
SHEETS = [(447, 459, 'cat'), (503, 509, 'mouse'), (522, 529, 'mouse_red'), (484, 490, 'mouse_gold')]

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
