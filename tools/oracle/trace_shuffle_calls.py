"""Log FI_ChangeFieldCollisionID calls of the original during a forced roulette outcome (default 5 = Everybody Move).
usage: trace_shuffle_calls.py <case 0-25> <outcome> [frames]"""
import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_PC, UC_ARM_REG_LR

case, force = int(sys.argv[1]), int(sys.argv[2]); frames = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed = (case, 1000 + case * 17) if case < 25 else (5, 2024)
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
for ga in (0x184c8c, 0x184ca0, 0x184ca8, 0x17518c): o.write(BASE + ga - G, struct.pack('<I', 0))
o.write(BASE + 0x17b604 - G, struct.pack('<I', 0)); o.write(BASE + 0x17b600 - G, struct.pack('<I', 0))
def hook(ga, name, force_ret=None):
    def cb(uc, a, s, u):
        r = [uc.reg_read(x) for x in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if force_ret is not None:
            uc.reg_write(UC_ARM_REG_R0, force_ret); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
        print('f%d %s %s' % (B.frame_no[0], name, [hex(v) for v in r]))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + ga - G, end=BASE + ga - G + 2)
hook(0x3c2bc, 'selector', force); hook(0x2e034, 'ChangeFieldCollisionID'); hook(0x3b490, 'ShuffleRockets')
rng = random.Random(seed); pend = {}
for f in range(10, 3000, 40): pend[f] = (rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4))
pt = o.heap_ptr; o.heap_ptr += 16
for f in range(1, frames + 1):
    B.frame_no[0] = f
    if f in pend:
        pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
