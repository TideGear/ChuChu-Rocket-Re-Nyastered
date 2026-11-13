import struct, math, sys
sys.path.insert(0, '.')
from ccr_oracle import *
G = 0x10000     # Ghidra image base offset: ghidra address - 0x10000 = file virtual address
o = Oracle(r'C:\Dev\ChuChu Rocket\analysis\extracted\apk115\lib\armeabi\libccrjni.so')
def lit(ga): return o.u32(BASE + ga - G)
def init_tables():
    for slot, fn in ((0x797a8, math.sin), (0x799c0, math.cos)):          # njSin / njCos table pointers (Ghidra addresses)
        tbl = o.heap_ptr; o.heap_ptr += 65536 * 4
        o.write(tbl, b''.join(struct.pack('<f', fn(i * 2 * math.pi / 65536)) for i in range(65536)))
        o.write(BASE + slot - G, struct.pack('<I', tbl))
def gcall(ga, *a): return o.call(ga - G, *a)
if __name__ == '__main__':
    init_tables()
    gcall(0x2ed04); gcall(0x2ed30, 0)                                   # GA_ResetGameParamStr, GA_SetGameType(0)
    print('cat speed:', u2f(gcall(0x2ee04)), ' mouse speed:', u2f(gcall(0x2edcc)))
    base = (lit(0x2de50) + 0x2de74 - G) & 0xffffffff                    # FI_GetFieldCollision array (file vaddr)
    print('coll array at file vaddr %#x' % base)
    o.write(BASE + base + 4 * (3 * 12 + 4), struct.pack('<I', 0xdeadbeef))
    pt = o.heap_ptr; o.heap_ptr += 16; o.write(pt, struct.pack('<hh', 4, 3))
    print('FI_GetFieldCollision(4,3) = %#x' % gcall(0x2de1c, pt))
    print('unhandled imports:', o.unhandled)
