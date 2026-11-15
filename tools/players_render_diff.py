"""Compare the iPad player-select frame around the two panes with HD 1.0."""
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

env = hd_env.make()
oracle = env.o
screen = env.alloc(0xe00)
pack = Path(hd_env.PACK) / 'ccrpad'
tile_record = env.T[0x126]
tilemap = env.put((pack / f'{tile_record:04d}.bin').read_bytes())
oracle.write(screen + 0xa10, struct.pack('<I', tilemap))
oracle.write(screen + 0xa14, oracle.read(env.appdata + 0x64c, 4))
oracle.write(screen + 0xa7c, b'\x01')
for image in (28, 34, 40, 51, 63, 75):
    obj = oracle.u32(env.appdata + 0x3cc + 4 * image)
    # The original converts the resource frame table to atlas coordinates
    # on upload. A zero atlas origin keeps the UVs comparable within each sheet.
    oracle.call(0xb194, obj, 0, 0, 0x44800000, 0x44800000)


def pane_hook(pane):
    def record(uc, address, size, user):
        env.log.append(('pane', pane))
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    return record


for pane, address in enumerate((0x33514, 0x2fa70)):
    oracle.uc.hook_add(UC_HOOK_CODE, pane_hook(pane), begin=address, end=address)


def identify_frames(image):
    obj = oracle.u32(env.appdata + 0x3cc + 4 * image)
    table = oracle.u32(obj + 0x28)
    result = {}
    for frame in range(oracle.u32(table)):
        u, v = struct.unpack('<2f', oracle.read(table + 4 + frame * 36, 8))
        assert (u, v) not in result
        result[u, v] = frame
    return result


def reference(case):
    state, pane, team, costume, loaded, count, cat_frame, mouse_frame, fade, cat_x, mouse_x = case
    oracle.write(env.appdata + 0x668, struct.pack('<i', state))
    oracle.write(env.appdata + 0x4f, bytes([costume]))
    oracle.write(screen + 0xa2c, struct.pack('<ii', loaded, count))
    oracle.write(screen + 0xa38, struct.pack('<f', fade))
    oracle.write(screen + 0xa40, struct.pack('<ii', team, pane))
    oracle.write(screen + 0xa4c, struct.pack('<ff', cat_x, 576))
    oracle.write(screen + 0xa60, struct.pack('<iff', cat_frame, mouse_x, 576))
    oracle.write(screen + 0xa78, struct.pack('<i', mouse_frame))
    env.log.clear()
    oracle.call(0x35154, screen)

    images = (40, (51, 75, 63)[costume]) if state == 0x23 else (28,) * 48 + (34,)
    frame_tables = {image: identify_frames(image) for image in set(images)}
    image_order = iter(images)
    trace = []
    for kind, *args in env.log:
        if kind == 'RenderTexture':
            x, y, w, h, u, v, r, g, b, alpha = args
            assert (r, g, b, alpha) == (255,) * 4
            image = next(image_order)
            frame = frame_tables[image][u, v]
            trace.append(f'RT {image} {frame} {x:.4f} {y:.4f} {w:.0f} {h:.0f}')
        elif kind == 'RenderFilledRect':
            assert args[:-1] == [0, 0, 1024, 768, 0, 0, 0]
            trace.append(f'black {args[-1]}')
        elif kind == 'PrintString':
            text, x, y, r, g, b, alpha, scale, align, vcenter, font = args
            assert (r, g, b, alpha, vcenter, font) == (255, 255, 255, 255, 0, 0)
            trace.append(f'PS {text.replace(chr(10), "|")} {x:.1f} {y:.1f} {scale:.3f} {align}')
        else:
            assert kind == 'pane'
            trace.append(f'pane {args[0]}')
    return trace


exe = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build' / 'game' / 'ccr.exe'
cases = [
    (0x23, 0, 0, 0, 0, 79, 0, 0, 500000, -153.6, -51.2),
    (0x23, 1, 0, 1, 39, 76, 13, 3, 500000, 450.25, 81.75),
    (0x23, 0, 1, 2, 76, 76, 19, 10, 500000, 997, 330),
]
cases += [(state, pane, team, 0, 79, 79, 0, 0, fade, 0, 0)
          for state, fade in ((0x24, 500000), (0x24, 250000), (0x25, 0),
                              (0x26, 16384), (0x26, 500000), (0x27, 0))
          for pane in (0, 1) for team in (0, 1)]
failed = count = 0
for case in cases:
    wanted = reference(case)
    config = ','.join(map(str, case))
    run = subprocess.run([str(exe), str(ROOT / 'local' / 'cache' / 'assets')],
                         env=dict(os.environ, CCR_PSRENDER=config, CCR_HEADLESS='1'),
                         capture_output=True, text=True, check=True)
    actual = run.stdout.splitlines()
    count += len(wanted)
    if wanted != actual:
        failed += 1
        for index in range(max(len(wanted), len(actual))):
            expected = wanted[index:index + 1]
            received = actual[index:index + 1]
            if expected != received:
                print(f'{config}, call {index}: original {expected}, port {received}')
                break
print(f'{len(cases)} frames, {count} calls, {failed} frames with mismatches')
sys.exit(bool(failed))
