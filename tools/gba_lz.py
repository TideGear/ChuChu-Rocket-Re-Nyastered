"""GBA BIOS LZ77 (type 0x10) scanner/decompressor."""
import struct, sys

def lz77(rom, off, maxout=0x80000):
    if rom[off] != 0x10: return None
    size = rom[off + 1] | rom[off + 2] << 8 | rom[off + 3] << 16
    if size == 0 or size > maxout: return None
    out = bytearray(); p = off + 4
    try:
        while len(out) < size:
            flags = rom[p]; p += 1
            for bit in range(8):
                if len(out) >= size: break
                if flags & (0x80 >> bit):
                    b0, b1 = rom[p], rom[p + 1]; p += 2
                    n = (b0 >> 4) + 3; disp = ((b0 & 15) << 8 | b1) + 1
                    if disp > len(out): return None
                    for _ in range(n):
                        out.append(out[-disp])
                else:
                    out.append(rom[p]); p += 1
    except IndexError:
        return None
    return bytes(out[:size]), p - off

def scan(rom, minsize=64):
    res = []; off = 0
    while off < len(rom) - 8:
        if rom[off] == 0x10 and off % 4 == 0:
            r = lz77(rom, off)
            if r and len(r[0]) >= minsize:
                res.append((off, len(r[0]), r[1]))
        off += 4
    return res

if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read()
    blocks = scan(rom)
    print(len(blocks), 'candidate LZ77 blocks')
    big = sorted(blocks, key=lambda b: -b[1])[:15]
    for b in big: print('  off %#x unpacked %d packed %d' % b)
