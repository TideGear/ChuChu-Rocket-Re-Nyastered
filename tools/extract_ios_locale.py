"""Extract the iOS per-language packs (ccrret_<lang>, ccrphn_<lang>): their index tables are the Mach-O symbols _<pack>0_<lang> (4-byte prefix + 16-byte records, as the Android locale tables).
Resource ids past the main pack's record count address these records (id - main count), which is how the HUD images with text (pause, timer frames...) are reached.
usage: extract_ios_locale.py <thin exe> <app dir> <pack> <lang> <out dir>   (derived data, never committed)"""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bhunpack, extract_packs as E
def main(exe, app, pack, lang, out):
    d = open(exe, 'rb').read(); syms, foff = E.macho_symbols(d)
    key = '_%s0_%s' % (pack, lang); off = foff(syms[key])
    ends = sorted(v for v in syms.values() if v > syms[key]); size = ends[0] - syms[key]
    recs = [struct.unpack_from('<4I', d, off + 4 + i * 16) for i in range((size - 4) // 16)]
    f = open(os.path.join(app, '%s_%s' % (pack, lang)), 'rb').read(); os.makedirs(out, exist_ok=True); index = []; bad = 0
    for i, r in enumerate(recs):
        o = r[0] & 0x07FFFFFF; comp = bool(r[0] & 0x80000000)
        try:
            data = bhunpack.unpack(f[o:o + r[2]], r[1]) if comp else f[o:o + r[1]]
            if len(data) != r[1]: raise ValueError
        except Exception: bad += 1; data = b''
        open(os.path.join(out, '%04d.bin' % i), 'wb').write(data)
        index.append({'i': i, 'flags': r[0] >> 27, 'offset': o, 'size': r[1], 'packed': r[2], 'compressed': comp})
    json.dump({'records': index}, open(os.path.join(out, 'index.json'), 'w'))
    print(key, len(recs), 'records,', bad, 'bad')
if __name__ == '__main__': main(*sys.argv[1:6])
