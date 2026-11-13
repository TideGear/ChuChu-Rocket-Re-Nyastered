import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, f0, f1 = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]); levels = [int(x) for x in sys.argv[5].split(',')]
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
tasks = {}
def cb(uc, a, s, u):
    t = uc.reg_read(UC_ARM_REG_R0); tasks.setdefault(len(tasks) if t not in tasks.values() else None, t) if False else None
    if t not in tasks.values(): tasks[len(tasks)] = t
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x29d6e - G, end=BASE + 0x29d6e - G + 2)
for p, lv in enumerate(levels):
    if lv >= 0: gcall(0x29d50, p, lv)
lcg = (lit(0x29da4) + 0x29d60) & 0xffffffff
def dump(t):
    b = o.read(t, 0x34); return 'st=%d timer=%d flags=%#x cur=(%d,%d) pl=%d tgt=(%d,%d) dir=%d cnt=%d' % (b[0], struct.unpack_from('<i', b, 4)[0], struct.unpack_from('<I', b, 8)[0], *struct.unpack_from('<hh', b, 0x10), b[0x2c], b[0x2d], b[0x2e], b[0x2f], struct.unpack_from('<H', b, 0x30)[0])
for f in range(1, f1 + 1):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    if f >= f0:
        for k, t in tasks.items(): print('f%d' % f, dump(t))
