import sys, os, collections
sys.path.insert(0, r'c:\Dev\ChuChu Rocket\tools')
import stage_registry as R
DLC = r'c:\Dev\ChuChu Rocket\Original Game Files\Dreamcast\DLC'
def walls_mobile(s):
    return tuple(s[0x6c + 25 * i + c] for i in range(10) for c in range(12)) + tuple(s[0x6c + 25 * i + 12 + c] for i in range(9) for c in range(13))
def walls_dlc(slot):
    L = [slot[r * 25:(r + 1) * 25] for r in range(19)]
    return tuple(L[2 * i][2 * c + 1] for i in range(10) for c in range(12)) + tuple(L[2 * i + 1][2 * c] for i in range(9) for c in range(13))
def dlc_slots(name):
    p = open(os.path.join(DLC, name + '.VMS'), 'rb').read()[640:]
    n = (len(p) + 1535) // 1536
    return [p[k * 1536:(k + 1) * 1536] for k in range(n) if len(p[k * 1536:(k + 1) * 1536]) >= 475]
if __name__ == '__main__':
    mob = {}
    for rec, st in R.groups_in(os.path.join(R.ROOT, R.SOURCES['ios_1.1.2'])):
        for k, s in enumerate(st): mob.setdefault(walls_mobile(s), []).append((rec, k, R.title(s)))
    print('mobile 1.1.2 distinct wall layouts:', len(mob), 'of 524')
    for n in ('PuzzleP', 'DEPuzzle'):
        slots = dlc_slots(n); hit = 0
        for k, sl in enumerate(slots):
            m = mob.get(walls_dlc(sl))
            if m: hit += 1; print('  %s[%d] walls == mobile rec%d[%d] %r' % (n, k, m[0][0], m[0][1], m[0][2]))
        print(n, 'slots', len(slots), 'matching mobile walls', hit)
