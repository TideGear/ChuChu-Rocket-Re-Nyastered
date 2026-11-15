"""Thumb-2 disassembly of a range of a thin iOS armv7 Mach-O with literal-pool and BL-name annotations.
usage: armdis.py <thin macho> <functions.txt> <start hex> <end hex>"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from macho import Macho
from capstone import *
from capstone.arm import *
m = Macho(sys.argv[1])
def rd(a, n):
    for s in m.segs:
        if s[1] <= a < s[1] + s[2]: o = s[3] + a - s[1]; return m.d[o:o + n]
names = {}
for l in open(sys.argv[2]):
    p = l.split()
    if len(p) >= 3:
        try: names[int(p[0], 16)] = p[2]
        except ValueError: pass
a, e = int(sys.argv[3], 16), int(sys.argv[4], 16)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True; md.skipdata = True
for i in md.disasm(rd(a, e - a), a):
    note = ''
    if i.mnemonic.startswith('vldr') and 'pc' in i.op_str or (i.mnemonic.startswith('ldr') and 'pc' in i.op_str):
        t = ((i.address + 4) & ~3) + i.operands[-1].mem.disp
        v = rd(t, 4)
        if v: note = '  ; =%#x (%g)' % (struct.unpack('<I', v)[0], struct.unpack('<f', v)[0])
    if i.mnemonic in ('bl', 'blx') and i.operands and i.operands[0].type == ARM_OP_IMM:
        t = i.operands[0].imm; note = '  ; ' + names.get(t, hex(t))
    print('%x: %s %s%s' % (i.address, i.mnemonic, i.op_str, note))
