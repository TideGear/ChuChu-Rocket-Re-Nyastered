"""Record Core::adjustAngle / Core::diffAngle results of the ORIGINAL code (Android 1.15 libccrjni.so under Unicorn) for random inputs -> local/testdata/angle_golden.txt.
Lines: cur target step adjust diff.   usage: make_angle_golden.py [count]"""
import random, sys
sys.path.insert(0, '.')
from cat_probe import *
n = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
rng = random.Random(9); out = open(r'C:\Dev\ChuChu Rocket\local\testdata\angle_golden.txt', 'w')
steps = [682, 1024, 2048, 2730, 4096, 5461, 8192]
for i in range(n):
    cur = rng.randrange(0, 1 << 16); tgt = (rng.randrange(4) << 14) if i % 2 else rng.randrange(0, 1 << 16); st = rng.choice(steps)
    a = gcall(0x2bc18, cur, tgt, st)
    d = gcall(0x2bc50, cur, tgt)
    out.write('%d %d %d %d %d\n' % (cur, tgt, st, a & 0xffffffff, d & 0xffffffff))
out.close(); print('wrote', n, 'cases')
