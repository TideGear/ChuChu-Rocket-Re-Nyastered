"""Diff of the port's Render::drawBubble against the original (Unicorn oracle, tools/oracle/hd_bubble_probe.py): same draw calls (images, frames, positions, flags, text lines).
usage: bubble_diff.py [ccr.exe path]"""
import os, subprocess, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools', 'oracle'))
import hd_bubble_probe as P
exe = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'game', 'ccr.exe')
cases = [(512, 300, 400, 'Hello world, this is a test of the bubble', 1, 0, 255), (512, 300, 400, 'Hello world, this is a test of the bubble', 0, 0, 255), (300, 500, 260, 'Learn the basics in the Tutorial to unlock Puzzle, Challenge and Battle modes!', 1, 1, 255),
         (700, 650, 330, 'Enjoy ChuChu Rocket!', 4, 0, 200), (500, 400, 250, 'Up to 4 players!', 5, 1, 255), (480, 330, 300, 'A very long text without any break characters aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 0, 0, 255),
         (200, 200, 100, 'Hi', 1, 0, 255), (800, 700, 500, 'Line one\nLine two\nand line three is a bit longer than the others', 4, 0, 255), (512, 384, 640, 'Select Tutorial to begin!', 0, 0, 255)]
cases.extend((792, 367, 350, 'Learn the basics in the Tutorial to unlock Puzzle, Challenge and Battle modes!', 1, frame, 255)
             for frame in (0, 1))
o, log, _ = P.make(); bad = 0
for c in cases:
    ref = P.bubble(o, log, *c)
    out = subprocess.run([exe, os.path.join(ROOT, 'local', 'cache', 'assets')], env=dict(os.environ, CCR_BUBBLE='%d,%d,%d,%d,%d,%d|%s' % (c[0], c[1], c[2], c[4], c[5], c[6], c[3]), CCR_HEADLESS='1'), capture_output=True, text=True).stdout.strip().splitlines()
    def norm(l):
        if l[0] == 'drawImage': return ('drawImage', l[1], l[2], round(l[3], 1), round(l[4], 1), l[5], round(l[6], 3), l[7])
        return ('printString', l[1], round(l[2], 1), round(l[3], 3), l[4], l[5], l[6], l[7], round(l[8], 3), l[9], l[10], l[11])
    def parse(s):
        t = s.split(' ')
        if t[0] == 'drawImage': return ('drawImage', int(t[1]), int(t[2]), round(float(t[3]), 1), round(float(t[4]), 1), int(t[5]), round(float(t[6]), 3), int(t[7]))
        txt = ' '.join(t[1:-10]); r = t[-10:]
        return ('printString', txt, round(float(r[0]), 1), round(float(r[1]), 3), int(r[2]), int(r[3]), int(r[4]), int(r[5]), round(float(r[6]), 3), int(r[7]), int(r[8]), int(r[9]))
    a = [norm(l) for l in ref]; b = [parse(s) for s in out]
    ok = a == b; bad += 0 if ok else 1
    print('OK ' if ok else 'DIFF', c[:3], c[4:], len(a), 'calls')
    if not ok:
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else None; y = b[i] if i < len(b) else None
            if x != y: print('   ref', x, '\n   got', y); break
print('mismatches:', bad)
sys.exit(1 if bad else 0)
