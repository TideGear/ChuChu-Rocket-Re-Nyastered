"""Trace the shared GBA death marker and its sound dispatch."""
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP

from gba_oracle import GBA, STOPADDR


def main():
    root = Path(__file__).resolve().parents[2]
    gba = GBA(root / 'analysis/gba/ccr.gba')
    uc = gba.uc
    marker = 0x03000740
    init = gba.r32(0x08002ed8)
    pending = gba.r32(0x08002ed4)
    assert (init, pending) == (gba.r32(0x08003404), gba.r32(0x08003400))
    calls = []

    def trace(uc, addr, size, data):
        calls.append((addr, uc.reg_read(UC_ARM_REG_R0), uc.reg_read(UC_ARM_REG_R1)))
        if addr != 0x08024930:
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for addr in (0x08024930, 0x0802495c, 0x08024fac, 0x08000c0c, 0x08000b68):
        uc.hook_add(UC_HOOK_CODE, trace, begin=addr, end=addr)

    def run(task):
        calls.clear()
        uc.reg_write(UC_ARM_REG_R0, marker)
        uc.reg_write(UC_ARM_REG_SP, 0x03007a00)
        uc.reg_write(UC_ARM_REG_LR, STOPADDR | 1)
        uc.emu_start(task, STOPADDR, count=10000)
        assert uc.reg_read(UC_ARM_REG_PC) == STOPADDR

    for x, y in ((100, 80), (32, 0), (216, 136)):
        uc.mem_write(marker, bytes(0x30))
        uc.mem_write(marker + 2, bytes([7]))
        uc.mem_write(pending, bytes([255]))
        gba.w16(marker + 10, x)
        gba.w16(marker + 14, y)
        run(init)
        assert len(calls) == 2 and calls[0][:2] == (0x08024930, 62)
        assert calls[1][0] == 0x08024fac
        assert calls[1][2] == gba.r32(gba.r32(0x08024958) + 8 * 62) == 0x08081f5c
        assert gba.r32(marker + 0x10) == 0x080878a8
        for tick in range(1, 193):
            run(gba.r32(marker + 4))
            assert (gba.r16(marker + 10), gba.r16(marker + 14)) == (x, y)
            if tick == 192:
                assert [(a, r0) for a, r0, _ in calls] == [(0x08000b68, marker)], calls
            else:
                assert calls == ([(0x08000c0c, 0, 7)] if tick // 16 % 2 else []), (tick, calls)
            assert gba.r8(pending) == 255
        print(f'marker at ({x}, {y}): cue 62, six blinks, pending byte retained')


if __name__ == '__main__':
    main()
