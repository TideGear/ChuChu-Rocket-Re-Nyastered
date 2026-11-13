"""Log SmpTskEntry/SmpTskDelete (frame, slot, exe fn, caller) in a CPU battle to learn task lifetimes."""
import sys, struct, collections
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, upto = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]); levels = [int(x) for x in sys.argv[4].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
pool = BASE + ((lit(0x3db84) + 0x3db60 + 4 - G) & 0xffffffff)
log = []
callers = []
def call_cb(uc, a, s, u): callers.append((uc.reg_read(UC_ARM_REG_LR) - BASE + G) & ~1)
def ent_cb(uc, a, s, u):
    r4 = uc.reg_read(UC_ARM_REG_R4)
    if r4: log.append((B.frame_no[0], 'new', (r4 - pool) // 0x58, (o.u32(r4 + 0x40) - BASE + G) & ~1, callers[-1] if callers else 0))
def del_cb(uc, a, s, u):
    r0 = uc.reg_read(UC_ARM_REG_R0)
    if pool <= r0 < pool + 0x16000: log.append((B.frame_no[0], 'del', (r0 - pool) // 0x58, (o.u32(r0 + 0x40) - BASE + G) & ~1, (uc.reg_read(UC_ARM_REG_LR) - BASE + G) & ~1))
o.uc.hook_add(UC_HOOK_CODE, call_cb, begin=BASE + 0x3dbc4 - G, end=BASE + 0x3dbc4 - G + 2)
o.uc.hook_add(UC_HOOK_CODE, ent_cb, begin=BASE + 0x3dafa - G, end=BASE + 0x3dafa - G + 2)
o.uc.hook_add(UC_HOOK_CODE, del_cb, begin=BASE + 0x3db0c - G, end=BASE + 0x3db0c - G + 2)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
for f in range(1, upto + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
seen = []; 
for l in log:
    if not seen or seen[-1] != l: seen.append(l)
c = collections.Counter((l[1], hex(l[3]), hex(l[4])) for l in seen)
for k, v in c.most_common(30): print(v, k)
open(r'C:\Dev\ChuChu Rocket\local\testdata\task_life2.txt', 'w').write('\n'.join(map(str, seen)))
