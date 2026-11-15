"""Compare the iPad rocket lid task and its primary draw call."""
from itertools import product
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parent.parent
TICKS = 640
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import u2f


def main():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    oracle.call(0x1a060)  # Render::create
    draw_order = []

    def record_draw(uc, addr, size, user):
        draw_order.append(oracle._r(0))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    draw_hooks = []
    for pointer in (0x16e50, 0x14964, 0x16afc):
        callback = oracle.u32(pointer) & ~1
        draw_hooks.append(oracle.uc.hook_add(UC_HOOK_CODE, record_draw, begin=callback, end=callback))
    for crossing in (65.9, 66.8, 67.6, 68.1):
        lid, cat, mouse = [oracle.alloc(0x58) for _ in range(3)]
        for task, z in ((lid, 67.5), (cat, crossing), (mouse, crossing)):
            oracle.write(task + 0x1c, struct.pack('<f', z))
        oracle.call(0x1493c, cat)
        oracle.call(0x16e28, lid)
        oracle.call(0x16ab0, mouse)
        oracle.call(0x1a008)
        assert draw_order == ([cat, mouse, lid] if crossing < 67 else
                              [cat, lid, mouse] if crossing < 68 else [lid, cat, mouse])
        draw_order.clear()
    for handle in draw_hooks:
        oracle.uc.hook_del(handle)

    field_ptr = oracle.alloc(4)
    oracle.write(field_ptr, struct.pack('<I', oracle.alloc(108 * 4)))
    oracle.write(oracle.u32(0x17acc), struct.pack('<I', field_ptr))
    clock = oracle.u32(0x18120)
    image_calls = []
    nodes = []

    def hook(uc, addr, size, user):
        r0, r1, r2, r3 = (oracle._r(i) for i in range(4))
        sp = uc.reg_read(UC_ARM_REG_SP)
        if addr == 0x1a250:
            flags, scale, alpha = struct.unpack('<IfI', oracle.read(sp, 12))
            assert (scale, alpha) == (u2f(0x3f4ccccd), 255)
            image_calls.append((r0, r1, flags, u2f(r2), u2f(r3)))
        elif addr == 0x1926c:
            nodes.append((r0, r1, r2, r3, oracle.u32(sp)))
        result = team if addr == 0x159bc else int(addr == 0x19448)
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for addr in (0x1a250, 0x1926c, 0x19448, 0x19474, 0x159bc):
        oracle.uc.hook_add(UC_HOOK_CODE, hook, begin=addr, end=addr)

    requests = []
    expected = []
    for player, team, x, y, alternate in product(range(4), (0, 1), (0, 4, 11), (0, 3, 8), (0, 1)):
        start = (-151 - x - 12 * y + alternate) & 255
        requests.append(f'{player} {team} {x} {y} {start}\n')
        task = oracle.alloc(0x58)
        world_z = (y + 0.5) * 15
        oracle.write(task + 0x14, struct.pack('<3f', (x + 0.5) * 15, 0, world_z))
        oracle.write(task + 0x2c, bytes([player]))
        nodes.clear()
        oracle.call(0x16e28, task)
        assert nodes == [(0x17bc9, task, int(world_z), 0xffffffc0, 15)]
        for tick in range(TICKS):
            oracle.write(clock, struct.pack('<I', start + tick))
            oracle.call(0x17530, task)
            image_calls.clear()
            oracle.call(0x17bc8, task)
            phase, count = struct.unpack('<2I', oracle.read(task, 8))
            assert len(image_calls) == 1
            expected.append((phase, count, oracle.u32(task + 0x20), u2f(oracle.u32(task + 0x30)),
                             *image_calls[0]))

    exe = ROOT / 'build/game/ccr.exe'
    rows = subprocess.run([exe], env=dict(os.environ, CCR_ROCKET_LID_TRACE='1'),
                          input=''.join(requests), capture_output=True, text=True,
                          check=True).stdout.splitlines()
    assert len(rows) == len(expected)
    for i, (row, ref) in enumerate(zip(rows, expected)):
        fields = row.split()
        actual = tuple(float.fromhex(f) if j in (3, 7, 8) else int(f) for j, f in enumerate(fields))
        assert actual == ref, (requests[i // TICKS], i % TICKS, ref, actual)
    print(f'{len(rows)} original lid state and primary image calls matched exactly')


if __name__ == '__main__':
    main()
