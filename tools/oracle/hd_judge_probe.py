"""Ground truth for JudgeWinPriority (HD 1.0 0x1c99c, the result screen drawing): logs its Render::drawImage calls for given scores, dense ranks, win point target and "reach" mask."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_bubble_probe as P
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
o, log, appdata = P.make()
def stub(uc, addr, size, user):
    a = addr & ~1
    if a == 0x200c8: uc.reg_write(UC_ARM_REG_R0, state['reach'])
    elif a == 0x15a14: uc.reg_write(UC_ARM_REG_R0, 0)
    else: return
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
state = {'reach': 0}
for a in (0x200c8, 0x15a14): o.uc.hook_add(UC_HOOK_CODE, stub, begin=a, end=a + 2)
arr = o.alloc(0x40); o.write(0xeb5a8, struct.pack('<I', arr))
def judge(scores, ranks, wp, reach=0, wins=(0, 0, 0, 0), winner=0, flag=0):
    for i in range(4): o.write(arr + 4 * i, struct.pack('<i', scores[i])); o.write(arr + 0x10 + 4 * i, struct.pack('<i', ranks[i]))
    for i in range(4): o.write(0x2596c4 + 0x14 + 4 * i, struct.pack('<i', wins[i]))
    o.write(0x2596c4 + 0x24, struct.pack('<i', winner)); o.write(0x2596c4 + 0x28, struct.pack('<i', flag)); o.write(0x104fb4, struct.pack('<i', wp)); state['reach'] = reach; del log[:]; o.call(0x1c99c, 0); return list(log)
if __name__ == '__main__':
    for l in judge([12, 5, 7, 0], [0, 2, 1, 3], 3, 0b0100): print(l)
