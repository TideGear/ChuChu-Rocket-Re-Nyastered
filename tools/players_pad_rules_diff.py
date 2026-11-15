"""Compare the local iPad Settings controls and preview slot against HD 1.0."""
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
for image in (17, 31, 33, 38, 39, 148):
    texture = o.u32(env.appdata + 0x3cc + image * 4)
    o.call(0xb194, texture, 0, 0, f2u(1024), f2u(1024))
    if image in (17, 33, 39):
        table = o.u32(texture + 0x28)
        for frame in range(o.u32(table)):
            u, v, _, _, w, h = struct.unpack('<4f2h', o.read(table + 4 + 36 * frame, 20))
            frames[u, v, w, h] = image, frame


def skip_preview_generation(uc, address, size, user):
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


o.uc.hook_add(UC_HOOK_CODE, skip_preview_generation, begin=0x19c94, end=0x19c94)
rule_options = o.u32(o.u32(0x302ec))
screen = env.alloc(0x1030)
o.write(screen + 0xa7c, b'\x01')
o.call(0x31690, screen)


def reference(points, speed, time, high, split):
    o.write(rule_options, struct.pack('<4I', points, speed, time, high))
    o.write(screen + 0xa7d, bytes([split]))
    env.log.clear()
    o.call(0x2fa70, screen)
    result = []
    for kind, *args in env.log[53:]:
        if kind == 'RenderTexture':
            x, y, w, h, u, v, r, g, b, alpha = args
            assert (r, g, b, alpha) == (255,) * 4
            coords = f'{int(x)} {int(y)} {int(w)} {int(h)}'
            if (u, v, w, h) in frames:
                image, frame = frames[u, v, w, h]
                result.append(f'RT {image} {frame} {coords}')
            else:
                assert (w, h) == (234, 188)
                result.append(f'preview {coords}')
        elif kind == 'RenderFilledRect':
            result.append('FR ' + ' '.join(str(int(value)) for value in args))
        else:
            assert kind == 'PrintString'
            text, x, y, r, g, b, alpha, scale, align, vcenter, font = args
            assert (r, g, b, alpha, round(scale, 2), align, vcenter, font) == (0, 0, 0, 255, 0.55, 0, 0, 0)
            result.append(f'PS {text} {int(x)} {int(y)}')
    assert len(result) == 17
    return result


cases = [(i, i, time, high, split) for i in range(5) for time in range(3)
         for high in (0, 1) for split in (0, 1)]
exe = ROOT / 'build' / 'game' / 'ccr.exe'
failures = calls = 0
for case in cases:
    wanted = reference(*case)
    config = ','.join(map(str, case))
    run = subprocess.run([str(exe), str(ROOT / 'local' / 'cache' / 'assets')],
                         env=dict(os.environ, CCR_PAD_RULES=config, CCR_HEADLESS='1'),
                         text=True, capture_output=True, check=True)
    actual = run.stdout.splitlines()
    calls += len(wanted)
    if actual != wanted:
        failures += 1
        for index in range(max(len(wanted), len(actual))):
            if wanted[index:index + 1] != actual[index:index + 1]:
                print(f'{config}, call {index}: HD {wanted[index:index + 1]}, port {actual[index:index + 1]}')
                break
print(f'{len(cases)} rule combinations, {calls} calls, {failures} mismatched frames')
sys.exit(bool(failures))
