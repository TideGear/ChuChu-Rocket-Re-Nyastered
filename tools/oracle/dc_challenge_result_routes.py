"""Exercise original-loop Challenge result branches with explicit injected fixtures.

Uses a live Challenge play state, not direct calls to result functions. The board
and actors remain those of the state: this tests routing, not final-stage play.
Inputs below use Flycast's libretro mapping (B = DC A, A = DC B).
"""
import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess


def word(ram, offset):
    return struct.unpack_from('<i', ram, offset)[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'core', 'system', 'save', 'disc', 'state', 'out'):
        p.add_argument('--' + name, required=True, type=Path)
    a = p.parse_args()
    paths = {k: v.resolve() for k, v in vars(a).items()}
    paths['out'].mkdir(parents=True, exist_ok=True)
    for complete in (False, True):
        for button, key in (('A', 'B'), ('B', 'A'), ('Start', 'START')):
            tag = ('repeat' if complete else 'first') + '_dc' + button
            prefix = paths['out'] / (tag + '_')
            save = paths['out'] / (tag + '_save')
            shutil.copytree(paths['save'], save, dirs_exist_ok=True)
            watch = Path(str(prefix) + 'watch.bin')
            # flyhost appends watches; remove this case's previous output only.
            if watch.exists():
                watch.unlink()
            env = os.environ.copy()
            for keyname in tuple(env):
                if keyname.startswith('FLY_') or keyname.startswith('FLYHOST_'):
                    del env[keyname]
            env.update(FLYHOST_STATE=str(paths['state']), FLY_DUMP='1',
                       FLY_WATCH='cdaa4:4:0',
                       FLY_POKE_ONCE='0:22d7fc=5,1af520=64,1af524=0,'
                       '1ae8bc=18,22d824=' + ('1ffffff' if complete else 'ffffff'))
            # Type 5 and score 100 > 0 enter the original success branch. The
            # original scheduler advances success -> result -> scripted input.
            cmd = [str(paths[n]) for n in ('host', 'core', 'system')]
            cmd += [str(save), str(paths['disc']), '850', str(prefix),
                    '2,400,800', key + '@550-552']
            with (paths['out'] / (tag + '.log')).open('w') as log:
                subprocess.run(cmd, env=env, stdout=log, stderr=log,
                               check=True, timeout=90)
            early = Path(str(prefix) + '00002.ram').read_bytes()
            result = Path(str(prefix) + '00400.ram').read_bytes()
            after = Path(str(prefix) + '00800.ram').read_bytes()
            pending = -1 if complete else 1
            expected_mode = 7 if complete and button == 'B' else 17
            assert word(early, 0xcdaa4) == pending, tag
            assert word(result, 0x22d804) == 5, tag
            assert word(result, 0x1af108) == 14, tag
            assert word(result, 0x22d824) == 0x1ffffff, tag
            assert word(result, 0x1ae8bc) == 24, tag
            assert word(after, 0x1af108) == expected_mode, tag
            rows = list(struct.iter_unpack('<Ii', watch.read_bytes()))
            changes = [(f, v) for i, (f, v) in enumerate(rows)
                       if i == 0 or v != rows[i - 1][1]]
            print(f'{tag}: pending {pending}, result phase 5, '
                  f'destination mode {expected_mode}, watch changes {changes}')


if __name__ == '__main__':
    main()
