"""Diff of the port's Options > Sounds drawing against the original (Unicorn oracle, tools/oracle/hd_options_probe.py): same textures, rects and strings at the same positions.
usage: options_diff.py [ccr.exe]"""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_options_probe as P
exe = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'game', 'ccr.exe'); bad = 0
for (m, s, d) in [(128, 255, 2), (200, 17, 0), (200, 17, 1), (255, 0, 0), (0, 255, 1), (75, 100, 1), (1, 254, 0)]:
    o, log, scr, ad = P.make(m, s, 1, d); ref = P.run(o, log, scr)
    exp = []
    for l in ref:
        if l[0] == 'RenderTexture': exp.append('RT %.1f %.1f %d %d %.1f' % (l[1], l[2], round(l[3]), round(l[4]), l[5]))
        elif l[0] == 'RenderFilledRect': exp.append('FR %.1f %.1f %.1f %d' % (l[1], l[2], l[3], round(l[4])))
        else: exp.append('PS %s %.1f %.1f %.1f %d' % (l[1], l[2], l[3], l[8], l[9]))
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_SNDTEST='%d,%d,%d' % (m, s, d), CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
    exp = [e.replace('RT ', 'RT ') for e in exp]
    ok = exp == out; bad += 0 if ok else 1; print('OK ' if ok else 'DIFF', (m, s, d), len(exp), 'calls')
    if not ok:
        for i in range(max(len(exp), len(out))):
            x = exp[i] if i < len(exp) else None; y = out[i] if i < len(out) else None
            if x != y: print('   ref', x, '\n   got', y); break
print('mismatches:', bad)
