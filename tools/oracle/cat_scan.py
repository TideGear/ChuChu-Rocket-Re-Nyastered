import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, upto = 4, 1068, int(sys.argv[1])
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
rng = random.Random(seed); pend = {}
for f in range(10, 3000, 40): pend[f] = (rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4))
pt = o.heap_ptr; o.heap_ptr += 16
H0 = o.heap_base if hasattr(o, 'heap_base') else None
for f in range(1, upto + 1):
    B.frame_no[0] = f
    if f in pend:
        pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    if f in (200, 400, 600, 640, 660, 680, 682):
        # scan the heap for task-like structs: x at +0x14, z at +0x1c within the field
        found = []
        lo, hi = o.heap_ptr - 0x400000, o.heap_ptr
        buf = o.read(lo, hi - lo)
        for i in range(0, len(buf) - 0x20, 4):
            x, z = struct.unpack_from('<f', buf, i + 0x14)[0], struct.unpack_from('<f', buf, i + 0x1c)[0]
            if 0 < x < 180 and 0 < z < 135 and struct.unpack_from('<f', buf, i + 0x18)[0] == 0.0 and struct.unpack_from('<I', buf, i)[0] in (0,) and abs(x - 82.5) < 40:
                found.append((i, round(x, 1), round(z, 1)))
        print(f, len(found), found[:8])
