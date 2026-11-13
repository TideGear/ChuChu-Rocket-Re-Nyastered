"""usage: hook_frames.py stage seed frames hexaddr...   prints frames at which each Ghidra address is entered (battle with scripted arrows)"""
import sys, struct, random
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
idx, seed, upto = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]); addrs = [int(a, 16) for a in sys.argv[4:]]
hits = {a: [] for a in addrs}
for a in addrs:
    def cb(uc, ad, s, u, a=a):
        if not hits[a] or hits[a][-1] != B.frame_no[0] or True: hits[a].append((B.frame_no[0], uc.reg_read(UC_ARM_REG_LR) - BASE + G & 0xfffffffe))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + a - G, end=BASE + a - G + 2)
tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, seed)
gcall(0x3d2bc)
rng = random.Random(seed); pend = {}
for f in range(10, 3000, 40): pend[f] = (rng.randrange(4), rng.randrange(12), rng.randrange(9), rng.randrange(4))
pt = o.heap_ptr; o.heap_ptr += 16
for f in range(1, upto + 1):
    B.frame_no[0] = f
    if f in pend:
        pl, x, y, dd = pend[f]; o.write(pt, struct.pack('<hh', x, y)); gcall(0x286ac, pl, pt, dd)
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
import collections
for a in addrs:
    c = collections.Counter(l for f, l in hits[a]); print(hex(a), len(hits[a]), [(hex(k), v) for k, v in c.most_common(12)])
    first = {}
    for f, l in hits[a]: first.setdefault(l, f)
    print('first frame per caller', {hex(k): v for k, v in first.items()})
