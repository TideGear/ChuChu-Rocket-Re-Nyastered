"""Log the first MO_MouseJimeExe (0x352a0) execution of every mouse task in the original under a forced outcome 7: frame, task, x, z, angle (+0x24).
usage: trace_jime_first.py <case> <from> <to>"""
import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR
case, lo, hi = (int(a) for a in sys.argv[1:4])
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed = (case, 1000 + case * 17) if case < 25 else (5, 2024)
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
B.spawns.clear(); setup_battle(tiles, walls, seed); gcall(0x3d2bc)
for ga in (0x184c8c, 0x184ca0, 0x184ca8, 0x17518c): o.write(BASE + ga - G, struct.pack('<I', 0))
o.write(BASE + 0x17b604 - G, struct.pack('<I', 0)); o.write(BASE + 0x17b600 - G, struct.pack('<I', 0))
def force(uc, a, s, u): uc.reg_write(UC_ARM_REG_R0, 7); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
o.uc.hook_add(UC_HOOK_CODE, force, begin=BASE + 0x3c2bc - G, end=BASE + 0x3c2bc - G + 2)
seen = set()
def jime(uc, a, s, u):
    t = uc.reg_read(UC_ARM_REG_R0)
    if t in seen or B.frame_no[0] < lo: return
    seen.add(t)
    x, y, z = struct.unpack('<3f', o.read(t + 0x14, 12)); ang, = struct.unpack('<i', o.read(t + 0x24, 4))
    print('f%d task %x x %.3f z %.3f angle %d (%.2f turns*16)' % (B.frame_no[0], t, x, z, ang, ang / 16384.0))
o.uc.hook_add(UC_HOOK_CODE, jime, begin=BASE + 0x352a0 - G, end=BASE + 0x352a0 - G + 2)
def dist(uc, a, s, u):
    f = B.frame_no[0]
    if 1535 <= f <= 1552:
        dv, = struct.unpack('<f', struct.pack('<I', uc.reg_read(UC_ARM_REG_R0)))
        if dv < 12: print('DIST f%d r4task %x d %.5f' % (f, uc.reg_read(4), dv))
def pos(uc, a, s, u):
    f = B.frame_no[0]
    if 1500 <= f <= 1552:
        t = uc.reg_read(UC_ARM_REG_R0); x, y, z = struct.unpack('<3f', o.read(t + 0x14, 12)); ang, = struct.unpack('<i', o.read(t + 0x24, 4))
        print('POS f%d %.4f %.4f %d' % (f, x, z, ang))
o.uc.hook_add(UC_HOOK_CODE, pos, begin=BASE + 0x352a0 - G, end=BASE + 0x352a0 - G + 2)
o.uc.hook_add(UC_HOOK_CODE, dist, begin=BASE + 0x352d0 - G, end=BASE + 0x352d0 - G + 2)
rng = random.Random(seed); pend = {}
for f in range(10, 3000, 40): pend[f] = (rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4))
pt = o.heap_ptr; o.heap_ptr += 16
for f in range(1, hi + 1):
    B.frame_no[0] = f
    if f in pend:
        pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
