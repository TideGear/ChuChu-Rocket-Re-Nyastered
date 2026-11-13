import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, upto = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]); levels = [int(x) for x in sys.argv[4].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
log = []
def hook(ga, name, nargs=2):
    def cb(uc, a, s, u):
        log.append((B.frame_no[0], name, [uc.reg_read(r) & 0xffffffff for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)][:nargs]))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + ga - G, end=BASE + ga - G + 2)
hook(0x3ccc8, 'dest0', 0); hook(0x3c3b8, 'RollRoulette4', 1); hook(0x3c2bc, 'select', 2); hook(0x3c56c, 'task_c56c', 0)
# jump table of event starters
tbl = (lit(0x3c7d8) + 0x3c6b0 - G) & 0xffffffff
targets = [ (o.u32(BASE + tbl + 4 * i) + lit(0x3c7d8) + 0x3c6b0) & 0xffffffff for i in range(8)]
print('event table', [hex(t) for t in targets])
for i, t in enumerate(targets): hook(t & ~1, 'event%d' % i, 0)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
for f in range(1, upto + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
seen = set()
for l in log:
    if l[1] == 'task_c56c': continue
    k = (l[0], l[1]);
    if k in seen: continue
    seen.add(k); print(l)
