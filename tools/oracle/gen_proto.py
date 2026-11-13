"""Python prototype of the battle generator (from the iOS decompile + Android asm), compared with the emulated original's spawn log."""
import sys, struct
sys.path.insert(0, '.')
M = 0xffffffff
class MT:
    def __init__(self, seed):
        s = (seed | 1) & M; self.mt = [s]
        while len(self.mt) < 624: s = (69069 * s) & M; self.mt.append(s)
        self.i = 624
    def _gen(self):
        mt = self.mt
        for kk in range(624):
            y = (mt[kk] & 0x80000000) | (mt[(kk + 1) % 624] & 0x7fffffff)
            mt[kk] = mt[(kk + 397) % 624] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
        self.i = 0
    def u32(self):
        if self.i >= 624: self._gen()
        y = self.mt[self.i]; self.i += 1
        y ^= y >> 11; y ^= (y << 7) & 0x9d2c5680; y ^= (y << 15) & 0xefc60000; y ^= y >> 18
        return y & M
    def rnd(self):
        import numpy as np
        return float(np.float32(self.u32()) * np.float32(1 / 4294967296))
class Gen:
    CAP0, CAP1, CAP2 = 100, 2, 1
    P, T1, T2, T3 = 0.0125, 0.01, 0.1, 0.05
    def __init__(self, gens, seed):
        self.gens = gens          # [(x, y, dir)]
        self.rng = MT(seed); self.catOut = 0; self.timer = 0; self.flags = 0
        self.lock1 = self.lock2 = 0; self.mice = 0; self.cnt1 = self.cnt2 = 0; self.out = []
    def frame(self, f):
        if self.lock2 > 0: self.lock2 -= 1
        if self.lock1 > 0: self.lock1 -= 1
        import numpy as np
        for (x, y, d) in self.gens:
            if not (self.flags & 8) and self.catOut == 0 and self.timer > 299:
                self.out.append((f, 'cat', x, y, d, 0)); self.catOut = 1; continue
            if self.mice >= self.CAP0: break
            r = self.rng.rnd()
            if not r < np.float32(self.P): continue
            r2 = self.rng.rnd(); thr = np.float32(self.T1)
            if not (self.flags & 2) and self.lock1 == 0 and self.cnt1 < self.CAP1 and r2 < thr:
                self.lock1 = 15; self.out.append((f, 'mouse', x, y, d, 1)); self.mice += 1; self.cnt1 += 1; continue
            thr = np.float32(thr + np.float32(self.T2))
            if not (self.flags & 4) and self.lock2 == 0 and self.cnt2 < self.CAP2 and r2 < thr:
                self.lock2 = 15; self.out.append((f, 'mouse', x, y, d, 2)); self.mice += 1; self.cnt2 += 1; continue
            if not (self.flags & 8) and self.catOut == 0 and r2 < np.float32(thr + np.float32(self.T3)):
                self.out.append((f, 'cat', x, y, d, 0)); self.catOut = 1; continue
            if self.flags & 1: continue
            self.out.append((f, 'mouse', x, y, d, 0)); self.mice += 1
        self.timer = self.timer + 1 if self.catOut == 0 else 0
Gen.CAP0 = 100
if __name__ == '__main__':
    from battle_probe import *
    d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
    idx = int(sys.argv[1]); seed = int(sys.argv[2]); frames = int(sys.argv[3])
    tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
    gens = [(c, r, tiles[r * 12 + c] - 5) for r in range(9) for c in range(12) if 5 <= tiles[r * 12 + c] <= 8]
    setup_battle(tiles, walls, seed)
    for f in range(1, frames + 1):
        frame_no[0] = f
        step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    real = spawns[::2]                       # the code hook fires twice per call
    g = Gen(gens, seed)
    for f in range(1, frames + 1): g.frame(f)
    print('generators', gens)
    print('real  ', len(real), real[:8]); print('proto ', len(g.out), g.out[:8])
    n = 0
    while n < min(len(real), len(g.out)) and real[n] == g.out[n]: n += 1
    print('first mismatch index:', n, '| real:', real[n:n + 2], '| proto:', g.out[n:n + 2])
