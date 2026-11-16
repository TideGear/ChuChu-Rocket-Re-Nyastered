"""Verify the original iPad Puzzle failure timer, task passes and automatic reset."""
import struct
from random import Random

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

import hd_env
from ios_oracle import u2f


def verify_focus():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    oracle.call(0x1a060)
    cat = oracle.alloc(0x58)
    renders = []
    order = []

    def trace(uc, address, size, data):
        order.append(address)
        if address == 0x1a250:
            flags, scale, alpha = struct.unpack('<IfI', oracle.read(uc.reg_read(UC_ARM_REG_SP), 12))
            renders.append((oracle._r(0), oracle._r(1), u2f(oracle._r(2)), u2f(oracle._r(3)), flags, scale, alpha))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    hud = 0x137c4
    cat_draw = oracle.u32(0x1490c) & ~1
    for address in (0x1a250, cat_draw, hud):
        oracle.uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)
    for passes in (1, 2):
        for x, z in ((37.5, 67.5), (172.5, 127.5)):
            oracle.call(0x17e0c)
            oracle.call(0x18e48, *struct.unpack('<3I', struct.pack('<3f', x, 0, z)))
            oracle.write(cat + 0x14, struct.pack('<3f', x, 0, z))
            for frame in range(1, 122):
                order.clear()
                renders.clear()
                for _ in range(passes):
                    oracle.call(0x17f24)
                oracle.call(0x17f34)
                oracle.call(0x148e4, cat)
                oracle.call(0x191cc, hud | 1, 0, 0xfffffcec, 15)
                oracle.call(0x1a008)
                expected = []
                if frame * passes < 180:
                    previous = 0
                    for age, opacity in enumerate((200, 120, 60)):
                        if age >= frame:
                            break
                        updates = (frame - age) * passes
                        scale = (16 - 0.5 * updates) * .8 * .8 if updates < 30 else .8
                        if scale != previous:
                            expected.append((scale, opacity))
                        previous = scale
                assert order == [hud, cat_draw] + [0x1a250] * len(expected), order
                for draw, (scale, opacity) in zip(renders, expected):
                    assert draw[:2] == (149, 0) and draw[4] == 0, draw
                    assert abs(draw[2] - (184 + x * 64 / 15)) < 0.001
                    assert abs(draw[3] - (32 + z * 64 / 15)) < 0.001
                    assert abs(draw[5] - scale) < 0.000002 and draw[6] == opacity, draw
            oracle.call(0x17e38)
    print('iPad focus layers, ring history, and Dash expiry matched at two positions')


def verify_teardown_render():
    env = hd_env.make()
    oracle = env.o
    for address in (0x15188, 0x1a060, 0x17e0c):
        oracle.call(address)
    screen = oracle.alloc(0xb00)
    state = oracle.u32(0x18684)
    oracle.write(env.appdata + 0x668, struct.pack('<I', 0x2d))
    order = []

    def trace(uc, address, size, data):
        order.append(address)
        if address == 0xeae60:
            assert tuple(oracle._r(index) for index in range(4)) == (0, 0, 0x3dcccccd, 0)
        elif address == 0xeae5c:
            assert oracle._r(0) == 0x4000
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    background_and_hud = [0xeae60, 0xeae5c, 0x3ce2c, 0x137c4]
    board = [0x156d0, 0x1591c]
    focus = [0x18ef4]
    for address in background_and_hud + board + focus + [0x3bb70]:
        oracle.uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)

    def check(phase, expected):
        oracle.write(state + 4, struct.pack('<I', phase))
        order.clear()
        oracle.call(0x13278, screen)
        assert order == background_and_hud + expected + [0x3bb70], (phase, order)

    oracle.call(0x18084, 0x18239, 0x18285, 0, 0)
    oracle.call(0x18e48, 0, 0, 0)
    oracle.call(0x17f24)
    check(6, board + focus)
    oracle.call(0x17e38)
    check(1, [])
    oracle.call(0x17e0c)
    oracle.call(0x18084, 0x18239, 0x18285, 0, 0)
    oracle.call(0x17f24)
    check(2, board)
    oracle.call(0x17e38)
    print('iPad Puzzle teardown leaves clear colour, stars and HUD before the board returns')


def verify_star_updates():
    env = hd_env.make()
    oracle = env.o
    oracle.call(0x15188)
    screen = oracle.alloc(0xb00)
    oracle.write(env.appdata + 0x668, struct.pack('<I', 0x2d))
    calls = []

    def trace(uc, address, size, data):
        if address in (0x3cd38, 0x18294):
            calls.append((address, oracle._r(0)))
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0x3cd38, 0x18294, 0x3bcb4):
        oracle.uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)
    state = oracle.u32(0x18684)
    for phase in (1, 2, 3, 6):
        for dash in (0, 1):
            calls.clear()
            oracle.write(state + 4, struct.pack('<2I', phase, dash))
            oracle.call(0x12994, screen)
            assert [address for address, _ in calls] == [0x3cd38, 0x18294], (phase, dash, calls)
            assert calls[0][1] == 0, (phase, dash, calls)
    print('iPad Puzzle updates stars horizontally once before the loop in all eight fixtures')


