"""List Thumb bl/blx call sites of given Android library addresses (ghidra addresses, hex). usage: find_calls.py 34aa0 [...]"""
import struct, sys
so = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\apk115\lib\armeabi\libccrjni.so', 'rb').read()
G = 0x10000
want = {int(a, 16) for a in sys.argv[1:]}
for o in range(0, len(so) - 4, 2):
    h1, h2 = struct.unpack_from('<2H', so, o)
    if (h1 & 0xf800) != 0xf000 or (h2 & 0xc000) != 0xc000: continue
    s = (h1 >> 10) & 1; j1 = (h2 >> 13) & 1; j2 = (h2 >> 11) & 1
    i1 = ~(j1 ^ s) & 1; i2 = ~(j2 ^ s) & 1
    off = (s << 24) | (i1 << 23) | (i2 << 22) | ((h1 & 0x3ff) << 12) | ((h2 & 0x7ff) << 1)
    if s: off -= 1 << 25
    t = o + G + 4 + off
    if (t & ~3 if not (h2 & 0x1000) else t) in want or t in want: print('%x -> %x' % (o + G, t))
