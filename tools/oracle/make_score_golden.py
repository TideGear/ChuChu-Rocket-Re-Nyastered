import sys, random
sys.path.insert(0, '.')
import score_diff as S
from score_diff import *
rng = random.Random(9); out = open(r'C:\Dev\ChuChu Rocket\local\testdata\score_golden.txt', 'w')
for i in range(1500):
    p = rng.randrange(4)
    if rng.random() < 0.8:
        d = rng.choice([1, 1, 1, 50, 50, 1, -3, 10]); gcall(0x3d2f0, p, d & 0xffffffff); out.write('A %d %d\n' % (p, d))
    else:
        gcall(0x3d354, p); out.write('C %d\n' % p)
    r = read(); out.write('R ' + ' '.join(str(r[k]) for k in (0, 1, 2, 3, 8, 9, 12, 13)) + '\n')
out.close(); print('written')
