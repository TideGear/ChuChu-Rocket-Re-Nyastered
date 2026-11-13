"""Battle mode (4-player free-for-all) in the original code: generator spawn log with a fixed RNG seed."""
import struct, sys, math
sys.path.insert(0, '.')
from full_stage import *            # oracle, sound patches, step()
from unicorn import UC_HOOK_CODE
def ascii_stage(rec):
    """25x19 ASCII map -> (tiles[108], walls[237]) mobile layout (rule from FUN_0002e6cc)."""
    L = [rec[r * 25:(r + 1) * 25] for r in range(19)]
    def tile(ch): return 0x11 if ch == 0x37 else 0 if ch == 0x39 else (ch - 0x40) & 0xff
    tiles = bytes(tile(L[2 * r + 1][2 * c + 1]) for r in range(9) for c in range(12))
    walls = bytearray(237)
    for i in range(10):
        for c in range(12): walls[25 * i + c] = 1 if L[2 * i][2 * c + 1] == 0x31 else 0
    for i in range(9):
        for c in range(13): walls[25 * i + 12 + c] = 1 if L[2 * i + 1][2 * c] == 0x31 else 0
    return tiles, bytes(walls)
spawns = []
def hook_put(ga, kind):
    def cb(uc, a, s, u):
        p = uc.reg_read(UC_ARM_REG_R0); x, y = struct.unpack('<hh', o.read(p, 4))
        spawns.append((frame_no[0], kind, x, y, uc.reg_read(UC_ARM_REG_R1) & 3, uc.reg_read(UC_ARM_REG_R2) & 0xff if kind == 'mouse' else 0))
    o.uc.hook_add(UC_HOOK_CODE, cb, begin=BASE + ga - G, end=BASE + ga - G + 2)
frame_no = [0]
hook_put(0x34ee4, 'mouse'); hook_put(0x28f14, 'cat')
def setup_battle(tiles, walls, seed, mode=0xc, gtype=0):
    step('Core::changeGlobalMode', 0x2bc74, mode)
    step('GA_Reset', 0x2ed04); step('GA_SetGameType', 0x2ed30, gtype); step('GA_SetStageNum', 0x2ed7c, 0, 0, 1)
    step('SmpTskInit', 0x3d904)
    tbl = (lit(0x2de0c) + 0x2dde4 - G) & 0xffffffff                      # per-type stage array pointer table (types 0..2)
    buf = o.heap_ptr; o.heap_ptr += 0x15c * 8
    st = bytearray(0x15c); st[0:108] = tiles; st[0x6c:0x6c + 237] = walls
    o.write(buf, bytes(st)); o.write(BASE + tbl + 4 * gtype, struct.pack('<I', buf))
    step('BHLib_SeedRNG', 0x25660, seed)
    step('GA_SetCharaSpeed', 0x2ee5c, 0x3f800000)
    step('GA_OnGameFlag', 0x2eea4)
    step('FI_InitFieldCollision', 0x2e568)
    step('AR_StartArrow4Manager', 0x28890)
    step('RO_StartRocket4Manager', 0x3b848)
    step('GE_StartGenerator4Manager', 0x34b08)
if __name__ == '__main__':
    d = open(r'C:\Dev\ChuChu Rocket\analysis\extracted\dc_files\ENGLISH\BTSTAGE25.DAT', 'rb').read()
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    tiles, walls = ascii_stage(d[idx * 477:idx * 477 + 475])
    setup_battle(tiles, walls, 12345)
    for f in range(1, 601):
        frame_no[0] = f
        step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)
    print('spawn events in 600 frames:', len(spawns)); print(spawns[:20])
    print('unhandled imports:', o.unhandled)
