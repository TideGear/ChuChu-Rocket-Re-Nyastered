"""Differential test: Dreamcast SC_AddScore (chunk @0x8C01E6A0) and SC_CatHasCome (@0x8C01E712) in the SH-4 interpreter vs the port's Scoreboard semantics (game/core/score.hpp)."""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))
from sh4 import SH4
root = os.path.join(os.path.dirname(__file__), '../..')
d = open(os.path.join(root, 'local/cache/assets/dreamcast/files/1ST_READ.BIN'), 'rb').read()
S = 0x8c1af500
class Port:
    def __init__(s): s.p = [0] * 4; s.t = [0] * 2; s.c = [20, 20]
    def add(s, p, dl):
        s.p[p] = max(0, s.p[p] + dl); s.t[p & 1] = max(0, s.t[p & 1] + dl); s.p[p] = min(s.p[p], 999); s.t[p & 1] = min(s.t[p & 1], 999)
    def cat(s, p):
        s.p[p] = max(0, s.p[p] - (s.p[p] + 2) // 3); s.t[p & 1] = max(0, s.t[p & 1] - (s.t[p & 1] + 2) // 3); s.c[p & 1] = max(0, s.c[p & 1] - 1)
m = SH4(); m.load(0x8C010000, d); m.hooks[0x8c01e420 & 0x1fffffff] = lambda m: None
rng = random.Random(3); N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000; bad = 0; port = Port()
for k in range(12): m.wr32(S + 4 * k, 0)
m.wr32(S + 48, 20); m.wr32(S + 52, 20)
def state(): return ([m.rd32(S + 4 * i) for i in range(4)], [m.rd32(S + 32 + 4 * i) for i in range(2)], [m.rd32(S + 48 + 4 * i) for i in range(2)])
for i in range(N):
    p = rng.randrange(4)
    if rng.random() < 0.7:
        dl = rng.choice([1, 1, 1, 50, 50, -3, 10, 25, -50]); m.call(0x8c01e6a0, p, dl & 0xffffffff); port.add(p, dl)
    else:
        m.call(0x8c01e712, p); port.cat(p)
    # the unrelated hook registers: the chunk's own registers r6 (array base) are loaded by the chunk itself
    if os.environ.get("V"): print(i, p, state(), (port.p, port.t, port.c))
    if state() != (port.p, port.t, port.c if True else None):
        bad += 1
        if bad < 4: print('MISMATCH op', i, state(), (port.p, port.t, port.c))
        break
print('dreamcast score ops: %d, %s' % (i + 1, 'identical' if not bad else 'DIFFERENT'))
