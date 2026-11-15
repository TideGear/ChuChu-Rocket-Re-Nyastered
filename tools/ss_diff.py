"""Diff of the port's stage select screen against the original under Unicorn (tools/oracle/hd_ss_probe.py)."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_ss_probe as P
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe'); bad = 0
cases = [(0, 0, 0), (0, 3, 0x155), (0, 24, 0x1ffffff), (1, 7, 0x0f0f0f), (2, 12, 1), (3, 0, 0x1000000)]
for pg, sl, bits in cases:
    exp = []
    for l in P.render(pg, sl, (bits, 0, 0, 0) if pg == 0 else (0, 0, 0, 0)):
        if l[0] == 'RenderTexture': exp.append('RT %.1f %.1f %d %d' % (l[1], l[2], round(l[3]), round(l[4])))
        elif l[0] == 'RenderFilledRect': exp.append('FR %d %d %d %d' % (l[1], l[2], l[3], l[4]))
        else: exp.append('PS %s %.1f %.1f %.3f %d' % (l[1].replace(chr(10), '|'), l[2], l[3], l[8], l[9]))
    arg = '%d,%d,%d' % (pg, sl, bits if pg == 0 else 0)
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_SSTEST=arg, CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
    ok = exp == out; bad += 0 if ok else 1; print('OK ' if ok else 'DIFF', (pg, sl, hex(bits)), len(exp))
    if not ok:
        for i in range(max(len(exp), len(out))):
            a = exp[i] if i < len(exp) else None; b2 = out[i] if i < len(out) else None
            if a != b2: print('  ref', a, '\n  got', b2); break
print('mismatches', bad)
