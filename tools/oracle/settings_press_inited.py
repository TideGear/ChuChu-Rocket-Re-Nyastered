"""Settings press table on an initialized battle-setup settings screen (HD 1.0 handleSettingsPaneInput 0x32d24).
Prerequisites run in order: field grids (FI_LoadAllMap 0x15928), playfield data (initializePlayfields 0x1ac88),
stage-select texture spaces (hd_env.place_stage_select), constructor 0x34a00, menu init 0x31690.
The screen is snapshotted after init and restored before every press, so each item starts from the same state."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_env
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
SFX, GS, HIT, SETTINGS = 0xc74c, 0xbcc4, 0xf2b0, 0x32d24
env = hd_env.make(); o = env.o
hd_env.place_stage_select(env)
o.call(0x15928, 0); o.call(0x1ac88)
scr = env.alloc(0xe00); o.call(0x34a00, scr)
o.write(scr + 0xa7c, bytes([0])); o.write(scr + 0xd35, bytes([0]))
o.call(0x31690, scr)
SNAP = bytes(o.read(scr, 0xe00))
log = []; ITEM = {'v': -1}
def hook(uc, a, s, u):
    x = a & ~1
    if x == HIT: uc.reg_write(UC_ARM_REG_R0, ITEM['v'] & 0xffffffff)
    else:
        log.append(('sfx' if x == SFX else 'gs', uc.reg_read(UC_ARM_REG_R1))); uc.reg_write(UC_ARM_REG_R0, 0)
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
for x in (SFX, GS, HIT): o.uc.hook_add(UC_HOOK_CODE, hook, begin=x, end=x + 2)
def run(item):
    ITEM['v'] = item; del log[:]
    o.write(scr, SNAP); o.write(scr + 0xa08, struct.pack('<I', scr + 0x8))
    o.call(SETTINGS, scr, 0, 0, 0)
    return list(log)
if __name__ == '__main__':
    for it in [-1] + list(range(10)) + [25, 26, 27]:
        print('item', it, run(it), flush=True)
