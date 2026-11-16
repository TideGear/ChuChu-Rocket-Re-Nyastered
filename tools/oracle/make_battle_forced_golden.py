"""Record whole-battle logs from the original with the roulette manager running and every roulette outcome forced.
usage: make_battle_forced_golden.py <outcome 0-7> [frames] [first_case] [case_count]
Output local/testdata/battle_forced_<outcome>.txt in the make_battle_golden.py format (CASE / A / SC / RL / S rows).
The selector (FUN_0003c2bc) is replaced by 'return <outcome>' so the event handler of that outcome runs past the trigger."""
import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR

import os
TEAM = os.environ.get('TEAM') == '1'   # TEAM=1: Team Battle (GA game type 1, mode 0xd); output battle_team_forced_<k>.txt
force = int(sys.argv[1])
frames = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
first = int(sys.argv[3]) if len(sys.argv) > 3 else 0
count = int(sys.argv[4]) if len(sys.argv) > 4 else 26
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
out = open(r'C:\Dev\ChuChu Rocket\local\testdata\battle_%sforced_%d.txt' % ('team_' if TEAM else '', force), 'w' if first == 0 else 'a')
rl = []
def hook_rl(ga):
    def cb(uc, a, s, u): rl.append(B.frame_no[0])
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + ga - G, end=BASE + ga - G + 2)
def hook_force(ga):
    def cb(uc, a, s, u):
        uc.reg_write(UC_ARM_REG_R0, force); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + ga - G, end=BASE + ga - G + 2)
hook_rl(0x3c2bc)
pa = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
cases = [(i, 1000 + i * 17, True) for i in range(25)] + [(5, 2024, False)]
for idx, seed, use_arrows in cases[first:first + count]:
    tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
    B.spawns.clear(); rl.clear(); setup_battle(tiles, walls, seed, 0xd, 1) if TEAM else setup_battle(tiles, walls, seed)
    gcall(0x3d2bc)                                              # SC_InitScoreBoard
    for ga in (0x184c8c, 0x184ca0, 0x184ca8, 0x17518c): o.write(BASE + ga - G, struct.pack('<I', 0))   # roulette globals left over from the previous case
    o.write(BASE + 0x17b604 - G, struct.pack('<I', 0)); o.write(BASE + 0x17b600 - G, struct.pack('<I', 0))   # game time and BCD time = 0, as battle_full_test GT=0 assumes
    hook_force(0x3c2bc)
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
    out.flush()
    print('forced', force, 'case', idx, seed, 'score changes', len(sc), 'roulette', r[:5], 'final', sc[-1] if sc else None, flush=True)
out.close()
