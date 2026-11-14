"""make_battle_golden.py with a chosen TI_GetGameTime value. usage: make_battle_golden_gt.py <frames> <gametime> [case,case,... | all] [threshold] [bcd] [outfile]   (threshold: every entry of the 128-float roulette threshold table, 0 = manager not started; bcd: TI_GetBCDTime value)"""
"""Record whole-battle logs from the original (emulated, no player input): per-frame score changes, roulette triggers, spawns.
Output local/testdata/battle_golden.txt:  CASE idx seed frames nscore nroul nspawn / SC frame s0 s1 s2 s3 / RL frame / S spawn rows.
Used by game/tests/battle_full_test.cpp (compared up to the first roulette trigger, where event handlers start to matter)."""
import os, sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
GT = int(sys.argv[2]) if len(sys.argv) > 2 else 0; ONLY = [int(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 and sys.argv[3] != 'all' else None; THR = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0; BCD = int(sys.argv[5], 0) if len(sys.argv) > 5 else 0; SPEED = float(os.environ.get('CHARA_SPEED', '1.0')); OUT = sys.argv[6] if len(sys.argv) > 6 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'local', 'testdata', 'battle_golden_gt%d.txt' % GT)
out = open(OUT, 'w')
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
    if ONLY is not None and idx not in ONLY: continue
    tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
    gens = len([1 for t in tiles if 5 <= t <= 8])
    B.spawns.clear(); rl.clear(); setup_battle(tiles, walls, seed)
    gcall(0x3d2bc)                                              # SC_InitScoreBoard
    step('GA_SetCharaSpeed', 0x2ee5c, struct.unpack('<I', struct.pack('<f', SPEED))[0])   # CHARA_SPEED env: the speed the roulette events set (2.0 speed up, 0.3 slow down)
    for ga in (0x184c8c, 0x184ca0, 0x184ca8, 0x17518c): o.write(BASE + ga - G, struct.pack('<I', 0))   # roulette globals left over from the previous case (a roll still running at frame 3000 blocked every later case)
    o.write(BASE + 0x17b604 - G, struct.pack('<I', GT)); o.write(BASE + 0x17b600 - G, struct.pack('<I', BCD))   # TI_GetBCDTime
    o.write(BASE + 0x184cac - G, struct.pack('<f', THR) * 128)   # the roulette threshold table (RL_StartRoulette4Manager fills it with random numbers; the harness never starts it); TI_GetGameTime above: the emulated game never advances it
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
