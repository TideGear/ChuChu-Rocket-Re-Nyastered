"""Diff of the battle setup players pane (ported part) against the original's renderPlayersPane under Unicorn (tools/oracle/hd_players_probe.py), default state (all human).
Excluded and reported separately: the two bottom sheets (y 287), Host / Join, the back button and the second corner button, and the level text ('Weak') (not traced yet)."""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_players_probe as P
o = P.o; env = P.env
LV = [int(x) for x in os.environ.get('LEVELS', '0,0,0,0').split(',')]
for i, v in enumerate(LV[1:]): o.write(P.scr + 0xd4c + 4 * i, __import__('struct').pack('<i', v))
o.call(0x32194, P.scr); env.log.clear()
for i, v in enumerate(LV[1:]): o.write(P.scr + 0xd4c + 4 * i, __import__('struct').pack('<i', v))
o.call(0x33514, P.scr)
exp = []
for l in env.log:
    if l[0] == 'RenderTexture':
        if l[1] == 0.0 and l[2] == 0.0 and False: continue
        exp.append('RT %.1f %.1f %d %d' % (l[1], l[2], round(l[3]), round(l[4])))
    elif l[0] == 'PrintString':
        if l[1] in ('Host', 'Join'): continue
        exp.append('PS %s %.1f %.1f %.3f 0' % (l[1], l[2], l[3], l[8]))
exe = os.path.join(ROOT, 'build', 'game', 'ccr.exe')
out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_PLAYERSTEST='1,1,1,1;' + os.environ.get('LEVELS', '0,0,0,0'), CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
got = [' '.join(l.split(' ')[:5]) if l.startswith('RT') else l for l in out]
got = ['RT %s %s %s %s' % tuple(l.split(' ')[1:5]) if l.startswith('RT') else l for l in got]
exp2 = [e for e in exp]
ok = exp2 == got
print('OK' if ok else 'DIFF', len(exp2), len(got))
if not ok:
    for i in range(max(len(exp2), len(got))):
        a = exp2[i] if i < len(exp2) else None; b = got[i] if i < len(got) else None
        if a != b: print(' ref', a, '\n got', b); break
