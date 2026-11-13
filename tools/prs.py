"""Sega PRS (LZ77 variant) decompressor and PVM archive unpacker.
usage: prs.py <file.PRS> <outdir>   -> decompressed blob (<name>.bin) and, for PVMH archives, one .pvr per texture."""
import os, struct, sys

def prs_decompress(src):
    out = bytearray(); p = 0; ctrl = 0; bits = 0
    def getbit():
        nonlocal ctrl, bits, p
        if bits == 0: ctrl = src[p]; p += 1; bits = 8
        b = ctrl & 1; ctrl >>= 1; bits -= 1; return b
    while p < len(src):
        if getbit(): out.append(src[p]); p += 1; continue
        if getbit():
            if p + 1 >= len(src): break
            a, b = src[p], src[p + 1]; p += 2
            off = (a | (b << 8)) >> 3; size = b & 7 if False else (a & 7)
            offv = ((b << 8) | a) >> 3
            if offv == 0: break
            offv -= 0x2000
            if (a & 7) == 0:
                size = src[p] + 1; p += 1
            else: size = (a & 7) + 2
            for _ in range(size): out.append(out[len(out) + offv])
        else:
            size = (getbit() << 1) | getbit(); size += 2
            offv = src[p] - 0x100; p += 1
            for _ in range(size): out.append(out[len(out) + offv])
    return bytes(out)

def unpack_pvm(d):
    """PVMH: u32 magic 'PVMH', u32 size, u16 flags, u16 count, then count x (u16 index, char[28] name, u32 attr?, u32 dim) depending on flags; then PVRT blobs"""
    flags, count = struct.unpack_from('<HH', d, 8)
    esz = 2 + (28 if flags & 1 else 0) + (4 if flags & 2 else 0) + (4 if flags & 4 else 0) + (4 if flags & 8 else 0)
    names = []; o = 12
    for i in range(count):
        e = d[o:o + esz]; q = 2
        nm = ''
        if flags & 1: nm = e[q:q + 28].split(b'\0')[0].decode('latin1'); q += 28
        names.append(nm); o += esz
    # textures: scan for GBIX/PVRT in order
    blobs = []; pos = o
    while True:
        g = d.find(b'GBIX', pos); r = d.find(b'PVRT', pos)
        if r < 0: break
        start = g if (g >= 0 and g < r and r - g <= 16) else r
        size = struct.unpack_from('<I', d, r + 4)[0] + 8
        blobs.append(d[start:r + size]); pos = r + size
    return list(zip(names, blobs))

def main(path, out):
    os.makedirs(out, exist_ok=True)
    raw = open(path, 'rb').read(); d = prs_decompress(raw)
    base = os.path.splitext(os.path.basename(path))[0]
    open(os.path.join(out, base + '.bin'), 'wb').write(d)
    kind = d[:4].decode('latin1')
    n = 0
    if d[:4] == b'PVMH':
        for nm, b in unpack_pvm(d):
            open(os.path.join(out, '%s_%s.pvr' % (base, nm or n)), 'wb').write(b); n += 1
    print(base, len(raw), '->', len(d), kind, n, 'textures')

if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
