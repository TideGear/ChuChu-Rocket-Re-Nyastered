"""Diff of the settings pane's four list-panel draws (port: SettingsListPanels::draws) against the original (measured uv corners of renderSettingsPane, texture 1024 x 1024 of image 28)."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import struct, hd_players_probe as P
o = P.o; scr = P.scr
try: o.call(0x34a00, scr)
except Exception: pass
o.write(scr + 0xa7c, bytes([0]))
try: o.call(0x31690, scr)
except Exception: pass
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP
rec = []
o.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: rec.append([struct.unpack('<f', bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_SP) + 4 * k, 4)))[0] for k in range(4)]), begin=0xac4c, end=0xac4e)
try: o.call(0x2fa70, scr)
except Exception: pass
dest = [(12, 57, 300, 186), (267, 137, 268, 201), (237, 135, 40, 108), (12, 205, 301, 39)]
ref = []
for (u0, v0, u1, v1), (x, y, w, h) in zip(rec[:4], dest):
    ref.append((round(u0 * 1024), round(v0 * 1024), round((u1 - u0) * 1024), round((v1 - v0) * 1024), x, y, w, h))
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_PANELS='1', CCR_HEADLESS='1'), capture_output=True, text=True).stdout.split('\n')
got = [tuple(int(v) for v in l.split()) for l in out if l.strip()]
bad = sum(0 if r == g else 1 for r, g in zip(ref, got)) + abs(len(ref) - len(got))
print('panels ref', len(ref), 'got', len(got), 'mismatches', bad)
for r, g in zip(ref, got):
    if r != g: print('DIFF', r, g)
