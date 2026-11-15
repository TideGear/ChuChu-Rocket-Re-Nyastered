"""Diff of the settings pane's CPU level list rows (port: SettingsLevelList::rows, scroll 0) against the original (renderSettingsPane under Unicorn, default state)."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_players_probe as P
o = P.o; scr = P.scr; env = P.env
try: o.call(0x34a00, scr)
except Exception: pass
o.write(scr + 0xa7c, bytes([0]))
try: o.call(0x31690, scr)
except Exception: pass
env.log.clear()
try: o.call(0x2fa70, scr)
except Exception: pass
ref = [(l[1], round(l[2], 1), round(l[3], 1), round(l[8], 3)) for l in env.log if l[0] == 'PrintString' and (l[1].startswith('Level') or l[1] == 'Random')]
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_LEVELROWS='1', CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
got = []
for l in out:
    t = l.split(' ')
    got.append((' '.join(t[1:-3]), round(float(t[-3]), 1), round(float(t[-2]), 1), round(float(t[-1]), 3)))
bad = sum(0 if r == g else 1 for r, g in zip(ref, got)) + abs(len(ref) - len(got))
print('rows ref', len(ref), 'got', len(got), 'mismatches', bad)
for r, g in zip(ref, got):
    if r != g: print('DIFF', r, g); break
