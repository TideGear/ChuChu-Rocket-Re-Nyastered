"""Differential test of the Dreamcast CPU-player task (0x8C01322E in 1ST_READ.BIN, run unmodified in the SH-4 interpreter) against the port's CpuPlayer::step.
Input: cases written by game/tests/cpu_dc_gen.cpp (real battle states + the port's decision). The tables the Dreamcast code reads are filled from each case:
collision words 0x8C1AE6FC (int32 per cell), heat map 0x8C1D393C (int16 per cell), rocket cells 0x8C1AF208 (two int16 per owner, 4 bytes stride), ranks 0x8C1AF510, global time 0x8C1AE8D8,
game type 0x8C1AE8B8, game flag 0x8C1AE8C0 (non-zero: running), LCG state 0x8C186B34. Task layout: state byte +0, timer +4, level flags +8, player byte +44, target x/y/dir bytes +45/+46/+47, counter int16 +48.
usage: dc_cpu_decide.py <cases.txt>"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
from sh4 import SH4
root = os.path.join(os.path.dirname(__file__), '../..')
d = open(os.path.join(root, 'local/cache/assets/dreamcast/files/1ST_READ.BIN'), 'rb').read()
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, 'local/testdata/cpu_dc_cases.txt')
T = 0x8c7f0000
branches = {}
m = SH4(); m.load(0x8C010000, d); n = bad = 0; found_cases = 0; first = []
for line in open(path):
    a, b = line.split('|'); v = [int(x) for x in a.split()]; o = [int(x) for x in b.split()]
    gtype, gtime, player, flags, count, timer, lcg = v[:7]; rank = v[7:11]; rocket = v[11:19]; coll = v[19:19 + 108]; heat = v[19 + 108:19 + 216]
    for i, w in enumerate(coll): m.wr32(0x8c1ae6fc + 4 * i, w)
    for i, h in enumerate(heat): m.wr16(0x8c1d393c + 2 * i, h & 0xffff)
    for p in range(5):
        x, y = (rocket[2 * p], rocket[2 * p + 1]) if p < 4 else (0, 0)
        m.wr16(0x8c1af208 + 4 * p, x & 0xffff); m.wr16(0x8c1af208 + 4 * p + 2, y & 0xffff)
    for p in range(4): m.wr32(0x8c1af510 + 4 * p, rank[p] & 0xffffffff)
    m.wr32(0x8c1ae8d8, gtime); m.wr32(0x8c1ae8b8, gtype); m.wr32(0x8c1ae8c0, 1); m.wr32(0x8c186b34, lcg)
    for k in range(0x40): m.wr8(T + k, 0)
    m.wr8(T, 0); m.wr32(T + 4, timer); m.wr32(T + 8, flags); m.wr8(T + 44, player); m.wr16(T + 48, count)
    m.call(0x8c01322e, T)
    st = m.rd8(T); tm = m.rd32(T + 4); cnt = m.rd16(T + 48); tx = m.rd8(T + 45); ty = m.rd8(T + 46); dr = m.rd8(T + 47); lg2 = m.rd32(0x8c186b34)
    pst, ptm, pcnt, ptx, pty, pdir, plg, pbr = o
    ok = st == pst and tm == ptm and cnt == pcnt and lg2 == plg
    if ok and pst == 1: ok = (tx, ty, dr) == (ptx, pty, pdir)
    n += 1; found_cases += pst == 1
    if not ok:
        bad += 1
        if len(first) < 5: first.append((n, 'dc', (st, tm, cnt, tx, ty, dr, hex(lg2)), 'port', (pst, ptm, pcnt, ptx, pty, pdir, hex(plg)), 'flags', hex(flags), 'player', player, 'gtype', gtype, 'port branch', pbr))
        branches[pbr] = branches.get(pbr, 0) + 1
for f in first: print('MISMATCH', f)
print('mismatches by port branch (1 defend, 2 attack enemy, 3 attack own, 4 random):', branches)
print('dreamcast CPU step vs port: %d cases (%d with a target chosen), %d different' % (n, found_cases, bad))
