"""Compare the iPad player pane's lower-right button with HD 1.0."""
import itertools
import os
from pathlib import Path
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R1

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import f2u

env = hd_env.make()
o = env.o
for image in (12, 17, 34, 35, 36, 39):
    texture = o.u32(env.appdata + 0x3cc + image * 4)
    o.call(0xb194, texture, 0, 0, f2u(1024), f2u(1024))

host_flag, ready_flag, sync_flag = [o.u32(o.u32(addr)) for addr in (0x32170, 0x3218c, 0x32190)]
sounds = []


def record_call(uc, address, size, user):
    if address == 0xc74c:
        sounds.append(uc.reg_read(UC_ARM_REG_R1))
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


# Run both real pane initializers. Only audio playback and preview rendering
# are stubbed, so the original hit test and pane switch still run.
for address in (0xc74c, 0x19c94):
    o.uc.hook_add(UC_HOOK_CODE, record_call, begin=address, end=address)

cases = list(itertools.product((0, 1), repeat=4))
expected = []
for connections, host, ready, d34 in cases:
    screen = env.alloc(0x1030)
    o.write(screen + 0xa7c, b'\x01')
    for address, value in ((host_flag, host), (ready_flag, ready), (sync_flag, 0),
                           (screen + 0xd20, connections), (screen + 0xd34, d34)):
        o.write(address, bytes([value]))
    o.call(0x32194, screen)
    sounds.clear()
    assert o.u32(screen + 0xa44) == 0
    o.call(0x31d24, screen, 995, 739, 0)
    opened = o.u32(screen + 0xa44)
    sync = o.read(sync_flag, 1)[0]
    expected.append(' '.join(map(str, (opened, sync, *sounds))))

exe = ROOT / 'build' / 'game' / 'ccr.exe'
run = subprocess.run([str(exe), str(ROOT / 'local' / 'cache' / 'assets')],
                     env=dict(os.environ, CCR_PLAY_SETTINGS='1', CCR_HEADLESS='1'),
                     text=True, capture_output=True, check=True)
actual = run.stdout.splitlines()
bad = [(case, ref, port) for case, ref, port in zip(cases, expected, actual) if ref != port]
for case, ref, port in bad:
    print(f'{case}: HD {ref}, port {port}')
mismatches = len(bad) + abs(len(expected) - len(actual))
print(f'{len(expected)} settings-button cases, {mismatches} mismatches')
sys.exit(bool(mismatches))
