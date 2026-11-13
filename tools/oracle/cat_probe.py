import struct, math, sys
sys.path.insert(0, '.')
from ccr_oracle import *
G = 0x10000     # Ghidra image base offset: ghidra address - 0x10000 = file virtual address
import os
o = Oracle(os.environ.get('CCR_ANDROID_SO', r'C:\Dev\ChuChu Rocket\analysis\extracted\apk115\lib\armeabi\libccrjni.so'))
def lit(ga): return o.u32(BASE + ga - G)
def trig_slot_for(sym_addr):
    """pointer-slot address (file vaddr) used by njSin/njCos at file vaddr sym_addr (Thumb: ldr rX,[pc,#k]; add rX,pc; ...)"""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB); a = sym_addr & ~1; code = o.d[a:a + 16]; lit = add = None
    for i in md.disasm(code, a):
        if i.mnemonic.startswith('ldr') and 'pc' in i.op_str and lit is None: lit = ((i.address + 4) & ~3) + int(i.op_str.split('#')[1].rstrip(']'), 0)
        if i.mnemonic == 'add' and i.op_str.endswith('pc') and add is None: add = i.address + 4
    return o.u32(BASE + lit) + add
def init_tables():
    syms = {}
    if os.environ.get('CCR_ANDROID_SO'):                    # other Android builds: resolve the sin/cos table slots from njSin/njCos
        import struct as _s
        d = o.d; shoff, = _s.unpack_from('<I', d, 0x20); shentsize, shnum, shstrndx = _s.unpack_from('<3H', d, 0x2e)
        secs = [_s.unpack_from('<10I', d, shoff + i * shentsize) for i in range(shnum)]; nm = lambda t, off: d[t + off:d.index(bytes([0]), t + off)].decode()
        for sc in secs:
            if nm(secs[shstrndx][4], sc[0]) == '.dynsym':
                link = secs[sc[6]]
                for i in range(sc[5] // 16):
                    a, v, sz, info, oth, x = _s.unpack_from('<IIIBBH', d, sc[4] + 16 * i); n = nm(link[4], a)
                    if n in ('_Z5njSini', '_Z5njCosi'): syms[n] = v
        slots = [trig_slot_for(syms['_Z5njSini']) + G, trig_slot_for(syms['_Z5njCosi']) + G]
    else: slots = [0x797a8, 0x799c0]
    for slot, fn in zip(slots, (math.sin, math.cos)):
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
