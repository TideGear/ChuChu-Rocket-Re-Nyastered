"""Diff of the port's battle banners (BattleCount modes 0..6, Round panel) against the original under Unicorn (tools/oracle/hd_task_probe.py)."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_task_probe as P
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe'); bad = n = 0
def run(kind, m, t):
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_BANNER='%d,%d,%d' % (kind, m, t), CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
    return [tuple(float(x) if '.' in x else int(x) for x in l.split()[1:]) for l in out]
def norm(calls): return [(c[1], c[2], round(c[3], 1), round(c[4], 1), c[5], round(c[6], 2), c[7]) for c in calls]
def norm2(rows): return [(int(r[0]), int(r[1]), round(float(r[2]), 1), round(float(r[3]), 1), int(r[4]), round(float(r[5]), 2), int(r[6])) for r in rows]
for m in range(7):
    for t in (0, 7, P.life(m) // 2, P.life(m) - 1):
        ref = norm(P.count_calls(m, t)); got = norm2(run(0, m, t)); n += 1
        if ref != got: bad += 1; print('DIFF count', m, t, ref, got)
for r in (1, 3, 12, 99):
    for t in (0, 1, 10, 37, 74):
        ref = norm(P.round_calls(r, t)); got = norm2(run(1, r, t)); n += 1
        if ref != got: bad += 1; print('DIFF round', r, t, ref, got)
print('cases', n, 'mismatches', bad)
