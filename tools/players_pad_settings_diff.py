"""Compare the iPad battle-settings hit regions with HD 1.0 under Unicorn."""
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import f2u, s32

env = hd_env.make()
o = env.o
for image in (17, 39):
    texture = o.u32(env.appdata + 0x3cc + image * 4)
    o.call(0xb194, texture, 0, 0, f2u(1024), f2u(1024))

network_flag = env.alloc(4)
host_flag = env.alloc(4)
o.write(0xeb450, struct.pack('<I', network_flag))
o.write(0xeb494, struct.pack('<I', host_flag))


def skip_preview(uc, address, size, user):
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


# The preview is independent of the menu item rectangles and hit test.
o.uc.hook_add(UC_HOOK_CODE, skip_preview, begin=0x19c94, end=0x19c94)


def settings_screen(network):
    screen = env.alloc(0x1030)
    o.write(screen + 0xa7c, b'\x01')
    o.write(network_flag, bytes([network]))
    o.call(0x31690, screen)
    assert o.u32(screen + 0xa44) == 1
    count = o.u32(screen + 4)
    rects = [struct.unpack('<4i', o.read(screen + 8 + 0x28 * i + 0x10, 16))
             for i in range(count)]
    return screen, rects


expected = []
requests = []
counts = []
hit_count = 0
for network in (0, 1):
    screen, rects = settings_screen(network)
    counts.append(len(rects))
    expected.append(f'count {len(rects)}')
    expected.extend(' '.join(map(str, rect)) for rect in rects)
    points = [(512, 100), (1024, 768), (423, 656), (601, 656)]
    for x, y, w, h in rects:
        points.extend(((x, y), (x + w, y + h), (x + w // 2, y + h // 2),
                       (x - 1, y), (x + w + 1, y), (x, y - 1), (x, y + h + 1)))
    requests.append(str(len(points)))
    for x, y in points:
        requests.append(f'{x} {y}')
        expected.append(f'hit {s32(o.call(0xf2b0, screen, x, y, 0))}')
    hit_count += len(points)

exe = ROOT / 'build' / 'game' / 'ccr.exe'
run = subprocess.run([str(exe), str(ROOT / 'local' / 'cache' / 'assets')],
                     env=dict(os.environ, CCR_PAD_SETTINGS='1', CCR_HEADLESS='1'),
                     text=True, capture_output=True, input='\n'.join(requests) + '\n', check=True)
actual = run.stdout.splitlines()
different = [(i, pair) for i, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]]
for i, (ref, port) in different[:8]:
    print(f'Line {i}: HD {ref}, port {port}')
mismatches = len(different) + abs(len(expected) - len(actual))
print(f'{counts[0]} local and {counts[1]} network rectangles, {hit_count} touch points, {mismatches} mismatches')
sys.exit(bool(mismatches))
