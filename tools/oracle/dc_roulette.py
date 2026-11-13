"""Differential test: the Dreamcast roulette selector (0x8C01D61A, from the user's 1ST_READ.BIN, run in the SH-4 interpreter) vs the port's Roulette::roll semantics (game/core/roulette.hpp)."""
import sys, os, re, struct, random
sys.path.insert(0, os.path.dirname(__file__))
from sh4 import SH4, f2u
root = os.path.join(os.path.dirname(__file__), '../..')
d = open(os.path.join(root, 'local/cache/assets/dreamcast/files/1ST_READ.BIN'), 'rb').read()
rows = re.findall(r'\{((?:[0-9.]+f, ){7}[0-9.]+f)\}', open(os.path.join(root, 'game/core/roulette.hpp')).read())
W = [[struct.unpack('<f', struct.pack('<f', float(x[:-1])))[0] for x in r.split(', ')] for r in rows]
f32 = lambda v: struct.unpack('<f', struct.pack('<f', v))[0]
def port_roll(table, rank, bcd, gt, exclude, lastA, lastB):
    row = W[(0 if bcd <= 0x2fff else 1 if bcd <= 0xffff else 2) * 4 + rank]; idx = 0
    for a in range(128):
        thr = table[(gt + a) & 127]; cum = row[0]; idx = 0
        while not (cum >= thr):
            idx += 1
            if idx == 7: break
            cum = f32(cum + row[idx])
        if idx == exclude: continue
        if 2 <= idx <= 5:
            if lastA == idx: continue
            return idx
        if lastA != idx or lastA != lastB: return idx
    return idx
rng = random.Random(1); bad = 0; N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
m = SH4(); m.load(0x8C010000, d)
for i in range(N):
    table = [f32(rng.random()) for _ in range(128)]; rank = rng.randrange(4); player = rng.randrange(4)
    bcd = rng.choice([rng.randrange(0x3000), 0x3000 + rng.randrange(0xd000), 0x10000 + rng.randrange(0x20000)]); gt = rng.randrange(100000)
    excl = rng.choice([-1, rng.randrange(8)]); la = rng.randrange(-1, 8); lb = rng.randrange(-1, 8)
    m.wr32(0x8c1ae8e0, bcd); m.wr32(0x8c1ae8e4, gt); m.wr32(0x8c1af510 + 4 * player, rank)
    for j, t in enumerate(table): m.wr32(0x8c1af23c + 4 * j, f2u(t))
    m.wr32(0x8c1af21c + 12, la & 0xffffffff); m.wr32(0x8c1af21c + 16, lb & 0xffffffff)
    got = m.call(0x8c01d61a, player, excl & 0xffffffff)
    got = got - (1 << 32) if got & 0x80000000 else got
    exp = port_roll(table, rank, bcd, gt, excl, la, lb)
    if got != exp:
        bad += 1
        if bad < 5: print('MISMATCH', i, got, exp, rank, hex(bcd), gt, excl, la, lb)
print('dreamcast roulette selector: %d cases, %d different' % (N, bad))
