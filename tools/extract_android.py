"""Extract resources from the Android ChuChu Rocket packs (res/raw/ccr*.png are disguised BHLib packs).
Resource index tables are embedded in libccrjni*.so as data symbols (ccrphn0, ccrphn0_<lang>)."""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bhunpack

def elf_symbols(d):
    shoff, = struct.unpack_from('<I', d, 0x20); shentsize, shnum, shstrndx = struct.unpack_from('<3H', d, 0x2e)
    secs = [struct.unpack_from('<10I', d, shoff + i * shentsize) for i in range(shnum)]
    syms = {}
    for s in secs:
        if s[1] in (2, 11):  # SYMTAB, DYNSYM
            strsec = secs[s[6]]
            for i in range(s[5] // 16):
                nm, val, size, info, other, shndx = struct.unpack_from('<IIIBBH', d, s[4] + i * 16)
                name = d[strsec[4] + nm: d.index(b'\0', strsec[4] + nm)].decode('latin1')
                if name: syms[name] = (val, size)
    segs = []
    phoff, = struct.unpack_from('<I', d, 0x1c); phentsize, phnum = struct.unpack_from('<2H', d, 0x2a)
    for i in range(phnum):
        t, off, va, pa, fs, ms, fl, al = struct.unpack_from('<8I', d, phoff + i * phentsize)
        if t == 1: segs.append((va, off, fs))
    return syms, segs

def v2o(segs, v):
    for va, off, fs in segs:
        if va <= v < va + fs: return off + v - va
    raise KeyError(hex(v))

def read_table(d, off):
    bs, tb, lb = struct.unpack_from('<3I', d, off)
    recs = [struct.unpack_from('<4I', d, off + 12 + i * 16) for i in range(tb // 16)]
    return bs, lb, recs

def read_locale_table(d, off, size):
    """Locale tables: 4-byte prefix + 16-byte records, no 12-byte header."""
    recs = [struct.unpack_from('<4I', d, off + 4 + i * 16) for i in range((size - 4) // 16)]
    return 0, 0, recs

def dump(table, pack_bytes, outdir):
    bs, lb, recs = table
    os.makedirs(outdir, exist_ok=True); index = []; bad = 0
    for i, r in enumerate(recs):
        o = r[0] & 0x07FFFFFF; comp = bool(r[0] & 0x80000000)
        try:
            if comp:
                data = bhunpack.unpack(pack_bytes[o:o + r[2]], r[1])
                if len(data) != r[1]: raise ValueError('size')
            else:
                data = pack_bytes[o:o + r[1]]
                if len(data) != r[1]: raise ValueError('short')
        except Exception:
            bad += 1; data = b''
        open(os.path.join(outdir, '%04d.bin' % i), 'wb').write(data)
        index.append({'i': i, 'flags': r[0] >> 27, 'offset': o, 'size': r[1], 'packed': r[2], 'compressed': comp})
    json.dump({'bufsize': bs, 'locale_bytes': lb, 'records': index}, open(os.path.join(outdir, 'index.json'), 'w'))
    return len(recs), bad

def try_dump(table, candidates, outdir):
    """Pick the candidate pack file that decodes with the fewest failures."""
    best = None
    for path in candidates:
        pack = open(path, 'rb').read()
        bs, lb, recs = table
        bad = 0
        for r in recs:
            o = r[0] & 0x07FFFFFF; n = r[2] if r[0] & 0x80000000 else r[1]
            if o + n > len(pack): bad += 1; continue
            if r[0] & 0x80000000:
                try:
                    if len(bhunpack.unpack(pack[o:o + n], r[1])) != r[1]: bad += 1
                except Exception: bad += 1
        if best is None or bad < best[0]: best = (bad, path, pack)
    bad, path, pack = best
    n, b = dump(table, pack, outdir)
    return os.path.basename(path), n, b

if __name__ == '__main__':
    apk, out = sys.argv[1], sys.argv[2]
    langs = {'en': 1, 'fr': 2, 'it': 3, 'de': 4, 'es': 5, 'ja': 6}
    raw = os.path.join(apk, 'res', 'raw')
    for lib in ('libccrjni.so', 'libccrjnil.so'):
        d = open(os.path.join(apk, 'lib', 'armeabi', lib), 'rb').read()
        syms, segs = elf_symbols(d)
        main = read_table(d, v2o(segs, syms['ccrphn0'][0]))
        tag = lib.replace('.so', '')
        print(lib, 'main', try_dump(main, [os.path.join(raw, 'ccr0.png'), os.path.join(raw, 'ccr0l.png')], os.path.join(out, tag, 'main')))
        for lg, n in langs.items():
            k = 'ccrphn0_' + lg
            if k in syms:
                t = read_locale_table(d, v2o(segs, syms[k][0]), syms[k][1])
                cands = [os.path.join(raw, 'ccr%d.png' % n), os.path.join(raw, 'ccr%dl.png' % n)]
                try: print(' ', lg, try_dump(t, cands, os.path.join(out, tag, lg)))
                except Exception as e: print(' ', lg, 'ERR', e)
