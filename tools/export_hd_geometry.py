"""Copy the HD 1.0 (iPad) frame tables of the playfield images into the app's asset dir, so sprites are drawn at the original iPad size
(geometry from HD 1.0, pixels from the larger retina sheets; docs/ui_art.md). Image id (HD 1.0) -> ccrpad frame-table record, read from
loadResources (0xdcd8) + the pad resource table (*0xeb548). usage: export_hd_geometry.py <extracted HD 1.0 ccrpad pack dir> <ret_all dir>"""
import os, shutil, sys
TABLES = {'hd_arrows': 567, 'hd_cursors': 654, 'hd_crowns': 648, 'hd_digits': 651}   # images 0x54, 0x60, 0x5e, 0x5f
def main(pack, out):
    for name, rec in TABLES.items():
        shutil.copyfile(os.path.join(pack, '%04d.bin' % rec), os.path.join(out, name + '.frames.bin')); print(name, rec)
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
