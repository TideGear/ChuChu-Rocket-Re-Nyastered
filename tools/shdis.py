"""SH-4 disassembly of a range of Dreamcast 1ST_READ.BIN with literal-pool loads resolved. usage: shdis.py <start> <end> (virtual addresses, 0x8c010000 base)"""
import sys, struct, os
from capstone import *
d = open(os.path.join(os.path.dirname(__file__), '../local/cache/assets/dreamcast/files/1ST_READ.BIN'), 'rb').read()
B = 0x8c010000
def u32(a): return struct.unpack_from('<I', d, a - B)[0]
def u16(a): return struct.unpack_from('<H', d, a - B)[0]
md = Cs(CS_ARCH_SH, CS_MODE_SH4 | CS_MODE_LITTLE_ENDIAN | CS_MODE_SHFPU)
a, b = int(sys.argv[1], 16), int(sys.argv[2], 16)
for i in md.disasm(d[a - B:b - B], a):
    n = ''
    op = u16(i.address)
    if (op & 0xf000) == 0xd000: t = ((i.address + 4) & ~3) + (op & 0xff) * 4; n = '  ; =%#x' % u32(t)
    elif (op & 0xf000) == 0x9000: t = i.address + 4 + (op & 0xff) * 2; n = '  ; =%#x' % u16(t)
    print('%08x  %-8s %s%s' % (i.address, i.mnemonic, i.op_str, n))
