"""Copy the HD 1.0 (iPad) frame tables of the playfield images into the app's asset dir, so sprites are drawn at the original iPad size
(geometry from HD 1.0, pixels from the larger retina sheets; docs/ui_art.md). Image id (HD 1.0) -> ccrpad frame-table record, read from
loadResources (0xdcd8) + the pad resource table (*0xeb548). usage: export_hd_geometry.py <extracted HD 1.0 ccrpad pack dir> <ret_all dir>"""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TABLES = {'hd_arrows': 567, 'hd_cursors': 654, 'hd_crowns': 648, 'hd_digits': 651,   # images 0x54, 0x60, 0x5e, 0x5f
          'hd_cat0': 345, 'hd_cat1': 354, 'hd_cat2': 363, 'hd_gold0': 392, 'hd_gold1': 396, 'hd_gold2': 400, 'hd_mouse0': 411, 'hd_mouse1': 415, 'hd_mouse2': 419}   # walk sheets side/back/front: HD images 0x28..0x2a, 0x2f..0x31, 0x33..0x35
SHEETS = {'hd_time': (677, 679)}   # HD 1.0 image 0x69: in-play timer digits (clock2D 0x20e54)
def main(pack, out):
    import struct, textures as T
    ts = {t['rec']: t for t in T.textures(pack)}
    for name, (tx, fr) in SHEETS.items():
        t = ts[tx]; im = T.to_image(t).convert('RGBA')
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', t['w'], t['h'])); f.write(im.tobytes())
        shutil.copyfile(os.path.join(pack, '%04d.bin' % fr), os.path.join(out, name + '.frames.bin')); print(name, tx, fr)
    for name, rec in TABLES.items():
        shutil.copyfile(os.path.join(pack, '%04d.bin' % rec), os.path.join(out, name + '.frames.bin')); print(name, rec)
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
