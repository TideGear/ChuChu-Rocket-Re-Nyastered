"""Per-language HD 1.0 assets: the language-pack sheets (puzzle HUD strip, pause banner, stage-select / menu / options headers) and the text table of every Latin language pack,
written to <assets>/ret_all/loc_<lang>/ (hd_<name>.tex.bin / .frames.bin, hd_text.tsv). usage: export_hd_locale.py <HD 1.0 app dir> <thin armv7> <ccrpad extracted dir> <ret_all dir>
Language order of the original: 0 en, 1 fr, 2 it, 3 de, 4 es, 5 ja (HD 1.0 has no ja pack)."""
import os, shutil, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LANGS = ['en', 'fr', 'it', 'de', 'es']
LOCALE_SHEETS = {'hd_phud5c': (27, 31), 'hd_pause79': (65, 70), 'hd_ss_hdr': (20, 26), 'hd_mn_deco': (7, 9), 'hd_op_hdr': (14, 16)}   # (texture record, frame record) inside the language pack
def main(app, thin, pack, out, count=885):
    import extract_ios_locale, textures as T
    for lg in LANGS:
        lp = pack + '_' + lg
        if not os.path.isdir(lp) or not os.listdir(lp):
            try: extract_ios_locale.main(thin, app, 'ccrpad', lg, lp)
            except KeyError: print('no pack', lg); continue
        dst = os.path.join(out, 'loc_' + lg); os.makedirs(dst, exist_ok=True)
        ls = {t['rec']: t for t in T.textures(lp)}
        for name, (tx, fr) in LOCALE_SHEETS.items():
            t = ls[tx]; im = T.to_image(t).convert('RGBA')
            with open(os.path.join(dst, name + '.tex.bin'), 'wb') as f: f.write(struct.pack('<2I', t['w'], t['h'])); f.write(im.tobytes())
            shutil.copyfile(os.path.join(lp, '%04d.bin' % fr), os.path.join(dst, name + '.frames.bin'))
        rows = []
        for r in range(965 - count, 1220 - count):
            f = os.path.join(lp, '%04d.bin' % r)
            if os.path.exists(f): rows.append('%d%s%s' % (r + count, chr(9), open(f, 'rb').read().split(bytes(1))[0].decode('latin-1')))
        open(os.path.join(dst, 'hd_text.tsv'), 'wb').write((chr(10).join(rows) + chr(10)).encode('latin-1')); print(lg, len(rows), 'texts')
if __name__ == '__main__': main(*sys.argv[1:5])
