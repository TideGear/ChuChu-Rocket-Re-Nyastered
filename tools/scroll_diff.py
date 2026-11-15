"""Diff of the settings pane's list scroll (port: SettingsListScroll, drag + release) against the original's handleSettingsPaneInput (0x32d24) under Unicorn (tools/oracle/hd_players_probe.py)."""
import os, struct, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_players_probe as P
o = P.o; scr = P.scr
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
def ref_case(offset0, last_y, y, row=40.0, thr=0.5, rows=10):
    try: o.call(0x34a00, scr)
    except Exception: pass
    o.write(scr + 0xa7c, bytes([0]))
    try: o.call(0x31690, scr)
    except Exception: pass
    f = lambda v: struct.pack('<f', v)
    o.write(scr + 0xa80, f(row)); o.write(scr + 0xa84, f(thr)); o.write(scr + 0xa34, struct.pack('<i', rows))
    o.write(scr + 0xab0, f(offset0)); o.write(scr + 0xab8, struct.pack('<i', 0)); o.write(scr + 0xabc, struct.pack('<i', last_y))
    try: o.call(0x32d24, scr, 100, y, 1)
    except Exception: pass
    drag = struct.unpack('<f', o.read(scr + 0xab0, 4))[0]
    try: o.call(0x32d24, scr, 100, y, 2)
    except Exception: pass   # the preview draw after the snap faults in the probe; the offset and row are written before it
    rel = struct.unpack('<f', o.read(scr + 0xab0, 4))[0]; idx = struct.unpack('<i', o.read(scr + 0x101c, 4))[0]
    return round(drag), round(rel), idx
bad = 0
for case in ((0.0, 300, 210), (-90.0, 210, 210), (-50.0, 100, 160), (0.0, 100, 400)):
    ref = ref_case(*case)
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_SCROLL='%d,%d,%d' % case, CCR_HEADLESS='1'), capture_output=True, text=True).stdout.split()
    got = tuple(int(v) for v in out)
    ok = got == ref; bad += 0 if ok else 1
    print('OK ' if ok else 'DIFF', case, 'ref', ref, 'port', got)
print('mismatches', bad)
