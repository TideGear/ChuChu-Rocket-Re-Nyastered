"""Export Dreamcast UI textures (the highest-resolution title logo) into the app's sheet format. usage: export_dc_ui.py <dreamcast prs_png dir> <ret_all output dir> [<dreamcast png dir>]   (the optional third directory supplies the English 'PRESS START BUTTON!' prompt, ENGLISH/PRESSSTART)   (derived data, never committed)"""
import os, struct, sys
from PIL import Image
def main(prs_png, out, png=None):
    os.makedirs(out, exist_ok=True)
    for src, name, src_dir in (('TITLE_newtitle0.png', 'dlogo', prs_png), ('ENGLISH__PRESSSTART.png', 'dpress', png)):
        if not src_dir: continue
        p = os.path.join(src_dir, src)
        if name == 'dlogo' and not os.path.exists(p):
            p = os.path.join(src_dir, '.__' + src)
        if not os.path.exists(p): continue
        im = Image.open(p).convert('RGBA'); bb = im.getbbox(); im = im.crop(bb); w, h = im.size           # crop the empty border
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', w, h)); f.write(im.tobytes())
        with open(os.path.join(out, name + '.frames.bin'), 'wb') as f: f.write(struct.pack('<I', 1)); f.write(struct.pack('<9f', 0, 0, 1, 1, 0, 0, 0, 0, 0))
        print(name, src, '%dx%d' % (w, h))
if __name__ == '__main__': main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
