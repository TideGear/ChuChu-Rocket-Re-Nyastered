"""Diff of the settings pane's touch hit test (port: SettingsPaneItems::hit) against the original's updateMenuItemFromTouchEvent (0xf2b0, press) under Unicorn, for many points."""
import os, random, struct, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_players_probe as P
o = P.o; scr = P.scr
try: o.call(0x34a00, scr)
except Exception: pass
o.write(scr + 0xa7c, bytes([0]))
try: o.call(0x31690, scr)
except Exception: pass
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
rnd = random.Random(3); pts = [(0, 711), (57, 768), (967, 711), (1024, 768), (12, 205), (42, 235), (43, 236), (248, 52), (278, 82), (443, 91), (473, 121), (300, 300), (5, 5)]
pts += [(rnd.randrange(0, 1024), rnd.randrange(0, 768)) for _ in range(40)]
bad = 0
for x, y in pts:
    o.write(scr + 0xa08, struct.pack('<I', 0))
    r = struct.unpack('<i', struct.pack('<I', o.call(0xf2b0, scr, x, y, 0)))[0]
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_HIT='%d,%d' % (x, y), CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip()
    got = int(out)
    if r != got: bad += 1; print('DIFF', (x, y), 'ref', r, 'port', got)
print('points', len(pts), 'mismatches', bad)
