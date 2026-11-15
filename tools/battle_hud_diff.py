"""Compare the iPad Battle HUD panels, digits, crowns and win-point icons."""
from itertools import product
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
from hd_bubble_probe import make


def main():
    o, calls, appdata = make()
    scores = o.u32(0xeb5a8)
    cpu = o.u32(0x1f3d4)
    task = o.alloc(0x58)
    o.write(appdata + 0x390, struct.pack('<I', 11))
    o.call(0x15188, max_insn=4_000_000)  # CoreSettingsInit sets the iPad field origin.
    assert struct.unpack('<2f', o.read(o.u32(o.u32(0x20878)), 8)) == (184, 32)
    rockets = o.u32(0x16c94)
    victories = o.u32(0x1bdb0) + 0x14
    paused_flag = o.u32(0x1f444) + 1

    cases = list(product((0, 1), (0, 1), range(16)))
    expected, requests = [], []
    for team, show, mask in cases:
        tick = (10, 11, 31, 32)[mask % 4]
        pscore = (0, 0, 0, 0) if mask % 5 == 0 else (999, 12, mask * 7, 999)
        tscore = (0, 0) if mask % 5 == 0 else (mask * 7, 100 if mask % 2 else mask * 7)
        prank = tuple(sorted(set(pscore), reverse=True).index(s) for s in pscore)
        trank = tuple(int(tscore[t] < tscore[1 - t]) for t in (0, 1))
        paused = (mask >> 2) & 1
        wins = (mask % 6, 2, (mask + 1) % 6, 0)
        cells = (0, 0, 11, 8, mask % 12, 4, 2, mask % 9)
        for p in range(4):
            o.write(cpu + p * 16 + 4, struct.pack('<3i', p, 0, (mask >> p) & 1))
        o.write(scores, struct.pack('<12i', *pscore, *prank, *tscore, *trank))
        o.write(victories, struct.pack('<4i', *wins))
        o.write(rockets, struct.pack('<8h', *cells))
        o.write(paused_flag, bytes([paused]))
        o.write(task + 4, struct.pack('<I', tick))
        o.call(0x159b0, team)  # GA_SetGameType
        o.call(0x1f4d4, 0xc + team)  # MC_ChangeGlobalMode, local battle
        calls.clear()
        o.call(0x3afa0 if team else 0x21038, 0)
        if show:
            o.call(0x1bde4 if team else 0x1bf54, 0)
        o.call(0x209ac, task)
        expected.extend(f'drawImage {image} {frame} {x:.2f} {y:.2f} {flags} {scale:.3f} {alpha}'
                        for _, image, frame, x, y, flags, scale, alpha in calls)
        expected.append('end')
        requests.append(' '.join(map(str, (team, show, tick, *pscore, *tscore, *prank,
                                          paused, *wins, *cells))))

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
