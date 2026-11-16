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

def write_atlas(root, out, pack, record, frame_record, name, image):
    data = open(os.path.join(root, 'libccrjni', pack, '%04d.bin' % frame_record), 'rb').read()
    count, = struct.unpack_from('<I', data)
    if not count or len(data) != 4 + 36 * count:
        raise ValueError(f'Unexpected frame table for Android {pack}/{record:04d}')
    frames = [struct.unpack_from('<9f', data, 4 + 36 * i) for i in range(count)]
    write_sheet(out, name, image, frames)
    print(name, pack, record, count, 'frames')


def main(root, out):
    os.makedirs(out, exist_ok=True)
    whole = lambda w, h: [(0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    for rec, name in ((90, 'a0090'), (97, 'a0097'), (100, 'a0100'), (134, 'a0134'), (110, 'a0110')):      # title background, "TAP THE SCREEN!" prompt, orbiting rocket, menu background (texture id 0x17 = file 023 = rec 0134), menu decoration (id 0x10 = rec 0110)
        p = find(root, rec)
        if p:
            im = Image.open(p); write_sheet(out, name, im, whole(*im.size)); print(name, os.path.basename(p))
    for rec, nxt, name in ((42, 49, 'a0042'), (113, 115, 'a0113'),
                           (422, 424, 'phone_pause_panel')):
        p = find(root, rec)
        if p:
            with Image.open(p) as image:
                write_atlas(root, out, 'main', rec, nxt, name, image)
    # Both Android builds put 576 base records before the localized resources.
    # The Puzzle HUD uses slots 0x67 and 0x73. The pause overlay uses 0x86.
    localized = ((40, 42, 'puzzle_hud'), (62, 64, 'pause_button'), (89, 93, 'pause_title'))
    import textures
    for locale in ('en', 'fr', 'de', 'es', 'it', 'ja'):
        pack = os.path.join(root, 'libccrjni', locale)
        if not os.path.isfile(os.path.join(pack, 'index.json')):
            continue
        sheets = {t['rec']: t for t in textures.textures(pack)}
        dest = os.path.join(out, 'phone_' + locale)
        os.makedirs(dest, exist_ok=True)
        for rec, frames, name in localized:
            sheet = sheets.get(rec)
            if sheet and sheet['next'] == frames:
                write_atlas(root, dest, locale, rec, frames, name, textures.to_image(sheet))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
