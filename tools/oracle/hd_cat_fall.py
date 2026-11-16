"""Trace the iPad HD 1.0 cat hole animation and render-list submission."""
import struct

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

import hd_env
from ios_oracle import u2f


def verify_handoff_and_respawn():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    task = oracle.alloc(0x58)
    field = oracle.u32(0x153e8)
    generators = oracle.u32(0x15b50)
    hole_flag = oracle.u32(0x147a0)
    game = oracle.u32(0x15b24)
    oracle.write(game, struct.pack('<I', 0))
    oracle.write(game + 12, struct.pack('<2f', 1, 1.5))
    cells = ((0, 0), (11, 8), (5, 3), (4, 7))
    oracle.write(generators, struct.pack('<I', len(cells)))
    for index, (x, y) in enumerate(cells):
        oracle.write(generators + 40 + index * 8, struct.pack('<2h', x, y))
        oracle.write(field + (x + y * 12) * 4, struct.pack('<I', index))
    oracle.write(field + (2 + 4 * 12) * 4, struct.pack('<I', 0x400))
    rng_calls = []
    sounds = []
    random_value = 0.0

    def trace(uc, address, size, data):
        if address == 0x152c4:
            rng_calls.append(random_value)
            uc.reg_write(UC_ARM_REG_R0, struct.unpack('<I', struct.pack('<f', random_value))[0])
        else:
            sounds.append(oracle._r(0))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0x152c4, 0x17dd0):
        oracle.uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)
    for random_value, index in ((0.0, 0), (0.25, 0), (0.26, 1), (0.51, 2), (0.99, 3)):
        position = (37.75, 0, 67.5)
        oracle.write(task + 0x10, struct.pack('<2h3fii3f', 2, 4, *position, 0x3333, 0, 0, 1, 0))
        oracle.write(hole_flag + 4, bytes(4))
        rng_calls.clear()
        oracle.call(0x14524, task)
        assert (oracle.u32(task + 0x40), oracle.u32(task + 0x44)) == (0x147b5, 0x148e5)
        assert oracle.u32(hole_flag + 4) == 1
        assert struct.unpack('<3f', oracle.read(hole_flag + 20, 12)) == position
        assert oracle.u32(task + 0x20) == 0x3333
        for _ in range(29):
            oracle.call(0x147b4, task)
        assert not rng_calls
        oracle.call(0x147b4, task)
        assert rng_calls == [random_value] and not sounds
        x, y = cells[index]
        actual = struct.unpack('<2h3f', oracle.read(task + 0x10, 16))
        assert actual == (x, y, (x + 0.5) * 15, 0, (y + 0.5) * 15), (random_value, index, actual)
        assert oracle.u32(task + 0x20) == (index << 14) + 0x1000
        assert oracle.u32(task + 0x24) == index << 14
        assert (oracle.u32(task + 0x40), oracle.u32(task + 0x44)) == (0x14525, 0x14911)
    print('5 iPad cat hole handoffs and generator selections matched')


def verify_overlap():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    oracle.call(0x1a060)
    cat, rocket, mouse = [oracle.alloc(0x58) for _ in range(3)]
    order = []

    def record(uc, address, size, data):
        order.append(address)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    field, objects, cat_draw, rocket_draw, mouse_draw = (
        oracle.u32(ptr) & ~1 for ptr in (0x156c0, 0x156c8, 0x1490c, 0x16e50, 0x16afc))
    for address in (field, objects, cat_draw, rocket_draw, mouse_draw):
        oracle.uc.hook_add(UC_HOOK_CODE, record, begin=address, end=address)
    for z in (65.9, 66.8, 67.6, 68.1):
        for task, depth in ((cat, z), (rocket, 67.5), (mouse, z)):
            oracle.write(task + 0x14, struct.pack('<3f', 37.5, 0, depth))
        oracle.call(0x156a0)
        oracle.call(0x148e4, cat)
        oracle.call(0x16e28, rocket)
        oracle.call(0x16ab0, mouse)
        oracle.call(0x1a008)
        sprites = ([cat_draw, mouse_draw, rocket_draw] if z < 67 else
                   [cat_draw, rocket_draw, mouse_draw] if z < 68 else [rocket_draw, cat_draw, mouse_draw])
        assert order == [field, objects, *sprites], order
        order.clear()
    print('4 iPad cat fall overlaps matched the field and sprite draw order')


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
    verify_handoff_and_respawn()
    verify_overlap()


if __name__ == '__main__':
    main()
