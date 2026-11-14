"""Export Android UI sprites (title screen pieces) into the app's sheet format next to the iOS sheets: <name>.tex.bin = u32 w, u32 h, RGBA; <name>.frames.bin = u32 n + n x 9 floats.
Whole-image sheets get one frame covering the image; the logo atlas (record 0042) gets the frame table stored in the pack (record 0049).
usage: export_android_ui.py <android build dir (contains main_png/ and libccrjni/main/)> <ret_all output dir>   (derived data, never committed)"""
import glob, os, struct, sys
from PIL import Image

def write_sheet(out, name, im, frames):
    im = im.convert('RGBA'); w, h = im.size
    with open(os.path.join(out, name + '.tex.bin'), 'wb') as f:
        f.write(struct.pack('<2I', w, h)); f.write(im.tobytes())
    with open(os.path.join(out, name + '.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', len(frames)))
        for fr in frames:
            f.write(struct.pack('<9f', *fr))

def find(root, rec):
    m = glob.glob(os.path.join(root, 'main_png', '*_rec%04d_*.png' % rec))
    return m[0] if m else None

def main(root, out):
    os.makedirs(out, exist_ok=True)
    whole = lambda w, h: [(0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    for rec, name in ((90, 'a0090'), (97, 'a0097'), (100, 'a0100'), (103, 'a0103')):      # title background, "TAP THE SCREEN!" prompt, orbiting rocket, menu background (unverified choice)
        p = find(root, rec)
        if p:
            im = Image.open(p); write_sheet(out, name, im, whole(*im.size)); print(name, os.path.basename(p))
    for rec, nxt, name in ((42, 49, 'a0042'), (113, 115, 'a0113')):          # atlases + the frame table record that follows them (4 + 36 n bytes): logo atlas, menu button bars
        p = find(root, rec)
        if p:
            im = Image.open(p); data = open(os.path.join(root, 'libccrjni', 'main', '%04d.bin' % nxt), 'rb').read(); n = struct.unpack_from('<I', data, 0)[0]
            assert len(data) == 4 + 36 * n, 'unexpected frame table layout'
            frames = [struct.unpack_from('<9f', data, 4 + 36 * i) for i in range(n)]
            write_sheet(out, name, im, frames); print(name, os.path.basename(p), n, 'frames')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
