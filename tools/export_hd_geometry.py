"""Copy the HD 1.0 (iPad) frame tables of the playfield images into the app's asset dir, so sprites are drawn at the original iPad size
(geometry from HD 1.0, pixels from the larger retina sheets; docs/ui_art.md). Image id (HD 1.0) -> ccrpad frame-table record, read from
loadResources (0xdcd8) + the pad resource table (*0xeb548). usage: export_hd_geometry.py <extracted HD 1.0 ccrpad pack dir> <ret_all dir>"""
import os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TABLES = {'hd_arrows': 567, 'hd_cursors': 654, 'hd_crowns': 648, 'hd_digits': 651,   # images 0x54, 0x60, 0x5e, 0x5f
          'hd_cat0': 345, 'hd_cat1': 354, 'hd_cat2': 363, 'hd_gold0': 392, 'hd_gold1': 396, 'hd_gold2': 400, 'hd_mouse0': 411, 'hd_mouse1': 415, 'hd_mouse2': 419}   # walk sheets side/back/front: HD images 0x28..0x2a, 0x2f..0x31, 0x33..0x35
SHEETS = {'hd_time': (677, 679), 'hd_bhud65': (661, 664), 'hd_bhud68': (671, 676), 'hd_stagenum': (752, 754), 'hd_frame78': (718, 720), 'hd_font0': (0, 3), 'hd_font1': (24, 32), 'hd_mn_bg': (108, 153), 'hd_mn_bars': (157, 161), 'hd_mn_masc': (166, 171), 'hd_bub9': (852, 855), 'hd_bubtail': (154, 156), 'hd_ss_bg': (250, 295), 'hd_ss_bubble': (300, 302), 'hd_ss_cells': (303, 305), 'hd_ss_tab': (310, 312), 'hd_ss_panel': (328, 333), 'hd_ss_arrows': (172, 174)}  # font0: image 0 = the default Latin font (BHLib_PrintString, non-Japanese), widths = record 874   # 0x65 player panels, 0x68 battle HUD pieces (renderFourBattleHud 0x21038)   # HD 1.0 image 0x69: in-play timer digits (clock2D 0x20e54)
LOCALE_SHEETS = {'hd_phud5c': (27, 31), 'hd_pause79': (65, 70), 'hd_ss_hdr': (20, 26), 'hd_mn_deco': (7, 9)}   # HD 1.0 image 0x5c (puzzle HUD strip/panel), ccrpad_en records 912/916 - 885
def main(pack, out):
    import struct, textures as T
    ts = {t['rec']: t for t in T.textures(pack)}
    for name, (tx, fr) in SHEETS.items():
        t = ts[tx]; im = T.to_image(t).convert('RGBA')
        with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', t['w'], t['h'])); f.write(im.tobytes())
        shutil.copyfile(os.path.join(pack, '%04d.bin' % fr), os.path.join(out, name + '.frames.bin')); print(name, tx, fr)
    shutil.copyfile(os.path.join(pack, '0874.bin'), os.path.join(out, 'hd_font0.widths.bin')); shutil.copyfile(os.path.join(pack, '0876.bin'), os.path.join(out, 'hd_font1.widths.bin'))
    lp = pack + '_en'
    if os.path.isdir(lp):
        ls = {t['rec']: t for t in T.textures(lp)}
        for name, (tx, fr) in LOCALE_SHEETS.items():
            t = ls[tx]; im = T.to_image(t).convert('RGBA')
            with open(os.path.join(out, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', t['w'], t['h'])); f.write(im.tobytes())
            shutil.copyfile(os.path.join(lp, '%04d.bin' % fr), os.path.join(out, name + '.frames.bin')); print(name, 'locale', tx, fr)
    for name, rec in TABLES.items():
        shutil.copyfile(os.path.join(pack, '%04d.bin' % rec), os.path.join(out, name + '.frames.bin')); print(name, rec)
def texts(pack, out, count=885):
    """HD 1.0 English text table (language-pack records, resource id = count + record): id TAB text lines."""
    lp = pack + '_en'; rows = []
    for r in range(965 - count, 1220 - count):
        f = os.path.join(lp, '%04d.bin' % r)
        if os.path.exists(f): rows.append('%d%s%s' % (r + count, chr(9), open(f, 'rb').read().split(bytes([0]))[0].decode('latin-1')))
    open(os.path.join(out, 'hd_text_en.tsv'), 'wb').write((chr(10).join(rows) + chr(10)).encode('latin-1')); print('texts', len(rows))
def textmap(thin, out):
    """Text keys of the puzzle HUD -> resource id, through getActualResourceID's pad table (HD 1.0 *0xeb548): 0x1ab..0x1af = Normal/Hard/Special/Mania/Tutorial (getPuzzleType), 0x1e8 + stage = stage name (FI_GetCommentStrP)."""
    import struct
    from macho import Macho
    m = Macho(thin)
    def rd(a, n):
        for sg in m.segs:
            if sg[1] <= a < sg[1] + sg[2]: o = sg[3] + a - sg[1]; return m.d[o:o + n]
    T = struct.unpack('<1200i', rd(struct.unpack('<I', rd(0xeb548, 4))[0], 4800))
    keys = [k for k in range(1200) if 965 <= T[k] < 1220]   # every key that resolves to a language-pack text
    open(os.path.join(out, 'hd_textmap.tsv'), 'wb').write((chr(10).join('%d%s%d' % (k, chr(9), T[k]) for k in keys) + chr(10)).encode('latin-1')); print('textmap', len(keys))
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2]); texts(sys.argv[1], sys.argv[2])
    if len(sys.argv) > 3: textmap(sys.argv[3], sys.argv[2])
