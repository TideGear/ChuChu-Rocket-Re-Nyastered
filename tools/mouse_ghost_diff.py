"""Compare HD 1.0 caught-mouse ghost movement, draw calls and retirement."""
from itertools import product
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import u2f


def main():
    oracle = hd_env.make().o
    oracle.call(0x15188)
    calls = []
    deleted = []

    def hook(uc, addr, size, data):
        if addr == 0x17fb8:
            deleted.append(oracle._r(0))
        else:
            flags, scale, alpha = struct.unpack('<IfI', oracle.read(uc.reg_read(UC_ARM_REG_SP), 12))
            assert alpha == 255
            calls.append((oracle._r(0), oracle._r(1), flags, u2f(oracle._r(2)), u2f(oracle._r(3)), scale))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for addr in (0x17fb8, 0x1a250):
        oracle.uc.hook_add(UC_HOOK_CODE, hook, begin=addr, end=addr)
    cases = list(product(((0.5, 0.5), (37.5, 67.5), (179.5, 134.5)), range(0, 65536, 16384)))
    for (x, z), angle in cases:
        task = oracle.alloc(0x58)
        oracle.write(task + 0x14, struct.pack('<3fii', x, 0, z, 0, angle))
        deleted.clear()
        for _ in range(47):
            oracle.call(0x16618, task)
            oracle.call(0x1695c, task)
        assert not deleted
        oracle.call(0x16618, task)
        assert deleted == [task]

    text = ''.join(f'{x} {z} {angle}\n' for (x, z), angle in cases)
    rows = subprocess.run([ROOT / 'build/game/ccr.exe'], input=text, capture_output=True, text=True,
                          env=dict(os.environ, CCR_MOUSE_GHOST_TRACE='1'), check=True).stdout.splitlines()
    assert len(rows) == len(calls)
    maximum_error = 0
    for i, (row, ref) in enumerate(zip(rows, calls)):
        fields = row.split()
        actual = tuple(int(f) if j < 3 else float.fromhex(f) for j, f in enumerate(fields))
        assert actual[:3] == ref[:3] and actual[5] == ref[5], (i, actual, ref)
        error = max(abs(a - b) for a, b in zip(actual[3:5], ref[3:5]))
        assert error <= 0.001, (i, actual, ref)
        maximum_error = max(maximum_error, error)
    print(f'{len(rows)} ghost draws matched, maximum position difference {maximum_error:.6f}px')


if __name__ == '__main__':
    main()
