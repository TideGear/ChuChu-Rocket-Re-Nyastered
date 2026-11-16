"""Log GE_MouseCountUp (0x34a6c) / GE_MouseCountDown (0x34a80) calls of the original per frame under a forced outcome.
usage: trace_count_calls.py <case> <outcome> <from> <to>"""
import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR
case, force, lo, hi = (int(a) for a in sys.argv[1:5])
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed = (case, 1000 + case * 17) if case < 25 else (5, 2024)
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
B.spawns.clear(); setup_battle(tiles, walls, seed); gcall(0x3d2bc)
for ga in (0x184c8c, 0x184ca0, 0x184ca8, 0x17518c): o.write(BASE + ga - G, struct.pack('<I', 0))
o.write(BASE + 0x17b604 - G, struct.pack('<I', 0)); o.write(BASE + 0x17b600 - G, struct.pack('<I', 0))
def fz(uc, a, s, u): uc.reg_write(UC_ARM_REG_R0, force); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
o.uc.hook_add(UC_HOOK_CODE, fz, begin=BASE + 0x3c2bc - G, end=BASE + 0x3c2bc - G + 2)
def mk(name):
    def cb(uc, a, s, u):
        f = B.frame_no[0]
        if lo <= f <= hi and uc.reg_read(UC_ARM_REG_R0) == 0: print('%s f%d type0' % (name, f))
    return cb
o.uc.hook_add(UC_HOOK_CODE, mk('UP'), begin=BASE + 0x34a6c - G, end=BASE + 0x34a6c - G + 2)
o.uc.hook_add(UC_HOOK_CODE, mk('DOWN'), begin=BASE + 0x34a80 - G, end=BASE + 0x34a80 - G + 2)
rng = random.Random(seed); pend = {}
for f in range(10, 3000, 40): pend[f] = (rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4))
pt = o.heap_ptr; o.heap_ptr += 16
for f in range(1, hi + 1):
    B.frame_no[0] = f
    if f in pend:
        pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    if lo <= f <= hi and f < 40: print('SAMPLE f%d %d' % (f, struct.unpack('<i', o.read(BASE + 0x17b810 - G + 0x18, 4))[0]))
