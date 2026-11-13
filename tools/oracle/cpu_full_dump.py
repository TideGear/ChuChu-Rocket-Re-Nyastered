"""Per-frame state dump of a CPU battle in the emulated original, for first-divergence search (compare with cpu_test FULLDUMP via state_cmp.py).
Lines: 'H f <108 heat values>' and 'C f p st timer cnt cx cy tx ty dir'."""
import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, upto, outp = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]; levels = [int(x) for x in sys.argv[5].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
tasks = []
def cb(uc, a, s, u):
    t = uc.reg_read(UC_ARM_REG_R0)
    if t not in tasks: tasks.append(t)
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x29d6e - G, end=BASE + 0x29d6e - G + 2)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
heat = o.u32(BASE + 0x79498 + 0x564 - G)
out = open(outp, 'w')
for f in range(1, upto + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    out.write('H %d %s\n' % (f, ' '.join(map(str, struct.unpack('<108h', o.read(heat, 216))))))
    for t in tasks:
        b = o.read(t, 0x34)
        out.write('C %d %d %d %d %d %d %d %d %d %d\n' % (f, b[0x2c], b[0], struct.unpack_from('<i', b, 4)[0], struct.unpack_from('<H', b, 0x30)[0], *struct.unpack_from('<hh', b, 0x10), b[0x2d], b[0x2e], b[0x2f]))
out.close()
