import sys, struct, collections, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_MEM_WRITE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
tiles, walls = ascii_stage(d[5 * 477:5 * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, 1085)
gcall(0x3d2bc)
pa = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff; arr = o.u32(BASE + pa)
w = collections.Counter(); log = []
def cb(uc, access, addr, size, val, u):
    pc = uc.reg_read(UC_ARM_REG_PC) - BASE + G
    w[hex(pc & ~1)] += 1; log.append((B.frame_no[0], (addr - arr) // 4, val & 0xffffffff, hex(pc & ~1)))
o.uc.hook_add(UC_HOOK_MEM_WRITE, cb, begin=arr + 16, end=arr + 32)
rng = random.Random(1085); pend = {}
for f in range(10, 3000, 40): pend[f] = (rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4))
pt = o.heap_ptr; o.heap_ptr += 16
for f in range(1, 2500):
    B.frame_no[0] = f
    if f in pend:
        pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
print(w.most_common(5)); print(log[:12])
