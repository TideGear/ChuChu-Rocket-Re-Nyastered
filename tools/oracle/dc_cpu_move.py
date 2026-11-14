"""Differential test of the second half of the Dreamcast CPU task (state 1: cursor movement and arrow placement) in the SH-4 interpreter vs the port's CpuPlayer::step.
The unmodified task function 0x8C01322E runs; only its two external calls are observed: CU_CursorControlByParameter 0x8C014DCC (stub: returns 1 = cursor free) and CU_PutArrow 0x8C014E78 (records player and direction;
the arrow cell is the task's cursor position at that moment). Cases come from game/tests/cpu_dc_move_gen.cpp. usage: dc_cpu_move.py <cases.txt>"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from sh4 import SH4
root = os.path.join(os.path.dirname(__file__), '../..')
d = open(os.path.join(root, 'local/cache/assets/dreamcast/files/1ST_READ.BIN'), 'rb').read()
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, 'local/testdata/cpu_dc_move_cases.txt')
T = 0x8c7f0000; m = SH4(); m.load(0x8C010000, d); rec = {'put': None}
def cursor_ctl(mm): mm.r[0] = 1
def put_arrow(mm): rec['put'] = (mm.r[4] & 0xff, mm.r[5] & 0xff)
m.hooks[0x8c014dcc & 0x1fffffff] = cursor_ctl; m.hooks[0x8c014e78 & 0x1fffffff] = put_arrow
n = bad = placed = 0; first = []
for line in open(path):
    a, b = line.split('|'); v = [int(x) for x in a.split()]; o = [int(x) for x in b.split()]
    player, cx, cy, tx, ty, dr, timer, count = v; pst, ptm, pcnt, pcx, pcy, pput, ppx, ppy, ppd = o
    m.wr32(0x8c1ae8d8, 2); m.wr32(0x8c1ae8c0, 1); m.wr32(0x8c1ae8b8, 0)      # global time (even), game flag, game type
    for k in range(0x40): m.wr8(T + k, 0)
    m.wr8(T, 1); m.wr32(T + 4, timer); m.wr32(T + 8, 0x55); m.wr16(T + 16, cx); m.wr16(T + 18, cy); m.wr8(T + 44, player); m.wr8(T + 45, tx); m.wr8(T + 46, ty); m.wr8(T + 47, dr); m.wr16(T + 48, count)
    rec['put'] = None; m.call(0x8c01322e, T)
    st = m.rd8(T); tm = m.rd32(T + 4); cnt = m.rd16(T + 48); gx = m.rd16(T + 16); gy = m.rd16(T + 18)
    put = rec['put'] is not None
    ok = st == pst and tm == ptm and cnt == pcnt and gx == pcx and gy == pcy and put == bool(pput)
    if ok and put: ok = rec['put'] == (player, ppd) and (gx, gy) == (ppx, ppy)
    n += 1; placed += put
    if not ok:
        bad += 1
        if len(first) < 5: first.append((n, v, 'dc', (st, tm, cnt, gx, gy, rec['put']), 'port', o))
for f in first: print('MISMATCH', f)
print('dreamcast CPU cursor/arrow stage vs port: %d cases (%d placed an arrow), %d different' % (n, placed, bad))
