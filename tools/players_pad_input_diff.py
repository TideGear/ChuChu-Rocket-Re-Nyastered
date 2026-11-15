"""Compare local iPad Players pane touch sequences with HD 1.0."""
import os
from pathlib import Path
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R1

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import f2u, s32


def main():
    env = hd_env.make()
    o = env.o
    screen = env.alloc(0x2000)
    for image in (12, 17, 34, 35, 36, 39):
        texture = o.u32(env.appdata + 0x3cc + 4 * image)
        o.call(0xb194, texture, 0, 0, f2u(1024), f2u(1024))

    calls = []

    def record(uc, address, size, user):
        calls.append((address, uc.reg_read(UC_ARM_REG_R1)))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (0xc74c, 0xbcc4, 0x19c94):
        o.uc.hook_add(UC_HOOK_CODE, record, begin=address, end=address)
    o.write(screen + 0xa7c, b'\x01')
    o.call(0x2f7e0, screen)  # initConnectVariables
    o.call(0x32194, screen)  # initPlayersPaneMenuItems

    cases = [(208, 50, 0), (816, 106, 0), (250, 230, 0), (250, 290, 0),
             (100, 590, 0), (900, 590, 0), (520, 590, 0)]
    for p in range(1, 4):
        x = 234 + 151 * p
        cases.extend([(x, 219, 0), (x + 103, 250, 0), (x, 278, 0), (x + 103, 309, 0)])
        for y in (314, 342, 370, 398, 426, 454, 482):
            cases.extend([(x, 278, 0), (x + 10, y, 1), (x + 10, y, 2),
                          (x + 9, y, 0), (x + 10, y, 0)])
    cases.extend([(57, 768, 0), (995, 739, 1), (995, 739, 0)])

    expected = []
    for x, y, phase in cases:
        calls.clear()
        o.call(0x31d24, screen, x, y, phase)
        row = [s32(o.u32(screen + offset)) for offset in (0xd3c, 0xd40, 0xd44, 0xd58, 0xa40,
                                                         0xd4c, 0xd50, 0xd54)]
        row.extend((o.u32(screen + 0xa44), int((0xbcc4, 0x26) in calls)))
        row.extend(arg for address, arg in calls if address == 0xc74c)
        expected.append(' '.join(map(str, row)))

    exe = ROOT / 'build' / 'game' / 'ccr.exe'
    assets = ROOT / 'local' / 'cache' / 'assets'
    requests = ''.join(' '.join(map(str, case)) + '\n' for case in cases)
    actual = subprocess.run([exe, assets], capture_output=True, text=True, input=requests, check=True,
                            env=dict(os.environ, CCR_HEADLESS='1', CCR_PAD_PLAYERS_INPUT='1')).stdout.splitlines()
    if actual != expected:
        for i, (ref, port) in enumerate(zip(expected, actual)):
            if ref != port:
                raise SystemExit(f'Case {i + 1} {cases[i]}: HD {ref}, port {port}')
        raise SystemExit(f'Expected {len(expected)} rows, got {len(actual)}')
    print(f'{len(cases)} local iPad Players touches match the original')


if __name__ == '__main__':
    main()
