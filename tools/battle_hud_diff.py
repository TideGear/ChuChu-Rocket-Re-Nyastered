"""Compare the iPad Battle HUD panels, digits and scoreboard crowns."""
from itertools import product
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
from hd_bubble_probe import make


def main():
    o, calls, _ = make()
    scores = o.u32(0xeb5a8)
    cpu = o.u32(0x1f3d4)
    task = o.alloc(0x58)

    def skip(uc, address, size, user):
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

    # The two calls render separate playfield crowns and win-point icons.
    for address in (0x20808, 0x2087c):
        o.uc.hook_add(UC_HOOK_CODE, skip, begin=address, end=address)

    cases = list(product((0, 1), (0, 1), range(16)))
    expected, requests = [], []
    for team, show, mask in cases:
        tick = (10, 11, 31, 32)[mask % 4]
        pscore = (0, 0, 0, 0) if mask % 5 == 0 else (999, 12, mask * 7, 999)
        tscore = (0, 0) if mask % 5 == 0 else (mask * 7, 100 if mask % 2 else mask * 7)
        prank = tuple(sorted(set(pscore), reverse=True).index(s) for s in pscore)
        trank = tuple(int(tscore[t] < tscore[1 - t]) for t in (0, 1))
        for p in range(4):
            o.write(cpu + p * 16 + 4, struct.pack('<3i', p, 0, (mask >> p) & 1))
        o.write(scores, struct.pack('<12i', *pscore, *prank, *tscore, *trank))
        o.write(task + 4, struct.pack('<I', tick))
        o.call(0x159b0, team)  # GA_SetGameType
        calls.clear()
        o.call(0x3afa0 if team else 0x21038, 0)
        if show:
            o.call(0x1bde4 if team else 0x1bf54, 0)
        o.call(0x209ac, task)
        expected.extend(f'drawImage {image} {frame} {x:.2f} {y:.2f} {flags} {scale:.3f} {alpha}'
                        for _, image, frame, x, y, flags, scale, alpha in calls)
        expected.append('end')
        requests.append(' '.join(map(str, (team, show, tick, *pscore, *tscore, *prank))))

    actual = subprocess.run([ROOT / 'build/game/ccr.exe', ROOT / 'local/cache/assets'],
                            env=dict(os.environ, CCR_HEADLESS='1', CCR_BATTLE_HUD_TRACE='1'),
                            capture_output=True, text=True, check=True,
                            input='\n'.join(requests) + '\n').stdout.splitlines()
    if actual != expected:
        for n, (ref, port) in enumerate(zip(expected, actual), 1):
            if ref != port:
                raise SystemExit(f'Call {n}: HD {ref}, port {port}')
        raise SystemExit(f'Expected {len(expected)} rows, got {len(actual)}')
    print(f'{len(cases)} iPad Battle HUD frames and {len(expected) - len(cases)} draw calls match')


if __name__ == '__main__':
    main()
