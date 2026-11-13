"""SC_AddScore / SC_CatHasCome on the iOS builds vs the port (Scoreboard semantics), random operation sequences. usage: ios_score_diff.py <build> [ops]"""
import random, struct, sys
sys.path.insert(0, '.')
from ios_cpu_run import *
from unicorn import UC_HOOK_MEM_WRITE
def trunc_div(a, b): q = abs(a) // abs(b); return q if (a >= 0) == (b > 0) else -q
class Port:
    def __init__(self): self.s = [0] * 16
    def add(self, p, d):
        s = self.s; s[p] += d
        if s[p] < 0: s[p] = 0
        t = (p & 1) + 8; s[t] += d
        if s[t] < 0: s[t] = 0
        if s[p] > 999: s[p] = 999
        if s[t] > 999: s[t] = 999
    def cat(self, p):
        s = self.s; s[p] += trunc_div(s[p] + 2, -3)
        if s[p] < 0: s[p] = 0
        t = (p & 1) + 8; s[t] += trunc_div(s[t] + 2, -3)
        if s[t] < 0: s[t] = 0
        c = (p & 1) + 12; s[c] -= 1
        if s[c] < 0: s[c] = 0
build = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
o = make(build); init_trig(o)
g(o, 'SmpTskInit'); g(o, 'SC_InitScoreBoard')
wr = []
h = o.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, acc, addr, size, val, u: wr.append(addr))
g(o, 'SC_AddScore', 0, 7); o.uc.hook_del(h)
base = min(wr) - 0                       # score[0] is the first word written
# find the array start: score[p] at base + 4p (player 0 first)
read = lambda: list(struct.unpack('<16i', o.read(base, 64)))
port = Port(); port.s = read(); port.s = [0] * 16; g(o, 'SC_InitScoreBoard'); port.s = read()
rng = random.Random(5); bad = 0
for i in range(n):
    p = rng.randrange(4)
    if rng.random() < 0.8:
        d = rng.choice([1, 1, 1, 50, 50, 1, -3, 10]); g(o, 'SC_AddScore', p, d & 0xffffffff); port.add(p, d)
    else: g(o, 'SC_CatHasCome', p); port.cat(p)
    IDX = (0, 1, 2, 3, 8, 9, 12, 13)
    if [read()[k] for k in IDX] != [port.s[k] for k in IDX]:
        bad += 1
        if bad <= 3: print('diverged at op', i, [read()[k] for k in IDX], [port.s[k] for k in IDX])
        port.s = read()
print(build, 'operations', n, 'divergences', bad)
