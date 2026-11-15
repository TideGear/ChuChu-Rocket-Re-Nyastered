"""Compare the iPad battle Settings pane's panels and stage grid with HD 1.0."""
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
for image in (17, 31, 38, 39):
    texture = o.u32(env.appdata + 0x3cc + image * 4)
    o.call(0xb194, texture, 0, 0, f2u(1024), f2u(1024))
    if image in (31, 38):
        table = o.u32(texture + 0x28)
        for frame in range(o.u32(table)):
            uv = struct.unpack('<2f', o.read(table + 4 + frame * 36, 8))
            frames[image, *uv] = frame


def skip_preview(uc, address, size, user):
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))


def stop_after_grid(uc, address, size, user):
    # The three panels and 25 cell/label pairs precede the rules controls.
    if len(env.log) == 53:
        uc.emu_stop()


o.uc.hook_add(UC_HOOK_CODE, skip_preview, begin=0x19c94, end=0x19c94)
o.uc.hook_add(UC_HOOK_CODE, stop_after_grid, begin=0x2fa70, end=0x3168e)


def reference(selected):
    screen = env.alloc(0x1030)
    o.write(screen + 0xa7c, b'\x01')
    o.write(screen + 0x101c, struct.pack('<I', selected))
    o.call(0x31690, screen)
    env.log.clear()
    o.call(0x2fa70, screen)
    assert len(env.log) == 53
    trace = []
    for index, (kind, *args) in enumerate(env.log):
        if kind == 'RenderTexture':
            image = 38 if index < 3 else 31
            x, y, w, h, u, v, r, g, b, alpha = args
            assert (r, g, b, alpha) == (255,) * 4
            trace.append(f'RT {image} {frames[image, u, v]} {int(x)} {int(y)} {int(w)} {int(h)}')
        else:
            assert kind == 'PrintString'
            text, x, y, r, g, b, alpha, scale, align, vcenter, font = args
            assert (r, g, b, alpha, scale, align, vcenter, font) == (255, 255, 255, 255, 0.75, 0, 0, 0)
            trace.append(f'PS {text} {int(x)} {int(y)}')
    return trace


exe = ROOT / 'build' / 'game' / 'ccr.exe'
failures = calls = 0
for selected in range(25):
    wanted = reference(selected)
    run = subprocess.run([str(exe), str(ROOT / 'local' / 'cache' / 'assets')],
                         env=dict(os.environ, CCR_PAD_SETTINGS_GRID=str(selected), CCR_HEADLESS='1'),
                         text=True, capture_output=True, check=True)
    actual = run.stdout.splitlines()
    calls += len(wanted)
    if actual != wanted:
        failures += 1
        for index in range(max(len(wanted), len(actual))):
            if wanted[index:index + 1] != actual[index:index + 1]:
                print(f'Selected {selected}, call {index}: HD {wanted[index:index + 1]}, port {actual[index:index + 1]}')
                break
print(f'25 selections, {calls} panel and grid draw calls, {failures} mismatched frames')
sys.exit(bool(failures))
