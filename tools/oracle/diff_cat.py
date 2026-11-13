"""Differential test: real cat/mouse tick (emulated libccrjni.so) vs a Python port of the reimplementation's step.
Random walled boards, single entity, no arrows/holes/rockets. Reports the first divergence per scenario."""
import struct, math, sys, random
sys.path.insert(0, '.')
from cat_run import *          # sets up oracle, ent, set_coll, put_entity, state
W = [0x10000, 0x20000, 0x40000, 0x80000]    # wall bits indexed by heading (S,W,N,E)
def mine_step(e, coll, speed, thr_f):
    sinv = [0, 1, 0, -1]; cosv = [1, 0, -1, 0]
    thr = max(speed * thr_f, 0.01)
    gx, gy, x, z, h = e
    cx, cz = (gx + 0.5) * 15, (gy + 0.5) * 15
    if math.hypot(x - cx, z - cz) < thr:
        f = coll[gy][gx]
        if f & 0xf0000:
            moved = False
            for k in (0, 1, 3, 2):
                d = (h + k) & 3
                if not (f & W[d]):
                    if d != h: x, z = cx, cz
                    h = d; moved = True; break
            if not moved: return (gx, gy, x, z, h)      # dead end: no movement
    x += -speed * sinv[h]; z += speed * cosv[h]
    if x < -7.5: x += 195
    elif x > 187.5: x -= 195
    if z < -7.5: z += 150
    elif z > 142.5: z -= 150
    ngx = min(max(int(x * 0.06666667), 0), 11) if x >= 0 else 0
    ngy = min(max(int(z * 0.06666667), 0), 8) if z >= 0 else 0
    return (ngx, ngy, x, z, h)
def random_board(rng, density):
    coll = [[0] * 12 for _ in range(9)]
    for r in range(10):
        for c in range(12):
            if rng.random() < density or ((r in (0, 9)) and rng.random() < 0.8):       # horizontal edge above row r
                if r < 9: coll[r][c] |= 0x40000
                if r > 0: coll[r - 1][c] |= 0x10000
    for r in range(9):
        for c in range(13):
            if rng.random() < density or (c in (0, 12) and rng.random() < 0.8):
                if c < 12: coll[r][c] |= 0x20000
                if c > 0: coll[r][c - 1] |= 0x80000
    return coll
if __name__ == '__main__':
    kind = sys.argv[1] if len(sys.argv) > 1 else 'cat'
    fn, speed, thr_f = (0x28ffc, 1.0, 0.51) if kind == 'cat' else (0x3501c, 1.5, 0.52)
    rng = random.Random(1); bad = 0; N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    for sc in range(N):
        coll = random_board(rng, 0.15); gx, gy, h = rng.randrange(12), rng.randrange(9), rng.randrange(4)
        set_coll(coll); put_entity(gx, gy, h)
        mine = (gx, gy, (gx + 0.5) * 15, (gy + 0.5) * 15, h)
        for t in range(1, 400):
            gcall(fn, ent); real = state(); mine = mine_step(mine, coll, speed, thr_f)
            m = (mine[0], mine[1], round(mine[2], 3), round(mine[3], 3), mine[4])
            if abs(real[2] - m[2]) > 0.01 or abs(real[3] - m[3]) > 0.01 or real[4] != m[4] or real[0] != m[0] or real[1] != m[1]:
                bad += 1
                if bad <= 6: print('scenario %d tick %d: real %s  mine %s' % (sc, t, real, m))
                break
    print(kind, 'scenarios', N, 'diverged', bad)
