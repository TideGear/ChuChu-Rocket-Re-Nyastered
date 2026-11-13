import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, upto = 4, 1068, int(sys.argv[1])
log = {}
def cb(uc, a, s, u):
    r0 = uc.reg_read(UC_ARM_REG_R0)
    try: x, _, z = struct.unpack('<fff', o.read(r0, 12))
    except Exception: return
    log.setdefault(r0, {})[B.frame_no[0]] = (round(x, 2), round(z, 2))
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x2e064 - G, end=BASE + 0x2e064 - G + 2)
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
rng = random.Random(seed); pend = {}
for f in range(10, 3000, 40): pend[f] = (rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4))
pt = o.heap_ptr; o.heap_ptr += 16
for f in range(1, upto + 1):
    B.frame_no[0] = f
    if f in pend:
        pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
for p, fr in log.items():
    if min(fr) == 181 or min(fr) == 180:
        print(hex(p), [(f, fr[f]) for f in sorted(fr) if f % 20 == 0 or 676 <= f <= 684][:80])
print('--- at 682')
for p, fr in log.items():
    if 682 in fr: print(hex(p), min(fr), fr[682], fr.get(681), fr.get(683))
print('--- mouse d224')
fr = log[0x1017d224]; print([(f, fr[f]) for f in sorted(fr) if f % 10 == 0 and f < 700])
