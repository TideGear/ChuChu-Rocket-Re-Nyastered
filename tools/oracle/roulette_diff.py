"""Differential test of the roulette outcome selector (FUN_0003c2bc) against a Python port."""
import sys, struct, random
sys.path.insert(0, '.')
from battle_probe import *
import numpy as np
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
tiles, walls = ascii_stage(d[0:475])
setup_battle(tiles, walls, 1)
step('SC_InitScoreBoard', 0x3d2bc)
step('RL_StartRoulette4Manager', 0x3cd90)
RS = (0x14898a + 0x3c302 - G) & 0xffffffff                  # roulette state block
TI = (0x14c53e + 0x2f0ba - G) & 0xffffffff                  # timer block: +8 BCD time, +0xc game time
SCP = (lit(0x3c3a4) + 0x3c2e6 - G) & 0xffffffff             # pointer to the score array
score_arr = o.u32(BASE + SCP)
WA = (lit(0x3c3a0) + 0x3c2de - G) & 0xffffffff; WB = (lit(0x3c3b0) + 0x3c396 - G) & 0xffffffff; WC = (lit(0x3c3b4) + 0x3c39c - G) & 0xffffffff
rows = {k: [struct.unpack('<8f', o.read(BASE + b + 32 * r, 32)) for r in range(4)] for k, b in (('A', WA), ('B', WB), ('C', WC))}
table = list(struct.unpack('<128f', o.read(BASE + RS + 0x20, 512)))
f32 = np.float32
def port(player, exclude, rank, bcd, gtime, lastA, lastB):
    row = rows['A' if bcd <= 0x2fff else 'B' if bcd <= 0xffff else 'C'][rank]
    idx = 0
    for att in range(128):
        thr = f32(table[(gtime + att) & 0x7f]); cum = f32(row[0]); idx = 0
        while not cum >= thr:
            idx += 1
            if idx == 7: break
            cum = f32(cum + f32(row[idx]))
        if idx == exclude: continue
        if 2 <= idx <= 5:
            if lastA == idx: continue
            return idx
        if lastA != idx or lastA != lastB: return idx
    return idx
if __name__ == '__main__':
    rng = random.Random(3); bad = 0; n = 4000
    print('weights A row0:', rows['A'][0], '| table[0:3]', table[:3])
    for i in range(n):
        player = rng.randrange(4); exclude = rng.choice([-1, -1, 0, 1, 2, 3, 4, 5, 6, 7]); rank = rng.randrange(4)
        bcd = rng.choice([rng.randrange(0, 0x3000), rng.randrange(0x3000, 0x10000), rng.randrange(0x10000, 0x40000)]); g = rng.randrange(0, 100000)
        lastA = rng.choice([-1, 0, 1, 2, 3, 4, 5, 6, 7]); lastB = rng.choice([lastA, lastA, -1, 0, 1, 2, 3, 4, 5, 6, 7])
        o.write(score_arr + 4 * (4 + player), struct.pack('<i', rank))
        o.write(BASE + TI + 8, struct.pack('<i', bcd)); o.write(BASE + TI + 0xc, struct.pack('<i', g))
        o.write(BASE + RS + 0xc, struct.pack('<ii', lastA, lastB))
        got = step('selector', 0x3c2bc, player, exclude & 0xffffffff)
        want = port(player, exclude, rank, bcd, g, lastA, lastB)
        if got != want:
            bad += 1
            if bad <= 4: print('MISMATCH', dict(player=player, exclude=exclude, rank=rank, bcd=hex(bcd), g=g, lastA=lastA, lastB=lastB), 'orig', got, 'port', want)
    print('selector calls', n, 'mismatches', bad)
