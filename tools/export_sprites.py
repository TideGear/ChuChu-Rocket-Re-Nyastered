"""Export character sprite sheets (pre-rendered 32-view turntables) from the extracted iOS ccrret pack into the simple
atlas format used by the dev viewer: <name>.tex.bin = u32 w, u32 h, RGBA8888 pixels; <name>.frames.bin = u32 n, then n x 9 floats (u0 v0 u1 v1 ...).
usage: export_sprites.py <ccrret pack dir (extracted)> <output dir>"""
import os, struct, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textures as T

# (texture record, frame-table record, name) for iOS v1.1.2 ccrret
SHEETS = [(447, 459, 'cat'), (503, 509, 'mouse'), (522, 529, 'mouse_red'), (484, 490, 'mouse_gold')]

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
    main(sys.argv[1], sys.argv[2])
