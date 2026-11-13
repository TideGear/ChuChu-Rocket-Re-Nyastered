import struct, os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bhunpack

def macho_symbols(d):
    magic, cpu, sub, ft, ncmds, szcmds, flags = struct.unpack('<7I', d[:28])
    p = 28; segs = []; sym = None
    for _ in range(ncmds):
        cmd, sz = struct.unpack('<2I', d[p:p + 8])
        if cmd == 1:
            vmaddr, vmsize, fileoff, filesize = struct.unpack('<4I', d[p + 24:p + 40])
            segs.append((vmaddr, vmsize, fileoff))
        elif cmd == 2:
            sym = struct.unpack('<4I', d[p + 8:p + 24])
        p += sz
    symoff, nsyms, stroff, _ = sym
    out = {}
    for i in range(nsyms):
        strx, typ, sect, desc, value = struct.unpack('<IBBHI', d[symoff + i * 12:symoff + i * 12 + 12])
        nm = d[stroff + strx: d.index(b'\0', stroff + strx)].decode('latin1')
        out[nm] = value
    def foff(v):
        for vm, vs, fo in segs:
            if vm <= v < vm + vs: return fo + v - vm
    return out, foff

def extract(exe_path, app_dir, pack, outdir):
    d = open(exe_path, 'rb').read()
    syms, foff = macho_symbols(d)
    key = '_%s0' % pack
    if key not in syms: return None
    off = foff(syms[key])
    bs, tb, lb = struct.unpack_from('<3I', d, off)
    recs = [struct.unpack_from('<4I', d, off + 12 + i * 16) for i in range(tb // 16)]
    f = open(os.path.join(app_dir, pack), 'rb').read()
    os.makedirs(outdir, exist_ok=True)
    index = []; bad = 0
    for i, r in enumerate(recs):
        o = r[0] & 0x07FFFFFF; comp = bool(r[0] & 0x80000000)
        try:
            if comp:
                data = bhunpack.unpack(f[o:o + r[2]], r[1])
                if len(data) != r[1]: raise ValueError('size')
            else:
                data = f[o:o + r[1]]
                if len(data) != r[1]: raise ValueError('short')
        except Exception as e:
            bad += 1; data = b''
        open(os.path.join(outdir, '%04d.bin' % i), 'wb').write(data)
        index.append({'i': i, 'flags': r[0] >> 27, 'offset': o, 'size': r[1], 'packed': r[2], 'compressed': comp})
    json.dump({'table_file_offset': off, 'bufsize': bs, 'locale_bytes': lb, 'records': index}, open(os.path.join(outdir, 'index.json'), 'w'))
    return len(recs), bad

if __name__ == '__main__':
    root = r'c:\Dev\ChuChu Rocket\analysis'
    jobs = [('ios_v112', ['ccrphn', 'ccrret']), ('ios_hd10', ['ccrphn', 'ccrpad']), ('ios_102', ['ccrphn']), ('ios_v11os30', ['ccrphn', 'ccrret'])]
    for build, packs in jobs:
        for pack in packs:
            r = extract(os.path.join(root, 'thin', 'CCR_' + build), os.path.join(root, 'extracted', build, 'Payload', 'CCR.app'), pack,
                        os.path.join(root, 'assets', build, pack))
            print(build, pack, r)
