"""Dump the SmpTsk pool (slot index, group byte, exe function) at chosen frames of a CPU battle."""
import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed = int(sys.argv[1]), int(sys.argv[2]); frames = [int(x) for x in sys.argv[3].split(',')]; levels = [int(x) for x in sys.argv[4].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
pool = BASE + ((lit(0x3db84) + 0x3db60 + 4 - G) & 0xffffffff)
def dump(tag):
    rows = []
    for i in range(1024):
        s = pool + i * 0x58; b = o.read(s, 0x58)
        fn = struct.unpack_from('<I', b, 0x40)[0]
        if fn: rows.append((i, b[2], (fn - BASE + G) & ~1, struct.unpack_from('<f', b, 0x14)[0], struct.unpack_from('<f', b, 0x1c)[0]))
    print(tag, len(rows)); 
    for r in rows: print('  slot %3d grp %d fn %#x pos (%.2f,%.2f)' % r)
for f in range(1, max(frames) + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    if f in frames: dump('after frame %d' % f)
