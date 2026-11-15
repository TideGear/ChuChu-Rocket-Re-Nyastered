"""Ground truth for PlayerSelectScreen::handlePlayersPaneInput (HD 1.0, 0x31d24): calls it for a given item (touch on a hit rect or the item index from updateMenuItemFromTouchEvent)
with a given state, and logs AppData::playSFX (0xc74c), changeGameState (0xbcc4), and the pane flags written. Used to check each case of the port."""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hd_players_probe as P
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *
o = P.o; scr = P.scr; env = P.env
SFX, GS, MUT = 0xc74c, 0xbcc4, 0x2f438
log = []
def hook(uc, a, s, u):
    x = a & ~1
    r0 = uc.reg_read(UC_ARM_REG_R0); r1 = uc.reg_read(UC_ARM_REG_R1)
    if x == SFX: log.append(('sfx', r1))
    elif x == GS: log.append(('gs', r1))
    uc.reg_write(UC_ARM_REG_R0, 0); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
for x in (SFX, GS): o.uc.hook_add(UC_HOOK_CODE, hook, begin=x, end=x + 2)
# the item the touch resolves to: updateMenuItemFromTouchEvent (0x0000f2b0 in the pane's base class). Stub it to return a chosen item.
ITEM = {'v': 0}
def item_stub(uc, a, s, u):
    uc.reg_write(UC_ARM_REG_R0, ITEM['v']); uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
def run(item, press=0, flags=None):
    ITEM['v'] = item; del log[:]
    o.write(scr + 0xa08, struct.pack('<I', scr + 0x8))   # current menu item pointer (the pane's first item)
    if flags:
        for off, val in flags.items(): o.write(scr + off, bytes([val]) if off < 0xd00 else struct.pack('<I', val))
    o.call(0x31d24, scr, 0, 0, press)
    return list(log)
o.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: item_stub(uc, a, s, u), begin=0xf2b0, end=0xf2b0 + 2)
if __name__ == '__main__':
    for i in range(10):
        print(i, run(i))
