"""Thumb disassembly of a range of the Android library with pc-relative literal loads resolved. usage: disasm.py <ghidra_start> <ghidra_end>"""
import sys, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
G = 0x10000
so = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\apk115\lib\armeabi\libccrjni.so', 'rb').read()
def u32(ga): o = ga - G; return struct.unpack_from('<I', so, o)[0]
def main(a, b):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = False
    code = so[a - G:b - G]
    for ins in md.disasm(code, a):
        note = ''
        if ins.mnemonic.startswith('ldr') and 'pc' in ins.op_str and '#' in ins.op_str:
            try:
                imm = int(ins.op_str.split('#')[1].rstrip(']'), 0); addr = ((ins.address + 4) & ~3) + imm; v = u32(addr); note = '   ; [%#x]=%#x (float %g)' % (addr, v, struct.unpack('<f', struct.pack('<I', v))[0])
            except Exception: pass
        print('%x  %s %s%s' % (ins.address, ins.mnemonic, ins.op_str, note))
if __name__ == '__main__': main(int(sys.argv[1], 16), int(sys.argv[2], 16))
