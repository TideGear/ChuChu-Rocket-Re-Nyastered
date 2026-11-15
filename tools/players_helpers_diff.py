"""Diff of the players-pane helpers (mutexPlayer, repositionSliderPanelItems) between the port and the original under Unicorn (tools/oracle/hd_players_helpers_probe.py)."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_players_helpers_probe as H
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe'); bad = 0
def run(arg):
    return subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_PLAYHELP=arg, CCR_HEADLESS='1'), capture_output=True, text=True).stdout.split()
for a, b, v in ((0, 1, 0), (0, 1, 1), (2, 3, 1), (4, 5, 0), (6, 7, 1)):
    ref = list(H.mutex(a, b, v)); got = [int(x) for x in run('m:%d,%d,%d' % (a, b, v))]
    ok = ref == got; bad += 0 if ok else 1; print('OK ' if ok else 'DIFF', 'mutex', (a, b, v), ref, got)
for x, y, hs in ((100, 200, [30, 40, 50, 60, 70]), (7, -3, [10, 10, 10, 10, 10]), (0, 0, [0, 0, 0, 0, 0])):
    _, rows = H.reposition(x, y, hs); ref = [v for r in rows for v in r]
    got = [int(t) for t in run('r:%d,%d,%s' % (x, y, ','.join(str(h) for h in hs)))][2:]
    ok = ref == got; bad += 0 if ok else 1; print('OK ' if ok else 'DIFF', 'reposition', (x, y), ref == got)
print('mismatches', bad)
