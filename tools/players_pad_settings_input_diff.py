"""Compare local iPad Settings touches with the original HD 1.0 handler."""
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import f2u


def main():
    env = hd_env.make()
    o = env.o
    screen = env.alloc(0x2000)
    for image in (17, 39):
        texture = o.u32(env.appdata + 0x3cc + 4 * image)
        o.call(0xb194, texture, 0, 0, f2u(1024), f2u(1024))

    preview, sound, change_state, players_pane = 0x19c94, 0xc74c, 0xbcc4, 0x32194
    calls = []

    def record(uc, address, size, user):
        calls.append((address, uc.reg_read(UC_ARM_REG_R1)))
        uc.reg_write(UC_ARM_REG_R0, 0)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    for address in (preview, sound, change_state, players_pane):
        o.uc.hook_add(UC_HOOK_CODE, record, begin=address, end=address)

    o.write(screen + 0xa7c, b'\x01')
    o.call(0x31690, screen)
    o.write(screen + 0x1020, struct.pack('<4i', 564, 367, 798, 555))
    snapshot = o.read(screen, 0x2000)
    rules = o.u32(o.u32(0x33510))
    rects = [struct.unpack('<4i', o.read(screen + 0x18 + i * 0x28, 16)) for i in range(37)]
    cases = []
    for x, y, w, h in rects:
        for px, py in ((x, y), (x + w, y + h), (x + w // 2, y + h // 2)):
            cases.append((px, py, 0, 7, 2, 2, 1, 0, 0, 0))
    for item in range(25, 37):
        x, y, w, h = rects[item]
        for values in ((0, 0, 0, 0, 0), (4, 4, 2, 1, 1)):
            cases.append((x + w // 2, y + h // 2, 0, 24, *values, 0))
    for x, y in ((564, 367), (798, 555), (563, 367), (798, 556), (1024, 768), (500, 0)):
        for phase, locked in ((0, 0), (1, 0), (2, 0), (0, 1)):
            cases.append((x, y, phase, 24, 0, 4, 2, 1, 1, locked))

    expected = []
    for x, y, phase, stage, points, speed, time, high, split, locked in cases:
        o.write(screen, snapshot)
        o.write(screen + 0x101c, struct.pack('<i', stage))
        o.write(screen + 0xa7d, bytes([split]))
        o.write(screen + 0xd35, bytes([locked]))
        o.write(rules, struct.pack('<4i', points, speed, time, high))
        calls.clear()
        o.call(0x32d24, screen, x, y, phase)
        action, sfx = 0, -1
        for address, arg in calls:
            if address == sound:
                sfx = arg
            elif address == preview:
                action = 1
                assert arg == o.u32(screen + 0x101c)
            elif address == players_pane:
                action = 2
            else:
                assert arg == 0x27
                assert o.u32(o.u32(o.u32(0x2f7c0))) == stage
                action = 3
        row = [action, sfx, o.u32(screen + 0x101c), *struct.unpack('<4i', o.read(rules, 16)),
               o.read(screen + 0xa7d, 1)[0], o.read(screen + 0xd35, 1)[0]]
        expected.append(' '.join(map(str, row)))

    requests = ''.join(' '.join(map(str, case)) + '\n' for case in cases)
    exe = ROOT / 'build' / 'game' / 'ccr.exe'
    output = subprocess.run([str(exe), str(ROOT / 'local' / 'cache' / 'assets')],
                            env=dict(os.environ, CCR_HEADLESS='1', CCR_PAD_SETTINGS_INPUT='1'),
                            input=requests, text=True, capture_output=True, check=True).stdout.splitlines()
    if output != expected:
        for case, ref, port in zip(cases, expected, output):
            if ref != port:
                print(f'{case}: HD {ref}, port {port}')
        raise SystemExit(f'Expected {len(expected)} rows, got {len(output)}')
    print(f'{len(cases)} local iPad Settings touches, zero mismatches')


if __name__ == '__main__':
    main()
