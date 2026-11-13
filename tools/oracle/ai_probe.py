import sys, struct, collections
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_MEM_WRITE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
tiles, walls = ascii_stage(d[0:475]); B.spawns.clear(); setup_battle(tiles, walls, 5)
G8 = 0x79498
heat = o.u32(BASE + G8 + 0x564 - G); owners = o.u32(BASE + G8 + 0x3a4 - G)
print('heat array ptr', hex(heat), 'table a638 ptr', hex(owners))
writers = collections.Counter()
def cb(uc, access, addr, size, val, u):
    pc = uc.reg_read(UC_ARM_REG_PC) - BASE + G
    writers[hex(pc & ~1)] += 1
o.uc.hook_add(UC_HOOK_MEM_WRITE, cb, begin=heat, end=heat + 108 * 2)
for f in range(1, 400):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
print(writers.most_common(10))
