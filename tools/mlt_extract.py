"""Split an SMLT bank container (Sega sound: DPETC/DP2SOUND.MLT, ENGLISH/CHU2_SE.MLT...) into its sections. Layout (measured): 0x20-byte header
('SMLT', ver, count), then count x 0x20-byte entries: tag(4) 0 offset(4) size(4) ... Sections: SOSB, SMPB (AICA sample data), SMDB (...), etc.
usage: mlt_extract.py <file.MLT> <outdir>"""
import os, struct, sys
def main(path, out):
    d = open(path, 'rb').read(); assert d[:4] == b'SMLT'
    n = struct.unpack_from('<I', d, 8)[0]; os.makedirs(out, exist_ok=True); rows = []
    for i in range(n):
        o = 0x20 + 0x20 * i; tag = d[o:o + 4].decode('latin1'); a, b, c = struct.unpack_from('<III', d, o + 8)
        rows.append((tag, a, b, c, d[o + 20:o + 32].hex()))
    for k, (tag, a, b, c, rest) in enumerate(rows):
        print(tag, hex(a), hex(b), hex(c), rest)
        open(os.path.join(out, '%02d_%s.bin' % (k, tag)), 'wb').write(d[a:a + b])        # offset, size (measured on both banks: sections tile the file)
    return rows, d
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
