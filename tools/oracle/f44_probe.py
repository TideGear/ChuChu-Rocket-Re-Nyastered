import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, f0, f1 = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]); levels = [int(x) for x in sys.argv[5].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
calls = []
def cb(uc, a, s, u):
    p = uc.reg_read(UC_ARM_REG_R1); x, y = struct.unpack('<hh', o.read(p, 4))
    calls.append((B.frame_no[0], uc.reg_read(UC_ARM_REG_R0), x, y, uc.reg_read(UC_ARM_REG_R2)))
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x29f44 - G, end=BASE + 0x29f44 - G + 2)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
for f in range(1, f1 + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
print(len(calls), calls[:12])
