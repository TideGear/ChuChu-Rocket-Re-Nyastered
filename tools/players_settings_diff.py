"""Diff of the settings pane's ten menu item rectangles (port: SettingsPaneItems::layout) against the original (initSettingsPaneMenuItems, read under Unicorn with the constructor run first)."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import struct, hd_players_probe as P
o = P.o; scr = P.scr
try: o.call(0x34a00, scr)
except Exception: pass
o.write(scr + 0xa7c, bytes([0]))
try: o.call(0x31690, scr)
except Exception: pass   # the later scroll-state code faults; the item rectangles are written before it
ref = []
for i in range(10):
    base = scr + 8 + 0x28 * i
    ref.append(tuple(struct.unpack('<i', o.read(base + off, 4))[0] for off in (0x10, 0x14, 0x18, 0x1c)))
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_SETTINGSRECTS='1', CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
got = [tuple(int(v) for v in l.split()[1:]) for l in out]
bad = 0
for i, (r, g) in enumerate(zip(ref, got)):
    ok = r == g; bad += 0 if ok else 1
    print('OK ' if ok else 'DIFF', i, r, g)
print('items', len(ref), 'mismatches', bad)
