"""Thumb disassembly of a range of an ELF .so (vaddr = file offset + 0x10000 for these Android builds) with pc-relative literals and BL targets (function names from <lib>.functions.txt) annotated.
usage: thumbdis.py <lib.so> <functions.txt> <start hex> <end hex>"""
import struct, sys
from capstone import *
from capstone.arm import *
d = open(sys.argv[1], 'rb').read(); B = 0x10000
names = {}
for l in open(sys.argv[2]):
    p = l.split()
    if len(p) >= 3: names[int(p[0], 16)] = p[2]
a, e = int(sys.argv[3], 16), int(sys.argv[4], 16)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True; md.skipdata = True
for i in md.disasm(d[a - B:e - B], a):
    note = ''
    if i.mnemonic == 'ldr' and 'pc' in i.op_str:
        t = ((i.address + 4) & ~3) + i.operands[1].mem.disp
        if t - B + 4 <= len(d): note = '  ; =%#x' % struct.unpack_from('<I', d, t - B)[0]
    if i.mnemonic in ('bl', 'blx') and i.operands and i.operands[0].type == ARM_OP_IMM:
        t = i.operands[0].imm; note = '  ; ' + names.get(t, hex(t))
    print('%x: %s %s%s' % (i.address, i.mnemonic, i.op_str, note))
