import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, upto = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]); levels = [int(x) for x in sys.argv[4].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
base = (lit(0x2de50) + 0x2de74 - G + 0x30) & 0xffffffff
for f in range(1, upto + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
w = struct.unpack('<108I', o.read(BASE + base, 432))
for y in range(9): print(' '.join('%05x' % (w[y * 12 + x] & 0xfffff) for x in range(12)))
