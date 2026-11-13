"""Record spawn logs of the original battle generator (emulated) for several stages/seeds: local/testdata/spawn_golden.txt
Also records, per frame, the externally-driven generator state (mouse counts, special counts, cat-out flag) so the
reimplementation can be tested as a pure function of those inputs."""
import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
out = open(r'C:\Dev\ChuChu Rocket\local\testdata\spawn_golden.txt', 'w')
STATE = (0x17b810 - G)                 # generator manager state block (file vaddr)
def state():
    w = struct.unpack('<9i', o.read(BASE + STATE, 36))
    return {'n': w[0], 'catOut': w[1], 'timer': w[2], 'flags': w[3], 'lock2': w[4], 'lock1': w[5], 'mice': w[6], 'cnt1': w[7], 'cnt2': w[8]}
cases = [(0, 12345), (0, 1), (3, 777), (10, 99999), (17, 424242), (24, 31337), (5, 2024), (8, 7), (12, 555), (20, 123456), (1, 99), (2, 31), (4, 4242), (6, 8), (7, 1000)]
for idx, seed in cases:
    tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
    gens = [(c, r, tiles[r * 12 + c] - 5) for r in range(9) for c in range(12) if 5 <= tiles[r * 12 + c] <= 8]
    B.spawns.clear(); setup_battle(tiles, walls, seed)
    frames = 1200; rows = []; prev = None
    for f in range(1, frames + 1):
        B.frame_no[0] = f
        before = state()
        key = (before['mice'], before['cnt1'], before['cnt2'], before['catOut'], before['flags'])
        if key != prev: rows.append((f,) + key); prev = key
        step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    ev = []
    for s in B.spawns:
        if not ev or ev[-1] != s: ev.append(s)           # the code hook fires more than once per call
    out.write('CASE %d %d %d %d %d %d\n' % (idx, seed, frames, len(gens), len(ev), len(rows)))
    for g in gens: out.write('G %d %d %d\n' % g)
    for r in rows: out.write('F %d %d %d %d %d %d\n' % r)
    for s in ev: out.write('S %d %s %d %d %d %d\n' % s)
    print('case', idx, seed, 'spawns', len(ev), 'state changes', len(rows), 'cats', sum(1 for s in ev if s[1] == 'cat'), 'specials', sum(1 for s in ev if s[5]))
out.close()
