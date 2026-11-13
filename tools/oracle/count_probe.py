import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, frames = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
log = []
def hk(ga, name):
    def cb(uc, a, s, u):
        r0 = uc.reg_read(UC_ARM_REG_R0)
        try: t = o.u32(r0 + 8)
        except Exception: t = -1
        log.append((B.frame_no[0], name, t, [round(x,1) for x in struct.unpack('<24f', o.read(r0, 96))]))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + ga - G, end=BASE + ga - G + 2)
hk(0x35004, 'down')
hk(0x34e54 + 0, 'getrocket')
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
rng = random.Random(seed); pend = {}
for f in range(10, frames, 40): pend[f] = (rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4))
pt = o.heap_ptr; o.heap_ptr += 16
for f in range(1, frames + 1):
    B.frame_no[0] = f
    if f in pend:
        pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)

for l in [l for l in log if l[1]=='down'][:12:2]: print(l)
