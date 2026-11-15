"""Diff of the port's How to Play screen (topic list and pages) against the original under Unicorn (tools/oracle/hd_help_probe.py): textures, rects and strings with positions."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_help_probe as P
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe'); bad = 0; cnts = {0: 6, 1: 2, 2: 2, 3: 1, 4: 1, 5: 1}
cases = [(-1, 0)] + [(t, p) for t in range(6) for p in range(cnts[t])]
for t, p in cases:
    if t < 0: P.state(-1, 0, -1, 0.0, 0, 0, 0, 6)
    else: P.state(t, p, 1, 0.0, 0, 0, 0, cnts[t])
    exp = []
    for l in P.render():
        if l[0] == 'RenderTexture': exp.append('RT %.1f %.1f %d %d' % (l[1], l[2], round(l[3]), round(l[4])))
        elif l[0] == 'RenderFilledRect': exp.append('FR %d %d %d %d' % (l[1], l[2], l[3], l[4]))
        else: exp.append('PS %s %.1f %.1f %.3f %d' % (l[1].replace(chr(10), '|'), l[2], l[3], l[8], l[9]))
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_HELPTEST='%d,%d' % (t, p), CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
    ok = exp == out; bad += 0 if ok else 1; print('OK ' if ok else 'DIFF', (t, p), len(exp))
    if not ok:
        for i in range(max(len(exp), len(out))):
            a = exp[i] if i < len(exp) else None; b = out[i] if i < len(out) else None
            if a != b: print('  ref', a, '\n  got', b); break
print('mismatches', bad)
