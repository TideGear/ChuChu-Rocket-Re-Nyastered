import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, F = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]); levels = [int(x) for x in sys.argv[4].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
ent = BASE + ((lit(0x299a4) + 0x29962 - G) & 0xffffffff)
for f in range(1, F + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60)
    if f == F:
        for i in range(60):
            e = o.read(ent + 24 * i, 24); tp, ty = struct.unpack_from('<I', e, 0)[0], e[4]
            if tp == 0: print('entry', i, 'NULL -> end'); break
            t = o.read(tp, 0x58); fn = struct.unpack_from('<I', t, 0x40)[0]
            print('entry %2d type %d task %#x live=%d mtype=%d grid=(%d,%d)' % (i, ty, tp, fn != 0, struct.unpack_from('<i', t, 8)[0], *struct.unpack_from('<hh', t, 0x10)))
    step('SmpColAnalyze', 0x29b1c)
