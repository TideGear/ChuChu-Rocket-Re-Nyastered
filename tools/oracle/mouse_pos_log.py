"""Per-frame positions of every mouse task at the entry of MO_MouseExe (Android 0x3501c) in the original, for one recorded battle case; used to find the first frame where the port diverges.
usage: mouse_pos_log.py <case idx> <seed> <arrows 0/1> <threshold> <bcd> <frames> <out.txt>   (same setup as make_battle_golden_gt.py: game time 0, roulette threshold table filled with <threshold>)
Output lines: 'F frame' then 'M x z' for each mouse entering MouseExe that frame (in task order)."""
import os, sys, struct, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
idx, seed, use_arrows = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]); THR = float(sys.argv[4]); BCD = int(sys.argv[5], 0); frames = int(sys.argv[6]); OUT = sys.argv[7]
SPEED = float(os.environ.get('CHARA_SPEED', '1.0'))
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
log = []
def cb(uc, a, s, u):
    p = uc.reg_read(UC_ARM_REG_R0); x, z = struct.unpack('<ff', o.read(p + 0x14, 4) + o.read(p + 0x1c, 4)); log.append((B.frame_no[0], x, z, p))
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x3501c - G, end=BASE + 0x3501c - G + 2)
o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + 0x352a0 - G, end=BASE + 0x352a0 - G + 2)   # MO_MouseJimeExe (Mouse Monopoly mouse task)
spd = []
chg = []
def cb3(uc, a, s, u):
    p = uc.reg_read(UC_ARM_REG_R0); x, y = struct.unpack('<hh', o.read(p, 4)); chg.append((B.frame_no[0], x, y, uc.reg_read(UC_ARM_REG_R1)))
o.uc.hook_add(UC_HOOK_CODE, cb3, begin=BASE + 0x2e034 - G, end=BASE + 0x2e034 - G + 2)
def cb2(uc, a, s, u): spd.append((B.frame_no[0], struct.unpack('<f', struct.pack('<I', uc.reg_read(UC_ARM_REG_R0)))[0], sum(1 for l in log if l[0] == B.frame_no[0]))); 
o.uc.hook_add(UC_HOOK_CODE, cb2, begin=BASE + 0x2ee5c - G, end=BASE + 0x2ee5c - G + 2)
outs = []
pa = (lit(0x3d3d8) + 0x3d366 + lit(0x3d3dc) - G) & 0xffffffff
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
step('GA_SetCharaSpeed', 0x2ee5c, struct.unpack('<I', struct.pack('<f', SPEED))[0])
for ga in (0x184c8c, 0x184ca0, 0x184ca8, 0x17518c): o.write(BASE + ga - G, struct.pack('<I', 0))
o.write(BASE + 0x17b604 - G, struct.pack('<I', 0)); o.write(BASE + 0x17b600 - G, struct.pack('<I', BCD))
o.write(BASE + 0x184cac - G, struct.pack('<f', THR) * 128)
rng = random.Random(seed); placements = []
if use_arrows:
    for f in range(10, 3000, 40): placements.append((f, rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4)))
pend = {p[0]: p for p in placements}; pt = o.heap_ptr; o.heap_ptr += 16
for f in range(1, frames + 1):
    B.frame_no[0] = f
    if f in pend:
        _, pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    oc = o.u32(BASE + 0x184c94 - G)
    if not outs or outs[-1][1] != oc: outs.append((f, oc))
with open(OUT, 'w') as fo:
    cur = -1
    for f, x, z, p in log:
        if f != cur: fo.write('F %d\n' % f); cur = f
        fo.write('M %.6f %.6f %d' % (x, z, p) + chr(10))
print('FI_ChangeFieldCollisionID calls (frame, x, y, id):', chg); print('roulette outcome global changes (frame, value):', outs); print('mouse entries', len(log)); print('GA_SetCharaSpeed calls (frame, value, mouse entries already run this frame):', spd)
per = {}
for f, x, z, p in log: per[f] = per.get(f, 0) + 1
print('entries per frame at those frames:', [(f, per.get(f)) for f, v, n in spd])
