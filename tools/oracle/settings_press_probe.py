"""Ground truth for PlayerSelectScreen::handleSettingsPaneInput (HD 1.0 0x32d24) on a zeroed screen object.
Stubs updateMenuItemFromTouchEvent (0xf2b0) to return the hit index, and logs playSFX (0xc74c) and changeGameState (0xbcc4).
Run with +0xa7c = 1 (level-list branch) and = 0 (phone-style branch); +0xd35 = 0 so the handler is not skipped."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_players_probe as P
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
o = P.o; env = P.env
SFX, GS, STUB_HIT, SETTINGS = 0xc74c, 0xbcc4, 0xf2b0, 0x32d24
log = []; ITEM = {'v': -1}
def hook(uc, a, s, u):
    x = a & ~1
    if x in (SFX, GS):
        log.append(('sfx' if x == SFX else 'gs', uc.reg_read(UC_ARM_REG_R1)))
    elif x == STUB_HIT:
        uc.reg_write(UC_ARM_REG_R0, ITEM['v'] & 0xffffffff)
    else:
        return
    uc.reg_write(UC_ARM_REG_R0, ITEM['v'] & 0xffffffff if x == STUB_HIT else 0)
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
for x in (SFX, GS, STUB_HIT): o.uc.hook_add(UC_HOOK_CODE, hook, begin=x, end=x + 2)
def run(item, a7c, press=0):
    ITEM['v'] = item; del log[:]
    scr = env.alloc(0xe00)
    o.write(scr + 0xa7c, bytes([a7c])); o.write(scr + 0xd35, bytes([0]))
    o.write(scr + 0xa08, struct.pack('<I', scr + 0x8))
    o.call(SETTINGS, scr, 0, 0, press)
    return list(log)
if __name__ == '__main__':
    for a7c in (1, 0):
        for item in [-1] + list(range(10)) + [25, 26, 27]:
            print('a7c=%d item=%d' % (a7c, item), run(item, a7c), flush=True)
