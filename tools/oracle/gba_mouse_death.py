"""Trace the GBA mouse catch and hole task handoffs without audio or video output."""
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP

from gba_oracle import GBA, STOPADDR


def main():
    root = Path(__file__).resolve().parents[2]
    gba = GBA(root / 'analysis/gba/ccr.gba')
    uc = gba.uc
    mouse, focus = 0x03000700, 0x03000740
    mode = gba.r32(0x08002e20)
    focus_pending = gba.r32(0x08002ed4)
    caught_init = gba.r32(0x08002ca4)
    caught_update = gba.r32(0x080044fc)
    hole_update = gba.r32(0x0800463c)
    focus_task = gba.r32(0x08002ed8)
    calls = []

    def trace(uc, addr, size, data):
        r0, r1 = (uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1))
        calls.append((addr, r0, r1))
        if addr == 0x080009e4:
            uc.reg_write(UC_ARM_REG_R0, focus)
        if addr == 0x080041ac:
            uc.reg_write(UC_ARM_REG_R0, 0xffffff80)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0x08024930, 0x0802495c, 0x080009e4, 0x080041ac,
                    0x08026da8, 0x08000c0c, 0x08000b68):
        uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)

    def run(address):
        calls.clear()
        uc.reg_write(UC_ARM_REG_R0, mouse)
        uc.reg_write(UC_ARM_REG_SP, 0x03007a00)
        uc.reg_write(UC_ARM_REG_LR, STOPADDR | 1)
        uc.emu_start(address | 1, STOPADDR, count=15000)
        assert not any(a in (0x08024930, 0x0802495c) for a, _, _ in calls), calls

    def reset(kind, game_mode, busy=False):
        uc.mem_write(mode, bytes([game_mode]))
        uc.mem_write(focus_pending, bytes([255 if busy else 0]))
        uc.mem_write(mouse, bytes(0x30))
        uc.mem_write(focus, bytes(0x30))
        gba.w16(mouse + 10, 100)
        gba.w16(mouse + 14, 200)
        if kind == 'catch':
            uc.mem_write(mouse + 3, bytes([0x80]))
        else:
            gba.w16(mouse + 0x20, 0x1000)

    for kind, update in (('catch', caught_init), ('hole', hole_update)):
        for game_mode in range(9):
            reset(kind, game_mode)
            run(0x08002c28)
            assert gba.r32(mouse + 4) == update, (kind, game_mode, hex(gba.r32(mouse + 4)))
            spawned = [r0 for a, r0, _ in calls if a == 0x080009e4]
            eligible = game_mode in ((2, 3, 7, 8) if kind == 'catch' else (2, 3, 4, 7, 8))
            assert spawned == ([focus_task] if eligible else []), (kind, game_mode, calls)
            if eligible:
                assert (gba.r16(focus + 10), gba.r16(focus + 14)) == (100, 200)
        reset(kind, 2, busy=True)
        run(0x08002c28)
        assert not any(a == 0x080009e4 for a, _, _ in calls)

    for kind in ('catch', 'hole'):
        reset(kind, 0)
        run(0x08002c28)
        if kind == 'catch':
            run(caught_init)
            assert gba.r32(mouse + 4) == caught_update and gba.r8(mouse + 0x21) == 8
        poses = []
        for _ in range(200):
            task = gba.r32(mouse + 4)
            run(task)
            if [a for a, _, _ in calls] == [0x08000b68]:
                break
            assert [a for a, _, _ in calls] == [0x08000c0c], calls
            poses.append(task)
        else:
            raise AssertionError(f'{kind} task did not retire')
        expected = [caught_update] * 64 + [0x08004409] * 19 if kind == 'catch' else [hole_update] * 54
        assert poses == expected, (kind, len(poses))
        print(f'{kind}: {len(poses)} sprite submissions before retirement')
    print('20 GBA catch/hole handoff cases matched')


if __name__ == '__main__':
    main()
