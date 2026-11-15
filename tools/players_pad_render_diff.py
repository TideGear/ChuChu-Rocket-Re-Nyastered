"""Compare the local iPad Players pane draw calls with HD 1.0."""
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
from ios_oracle import f2u

env = hd_env.make()
o = env.o
frames = {}
for image in (12, 17, 34, 35, 36):
    texture = o.u32(env.appdata + 0x3cc + image * 4)
    o.call(0xb194, texture, 0, 0, f2u(1024), f2u(1024))
    table = o.u32(texture + 0x28)
    for frame in range(o.u32(table)):
        u, v, _, _, w, h = struct.unpack('<4f2h', o.read(table + 4 + frame * 36, 20))
        assert (u, v, w, h) not in frames
        frames[(u, v, w, h)] = image, frame


def skip_sound(uc, address, size, user):
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


o.uc.hook_add(UC_HOOK_CODE, skip_sound, begin=0xc74c, end=0xc74c)
o.write(env.appdata + 0x668, struct.pack('<I', 0x25))


def reference(human, levels, slider, pressed):
    screen = env.alloc(0x1030)
    o.write(screen + 0xa7c, b'\x01')
    o.write(screen + 0xd38, struct.pack('<4I', *(1 - player for player in human)))
    o.write(screen + 0xd4c, struct.pack('<3I', *levels[1:]))
    o.call(0x32194, screen)
    if pressed >= 0:
        o.write(screen + 0xa08, struct.pack('<I', screen + 8 + 40 * pressed))
    if slider > 0:
        o.call(0x31d24, screen, 250 + slider * 151, 290, 0)
    env.log.clear()
    o.call(0x33514, screen)
    result = []
    for kind, *args in env.log:
        if kind == 'RenderTexture':
            x, y, w, h, u, v, r, g, b, alpha = args
            assert (r, g, b, alpha) == (255,) * 4
            image, frame = frames[u, v, w, h]
            result.append(f'RT {image} {frame} {int(x)} {int(y)} {int(w)} {int(h)}')
        else:
            assert kind == 'PrintString'
            text, x, y, r, g, b, alpha, scale, align, vcenter, font = args
            assert r == g == b and (alpha, align, vcenter, font) == (255, 0, 0, 0)
            result.append(f'PS {text} {int(x)} {y:.1f} {scale:.3f} {r}')
    return result


cases = [
    ((1, 0, 0, 0), (0, 0, 0, 0), -1, -1),
    ((1, 1, 1, 1), (0, 1, 2, 3), -1, -1),
    ((1, 0, 1, 0), (0, 4, 5, 1), -1, 8),
    ((1, 1, 0, 1), (0, 0, 4, 2), -1, 9),
]
for player in (1, 2, 3):
    for selection in range(6):
        levels = [0] * 4
        levels[player] = selection
        cases.append(((1, 0, 0, 0), levels, player, -1))

exe = ROOT / 'build' / 'game' / 'ccr.exe'
failures = calls = 0
for human, levels, slider, pressed in cases:
    wanted = reference(human, levels, slider, pressed)
    config = ','.join(map(str, (*human, *levels, slider, pressed)))
    result = subprocess.run([str(exe), str(ROOT / 'local' / 'cache' / 'assets')],
                            env=dict(os.environ, CCR_PAD_PLAYERS=config, CCR_HEADLESS='1'),
                            capture_output=True, text=True, check=True)
    actual = result.stdout.splitlines()
    calls += len(wanted)
    if wanted != actual:
        failures += 1
        for index in range(max(len(wanted), len(actual))):
            if wanted[index:index + 1] != actual[index:index + 1]:
                print(f'{config}, call {index}: HD {wanted[index:index + 1]}, port {actual[index:index + 1]}')
                break
print(f'{len(cases)} iPad Players frames, {calls} draw calls, {failures} mismatched frames')
sys.exit(bool(failures))
