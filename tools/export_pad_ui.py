"""Export iPad HD UI sprites (the largest mobile versions) into the app's sheet format: title prompt, rocket, two-cat decoration, menu button atlas (with its frame table).
usage: export_pad_ui.py <HD pack dir containing ccrpad_png/ and ccrpad/> <ret_all output dir>   (derived data, never committed)"""
import glob, os, re, struct, sys
from PIL import Image
def write(out, name, im, frames):
    im = im.convert('RGBA'); w, h = im.size
    with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', w, h)); f.write(im.tobytes())
    with open(os.path.join(out, name + '.frames.bin'), 'wb') as f:
        f.write(struct.pack('<I', len(frames)))
        for fr in frames: f.write(struct.pack('<9f', *fr))
def main(pack, out):
    os.makedirs(out, exist_ok=True)
    for rec, nxt, name in ((102, None, 'pprompt'), (105, None, 'procket'), (154, None, 'pdeco'), (157, 161, 'pbtn')):
        m = glob.glob(os.path.join(pack, 'ccrpad_png', '*_rec%04d_*.png' % rec))
        if not m: continue
        im = Image.open(m[0])
        if nxt:
            d = open(os.path.join(pack, 'ccrpad', '%04d.bin' % nxt), 'rb').read(); n = struct.unpack_from('<I', d, 0)[0]
            assert len(d) == 4 + 36 * n; frames = [struct.unpack_from('<9f', d, 4 + 36 * i) for i in range(n)]
        else: frames = [(0.0, 0.0, 1.0, 1.0, 0, 0, 0, 0, 0)]
        write(out, name, im, frames); print(name, os.path.basename(m[0]), len(frames), 'frames')
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