def verify_star_motion():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    rng = Random(1)
    seeded = []
    draws = []

    def f32(value):
        return struct.unpack('<f', struct.pack('<f', value))[0]

    def trace(uc, address, size, data):
        result = 0
        if address == 0xa568:
            result = rng.getrandbits(32)
            seeded.append(result)
        elif address == 0xeadcc:
            result = oracle._r(0) % oracle._r(1)
        else:
            flags, scale, alpha = struct.unpack('<IfI', oracle.read(uc.reg_read(UC_ARM_REG_SP), 12))
            assert (oracle._r(0), flags, scale, alpha) == (154, 0, 1.0, 128)
            draws.append((oracle._r(1), u2f(oracle._r(2)), u2f(oracle._r(3))))
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0xa568, 0xeadcc, 0x1a250):
        oracle.uc.hook_add(UC_HOOK_CODE, trace, begin=address, end=address)
    oracle.call(0x3cef0)
    assert len(seeded) == (322 + 161) * 4
    groups = list(zip(*(iter(seeded),) * 4))
    stars = [(frame & 31, x % 1024, y % 768, f32((speed & 255) / 64 + 0.3))
             for x, y, speed, frame in groups[:322]]
    twinkles = [(x % 1024, y % 768, 3 + (period & 63), offset)
                for x, y, period, offset in groups[322:]]
    for tick in range(131):
        draws.clear()
        oracle.call(0x3ce2c, 0)
        expected = [(frame, x, y) for frame, x, y, _ in stars]
        expected.extend((11, x, y) for x, y, period, offset in twinkles
                        if (offset % period - tick) % (period + 1) < period / 2)
        assert draws == expected, (tick, len(draws), len(expected))
        vertical = 65 <= tick < 130
        oracle.call(0x3cd38, int(vertical))
        if vertical:
            moved = [(frame, x, f32(y + 2 * speed), speed) for frame, x, y, speed in stars]
            stars = [(frame, x, f32(y - 768) if y > 768 else y, speed) for frame, x, y, speed in moved]
        else:
            moved = [(frame, f32(x - 1.5 * speed), y, speed) for frame, x, y, speed in stars]
            stars = [(frame, f32(x + 1024) if x < 0 else x, y, speed) for frame, x, y, speed in moved]
    print('iPad star initialization, horizontal and vertical wrap, and twinkles matched across 131 frames')


def main():
    oracle = hd_env.make().o
    state = oracle.u32(0x18684)
    calls = []
    task_pass = [0x14cb8, 0x17f24, 0x14ee0]
    rebuild = [0x15a70, 0x17e0c, 0x18084, 0x15a20, 0x15804, 0x17364, 0x16044, 0x144c0,
               0x1e028, 0x1de1c, 0x140cc, 0x1f404, 0x18084]
    failure = [0x18e48, 0x1f414, 0x15a20, 0x15a08, 0x17dd0]
    mouse_failed = False

    def hook(uc, address, size, data):
        calls.append((address, oracle._r(0)))
        result = int(address == 0x15f24 or address == (0x15f30 if mouse_failed else 0x143fc))
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    monitored = {0x15f24, 0x15f30, 0x143fc, 0x17e38, 0x3baf8, 0x3bcb4, *task_pass, *rebuild, *failure}
    for address in monitored:
        oracle.uc.hook_add(UC_HOOK_CODE, hook, begin=address, end=address)

    for mouse_failed in (False, True):
        for dash in (0, 1):
            oracle.write(state, struct.pack('<8I', 777, 3, dash, 0, 0, 0, 0, 0))
            for frame in range(123):
                calls.clear()
                oracle.call(0x18294)
                addresses = [address for address, _ in calls]
                phase = struct.unpack('<3I', oracle.read(state, 12))
                if frame == 0:
                    checks = [0x15f24, 0x15f30] + ([] if mouse_failed else [0x143fc])
                    assert phase == (1, 6, dash)
                    assert addresses == checks + failure + task_pass * (dash + 1), calls
                    assert (0x17dd0, 27) in calls
                elif frame < 120:
                    assert phase == (frame + 1, 6, dash)
                    assert addresses == task_pass * (dash + 1), calls
                elif frame == 120:
                    assert phase == (121, 1, dash)
                    assert addresses == [0x17e38] + task_pass * (dash + 1), calls
                else:
                    assert phase == (frame - 120, 2, 0)
                    assert addresses == (rebuild if frame == 121 else []) + task_pass, calls
    print('4 iPad Puzzle cases matched, including Dash, task teardown and automatic arrow-preserving reset')
    verify_focus()
    verify_teardown_render()
    verify_star_updates()
    verify_star_motion()


if __name__ == '__main__':
    main()
