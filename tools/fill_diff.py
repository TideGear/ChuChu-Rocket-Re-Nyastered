"""Diff of the settings pane's filled rectangle (port: SettingsListFill) against the original's _BHLib_RenderFilledRect call in renderSettingsPane (read via the probe's logged fill, tools/oracle/hd_players_probe.py; env RenderFilledRect hook)."""
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
ref = [tuple(int(v) for v in l[1:9]) for l in env.log if l[0] == 'RenderFilledRect'][:1]
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_FILL='1', CCR_HEADLESS='1'), capture_output=True, text=True).stdout.split()
got = tuple(int(v) for v in out)
print('fill ref', ref, 'got', got, 'OK' if ref and ref[0] == got else 'DIFF')
