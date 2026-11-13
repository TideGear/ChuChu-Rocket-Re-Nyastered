"""Differential test: original SC_AddScore / SC_CatHasCome vs the port, random operation sequences."""
import sys, struct, random
sys.path.insert(0, '.')
from full_stage import *
init_tables() if False else None
gcall(0x3d904)                                   # SmpTskInit (allocator state)
gcall(0x3d2bc)                                   # SC_InitScoreBoard
# score array pointer: [ (0x3c132 + 0x3d364 + 0x3a4) ] in ghidra space
pa = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
arr = o.u32(BASE + pa)
def read(): return list(struct.unpack('<16i', o.read(arr, 64)))
def trunc_div(a, b): q = abs(a) // abs(b); return q if (a >= 0) == (b > 0) else -q
class Port:
    def __init__(self): self.s = [0] * 16
    def add(self, p, d):
        s = self.s
        s[p] += d
        if s[p] < 0: s[p] = 0
        t = (p & 1) + 8; s[t] += d
        if s[t] < 0: s[t] = 0
        if s[p] > 999: s[p] = 999
        if s[t] > 999: s[t] = 999
    def cat(self, p):
        s = self.s
        s[p] += trunc_div(s[p] + 2, -3)
        if s[p] < 0: s[p] = 0
        t = (p & 1) + 8; s[t] += trunc_div(s[t] + 2, -3)
        if s[t] < 0: s[t] = 0
        c = (p & 1) + 12; s[c] -= 1
        if s[c] < 0: s[c] = 0
if __name__ == '__main__':
    rng = random.Random(5); port = Port(); bad = 0; n = 3000
    port.s = read()
    print('initial array:', port.s)
    for i in range(n):
        p = rng.randrange(4)
        if rng.random() < 0.8:
            d = rng.choice([1, 1, 1, 50, 50, 1, -3, 10]); gcall(0x3d2f0, p, d & 0xffffffff); port.add(p, d)
        else:
            gcall(0x3d354, p); port.cat(p)
        IDX = (0, 1, 2, 3, 8, 9, 12, 13)
        if [read()[k] for k in IDX] != [port.s[k] for k in IDX]:
            bad += 1
            if bad <= 3: print('diverged at op', i, [read()[k] for k in IDX], [port.s[k] for k in IDX])
            port.s = read()
    print('operations', n, 'divergences', bad)
