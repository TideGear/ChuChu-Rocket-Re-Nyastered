"""usage: traj_dump.py stage seed frames out  -> lines 'frame idx x z' (idx = order of first appearance of the entity's FI_CheckWarp pointer)"""
import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, upto, outp = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]; levels = [int(x) for x in sys.argv[5].split(',')]
ids = {}; rows = []
def cb(uc, a, s, u):
    r0 = uc.reg_read(UC_ARM_REG_R0)
    try: x, _, z = struct.unpack('<fff', o.read(r0, 12))
    except Exception: return
    k = ids.setdefault(r0, len(ids)); rows.append((B.frame_no[0], k, x, z))
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x2e064 - G, end=BASE + 0x2e064 - G + 2)
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
for f in range(1, upto + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
with open(outp, 'w') as fo:
    for r in rows: fo.write('%d %d %.3f %.3f\n' % r)
print(len(ids), 'entities', len(rows), 'rows')
