import sys, struct
sys.path.insert(0, '.')
import battle_probe as B
from battle_probe import *
from unicorn import UC_HOOK_CODE
d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
tiles, walls = ascii_stage(d[12 * 477:12 * 477 + 475]); B.spawns.clear(); setup_battle(tiles, walls, 31)
gcall(0x3d2bc)
for p in range(4): gcall(0x29d50, p, 2)
sel = []
def cb(uc, a, s, u): sel.append((B.frame_no[0], gcall(0x2ef5c) if False else None))
for f in range(1, 400):
    B.frame_no[0] = f
    step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    if f in (1, 2, 396, 397, 398): print(f, [ (hex(a), gcall(a)) for a in (0x2f0ec, 0x2f0b4, 0x2f058, 0x2f108)])
