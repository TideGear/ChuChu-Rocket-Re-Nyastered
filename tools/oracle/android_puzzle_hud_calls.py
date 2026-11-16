"""Record the draw calls of Android's handset Puzzle HUD (renderPuzzleHudA800) for given arrow stocks and stage numbers.
usage: android_puzzle_hud_calls.py <libccrjni.so>   (Android 1.15 offsets; the literal-pool offsets differ in 1.14)"""
from pathlib import Path
import struct, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ccr_oracle import BASE, HEAP, Oracle, u2f
from extract_android import elf_symbols
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

IMG = ('_ZN6Render9drawImageEiiffif', '_ZN6Render9drawImageEiiff', '_ZN6Render9drawImageEiiffi', '_ZN6Render9drawImageEiiffifi')


def run(path, stock, stage, wide, flash=1, mode=0, name='_Z19renderPuzzleHudA800Pv', literal=0x1d8):
    o = Oracle(str(path))
    syms, _ = elf_symbols(o.d)
    A = lambda n: BASE + (syms[n][0] & ~1)
    glow = next(k for k in syms if k.startswith('_ZN6Render11getGlowFlag'))
    fn = syms[name][0] & ~1
    got = BASE + fn + 0x16 + o.u32(BASE + fn + literal)
    slot = lambda off: o.u32(got + off)
    o.write(slot(0x4e4), struct.pack('<i', mode))               # 1 selects the alternate layout
    app = HEAP + 0x2000
    o.write(slot(0x31c), struct.pack('<I', app))
    o.write(app + 0x6c84, struct.pack('<i', 5 if wide else 0))  # language 5 takes the wide-character path
    calls = []
    hooks = {A(n): 'img' for n in IMG}
    hooks.update({A('_ZN6Render11printStringEPKhffhhhhftbi'): 'str', A('_ZN6Render12getFlashFlagEi'): 'flash',
                  A(glow): 'glow', A('_ZN6Render12getGlowScaleEv'): 'scale', A('_Z21AR_GetArrowdataPuzzlePc'): 'arrows',
                  A('_Z14GA_GetStageNumv'): 'stage', A('_Z19renderPuzzleHudLeftf'): 'left', A('wide_sprintf'): 'wsp'})

    def hook(uc, addr, size, data):
        kind = hooks[addr]
        r = [uc.reg_read(x) for x in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        sp = uc.reg_read(UC_ARM_REG_SP)
        ret = 0
        if kind == 'img':
            st = struct.unpack('<4I', o.read(sp, 16))
            calls.append(('img', hex(addr - BASE), r[0], r[1], u2f(r[2]), u2f(r[3]), [hex(v) for v in st]))
        elif kind == 'str':
            calls.append(('str', bytes(o.read(r[0], 4)), u2f(r[1]), u2f(r[2]),
                          [hex(v) for v in struct.unpack('<6I', o.read(sp, 24))], hex(r[3])))
        elif kind == 'flash':
            ret = flash
        elif kind == 'arrows':
            o.write(r[0], bytes(stock))
        elif kind == 'stage':
            ret = stage
        elif kind == 'left':
            calls.append(('left',))
        elif kind == 'wsp':
            o.write(r[0], b'%d\x00' % r[2])
            calls.append(('count', r[2]))
        uc.reg_write(UC_ARM_REG_R0, ret)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for a in hooks:
        o.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a)
    try:
        o.call(fn, 0)
    except Exception:
        print('fault pc', hex(o.uc.reg_read(UC_ARM_REG_PC) - BASE), calls[-3:])
        raise
    return calls


if __name__ == '__main__':
    for m in (0, 1):
        print('mode', m)
        for c in run(Path(sys.argv[1]), (2, 0, 3, 1), 7, False, mode=m, name='_Z21renderPuzzleHudiPhonePv', literal=0x1e4):
            print(c)
