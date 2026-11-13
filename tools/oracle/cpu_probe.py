import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, frames = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]); levels = [int(x) for x in sys.argv[4].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
puts = []
def cb(uc, a, s, u):
    pl = uc.reg_read(UC_ARM_REG_R0); p = uc.reg_read(UC_ARM_REG_R1); dd = uc.reg_read(UC_ARM_REG_R2)
    x, y = struct.unpack('<hh', o.read(p, 4)); puts.append((B.frame_no[0], pl, x, y, dd & 0xff))
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x286ac - G, end=BASE + 0x286ac - G + 2)
gcall(0x3d2bc)                                   # SC_InitScoreBoard
gcall(0x2ef3c) if False else None
print('global time before', gcall(0x2ef3c), 'game time', gcall(0x2ef44) if False else '')
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)            # CT_StartCompThink(player, level)
for f in range(1, frames + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    if f in (1, 2, 3): print('frame', f, 'global time', gcall(0x2ef3c))
print(len(puts), 'AR_PutArrow calls'); print(puts[:40])
