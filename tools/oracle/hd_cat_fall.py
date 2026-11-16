"""Trace the iPad HD 1.0 cat hole animation and render-list submission."""
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

import hd_env
from ios_oracle import u2f


def main():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    task = oracle.alloc(0x58)
    calls = []
    mode = stage = 0

    def trace(uc, address, size, data):
        if address == 0x1926c:
            group, = struct.unpack('<I', oracle.read(uc.reg_read(UC_ARM_REG_SP), 4))
            calls.append((address, *(oracle._r(i) for i in range(4)), group))
        elif address == 0x1a250:
            flags, scale, alpha = struct.unpack('<IfI', oracle.read(uc.reg_read(UC_ARM_REG_SP), 12))
            calls.append((address, oracle._r(0), oracle._r(1),
                          u2f(oracle._r(2)), u2f(oracle._r(3)), flags, scale, alpha))
        else:
            calls.append(address)
            uc.reg_write(UC_ARM_REG_R0, {0x159bc: mode, 0x159c8: stage}.get(address, 0))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0x1926c, 0x1a250, 0x159bc, 0x159c8, 0x15b48, 0x17fb8):
        oracle.uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)

    for mode, stage in ((0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (3, 0), (4, 0), (5, 0)):
        slow = mode in (3, 4) or mode == 2 and stage < 3
        duration = 151 if slow else 30
        tries_respawn = mode in (0, 1) or mode == 2 and stage >= 3
        for x, z in ((0.5, 0.5), (37.5, 67.5), (179.5, 134.5)):
            initial_angle = 0xf333
            oracle.write(task + 0x14, struct.pack('<3fii3f', x, 0, z, initial_angle, 0, 0, 1, 0))
            previous_scale = 2
            for tick in range(duration):
                angle = initial_angle + tick * 0x1000
                scale = u2f(oracle.u32(task + 0x2c))
                assert 0 < scale < previous_scale
                previous_scale = scale
                calls.clear()
                oracle.call(0x148e4, task)
                oracle.call(0x14968, task)
                queue, draw = calls
                assert queue == (0x1926c, 0x14969, task, int(z), 0xffffffc0, 15), queue
                assert draw[:3] == (0x1a250, 0x2b, (angle & 0xffff) >> 11), draw
                assert draw[5:] == (0, scale, 255), draw
                assert abs(draw[3] - (184 + x * 64 / 15)) < 0.001, draw
                assert abs(draw[4] - (32 + z * 64 / 15)) < 0.001, draw
                calls.clear()
                oracle.call(0x147b4, task)
                assert (0x17fb8 in calls) == (tick == duration - 1), (mode, stage, tick, calls)
                assert (0x15b48 in calls) == (tries_respawn and tick == duration - 1)
                if tick != duration - 1:
                    assert oracle.u32(task + 0x20) == angle + 0x1000
    print('30 iPad cat fall cases matched across mode, stage, and position')


if __name__ == '__main__':
    main()
