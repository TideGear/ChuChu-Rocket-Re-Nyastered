"""Trace every visible iPad roulette pose and compare the port frame by frame."""
from itertools import product
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import u2f


def main():
    o = hd_env.make().o
    o.call(0x15188, max_insn=4_000_000)  # CoreSettingsInit
    manager = o.u32(0x1d6d0)
    rockets = o.u32(0x16c94)
    task = o.alloc(0x58)
    expected = []

    def record(uc, address, size, user):
        if address == 0x1a970:
            expected.append(tuple(u2f(uc.reg_read(UC_ARM_REG_R0 + i)) for i in range(4)))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0x1a970, 0x17870):
        o.uc.hook_add(UC_HOOK_CODE, record, begin=address, end=address)
    cases = [(x, y, outcome) for (x, y), outcome in product(((0, 0), (11, 8), (2, 4), (8, 2)), range(8))]
    for x, y, outcome in cases:
        o.write(task, bytes(0x58))
        o.write(manager + 4, struct.pack('<2i', 2, outcome))
        o.write(rockets + 8, struct.pack('<2h', x, y))
        for _ in range(120):
            o.call(0x1d4dc, task)  # RL_RouletteExec
            o.call(0x1dd2c, task)  # RL_RouletteDrawPriority

    exe = ROOT / 'build/game/ccr.exe'
    requests = ''.join(f'{x} {y} {outcome}\n' for x, y, outcome in cases)
    rows = subprocess.run([exe], env=dict(os.environ, CCR_ROULETTE_POSE_TRACE='1'), input=requests,
                          check=True, capture_output=True, text=True).stdout.splitlines()
    assert len(rows) == len(expected) == 120 * len(cases)
    for i, (ref, row) in enumerate(zip(expected, rows)):
        actual = tuple(float.fromhex(x) for x in row.split())
        assert actual == ref, (cases[i // 120], i % 120, ref, actual)
    print(f'{len(expected)} iPad roulette poses match exactly across all eight outcomes')


if __name__ == '__main__':
    main()
