"""Compare original and ported iPad rocket lift-off and smoke draws."""
from itertools import product
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import u2f


def main():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    oracle.call(0x1a060)  # Render::create
    field_ptr = oracle.alloc(4)
    oracle.write(field_ptr, struct.pack('<I', oracle.alloc(108 * 4)))
    oracle.write(oracle.u32(0x17acc), struct.pack('<I', field_ptr))
    clock = oracle.u32(0x18120)
    expected = []
    requests = []

    def record(uc, address, size, user):
        if address == 0x1a250:
            image, frame, x, y = (oracle._r(i) for i in range(4))
            flags, scale, alpha = struct.unpack('<IfI', oracle.read(uc.reg_read(UC_ARM_REG_SP), 12))
            height = screen_z - u2f(y)
            depth = int(world_z if 0x56 <= image <= 0x5b else
                        world_z + height - (1 if image == 0x92 else 0))
            expected.append((tick, depth, image, frame, alpha, flags, u2f(x), u2f(y), scale))
        else:
            uc.reg_write(UC_ARM_REG_R0, team if address == 0x159bc else int(address == 0x19448))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for addr in (0x1a250, 0x159bc, 0x19448, 0x19474):
        oracle.uc.hook_add(UC_HOOK_CODE, record, begin=addr, end=addr)
    for player, team, (x, y), clock_phase in product(range(4), (0, 1, 3), ((0, 0), (11, 8)), (0, 3, 7)):
        requests.append(f'{player} {int(team == 1)} {x} {y} {clock_phase}\n')
        oracle.call(0x17e0c)  # SmpTskInit
        task = oracle.call(0x18084, 0x1765d, 0x16e55, 0, 0)
        lid = oracle.call(0x18084, 0x17531, 0x16e29, 0, 0)
        assert task and lid
        world_z = (y + 0.5) * 15
        screen_z = 32 + struct.unpack('<f', struct.pack('<f', world_z * u2f(0x40888889)))[0]
        for obj in (task, lid):
            oracle.write(obj + 0x14, struct.pack('<3f', (x + 0.5) * 15, 0, world_z))
            oracle.write(obj + 0x2c, bytes([player]))
        for tick in range(240):
            oracle.write(clock, struct.pack('<I', clock_phase + tick))
            oracle.call(0x17f24)  # SmpTskExeServer
            oracle.call(0x17f34)  # SmpTskDrawServer
            oracle.call(0x1a008)  # Sort and render the list, then clear it.

    executable = ROOT / 'build/game/ccr.exe'
    output = subprocess.run([executable], env=dict(os.environ, CCR_ROCKET_LAUNCH_TRACE='1'),
                            input=''.join(requests), capture_output=True, text=True, check=True).stdout
    rows = [line.split() for line in output.splitlines() if line]
    assert len(rows) == len(expected), (len(rows), len(expected))
    for i, (row, ref) in enumerate(zip(rows, expected)):
        actual = tuple(int(value) if j < 6 else float.fromhex(value) for j, value in enumerate(row))
        assert actual == ref, (i, ref, actual)
    print(f'{len(rows)} original rocket, lid, and smoke draws matched in sorted order')


if __name__ == '__main__':
    main()
