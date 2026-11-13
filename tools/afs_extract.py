"""Extract an AFS archive (u32 'AFS\0', u32 count, count x (offset,size) ...) to numbered files; ADX entries get .adx.
usage: afs_extract.py <file.AFS> <outdir>"""
import os, struct, sys
def main(path, out):
    d = open(path, 'rb').read(); assert d[:4] == b'AFS\0'
    n = struct.unpack_from('<I', d, 4)[0]; os.makedirs(out, exist_ok=True)
    names = []
    tbl = struct.unpack_from('<II', d, 8 + 8 * n)                 # optional name table pointer after the entries
    for i in range(n):
        o, s = struct.unpack_from('<II', d, 8 + 8 * i)
        blob = d[o:o + s]; ext = 'adx' if blob[:1] == b'\x80' and blob[4:5] in (b'\x03',) else 'bin'
        open(os.path.join(out, '%04d.%s' % (i, ext)), 'wb').write(blob); names.append((i, o, s, ext))
    print(os.path.basename(path), n, 'entries;', sum(1 for x in names if x[3] == 'adx'), 'ADX')
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
