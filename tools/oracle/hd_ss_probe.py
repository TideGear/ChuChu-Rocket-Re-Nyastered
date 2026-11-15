"""Ground truth for StageSelectScreen (iPad branch): init 0x10798, render 0x10b54. state(page, sel, cleared bits) -> low-level draw calls."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_env
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
env = hd_env.make(); o = env.o; scr = env.alloc(0xd00); o.write(scr + 0xa18, bytes([1]))
vmu = env.alloc(0x100); clr = {'bits': [0, 0, 0, 0]}
def stub(uc, addr, size, user):
    a = addr & ~1
    if a == 0x37154:   # VMU::isPuzzleCleared(stage)
        s = uc.reg_read(UC_ARM_REG_R0); uc.reg_write(UC_ARM_REG_R0, (clr['bits'][s // 25] >> (s % 25)) & 1)
    elif a in (0x19c94, 0xf8a0): uc.reg_write(UC_ARM_REG_R0, 0)
    else: return
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
for a in (0x37154, 0x19c94): o.uc.hook_add(UC_HOOK_CODE, stub, begin=a, end=a + 2)
ok = True
try: o.call(0x10798, scr)
except Exception as e: print('init failed', e); ok = False
def render(page=0, sel=0, bits=(0, 0, 0, 0), fade=0.0, font1=True):
    clr['bits'] = list(bits); o.write(scr + 0xa24, struct.pack('<i', page)); o.write(scr + 0xa2c, struct.pack('<i', sel)); o.write(scr + 0xa14, struct.pack('<f', fade))
    # font object of the screen (+0xa30) and texture space (+0xa34)
    o.write(scr + 0xa30, struct.pack('<I', o.u32(env.appdata + 0x384))); o.write(scr + 0xa34, struct.pack('<I', 2))
    del env.log[:]; o.call(0x10b54, scr); return list(env.log)
if __name__ == '__main__':
    for l in render(0, 3, (0x1ffffff & 0x155, 0, 0, 0)): print(l[:7] if l[0] != 'PrintString' else l[:4] + l[8:])
