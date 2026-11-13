"""Run a whole puzzle stage in the original code (emulated libccrjni.so): original setup calls, original frame loop."""
import struct, sys, math
sys.path.insert(0, '.')
from cat_probe import *
init_tables()
BX_LR = b'\x70\x47'
for ga in (0x3d434, 0x3d438, 0x3d444, 0x3d448, 0x3d44c, 0x3d450, 0x3d454, 0x3d458, 0x3d45c, 0x3d464, 0x3d480, 0x3d49c, 0x3d4b4, 0x3d4cc, 0x3d4e4, 0x3d508,
           0x69b04, 0x69b0c, 0x69b18, 0x69b3c, 0x69b48, 0x69b54, 0x69b60, 0x69b74, 0x2bb28):          # sound/BGM entry points (they call into JNI): no-ops
    o.write(BASE + ga - G, BX_LR)
for name in ('BGM_Play', 'BGM_Stop', 'BGM_Change', 'BGM_SetVolume'):
    pass
def step(name, ga, *a):
    try: return gcall(ga, *a)
    except Exception as e:
        pc = o.uc.reg_read(UC_ARM_REG_PC); lr = o.uc.reg_read(UC_ARM_REG_LR)
        print('STEP FAILED:', name, '|', e, '| pc ghidra=%#x lr ghidra=%#x' % (pc - BASE + G, lr - BASE + G), 'r0-r3', [hex(o.uc.reg_read(r)) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)])
        raise SystemExit(1)
def run_stage(tiles, walls, counts, arrows, frames=60 * 120, trace=False):
    """tiles[108], walls[237], counts[4] arrow stock per direction, arrows [(x,y,dir)] placed at frame 0. Returns dict of results."""
    stage = bytearray(380)
    stage[0:108] = tiles; stage[0x6c:0x6c + 237] = walls; stage[0x15c:0x160] = bytes(counts)
    step('GA_Reset', 0x2ed04); step('GA_SetGameType', 0x2ed30, 3); step('GA_SetStageNum', 0x2ed7c, 0, 0, 1)          # GA_ResetGameParamStr, GA_SetGameType(3), GA_SetStageNum(0)
    step('SmpTskInit', 0x3d904)                                                # SmpTskInit
    ptr = step('FI_GetFIPSptr', 0x2ddd0, 3, 0)                                    # FI_GetFIPSptr(3, 0) -> address of the stage struct
    o.write(ptr, bytes(stage))
    step('GA_SetCharaSpeed', 0x2ee5c, 0x3f800000)                                    # GA_SetCharaSpeed(1.0)
    step('GA_OnGameFlag', 0x2eea4)                                                   # enables the rocket/hole branches of the entity ticks
    step('FI_InitFieldCollision', 0x2e568)                                           # builds the collision words from the stage struct
    step('AR_StartArrowPzManager', 0x28858)                                                # AR_StartArrowPzManager
    step('RO_StartRocketPzManager', 0x3b798)                                                # RO_StartRocketPzManager
    mice = step('MO_PutMousePuzzle', 0x34f7c)                                         # MO_PutMousePuzzle -> number of mice
    step('CA_PutCatPuzzle', 0x28f98)                                                # CA_PutCatPuzzle
    pt = o.heap_ptr; o.heap_ptr += 16
    for (x, y, d) in arrows:
        o.write(pt, struct.pack('<hh', x, y)); step('AR_PutArrowPz', 0x28570, pt, d)    # AR_PutArrowPz
    out = {'mice': mice, 'saved': 0, 'frames': 0}
    for f in range(frames):
        step('SmpColLoopInit', 0x2993c); step('SmpTskExeServer', 0x3da60); step('SmpColAnalyze', 0x29b1c)            # SmpColLoopInit, SmpTskExeServer, SmpColAnalyze
        out['frames'] = f + 1
        out['saved'] = gcall(0x34e54)                             # MO_GetRocketMouse
        if out['saved'] >= mice: break
    return out
if __name__ == '__main__':
    sys.path.insert(0, '.')
    from arrow_probe import load_stage
    tiles, walls, sol, title = load_stage(0)
    counts = [0, 0, 0, 0]
    for (x, y, d) in sol: counts[d] += 1
    print(title, sol, counts)
    print(run_stage(tiles, walls, counts, sol, frames=1500))
    print('unhandled imports:', o.unhandled)
