"""Trace GBA cat hole, rocket entry, and forced removal paths."""
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

from gba_oracle import GBA, STOPADDR


def main():
    root = Path(__file__).resolve().parents[2]
    gba = GBA(root / 'analysis/gba/ccr.gba')
    uc = gba.uc
    cat, focus = 0x03000700, 0x03000740
    mode, pending, focus_task = (gba.r32(a) for a in (0x080033fc, 0x08003400, 0x08003404))
    removal_mask = gba.r32(0x08003168)
    fall_update = gba.r32(0x0800463c)
    calls = []
    collision = 0x80
    arrival = 0

    def trace(uc, addr, size, data):
        calls.append((addr, uc.reg_read(UC_ARM_REG_R0)))
        if addr == 0x080041ac:
            uc.reg_write(UC_ARM_REG_R0, collision)
        elif addr == 0x08003508:
            uc.reg_write(UC_ARM_REG_R0, arrival)
        elif addr == 0x080009e4:
            uc.reg_write(UC_ARM_REG_R0, focus)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for addr in (0x080041ac, 0x08003508, 0x080009e4, 0x08026da8,
                 0x08000c0c, 0x08000b68, 0x08024930, 0x0802495c):
        uc.hook_add(UC_HOOK_CODE, trace, begin=addr, end=addr)

    def run(task, cue=None):
        calls.clear()
        uc.reg_write(UC_ARM_REG_R0, cat)
        uc.reg_write(UC_ARM_REG_SP, 0x03007a00)
        uc.reg_write(UC_ARM_REG_LR, STOPADDR | 1)
        uc.emu_start(task | 1, STOPADDR, count=15000)
        sounds = [(a, r0) for a, r0 in calls if a in (0x08024930, 0x0802495c)]
        assert sounds == ([] if cue is None else [(0x08024930, cue)]), calls

    def reset(game_mode, busy=False):
        uc.mem_write(cat, bytes(0x30))
        uc.mem_write(focus, bytes(0x30))
        uc.mem_write(mode, bytes([game_mode]))
        uc.mem_write(pending, bytes([255 if busy else 0]))
        uc.mem_write(cat + 0x1b, bytes([4]))
        gba.w16(cat + 10, 100)
        gba.w16(cat + 14, 200)
        gba.w16(cat + 0x20, 0x1000)

    for collision in (0x80, 0x20):
        for game_mode, busy in [(m, False) for m in range(9)] + [(4, True)]:
            reset(game_mode, busy)
            run(0x08003140)
            assert gba.r32(cat + 4) == fall_update
            focused = collision == 0x80 and game_mode == 4 and not busy
            assert [r0 for a, r0 in calls if a == 0x080009e4] == ([focus_task] if focused else [])
            if focused:
                assert (gba.r16(focus + 10), gba.r16(focus + 14)) == (100, 200)
            for frame in range(55):
                run(fall_update)
                assert calls == ([(0x08000c0c, 0x1f)] if frame < 54 else [(0x08000b68, cat)]), calls

    collision, arrival = 0x20, 1
    rocket_update = gba.r32(0x080046cc)
    rocket_poses = gba.r32(0x08004680)
    for size, cue in ((0, 36), (50, 43)):
        reset(0)
        uc.mem_write(cat + 0x19, bytes([size]))
        run(0x08003140, cue)
        assert gba.r32(cat + 4) == rocket_update
        for frame in range(18):
            run(rocket_update)
            assert gba.r32(cat + 0x10) == gba.r32(rocket_poses + 4 * (frame // 6))
            assert calls == ([(0x08000c0c, 4)] if frame < 17 else [(0x08000b68, cat)]), calls

    reset(0)
    uc.mem_write(removal_mask, bytes([1 << 4]))
    run(0x08003140)
    assert calls == [(0x08000b68, cat)]
    print('20 GBA cat falls: 54 sprite submissions each; forced removal deletes immediately')
    print('2 GBA accepted rocket entries: 17 sprite submissions each, cue 36 or 43 at handoff')


if __name__ == '__main__':
    main()
