"""Compare the iPad battle rules applied at launch with the original code."""
from itertools import product
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools' / 'oracle'))
import hd_env
from ios_oracle import f2u, u2f


def main():
    o = hd_env.make().o
    options = o.u32(o.u32(0x33510))
    win_point_option = o.u32(o.u32(0x217b0))
    bcd_timer = o.u32(0x15acc)
    generator_params = o.u32(0x15d04)
    cases = list(product(range(5), range(5), range(3), range(2)))
    expected = []
    for mode in (0xc, 0xd):
        rows = []
        for case in cases:
            o.write(options, struct.pack('<4i', *case))
            o.call(0x17e0c)  # SmpTskInit, needed by the generator manager
            o.call(0x15b28)  # GA_ResetGameParamStr
            o.call(0x1f4d4, mode)
            o.call(0x1f3e4, o.u32(win_point_option))  # SetWinPoint, as in FourBattleGameScreen::process
            o.call(0x15a70)  # GA_OnGameFlag
            o.call(0x15a20, f2u(1.0))
            o.call(0x15c14)  # GE_StartGenerator4Manager
            minutes = o.u32(bcd_timer) >> 16  # the one-digit BCD minute field
            rows.append((o.call(0x1f3d8), minutes * 60 * 60, u2f(o.call(0x15b04)),
                         u2f(o.call(0x15ad4)), u2f(o.u32(generator_params + 20))))
        expected.append(rows)

    exe = ROOT / 'build' / 'game' / 'ccr.exe'
    assets = ROOT / 'local' / 'cache' / 'assets'
    requests = ''.join(' '.join(map(str, case)) + '\n' for case in cases)
    for mode, rows in zip((0xc, 0xd), expected):
        env = dict(os.environ, CCR_HEADLESS='1', CCR_PAD_MATCH_RULES='1')
        env.pop('CCR_TEAM', None)
        if mode == 0xd:
            env['CCR_TEAM'] = '1'
        output = subprocess.run([exe, assets], env=env, input=requests, text=True,
                                capture_output=True, check=True).stdout.splitlines()
        assert len(output) == 2 * len(rows), (len(output), len(rows))
        for index, line in enumerate(output):
            points, frames, cat, mouse, special = line.split()
            observed = (int(points), int(frames), *(float.fromhex(x) for x in (cat, mouse, special)))
            assert observed == rows[index // 2], (mode, cases[index // 2], observed, rows[index // 2])
    print(f'{2 * len(cases)} iPad battle settings combinations match on launch and restart')


if __name__ == '__main__':
    main()
