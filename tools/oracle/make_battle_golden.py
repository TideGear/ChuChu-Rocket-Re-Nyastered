"""Record whole-battle logs from the original (emulated, no player input): per-frame score changes, roulette triggers, spawns.
Output local/testdata/battle_golden.txt:  CASE idx seed frames nscore nroul nspawn / SC frame s0 s1 s2 s3 / RL frame / S spawn rows.
Used by game/tests/battle_full_test.cpp (compared up to the first roulette trigger, where event handlers start to matter)."""
import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
out = open(r'C:\Dev\ChuChu Rocket\local\testdata\battle_golden.txt', 'w')
rl = []
def hook_rl(ga):
    def cb(uc, a, s, u): rl.append(B.frame_no[0])
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + ga - G, end=BASE + ga - G + 2)
hook_rl(0x3c2bc)
pa = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
import random
cases = [(i, 1000 + i * 17, True) for i in range(25)] + [(5, 2024, False)]
frames = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
for idx, seed, use_arrows in cases:
    tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
    gens = len([1 for t in tiles if 5 <= t <= 8])
    B.spawns.clear(); rl.clear(); setup_battle(tiles, walls, seed)
    gcall(0x3d2bc)                                              # SC_InitScoreBoard
    arr = o.u32(BASE + pa)
    sc = []; prev = None
    rng = random.Random(seed); placements = []
    if use_arrows:
        for f in range(10, frames, 40):
            placements.append((f, rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4)))
    pend = {p[0]: p for p in placements}
    pt = o.heap_ptr; o.heap_ptr += 16
    for f in range(1, frames + 1):
        B.frame_no[0] = f
        if f in pend:
            _, pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
        step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
        s = tuple(struct.unpack('<4i', o.read(arr, 16)))
        if s != prev: sc.append((f,) + s); prev = s
    ev = []
    for s in B.spawns:
        if not ev or ev[-1] != s: ev.append(s)
    r = sorted(set(rl))
    out.write('CASE %d %d %d %d %d %d %d\n' % (idx, seed, frames, len(sc), len(r), len(ev), len(placements)))
    for x in placements: out.write('A %d %d %d %d %d\n' % x)
    for x in sc: out.write('SC %d %d %d %d %d\n' % x)
    for x in r: out.write('RL %d\n' % x)
    for s in ev: out.write('S %d %s %d %d %d %d\n' % s)
    print('case', idx, seed, 'score changes', len(sc), 'roulette', r[:5], 'final', sc[-1] if sc else None, flush=True)
out.close()
