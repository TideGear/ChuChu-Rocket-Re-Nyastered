"""Record CPU-player arrow placements (calls of the original AR_PutArrow) for battles with CPU players: local/testdata/cpu_golden.txt"""
import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
puts = []
def cb(uc, a, s, u):
    pl = uc.reg_read(UC_ARM_REG_R0); p = uc.reg_read(UC_ARM_REG_R1); dd = uc.reg_read(UC_ARM_REG_R2)
    x, y = struct.unpack('<hh', o.read(p, 4)); puts.append((B.frame_no[0], pl, x, y, dd & 0xff))
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x286ac - G, end=BASE + 0x286ac - G + 2)
pa = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
import random
_r = random.Random(2026)
cases = [(i % 25, _r.randrange(1, 100000), [_r.choice([-1, 0, 1, 2, 3, 4]) for _ in range(4)]) for i in range(40)]
cases = [(i, sd, lv if any(x >= 0 for x in lv) else [0, 1, 2, 3]) for i, sd, lv in cases]
frames = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
which = int(sys.argv[2]); out = open('C:/Dev/ChuChu Rocket/local/testdata/cpu_golden2_%d.txt' % which, 'w')
for idx, seed, levels in [cases[which]]:
    tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); puts.clear(); setup_battle(tiles, walls, seed)
    gcall(0x3d2bc)
    for p, lv in enumerate(levels):
        if lv >= 0: gcall(0x29d50, p, lv)
    for f in range(1, frames + 1):
        B.frame_no[0] = f
        step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    ev = []
    for p in puts:
        if not ev or ev[-1] != p: ev.append(p)
    out.write('CASE %d %d %d %d %d %d %d %d\n' % ((idx, seed, frames) + tuple(levels) + (len(ev),)))
    for p in ev: out.write('P %d %d %d %d %d\n' % p)
    print('case', idx, seed, levels, len(ev), 'placements', flush=True)
out.close()
